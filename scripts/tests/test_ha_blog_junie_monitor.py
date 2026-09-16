# SPDX-License-Identifier: Apache-2.0
"""Offline checks of the production Junie artifact/retry boundary."""

import copy
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import ha_blog_gemini as common
from scripts import ha_blog_junie_monitor as monitor


class JunieMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.today = date(2026, 9, 16)
        self.posts = [
            dict(path=f"post-{i}.md", title=f"Post {i}", text=f"News {i}", date="2026-09-16")
            for i in range(2)
        ]
        self.sources = {"entity.py": "actual source line"}
        self.store = Mock()
        self.saved = []
        self.store.save.side_effect = lambda value: self.saved.append(copy.deepcopy(value))
        self.publisher = Mock(return_value={"html_url": "https://github.com/o/r/issues/1"})

    def plan(self, state=None, day=0, **kwargs):
        return monitor.prepare_plan(
            self.posts,
            self.sources,
            state or {"version": 1, "entries": {}},
            set(),
            self.today + timedelta(days=day),
            self.store,
            "b" * 40,
            repository="o/r",
            revision="a" * 40,
            output=self.root / "plan",
            **kwargs,
        )

    def result(self, post):
        return {
            "id": common.post_id(post),
            "assessment": "no-impact",
            "reason": "Kein Bedarf",
            "next_steps": "Keine",
            "ha_version": "2027.10",
            "evidence": [],
            "opportunity": {
                "assessment": "none",
                "reason": "Kein Nutzen",
                "next_steps": "Keine",
                "evidence": [],
            },
        }

    def artifact(self, post, data=None, **extra):
        monitor.write_json(
            self.root / "results" / f"junie-result-{common.post_id(post)}" / "result.json",
            {"data": data or {"results": [self.result(post)]}, **extra},
        )

    def finish(self, plan):
        return monitor.finish_plan(plan, self.root / "results", self.store, self.publisher)

    def test_each_packet_has_one_post_and_reservation_precedes_workers(self):
        plan = self.plan()
        self.assertEqual(len(self.saved[0]["entries"]), 2)
        for post in self.posts:
            packet = self.root / "plan" / "packets" / common.post_id(post)
            data = monitor.read_json(packet / "input.json")
            self.assertEqual([p["path"] for p in data["posts"]], [post["path"]])
        self.assertEqual(len(plan["keys"]), 2)

    def test_partial_failure_retries_only_failed_post_next_day_then_turns_red(self):
        plan = self.plan()
        self.artifact(self.posts[0])
        first = self.finish(plan)
        self.assertEqual(first["failed"], [])
        self.assertEqual(len(first["retry_pending"]), 1)
        state = self.saved[-1]
        same_day = self.plan(state, retry_only=True)
        self.assertEqual(same_day["posts"], [])
        second = self.finish(self.plan(state, day=1, retry_only=True))
        self.assertEqual(len(second["failed"]), 1)
        self.assertEqual(second["retry_pending"], [])
        terminal = self.plan(self.saved[-1], day=2, retry_only=True)
        self.assertEqual(terminal["posts"], [])
        self.publisher.assert_not_called()

    def test_quiet_results_are_remembered_without_issue_or_weekly_reanalysis(self):
        plan = self.plan(publish=True)
        for post in self.posts:
            self.artifact(post)
        report = self.finish(plan)
        self.publisher.assert_not_called()
        self.assertNotIn("issue_url", report)
        self.assertEqual(len(report["silent_reviewed"]), 2)
        state = json.loads(json.dumps(self.saved[-1]))
        monitor.scheduler.validate_state(state)
        self.assertEqual(state["entries"], {})
        self.assertEqual(len(state["reviewed"]), 2)
        self.assertEqual(self.plan(state, day=7)["keys"], [])
        self.posts[0]["text"] += " Updated announcement"
        self.assertEqual(self.plan(state, day=7)["keys"], [common.post_id(self.posts[0])])

    def test_mixed_results_publish_only_the_independent_improvement(self):
        plan = self.plan()
        self.artifact(self.posts[0])
        result = self.result(self.posts[1])
        result["opportunity"].update(
            assessment="recommended",
            evidence=[{"path": "entity.py", "line": 1, "quote": "actual source line"}],
        )
        self.artifact(self.posts[1], {"results": [result]})
        self.finish(plan)
        payload = self.publisher.call_args.args[0]
        self.assertIn("1 Beiträge", payload["title"])
        self.assertNotIn("Post 0", payload["body"])
        self.assertIn("Post 1", payload["body"])
        self.assertIn("Verbesserungen: Empfohlen", payload["body"])
        self.assertEqual(len(self.saved[-1]["reviewed"]), 2)

    def test_uncertain_impact_or_opportunity_still_requests_review(self):
        plan = self.plan()
        for i, field in enumerate(("assessment", "opportunity")):
            result = self.result(self.posts[i])
            if field == "assessment":
                result[field] = "uncertain"
            else:
                result[field]["assessment"] = "uncertain"
            self.artifact(self.posts[i], {"results": [result]})
        self.finish(plan)
        self.publisher.assert_called_once()
        body = self.publisher.call_args.args[0]["body"]
        self.assertIn("Kompatibilität: uncertain", body)
        self.assertIn("Verbesserungen: Zu prüfen", body)

    def test_publication_failure_preserves_silent_success_and_retries_only_relevant(self):
        plan = self.plan()
        self.artifact(self.posts[0])
        result = self.result(self.posts[1])
        result["assessment"] = "uncertain"
        self.artifact(self.posts[1], {"results": [result]})
        self.publisher.side_effect = OSError("Failed publication")
        report = self.finish(plan)
        self.assertEqual(len(report["retry_pending"]), 1)
        state = self.saved[-1]
        self.assertIn(common.post_id(self.posts[0]), state["reviewed"])
        self.assertNotIn(common.post_id(self.posts[1]), state["reviewed"])
        self.assertEqual(self.plan(state, day=1)["keys"], [common.post_id(self.posts[1])])

    def test_silent_state_save_failure_is_not_reported_as_success(self):
        plan = self.plan()
        for post in self.posts:
            self.artifact(post)
        self.store.save.side_effect = OSError("Cannot save")
        with self.assertRaises(monitor.scheduler.InfrastructureError):
            self.finish(plan)
        self.publisher.assert_not_called()

    def test_invalid_silent_receipt_is_rejected_instead_of_skipping_content(self):
        for reviewed in ([], {"bad-id": "2026-09-16"}, {"a" * 64: "not-a-date"}):
            with self.assertRaises(ValueError):
                monitor.scheduler.validate_state(
                    {"version": 1, "entries": {}, "reviewed": reviewed}
                )

    def test_next_day_success_clears_original_failure(self):
        self.finish(self.plan())
        state = self.saved[-1]
        for post in self.posts:
            self.artifact(post)
        result = self.finish(self.plan(state, day=1, retry_only=True))
        self.assertEqual(result["failed"], [])
        self.assertEqual(self.saved[-1]["entries"], {})

    def test_wrong_id_and_fabricated_quote_are_rejected_at_publication(self):
        plan = self.plan()
        self.artifact(self.posts[0], {"results": [self.result(self.posts[1])]})
        result = self.result(self.posts[1])
        result.update(
            assessment="impacted",
            evidence=[{"path": "entity.py", "line": 1, "quote": "invented source"}],
        )
        self.artifact(self.posts[1], {"results": [result]})
        report = self.finish(plan)
        self.assertEqual(len(report["retry_pending"]), 2)
        self.publisher.assert_not_called()

    def test_positive_impact_and_independent_improvement_are_preserved(self):
        plan = self.plan()
        result = self.result(self.posts[0])
        evidence = [{"path": "entity.py", "line": 1, "quote": "actual source line"}]
        result.update(assessment="impacted", evidence=evidence)
        result["opportunity"].update(assessment="recommended", evidence=evidence)
        self.artifact(self.posts[0], {"results": [result]})
        self.finish(plan)
        body = self.publisher.call_args.args[0]["body"]
        self.assertIn("Kompatibilität: impacted", body)
        self.assertIn("Verbesserungen: Empfohlen", body)
        self.assertIn("2027.10", body)

    def test_usage_only_exports_costs_and_models_and_unknown_is_not_zero(self):
        plan = self.plan()
        self.artifact(
            self.posts[0],
            usage={
                "cost_usd": 999,
                "models": [{"model": "gemini-3.7-flash", "cost": 0.05, "secret": "never-publish"}],
            },
        )
        self.artifact(self.posts[1])
        report = self.finish(plan)
        self.assertEqual(report["reported_cost_usd"], 0.05)
        self.assertEqual(report["unmeasured_posts"], 1)
        self.assertNotIn("never-publish", json.dumps(report))
        self.assertIn("llmUsage", report["summary"])

    def test_invalid_usage_does_not_invalidate_good_result_or_publish_unsafe_text(self):
        plan = self.plan()
        self.artifact(self.posts[0], usage={"models": [{"model": "bad\n@all", "cost": 1}]})
        self.artifact(self.posts[1], usage={"models": [{"model": "ok", "cost": float("nan")}]})
        report = self.finish(plan)
        self.assertEqual(len(report["results"]), 2)
        self.assertEqual(report["unmeasured_posts"], 2)
        self.assertNotIn("@all", report["summary"])

    def test_collect_retains_measured_cost_even_after_failed_agent(self):
        packet = self.root / "packet"
        usage = self.root / "usage.json"
        monitor.write_json(
            usage,
            {
                "llmUsage": [
                    {
                        "model": "model",
                        "cost": 0.1,
                        "inputTokens": 2,
                        "cacheInputTokens": 0,
                        "outputTokens": 1,
                    }
                ],
                "secret": "private",
            },
        )
        out = self.root / "result.json"
        monitor.collect(packet, usage, "failure", out)
        result = monitor.read_json(out)
        self.assertNotIn("data", result)
        self.assertEqual(result["usage"]["cost_usd"], 0.1)
        self.assertNotIn("private", out.read_text())

    def test_known_posts_and_daily_new_posts_make_no_tasks(self):
        plan = self.plan(retry_only=True)
        self.assertEqual(plan["keys"], [])
        self.store.save.assert_not_called()

    def test_dry_run_does_not_mutate_caller_state(self):
        state = {"version": 1, "entries": {}}
        original = copy.deepcopy(state)
        plan = monitor.prepare_plan(
            self.posts,
            self.sources,
            state,
            set(),
            self.today,
            monitor.MemoryStore(),
            "b" * 40,
            output=self.root / "dry",
        )
        self.assertFalse(plan["publish"])
        self.assertEqual(state, original)

    def test_malformed_worker_envelope_only_retries_its_own_post(self):
        plan = self.plan()
        monitor.write_json(
            self.root / "results" / f"junie-result-{common.post_id(self.posts[0])}" / "result.json",
            ["invalid worker envelope"],
        )
        self.artifact(self.posts[1])
        report = self.finish(plan)
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(len(report["retry_pending"]), 1)
        self.assertEqual(report["failed"], [])

    def test_concurrent_state_change_prevents_publication_and_overwrite(self):
        self.plan(publish=True)
        self.store.load.return_value = {"version": 1, "entries": {}}
        self.store.save.reset_mock()
        with (
            patch("sys.argv", ["monitor", "finish"]),
            patch.object(monitor, "OUTPUT", self.root / "plan"),
            patch.object(monitor, "github", return_value=("o/r", "a" * 40, Mock())),
            patch.object(monitor.scheduler, "GithubState", return_value=self.store),
            patch.object(monitor, "finish_plan") as finish,
        ):
            with self.assertRaisesRegex(ValueError, "changed since reservation"):
                monitor.main()
        finish.assert_not_called()
        self.store.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
