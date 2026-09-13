# SPDX-License-Identifier: Apache-2.0
"""Offline checks for blog triage and issue publication boundaries."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from scripts import ha_blog_monitor as monitor


class BlogMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.component = self.root / "custom_components/enigma2_connect"
        self.component.mkdir(parents=True)
        (self.component / "entity.py").write_text(
            "from homeassistant.helpers.entity import DeviceInfo as Info\n"
            "from homeassistant.helpers import device_registry as dr\n"
            "def example():\n    return dr.async_get_device()\n",
            encoding="utf-8",
        )
        (self.component / "manifest.json").write_text("{}", encoding="utf-8")
        self.index = monitor.code_index(self.root)
        self.blog = self.root / "blog"
        self.blog.mkdir()

    def post(self, text="DeviceInfo changes", path="2026-09-04-test.md"):
        return {"title": "Test", "text": text, "path": path, "date": "2026-09-04"}

    def process(self, posts, request=None, limit=5):
        return monitor.process(
            posts, self.index, self.root, request, "owner/repo", "a" * 40, "b" * 40, limit
        )

    def test_alias_and_member_evidence(self):
        result = monitor.assess(self.post("DeviceInfo and async_get_device"), self.index, self.root)
        self.assertEqual(result["status"], "code-match")
        self.assertIn(
            {
                "reason": "DeviceInfo",
                "path": "custom_components/enigma2_connect/entity.py",
                "line": 1,
            },
            result["evidence"],
        )
        self.assertIn("async_get_device", [item["reason"] for item in result["evidence"]])

    def test_unrelated_platform_and_identifier_boundaries(self):
        result = monitor.assess(
            self.post("LawnMowerEntity supports IDLE. MyDeviceInfoExtra.\n```python\npass\n```"),
            self.index,
            self.root,
        )
        self.assertEqual(result["status"], "no-match")

    def test_cross_cutting_topic_and_frontend(self):
        result = monitor.assess(self.post("Python minimum version changes"), self.index, self.root)
        self.assertEqual(result["status"], "topic-review")
        (self.root / "www").mkdir()
        (self.root / "www/enigma2-connect-remote-card.js").touch()
        result = monitor.assess(self.post("Frontend changes"), self.index, self.root)
        self.assertEqual(result["evidence"][0]["path"], "www/enigma2-connect-remote-card.js")

    def test_dates_drafts_and_complete_content(self):
        for day in ("01", "04", "20"):
            (self.blog / f"2026-09-{day}-example.md").write_text(
                "---\ntitle: 'Example'\n---\nFull text\n<!-- truncate -->\nDeviceInfo",
                encoding="utf-8",
            )
        (self.blog / "2026-09-05-draft.mdx").write_text(
            "---\ntitle: Draft\ndraft: true\n---\nFuture", encoding="utf-8"
        )
        posts = monitor.read_posts(self.blog, date(2026, 9, 4), date(2026, 9, 13))
        self.assertEqual(len(posts), 1)
        self.assertIn("DeviceInfo", posts[0]["text"])
        self.assertEqual(posts[0]["title"], "Example")

    def test_empty_or_changed_source_fails_loudly(self):
        with self.assertRaises(ValueError):
            monitor.read_posts(self.blog, date(2026, 9, 1), date(2026, 9, 13))
        (self.blog / "unexpected.md").write_text("new format", encoding="utf-8")
        with self.assertRaises(ValueError):
            monitor.read_posts(self.blog, date(2026, 9, 1), date(2026, 9, 13))
        (self.blog / "2026-09-04-invalid.md").write_text("no metadata", encoding="utf-8")
        with self.assertRaises(ValueError):
            monitor.read_posts(self.blog, date(2026, 9, 1), date(2026, 9, 13))

    def test_dry_run_never_needs_github(self):
        results = self.process([self.post(), self.post("LawnMowerEntity")])
        self.assertEqual([r["action"] for r in results], ["would-create", "report-only"])

    def test_closed_issue_on_second_page_suppresses_duplicate(self):
        request = Mock(
            side_effect=[
                [{"body": None}] * 100,
                [{"state": "closed", "body": monitor.marker(self.post()["path"])}],
            ]
        )
        result = self.process([self.post()], request)
        self.assertEqual(result[0]["action"], "existing-issue")
        self.assertEqual(request.call_count, 2)
        self.assertIn("state=all", request.call_args_list[1].args[0])
        self.assertIn("page=2", request.call_args_list[1].args[0])

    def test_read_failure_prevents_publication(self):
        request = Mock(side_effect=[[{"body": None}] * 100, OSError("network unavailable")])
        with self.assertRaises(OSError):
            self.process([self.post()], request)
        self.assertTrue(all(len(call.args) == 1 for call in request.call_args_list))

    def test_issue_cap_defers_work_and_repeat_is_idempotent(self):
        request = Mock(side_effect=[[], {"html_url": "https://github.com/owner/repo/issues/1"}])
        posts = [self.post(), self.post(path="2026-09-05-next.md")]
        results = self.process(posts, request, limit=1)
        self.assertEqual([r["action"] for r in results], ["created", "deferred"])
        body = request.call_args.args[1]["body"]
        self.assertIn("/blob/" + "a" * 40, body)
        self.assertIn("/blob/" + "b" * 40, body)
        retry = Mock(
            side_effect=[[{"body": body}], {"html_url": "https://github.com/owner/repo/issues/2"}]
        )
        results = self.process(posts, retry, limit=1)
        self.assertEqual([r["action"] for r in results], ["existing-issue", "created"])

    def test_post_failure_is_not_retried(self):
        request = Mock(side_effect=[[], TimeoutError("response lost")])
        with self.assertRaises(TimeoutError):
            self.process([self.post()], request)
        self.assertEqual(request.call_count, 2)

    def test_title_is_inert_markdown(self):
        safe = monitor.inline("[click](bad) | <script> @owner\nnext")
        self.assertNotIn("<script>", safe)
        self.assertNotIn("@owner", safe)
        self.assertNotIn("\n", safe)
        self.assertIn(r"\|", safe)

    def test_missing_or_broken_integration_fails(self):
        with self.assertRaises(ValueError):
            monitor.code_index(self.root / "missing")
        (self.component / "bad.py").write_text("broken ?", encoding="utf-8")
        with self.assertRaises(SyntaxError):
            monitor.code_index(self.root)


if __name__ == "__main__":
    unittest.main()
