# SPDX-License-Identifier: Apache-2.0
"""Offline verification of bounded Gemini analysis and durable issue receipts."""

import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from scripts import ha_blog_gemini as gemini


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = "custom_components/enigma2_connect/entity.py"
        source = self.root / self.path
        source.parent.mkdir(parents=True)
        source.write_text("from homeassistant.helpers.entity import DeviceInfo\n", encoding="utf-8")
        self.sources = gemini.source_snapshot(self.root)
        self.post = {
            "path": "2026-09-04-test.md",
            "title": "Registry change",
            "text": "DeviceInfo changes",
            "date": "2026-09-04",
        }
        self.result = {
            "id": gemini.post_id(self.post),
            "assessment": "impacted",
            "reason": "Konkrete Änderung",
            "ha_version": "2026.10",
            "next_steps": "DeviceInfo prüfen",
            "opportunity": {
                "assessment": "none",
                "reason": "Nur eine notwendige Migration, keine zusätzliche Funktion.",
                "next_steps": "Keine optionale Erweiterung vorgeschlagen.",
                "evidence": [],
            },
            "evidence": [{"path": self.path, "line": 1, "quote": self.sources[self.path].strip()}],
        }
        self.blog = self.root / "blog"
        self.blog.mkdir()
        (self.blog / self.post["path"]).write_text(
            "---\ntitle: Registry change\n---\nDeviceInfo changes", encoding="utf-8"
        )
        self.args = argparse.Namespace(
            root=self.root,
            blog_dir=self.blog,
            since=date(2026, 9, 1),
            output_dir=self.root / "output",
            publish=True,
            prepare_only=False,
        )
        self.env = {
            "GH_TOKEN": "github-test",
            "GEMINI_API_KEY": "google-test",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_SHA": "a" * 40,
            "BLOG_SHA": "b" * 40,
        }

    def test_snapshot_excludes_secrets_and_local_files(self):
        (self.root / ".env").write_text("SECRET=private")
        (self.root / ".work").mkdir()
        (self.root / ".work/private.py").write_text("SECRET=private")
        self.assertEqual(list(gemini.source_snapshot(self.root)), [self.path])

    def test_new_content_requeues_but_completed_posts_do_not(self):
        known = {gemini.post_id(self.post)}
        self.assertEqual(gemini.select_batch([self.post], known, self.sources), ([], "", 0))
        changed = {**self.post, "text": "Updated migration"}
        batch, prompt, deferred = gemini.select_batch([changed], known, self.sources)
        self.assertEqual(batch, [changed])
        self.assertIn("1: from homeassistant", prompt)
        self.assertEqual(deferred, 0)

    def test_batch_is_capped_and_never_truncates_source(self):
        posts = [{**self.post, "path": f"2026-09-04-{i}.md"} for i in range(8)]
        batch, prompt, deferred = gemini.select_batch(posts, set(), self.sources)
        self.assertEqual((len(batch), deferred), (5, 3))
        self.assertIn(self.sources[self.path].strip(), prompt)
        with patch.object(gemini, "MAX_INPUT_BYTES", 1):
            with self.assertRaises(ValueError):
                gemini.select_batch(posts, set(), self.sources)

    def test_receipts_include_closed_reports_and_pagination(self):
        marker = f"<!-- ha-blog-gemini:{gemini.post_id(self.post)} -->"
        request = Mock(side_effect=[[{"body": None}] * 100, [{"body": marker, "state": "closed"}]])
        self.assertEqual(gemini.reviewed_ids(request), {gemini.post_id(self.post)})
        self.assertIn("page=2", request.call_args.args[0])

    def test_all_statuses_require_complete_valid_results(self):
        for status in ("impacted", "uncertain", "no-impact"):
            result = {**self.result, "assessment": status}
            self.assertEqual(
                gemini.validate_results({"results": [result]}, [self.post], self.sources), [result]
            )
        for data in ({}, {"results": []}, {"results": [self.result, self.result]}):
            with self.assertRaises(ValueError):
                gemini.validate_results(data, [self.post], self.sources)

    def test_invented_paths_lines_quotes_and_unsupported_claims_rejected(self):
        for changed in (
            {"path": "../../.env"},
            {"line": 999},
            {"line": True},
            {"quote": "invented"},
        ):
            evidence = {**self.result["evidence"][0], **changed}
            with self.assertRaises(ValueError):
                gemini.validate_results(
                    {"results": [{**self.result, "evidence": [evidence]}]},
                    [self.post],
                    self.sources,
                )
        for changed in (
            {"evidence": []},
            {"assessment": "safe"},
            {"id": "unknown"},
            {"reason": ""},
        ):
            with self.assertRaises(ValueError):
                gemini.validate_results(
                    {"results": [{**self.result, **changed}]}, [self.post], self.sources
                )

    def test_api_is_one_request_without_tools_or_key_in_url(self):
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": json.dumps({"results": [self.result]})}]},
                }
            ],
            "usageMetadata": {"promptTokenCount": 25},
        }

        @contextmanager
        def reply(*args, **kwargs):
            yield io.StringIO(json.dumps(response))

        with patch.object(gemini, "urlopen", side_effect=reply) as network:
            data, usage = gemini.generate("untrusted data", "test-key")
        self.assertEqual(network.call_count, 1)
        request = network.call_args.args[0]
        self.assertNotIn("test-key", request.full_url)
        payload = json.loads(request.data)
        self.assertNotIn("tools", payload)
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 8192)
        self.assertEqual(data["results"], [self.result])
        self.assertEqual(usage["promptTokenCount"], 25)

    def test_optional_improvement_publishes_even_without_compatibility_impact(self):
        result = {
            **self.result,
            "assessment": "no-impact",
            "evidence": [],
            "opportunity": {
                "assessment": "recommended",
                "reason": "Neue Geräteinformationen erleichtern die Bedienung.",
                "next_steps": "Neue Metadaten am vorhandenen DeviceInfo ergänzen; HA-Version prüfen.",
                "evidence": self.result["evidence"],
            },
        }
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(
                gemini, "github_request", side_effect=[[], {"html_url": "issue/1"}]
            ) as github,
            patch.object(gemini, "generate", return_value=({"results": [result]}, {})) as generate,
        ):
            gemini.run(self.args)
        generate.assert_called_once()
        body = github.call_args.args[3]["body"]
        self.assertIn("Kompatibilität: no-impact", body)
        self.assertIn("Ergänzungen und Verbesserungen: Empfohlen", body)
        self.assertIn(result["opportunity"]["reason"], body)
        self.assertIn("/blob/" + "a" * 40, body)
        report = json.loads((self.args.output_dir / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["results"][0]["opportunity"], result["opportunity"])

    def test_opportunities_are_independent_and_cannot_be_omitted(self):
        for compatibility in ("impacted", "no-impact", "uncertain"):
            for opportunity in ("recommended", "none", "uncertain"):
                result = {
                    **self.result,
                    "assessment": compatibility,
                    "opportunity": {
                        **self.result["opportunity"],
                        "assessment": opportunity,
                        "evidence": self.result["evidence"],
                    },
                }
                gemini.validate_results({"results": [result]}, [self.post], self.sources)
        old_result = {k: v for k, v in self.result.items() if k != "opportunity"}
        with self.assertRaises(ValueError):
            gemini.validate_results({"results": [old_result]}, [self.post], self.sources)

    def test_invalid_opportunities_do_not_publish(self):
        for change in (
            {"assessment": "invented"},
            {"assessment": "recommended", "evidence": []},
            {"reason": ""},
            {"next_steps": ""},
            {"evidence": [{"path": "invented.py", "line": 1, "quote": "fake"}]},
            {"evidence": [{"path": self.path, "line": 999, "quote": "fake"}]},
            {"evidence": [{"path": self.path, "line": 1, "quote": "fake"}]},
        ):
            result = {**self.result, "opportunity": {**self.result["opportunity"], **change}}
            with (
                patch.dict(os.environ, self.env, clear=True),
                patch.object(gemini, "github_request", return_value=[]) as github,
                patch.object(gemini, "generate", return_value=({"results": [result]}, {})),
            ):
                with self.assertRaises(ValueError):
                    gemini.run(self.args)
            self.assertEqual(github.call_count, 1)
            self.assertIsNone(github.call_args.args[3])

    def test_quota_error_is_not_retried(self):
        error = HTTPError("https://google.example", 429, "quota", {}, None)
        with patch.object(gemini, "urlopen", side_effect=error) as network:
            with self.assertRaises(HTTPError):
                gemini.generate("data", "test-key")
        self.assertEqual(network.call_count, 1)

    def test_quota_and_bad_output_never_publish_receipts(self):
        for response in (HTTPError("url", 429, "quota", {}, None), ({"results": []}, {})):
            with (
                patch.dict(os.environ, self.env, clear=True),
                patch.object(gemini, "github_request", return_value=[]) as github,
                patch.object(gemini, "generate", side_effect=[response]),
            ):
                with self.assertRaises((HTTPError, ValueError)):
                    gemini.run(self.args)
            self.assertEqual(github.call_count, 1)
            self.assertIsNone(github.call_args.args[3])

    def test_no_impact_gets_a_durable_report_and_skips_next_ai_call(self):
        no_impact = {**self.result, "assessment": "no-impact", "evidence": []}
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(
                gemini,
                "github_request",
                side_effect=[[], {"html_url": "https://github.com/owner/repo/issues/1"}],
            ) as github,
            patch.object(
                gemini, "generate", return_value=({"results": [no_impact]}, {})
            ) as generate,
        ):
            gemini.run(self.args)
        self.assertEqual(generate.call_count, 1)
        body = github.call_args.args[3]["body"]
        self.assertIn("no-impact", body)
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(gemini, "github_request", return_value=[{"body": body}]),
            patch.object(gemini, "generate") as generate,
        ):
            gemini.run(self.args)
        generate.assert_not_called()

    def test_prepare_only_needs_no_key_and_never_calls_services(self):
        self.args.publish = False
        self.args.prepare_only = True
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(gemini, "generate") as generate,
            patch.object(gemini, "github_request") as github,
        ):
            gemini.run(self.args)
        generate.assert_not_called()
        github.assert_not_called()
        self.assertIn("Keine Gemini-Anfrage", (self.args.output_dir / "summary.md").read_text())

    def test_dry_run_uses_ai_but_never_writes_github(self):
        self.args.publish = False
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(gemini, "github_request", return_value=[]) as github,
            patch.object(gemini, "generate", return_value=({"results": [self.result]}, {})),
        ):
            gemini.run(self.args)
        self.assertEqual(github.call_count, 1)
        self.assertIsNone(github.call_args.args[3])

    def test_report_escapes_model_text_and_pins_code_and_blog(self):
        result = {
            **self.result,
            "reason": "@owner <script> [click](bad)",
            "opportunity": {
                **self.result["opportunity"],
                "reason": "@owner <script> [click](bad)",
                "next_steps": "@owner <script> [click](bad)",
            },
        }
        body = gemini.render_report([self.post], [result], "owner/repo", "a" * 40, "b" * 40, 2)
        self.assertNotIn("@owner", body)
        self.assertNotIn("<script>", body)
        self.assertIn("/blob/" + "a" * 40, body)
        self.assertIn("/blob/" + "b" * 40, body)


if __name__ == "__main__":
    unittest.main()
