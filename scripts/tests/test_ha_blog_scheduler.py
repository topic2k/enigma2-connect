# SPDX-License-Identifier: Apache-2.0
"""Offline, multi-day retry and persistence checks; no real API requests."""

import argparse
import base64
import copy
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from scripts import ha_blog_gemini as gemini
from scripts import ha_blog_scheduler as scheduler


def http_error(code):
    return HTTPError("https://example.invalid", code, "private response", {}, None)


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 9, 14)
        self.posts = [
            {
                "path": f"2026-09-14-{i}.md",
                "title": f"Post {i}",
                "text": f"News {i}",
                "date": "2026-09-14",
            }
            for i in range(2)
        ]
        self.sources = {"custom_components/enigma2_connect/entity.py": "source line\n"}
        self.state = {"version": 1, "entries": {}}
        self.saved = []
        self.store = Mock()
        self.store.save.side_effect = lambda value: self.saved.append(copy.deepcopy(value))
        self.generate = Mock(
            return_value=(
                {"results": [self.result(p) for p in self.posts]},
                {"promptTokenCount": 10},
            )
        )
        self.publish = Mock(return_value={"html_url": "https://github.com/owner/repo/issues/1"})

    def result(self, post):
        return {
            "id": gemini.post_id(post),
            "assessment": "no-impact",
            "reason": "Kein Bedarf",
            "ha_version": "2026.10",
            "next_steps": "Keine",
            "evidence": [],
            "opportunity": {
                "assessment": "none",
                "reason": "Kein Nutzen",
                "next_steps": "Keine",
                "evidence": [],
            },
        }

    def process(self, day=0, **kwargs):
        return scheduler.process(
            self.posts,
            self.sources,
            self.state,
            kwargs.pop("known", set()),
            self.today + timedelta(days=day),
            self.store,
            self.generate,
            self.publish,
            "owner/repo",
            "a" * 40,
            kwargs.pop("upstream", "b" * 40),
            **kwargs,
        )

    def fail_first(self):
        self.generate.side_effect = http_error(503)
        return self.process()

    def test_first_failure_is_pending_and_attempt_reserved_before_ai(self):
        report = self.fail_first()
        self.assertEqual(report["failed"], [])
        self.assertEqual(len(report["retry_pending"]), 2)
        self.assertEqual(report["retry_pending"][0]["due"], "2026-09-15")
        self.assertEqual(report["retry_pending"][0]["error"], "Gemini-Anfrage: HTTP 503")
        self.assertEqual(len(self.saved[0]["entries"]), 2)
        self.publish.assert_not_called()
        self.generate.assert_called_once()
        scheduler.validate_state(self.saved[-1])

    def test_same_day_rerun_does_not_spend_second_attempt(self):
        self.fail_first()
        self.generate.reset_mock()
        report = self.process(retry_only=True)
        self.generate.assert_not_called()
        self.assertEqual(report["failed"], [])
        self.assertTrue(all(e["attempts"] == 1 for e in self.state["entries"].values()))

    def test_next_day_success_clears_state_and_publishes(self):
        self.fail_first()
        # Simulate another runner loading the durable JSON, not shared process memory.
        self.state = json.loads(json.dumps(self.saved[-1]))
        self.generate.side_effect = None
        report = self.process(day=1, retry_only=True)
        self.assertEqual(report["failed"], [])
        self.assertEqual(report["retry_pending"], [])
        self.assertEqual(self.saved[-1]["entries"], {})
        self.publish.assert_called_once()

    def test_second_failure_is_terminal_and_not_automatically_retried(self):
        self.fail_first()
        report = self.process(day=1, retry_only=True)
        self.assertEqual(len(report["failed"]), 2)
        self.assertEqual(report["retry_pending"], [])
        self.assertTrue(
            all(e["attempts"] == 2 and e["due"] is None for e in self.saved[-1]["entries"].values())
        )
        self.generate.reset_mock()
        self.process(day=2, retry_only=True)
        self.process(day=7)
        self.generate.assert_not_called()
        self.generate.side_effect = None
        self.process(day=8, retry_only=True, retry_failed=True)
        self.generate.assert_called_once()
        self.assertEqual(self.state["entries"], {})

    def test_missing_next_day_run_is_caught_up_later(self):
        self.fail_first()
        report = self.process(day=3, retry_only=True)
        self.assertEqual(len(report["failed"]), 2)

    def test_exhausted_content_does_not_block_new_or_edited_posts(self):
        self.fail_first()
        self.process(day=1, retry_only=True)
        self.posts = [{**self.posts[0], "text": "Updated announcement"}]
        self.generate.side_effect = None
        self.generate.return_value = ({"results": [self.result(self.posts[0])]}, {})
        report = self.process(day=7)
        self.assertEqual(report["failed"], [])
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(len(self.state["entries"]), 2)

    def test_partial_success_retries_only_the_missing_post(self):
        self.generate.return_value = ({"results": [self.result(self.posts[0])]}, {})
        first = self.process()
        self.assertEqual(len(first["retry_pending"]), 1)
        self.assertEqual(first["retry_pending"][0]["id"], gemini.post_id(self.posts[1]))
        self.assertIn("Post 0", self.publish.call_args.args[0]["body"])
        self.assertNotIn("Post 1", self.publish.call_args.args[0]["body"])
        self.generate.return_value = ({"results": [self.result(self.posts[1])]}, {})
        self.process(day=1, retry_only=True)
        sent = json.loads(self.generate.call_args.args[0])["posts"]
        self.assertEqual([p["id"] for p in sent], [gemini.post_id(self.posts[1])])
        self.assertEqual(self.state["entries"], {})

    def test_partial_failure_second_day_still_publishes_valid_result(self):
        self.fail_first()
        self.generate.side_effect = None
        self.generate.return_value = ({"results": [self.result(self.posts[0])]}, {})
        report = self.process(day=1, retry_only=True)
        self.assertEqual(len(report["failed"]), 1)
        self.publish.assert_called_once()
        self.assertEqual(len(self.state["entries"]), 1)

    def test_duplicate_or_invalid_results_do_not_invalidate_other_posts(self):
        a, b = (self.result(p) for p in self.posts)
        for invalid in ([a, a, b], [{**a, "evidence": [{"path": "fake"}]}, b]):
            valid, failures = scheduler.partial_results(
                {"results": invalid}, self.posts, self.sources
            )
            self.assertEqual(valid, [b])
            self.assertEqual(list(failures), [a["id"]])

    def test_daily_run_ignores_new_posts_and_retries_original_content_and_revision(self):
        self.fail_first()
        originals = copy.deepcopy(self.posts)
        self.posts = [{**p, "text": "Edited upstream text"} for p in self.posts]
        self.generate.side_effect = None
        self.process(day=1, retry_only=True, upstream="c" * 40)
        sent = json.loads(self.generate.call_args.args[0])["posts"]
        self.assertCountEqual([p["text"] for p in sent], [p["text"] for p in originals])
        body = self.publish.call_args.args[0]["body"]
        self.assertIn("/blob/" + "b" * 40, body)
        self.assertNotIn("/blob/" + "c" * 40, body)
        self.generate.reset_mock()
        self.process(day=2, retry_only=True)
        self.generate.assert_not_called()

    def test_ambiguous_issue_publication_is_reconciled_without_another_ai_call(self):
        self.publish.side_effect = http_error(503)
        report = self.process()
        self.assertEqual(len(report["retry_pending"]), 2)
        self.assertIn("GitHub-Bericht", report["retry_pending"][0]["error"])
        self.generate.reset_mock()
        self.process(day=1, retry_only=True, known={gemini.post_id(p) for p in self.posts})
        self.generate.assert_not_called()

    def test_state_save_failure_is_not_hidden_and_prevents_ai(self):
        self.store.save.side_effect = http_error(503)
        with self.assertRaisesRegex(scheduler.InfrastructureError, "GitHub-Status speichern"):
            self.process()
        self.generate.assert_not_called()
        self.publish.assert_not_called()

    def test_oversized_post_gets_next_day_attempt_without_ai(self):
        with patch.object(gemini, "MAX_INPUT_BYTES", 1):
            first = self.process()
            second = self.process(day=1, retry_only=True)
        self.assertEqual(len(first["retry_pending"]), 1)
        self.assertEqual(len(second["failed"]), 1)
        self.generate.assert_not_called()

    def test_runner_exit_status_only_fails_for_exhausted_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(
                publish=True,
                retry_only=True,
                retry_failed=False,
                root=Path(directory),
                blog_dir=Path(directory),
                output_dir=Path(directory),
            )
            env = {"GH_TOKEN": "test", "GITHUB_SHA": "a" * 40, "BLOG_SHA": "b" * 40}
            for failures in ([], [{"path": "post.md"}]):
                report = {"failed": failures, "summary": "Bericht"}
                with (
                    patch.dict(os.environ, env, clear=True),
                    patch.object(gemini, "reviewed_ids", return_value=set()),
                    patch.object(scheduler, "GithubState"),
                    patch.object(gemini, "source_snapshot", return_value={}),
                    patch.object(scheduler, "process", return_value=report),
                ):
                    if failures:
                        with self.assertRaises(SystemExit) as error:
                            scheduler.run(args)
                        self.assertEqual(error.exception.code, 1)
                    else:
                        scheduler.run(args)


class GithubStateTests(unittest.TestCase):
    def test_initial_state_branch_and_file_write_never_target_main(self):
        request = Mock(
            side_effect=[http_error(404), http_error(404), {}, {"content": {"sha": "file-sha"}}]
        )
        store = scheduler.GithubState(request, "a" * 40)
        state = store.load()
        store.save(state)
        self.assertEqual(
            request.call_args_list[2].args[1]["ref"], "refs/heads/ha-blog-monitor-state"
        )
        write = request.call_args
        self.assertEqual(write.kwargs, {"method": "PUT"})
        self.assertEqual(write.args[1]["branch"], scheduler.STATE_BRANCH)
        self.assertNotIn("sha", write.args[1])
        self.assertEqual(json.loads(base64.b64decode(write.args[1]["content"])), state)

    def test_existing_state_uses_sha_to_prevent_lost_updates(self):
        state = {"version": 1, "entries": {}}
        request = Mock(
            side_effect=[
                {"sha": "old", "content": base64.b64encode(json.dumps(state).encode()).decode()},
                {"content": {"sha": "new"}},
            ]
        )
        store = scheduler.GithubState(request, "a" * 40)
        store.save(store.load())
        self.assertEqual(request.call_args.args[1]["sha"], "old")
        self.assertEqual(store.sha, "new")

    def test_unavailable_or_corrupt_state_does_not_become_empty_state(self):
        for response in (
            http_error(503),
            {"sha": "old", "content": base64.b64encode(b'{"version":2}').decode()},
        ):
            store = scheduler.GithubState(Mock(side_effect=[response]), "a" * 40)
            with self.assertRaises((HTTPError, ValueError)):
                store.load()


if __name__ == "__main__":
    unittest.main()
