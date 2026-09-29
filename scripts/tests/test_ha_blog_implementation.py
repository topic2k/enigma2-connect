# SPDX-License-Identifier: Apache-2.0
"""Offline tests of the untrusted proposal / trusted draft publisher boundary."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from scripts import ha_blog_implementation as implementation


class ImplementationTests(unittest.TestCase):
    def setUp(self):
        self.base = "a" * 40
        self.key = "b" * 64
        self.data = {
            "base": self.base,
            "changes": [
                {"path": "custom_components/enigma2_connect/entity.py", "content": "source\n"}
            ],
        }
        self.responses = {
            "issues/12": {
                "state": "open",
                "title": "[HA-Blog] Tool results",
                "body": f"<!-- ha-blog-gemini:{self.key} -->",
                "html_url": "https://github.com/o/r/issues/12",
            },
            "pulls?state=all&base=develop&per_page=100&page=1": [],
            "git/ref/heads/develop": {"object": {"sha": self.base}},
            f"git/commits/{self.base}": {"tree": {"sha": "c" * 40}},
            f"git/trees/{'c' * 40}?recursive=1": {"tree": [], "truncated": False},
            "git/trees": {"sha": "d" * 40},
            "git/commits": {"sha": "e" * 40},
            "git/refs": {},
            "pulls": {"html_url": "https://github.com/o/r/pull/13"},
        }

        def request(endpoint, payload=None):
            if endpoint.startswith("git/ref/heads/ha-blog/") and endpoint not in self.responses:
                raise HTTPError("https://api.github.com/", 404, "Not found", {}, None)
            return self.responses[endpoint]

        self.request = Mock(side_effect=request)

    def publish(self):
        return implementation.publish(
            self.request,
            "o/r",
            self.base,
            12,
            self.key,
            self.data,
            "https://github.com/o/r/actions/runs/123",
        )

    def test_creates_draft_against_develop_with_issue_and_run_links(self):
        self.assertIn("/pull/13", self.publish())
        calls = {
            call.args[0]: call.args[1]
            for call in self.request.call_args_list
            if len(call.args) == 2
        }
        self.assertEqual(calls["pulls"]["base"], "develop")
        self.assertTrue(calls["pulls"]["draft"])
        self.assertIn("/issues/12", calls["pulls"]["body"])
        self.assertIn("/actions/runs/123", calls["pulls"]["body"])
        self.assertEqual(calls["git/commits"]["parents"], [self.base])
        self.assertEqual(calls["git/refs"]["ref"], "refs/heads/ha-blog/tool-results")

    def test_existing_closed_or_open_pr_is_not_recreated_or_updated(self):
        endpoint = next(key for key in self.responses if key.startswith("pulls?"))
        self.responses[endpoint] = [
            {
                "html_url": "https://github.com/o/r/pull/13",
                "body": f"<!-- ha-blog-implementation:12:{self.key} -->",
            }
        ]
        self.assertIn("unverändert", self.publish())
        self.assertTrue(all(len(call.args) == 1 for call in self.request.call_args_list))

    def test_topic_branch_collision_uses_issue_number_without_overwriting(self):
        self.responses["git/ref/heads/ha-blog/tool-results"] = {"object": {"sha": "f" * 40}}
        self.publish()
        ref = next(
            call.args[1]["ref"]
            for call in self.request.call_args_list
            if call.args[0] == "git/refs"
        )
        self.assertEqual(ref, "refs/heads/ha-blog/tool-results-12")

    def test_slug_normalizes_unicode_and_rejects_empty_or_unsafe_branch_text(self):
        self.assertEqual(
            implementation.branch_name("[HA-Blog] Größere Geräte / Tool Results!", 12),
            "ha-blog/grossere-gerate-tool-results",
        )
        self.assertEqual(implementation.branch_name("[HA-Blog] ???", 12), "ha-blog/issue-12")
        self.assertLessEqual(len(implementation.branch_name("x" * 200, 12)), 68)

    def test_stale_develop_and_closed_issue_prevent_writes(self):
        for kind in ("base", "issue"):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == "base":
                    self.responses["git/ref/heads/develop"]["object"]["sha"] = "f" * 40
                else:
                    self.responses["issues/12"]["state"] = "closed"
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertTrue(all(len(call.args) == 1 for call in self.request.call_args_list))

    def test_empty_proposal_does_not_publish(self):
        self.data["changes"] = []
        self.assertIn("Keine umsetzbare", self.publish())
        self.request.assert_not_called()

    def test_protected_traversal_duplicate_and_binary_paths_rejected(self):
        for path in (
            "../escape.py",
            "/tmp/escape.py",
            ".github/workflows/ci.yml",
            "AGENTS.md",
            "tests/../escape.py",
            "docs/.secret.md",
            "custom_components/enigma2_connect/quality_scale.yaml",
            "tests/AGENTS.md",
            "tests\\escape.py",
            "tests/data.bin",
        ):
            with self.subTest(path=path):
                data = copy.deepcopy(self.data)
                data["changes"][0]["path"] = path
                with self.assertRaises(ValueError):
                    implementation.validate_changes(data, self.base)
        for changes in (
            [self.data["changes"][0]] * 2,
            [{"path": "tests/test.py", "content": "a\0b"}],
        ):
            with self.assertRaises(ValueError):
                implementation.validate_changes({"base": self.base, "changes": changes}, self.base)

    def test_base_mismatch_size_and_symlink_base_rejected(self):
        with self.assertRaises(ValueError):
            implementation.validate_changes(self.data, "f" * 40)
        with patch.object(implementation, "MAX_BYTES", 10), self.assertRaises(ValueError):
            implementation.validate_changes(self.data, self.base)
        self.responses[f"git/trees/{'c' * 40}?recursive=1"]["tree"] = [
            {"path": self.data["changes"][0]["path"], "mode": "120000"}
        ]
        with self.assertRaises(ValueError):
            self.publish()
        self.assertTrue(all(len(call.args) == 1 for call in self.request.call_args_list))

    def test_collection_preserves_added_changed_and_deleted_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tests").mkdir()
            (root / "tests/new.py").write_text("new\n", encoding="utf-8")
            (root / "tests/existing.py").write_text("changed\n", encoding="utf-8")
            output = root / "proposal.json"
            with patch.object(
                implementation.subprocess,
                "check_output",
                side_effect=[b"tests/existing.py\0tests/deleted.py\0", b"tests/new.py\0"],
            ):
                implementation.collect(root, self.base, output)
            import json

            changes = {
                item["path"]: item["content"] for item in json.loads(output.read_text())["changes"]
            }
            self.assertEqual(
                changes,
                {
                    "tests/existing.py": "changed\n",
                    "tests/deleted.py": None,
                    "tests/new.py": "new\n",
                },
            )


if __name__ == "__main__":
    unittest.main()
