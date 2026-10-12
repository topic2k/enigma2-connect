# SPDX-License-Identifier: Apache-2.0
"""Offline tests of durable assessment transactions and Atom semantics."""

import base64
import copy
import hashlib
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from scripts import ha_blog_feed as feed
from scripts import ha_blog_gemini as common
from scripts import ha_blog_junie_monitor as monitor
from scripts import ha_blog_scheduler as scheduler


class Git:
    """Small Git API double implementing blob/tree/commit/ref semantics."""

    def __init__(self):
        self.refs, self.trees, self.commits, self.blobs = {}, {}, {}, {}
        self.calls = []
        self.runs = {}
        self.prs = []

    def request(self, endpoint, payload=None, *, method=None):
        self.calls.append((endpoint, copy.deepcopy(payload), method))
        if endpoint.startswith("git/ref/heads/"):
            branch = endpoint.removeprefix("git/ref/heads/")
            if branch not in self.refs:
                raise HTTPError("https://api.github.com/", 404, "Missing", {}, None)
            return {"object": {"sha": self.refs[branch]}}
        if endpoint == "git/trees":
            tree = copy.deepcopy(self.trees.get(payload.get("base_tree"), {}))
            for item in payload["tree"]:
                sha = hashlib.sha1(item["content"].encode()).hexdigest()
                self.blobs[sha] = item["content"]
                tree[item["path"]] = {
                    "path": item["path"],
                    "type": "blob",
                    "mode": "100644",
                    "sha": sha,
                }
            sha = hashlib.sha1(json.dumps(tree, sort_keys=True).encode()).hexdigest()
            self.trees[sha] = tree
            return {"sha": sha}
        if endpoint.startswith("git/trees/"):
            sha = endpoint.split("/")[2].split("?")[0]
            return {"tree": list(self.trees[sha].values())}
        if endpoint.startswith("git/blobs/"):
            return {
                "encoding": "base64",
                "content": base64.b64encode(self.blobs[endpoint.split("/")[-1]].encode()).decode(),
            }
        if endpoint == "git/commits":
            sha = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            self.commits[sha] = {"tree": {"sha": payload["tree"]}, "parents": payload["parents"]}
            return {"sha": sha}
        if endpoint.startswith("git/commits/"):
            return self.commits[endpoint.split("/")[-1]]
        if endpoint == "git/refs":
            branch = payload["ref"].removeprefix("refs/heads/")
            if branch in self.refs:
                raise ValueError("Ref already exists")
            self.refs[branch] = payload["sha"]
            return {}
        if endpoint.startswith("git/refs/heads/"):
            branch = endpoint.removeprefix("git/refs/heads/")
            assert method == "PATCH" and payload["force"] is False
            assert self.commits[payload["sha"]]["parents"] == [self.refs[branch]]
            self.refs[branch] = payload["sha"]
            return {}
        if endpoint.startswith("actions/runs/"):
            return self.runs[endpoint]
        if endpoint.startswith("pulls?"):
            return self.prs
        raise AssertionError(endpoint)


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.git = Git()
        self.store = feed.FeedState(self.git.request, "a" * 40, "o/r")
        self.state = self.store.load()
        self.post = {
            "path": "2026-10-01-example.md",
            "title": "Überprüfung & <Titel>",
            "date": "2026-10-01",
            "text": "Public news",
        }
        self.key = common.post_id(self.post)
        self.env = patch.dict(os.environ, {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.clock = patch.object(feed, "timestamp", return_value="2026-10-12T10:00:00Z")
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.result = {
            "id": self.key,
            "assessment": "no-impact",
            "reason": "Keine Auswirkung & <script>test</script>",
            "next_steps": "Keine",
            "ha_version": "2026.11",
            "evidence": [],
            "opportunity": {
                "assessment": "none",
                "reason": "Kein Nutzen",
                "next_steps": "Keine",
                "evidence": [],
            },
        }

    @property
    def record(self):
        return self.store.records[feed.identity(self.post["path"])]

    def reserve(self):
        scheduler.reserve_attempts(
            [self.post], self.state, date(2026, 10, 12), self.store, "b" * 40
        )

    def complete(self, result=True, publisher=None):
        if publisher is None:
            publisher = Mock(
                return_value={"html_url": "https://github.com/o/r/issues/4", "number": 4}
            )
        return scheduler.complete_processing(
            [self.post],
            {},
            self.state,
            date(2026, 10, 12),
            self.store,
            [self.result] if result else [],
            {} if result else {self.key: "Analyse: keine gültige Antwort"},
            {"deferred": 0},
            publisher,
            "o/r",
            "a" * 40,
        )

    def atom(self):
        return feed.render_atom(self.store.records, "o/r", "https://o.github.io/r/")

    def test_reservation_and_retry_state_are_one_atomic_commit(self):
        self.reserve()
        head = self.git.refs[scheduler.STATE_BRANCH]
        files = self.git.trees[self.git.commits[head]["tree"]["sha"]]
        self.assertIn(scheduler.STATE_PATH, files)
        self.assertIn(feed.INDEX, files)
        self.assertIn(feed.PREFIX + "posts/" + self.record["id"] + ".json", files)
        self.assertEqual(self.record["attempts"][0]["status"], "started")
        self.assertNotIn("main", self.git.refs)

    def test_quiet_result_is_durable_and_does_not_create_issue(self):
        self.reserve()
        publisher = Mock()
        self.complete(publisher=publisher)
        publisher.assert_not_called()
        fresh = feed.FeedState(self.git.request, "a" * 40, "o/r")
        state = fresh.load()
        self.assertEqual(state["entries"], {})
        event = fresh.records[self.record["id"]]["attempts"][0]
        self.assertEqual(event["result"], self.result)
        self.assertEqual(event["publication"], "not_required")
        self.assertEqual(feed.summary(event), "Ohne Handlungsbedarf")

    def test_failed_attempt_and_successful_retry_keep_one_atom_id(self):
        self.reserve()
        self.complete(result=False)
        before = ET.fromstring(self.atom()).find(f"{{{feed.ATOM}}}entry/{{{feed.ATOM}}}id").text
        os.environ["GITHUB_RUN_ID"] = "124"
        self.reserve()
        self.complete()
        root = ET.fromstring(self.atom())
        entries = root.findall(f"{{{feed.ATOM}}}entry")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].find(f"{{{feed.ATOM}}}id").text, before)
        self.assertEqual([e["status"] for e in self.record["attempts"]], ["failed", "completed"])

    def test_content_change_keeps_id_but_new_content_receipt(self):
        self.reserve()
        self.complete()
        original = self.record["id"]
        self.post["text"] += " updated"
        self.key = common.post_id(self.post)
        self.result["id"] = self.key
        os.environ["GITHUB_RUN_ID"] = "124"
        self.reserve()
        self.complete()
        self.assertEqual(self.record["id"], original)
        self.assertEqual(len(self.record["attempts"]), 2)
        self.assertNotEqual(*[e["content_id"] for e in self.record["attempts"]])

    def test_run_attempt_prevents_duplicate_or_colliding_reservations(self):
        self.reserve()
        self.store.save(self.state)
        self.assertEqual(len(self.record["attempts"]), 1)
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        self.reserve()
        self.assertEqual(len(self.record["attempts"]), 2)

    def test_publication_failure_preserves_valid_assessment(self):
        self.result["assessment"] = "uncertain"
        self.reserve()
        report = self.complete(
            publisher=Mock(
                side_effect=HTTPError("https://api.github.com/", 503, "private", {}, None)
            )
        )
        self.assertEqual(len(report["retry_pending"]), 1)
        event = self.record["attempts"][0]
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["result"], self.result)
        self.assertEqual(event["publication"], "failed")
        self.assertIn("Issue-Veröffentlichung fehlgeschlagen", feed.summary(event))

    def test_terminal_failures_and_uncertain_assessments_have_distinct_summaries(self):
        self.reserve()
        self.complete(result=False)
        self.assertIn("Wiederholung vorgemerkt", feed.summary(self.record["attempts"][-1]))
        os.environ["GITHUB_RUN_ID"] = "124"
        self.reserve()
        self.complete(result=False)
        self.assertIn("manuelle Prüfung", feed.summary(self.record["attempts"][-1]))
        self.result["assessment"] = "uncertain"
        os.environ["GITHUB_RUN_ID"] = "125"
        self.reserve()
        self.complete()
        self.assertIn("unklar", feed.summary(self.record["attempts"][-1]))

    def test_reexport_preserves_timestamps_and_bytes(self):
        self.reserve()
        self.complete()
        before = self.atom()
        head = self.git.refs[scheduler.STATE_BRANCH]
        self.store.save(self.state)
        self.assertEqual(self.git.refs[scheduler.STATE_BRANCH], head)
        self.assertEqual(self.atom(), before)

    def test_xml_roundtrip_escapes_external_markup_and_keeps_unicode(self):
        self.reserve()
        self.complete()
        root = ET.fromstring(self.atom())
        entry = root.find(f"{{{feed.ATOM}}}entry")
        self.assertEqual(entry.find(f"{{{feed.ATOM}}}title").text, self.post["title"])
        content = entry.find(f"{{{feed.ATOM}}}content").text
        self.assertIn("&lt;script&gt;", content)
        self.assertNotIn("<script>", content)
        self.assertEqual(entry.find(f"{{{feed.ATOM}}}published").text, self.record["published"])
        self.assertEqual(entry.find(f"{{{feed.ATOM}}}updated").text, self.record["updated"])

    def test_reconciliation_uses_real_attempt_conclusion_and_leaves_running_alone(self):
        self.reserve()
        endpoint = "actions/runs/123/attempts/1"
        self.git.runs[endpoint] = {"status": "in_progress"}
        self.store.reconcile()
        self.assertEqual(self.record["attempts"][0]["status"], "started")
        self.git.runs[endpoint] = {
            "status": "completed",
            "conclusion": "cancelled",
            "updated_at": "2026-10-12T12:00:00Z",
        }
        attempts = self.state["entries"][self.key]["attempts"]
        self.store.reconcile()
        self.assertEqual(self.record["attempts"][0]["status"], "cancelled")
        self.assertEqual(self.state["entries"][self.key]["attempts"], attempts)

    def test_stale_branch_write_cannot_overwrite_other_writer(self):
        self.reserve()
        self.git.refs[scheduler.STATE_BRANCH] = "f" * 40
        with self.assertRaisesRegex(ValueError, "stale write"):
            self.store.save(self.state)
        self.assertEqual(self.git.refs[scheduler.STATE_BRANCH], "f" * 40)

    def test_corrupt_or_incomplete_history_never_becomes_empty_feed(self):
        self.reserve()
        head = self.git.refs[scheduler.STATE_BRANCH]
        tree = self.git.trees[self.git.commits[head]["tree"]["sha"]]
        del tree[feed.PREFIX + "posts/" + self.record["id"] + ".json"]
        with self.assertRaisesRegex(ValueError, "Missing assessment"):
            self.store.load()

    def test_implementation_results_update_same_entry_idempotently(self):
        self.result["assessment"] = "uncertain"
        self.reserve()
        self.complete()
        item = {
            "version": 1,
            "content_id": self.key,
            "issue_number": 4,
            "outcome": {
                "status": "draft",
                "updated": "2026-10-12T13:00:00Z",
                "run_url": "https://github.com/o/r/actions/runs/123/attempts/1",
                "pr_url": "https://github.com/o/r/pull/5",
                "summary": "Vorschlag",
                "reason": "Begründung",
                "tests": "Gemeldete Tests",
            },
        }
        feed.apply_implementation(self.store, item)
        first = self.atom()
        feed.apply_implementation(self.store, item)
        self.assertEqual(self.atom(), first)
        self.assertEqual(len(self.record["attempts"][0]["implementations"]), 1)
        self.assertEqual(self.record["updated"], item["outcome"]["updated"])

    def test_implementation_rejects_foreign_issue_and_forged_pr_url(self):
        self.result["assessment"] = "uncertain"
        self.reserve()
        self.complete()
        item = {
            "version": 1,
            "content_id": self.key,
            "issue_number": 9,
            "outcome": {"status": "failed", "updated": "2026-10-12T13:00:00Z"},
        }
        with self.assertRaises(ValueError):
            feed.apply_implementation(self.store, item)
        item["issue_number"] = 4
        item["outcome"]["pr_url"] = "https://evil.example/token"
        with self.assertRaises(ValueError):
            feed.apply_implementation(self.store, item)

    def test_missing_implementation_artifact_is_reconciled_without_inventing_tests(self):
        self.result["assessment"] = "uncertain"
        self.reserve()
        self.complete()
        self.git.runs["actions/runs/123/attempts/1"] = {
            "status": "completed",
            "updated_at": "2026-10-12T14:00:00Z",
        }
        self.store.reconcile_implementations()
        outcome = self.record["attempts"][0]["implementations"][0]
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("Keine unabhängig", outcome["tests"])

    def test_legacy_receipts_are_unknown_and_import_is_idempotent(self):
        self.state["reviewed"] = {self.key: "2026-10-01"}
        imported = feed.import_history(self.store, self.state, [self.post], [], [])
        self.assertEqual(imported["unmatched"], [])
        self.assertEqual(self.record["attempts"][0]["status"], "historical")
        self.assertNotIn("Ohne Handlungsbedarf", self.atom())
        first = self.atom()
        feed.import_history(self.store, self.state, [self.post], [], [])
        self.assertEqual(self.atom(), first)

    def test_historical_reports_keep_exact_results_and_ignore_dry_runs(self):
        report = {"dry_run": False, "revision": "a" * 40, "results": [self.result]}
        envelope = {"id": 100, "created_at": "2026-10-01T12:00:00Z", "report": report}
        feed.import_history(self.store, self.state, [self.post], [envelope], [])
        self.assertEqual(self.record["attempts"][0]["result"], self.result)
        envelope["id"] = 101
        report["dry_run"] = True
        feed.import_history(self.store, self.state, [self.post], [envelope], [])
        self.assertEqual(len(self.record["attempts"]), 1)

    def test_unmatched_historical_content_is_reported_without_fabricated_entry(self):
        self.state["reviewed"] = {"f" * 64: "2026-10-01"}
        imported = feed.import_history(self.store, self.state, [self.post], [], [])
        self.assertEqual(imported["unmatched"], [{"content_id": "f" * 64}])
        self.assertEqual(self.store.records, {})

    def test_paths_and_links_cannot_escape_allowed_origins(self):
        for value in ("../post.md", "C:/post.md", "/post.md", "a\\post.md", "post.txt"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                feed.identity(value)
        for value in (
            "javascript:alert(1)",
            "https://o.github.io/r/?token=x",
            "http://o.github.io/r/",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                feed.render_atom({}, "o/r", value)

    def test_dry_export_cannot_mutate_github(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = Mock(side_effect=self.git.request)
            with (
                patch.dict(
                    os.environ,
                    {"GITHUB_REPOSITORY": "o/r", "GITHUB_SHA": "a" * 40, "GH_TOKEN": "test"},
                ),
                patch.object(
                    common,
                    "github_request",
                    side_effect=lambda repo, token, endpoint, payload=None, **kw: request(
                        endpoint, payload, **kw
                    ),
                ),
                patch(
                    "sys.argv",
                    ["feed", "--base-url", "https://o.github.io/r/", "--output", temporary],
                ),
            ):
                feed.main()
            self.assertTrue((Path(temporary) / "atom.xml").exists())
            self.assertTrue(all(c.args[1] is None for c in request.call_args_list))
            self.assertEqual(self.git.refs, {})

    def test_production_prepare_and_finish_roundtrip_preserves_quiet_assessment(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            output = directory / "monitor"
            with (
                patch.object(monitor, "OUTPUT", output),
                patch.object(monitor, "github", return_value=("o/r", "a" * 40, self.git.request)),
                patch.object(common, "read_posts", return_value=[self.post]),
                patch.object(common, "reviewed_ids", return_value=set()),
                patch.object(common, "source_snapshot", return_value={"entity.py": "actual code"}),
                patch.dict(
                    os.environ,
                    {
                        "BLOG_SHA": "b" * 40,
                        "GITHUB_OUTPUT": str(directory / "outputs"),
                        "GITHUB_STEP_SUMMARY": str(directory / "summary"),
                    },
                ),
            ):
                with patch(
                    "sys.argv", ["monitor", "prepare", "--publish", "--blog-dir", temporary]
                ):
                    monitor.main()
                monitor.write_json(
                    directory / f"result-{self.key}.json", {"data": {"results": [self.result]}}
                )
                with patch("sys.argv", ["monitor", "finish", "--results-dir", temporary]):
                    monitor.main()
            fresh = feed.FeedState(self.git.request, "a" * 40, "o/r")
            state = fresh.load()
            self.assertIn(self.key, state["reviewed"])
            self.assertEqual(len(fresh.records), 1)
            event = next(iter(fresh.records.values()))["attempts"][0]
            self.assertEqual(event["result"], self.result)
            self.assertEqual(event["publication"], "not_required")


if __name__ == "__main__":
    unittest.main()
