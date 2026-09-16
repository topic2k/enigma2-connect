# SPDX-License-Identifier: Apache-2.0
"""Offline checks of the read-only Cloudflare adapter."""

import argparse
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import ha_blog_cloudflare as cf


class CloudflareTests(unittest.TestCase):
    def test_individual_requests_isolate_posts_and_preserve_success_before_error(self):
        posts = [
            {
                "path": f"2026-09-01-{i}.md",
                "title": f"Post {i}",
                "date": "2026-09-01",
                "text": f"Distinct topic {i}",
            }
            for i in range(2)
        ]
        entry_map = {cf.common.post_id(p): {"post": p, "upstream": "a" * 40} for p in posts}
        result = {
            "id": cf.common.post_id(posts[0]),
            "assessment": "no-impact",
            "ha_version": "Nicht angegeben",
            "reason": "Keine Nutzung",
            "next_steps": "Keine",
            "evidence": [],
            "opportunity": {
                "assessment": "none",
                "reason": "Kein Nutzen",
                "next_steps": "Keine",
                "evidence": [],
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            args = argparse.Namespace(output_dir=Path(temp))
            with (
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_SHA": "b" * 40}),
                patch.object(
                    cf,
                    "generate",
                    side_effect=[
                        ({"results": [result]}, {"neurons": 100}),
                        cf.CloudflareError("HTTP 429"),
                    ],
                ) as generate,
            ):
                with self.assertRaises(cf.CloudflareError):
                    cf.run_individual(args, posts, {"entity.py": "class Entity: pass"}, entry_map)
                for index, call in enumerate(generate.call_args_list):
                    self.assertEqual(
                        json.loads(call.args[0])["posts"],
                        [{"id": cf.common.post_id(posts[index]), **posts[index]}],
                    )
                report = json.loads((Path(temp) / "report.json").read_text())
                self.assertEqual(report["results"], [result])
                self.assertEqual(report["usage"]["neurons"], 100)
                self.assertEqual([r["status"] for r in report["requests"]], ["validated", "failed"])
                self.assertIn("Post 0", (Path(temp) / "summary.md").read_text())

    def test_individual_wrong_post_id_is_rejected(self):
        post = {"path": "p.md", "title": "One", "text": "One", "date": "2026-09-01"}
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(
                cf,
                "generate",
                return_value=({"results": [{"id": "another-post"}]}, {"neurons": 50}),
            ),
        ):
            with self.assertRaises(ValueError):
                cf.run_individual(argparse.Namespace(output_dir=Path(temp)), [post], {}, {})
            report = json.loads((Path(temp) / "report.json").read_text())
            self.assertEqual(report["results"], [])
            self.assertEqual(report["usage"]["neurons"], 50)

    def test_observed_chat_completion_uses_final_content_only(self):
        result = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"results": []}',
                        "reasoning": "not JSON",
                        "refusal": None,
                    },
                }
            ],
            "usage": {"neurons": 19.3},
        }
        self.assertEqual(cf.parse_result(result), ({"results": []}, {"neurons": 19.3}))
        result["choices"][0]["finish_reason"] = "length"
        with self.assertRaises(ValueError):
            cf.parse_result(result)

    def test_structured_and_string_response(self):
        answer = {"results": []}
        for response in (answer, json.dumps(answer)):
            with self.subTest(response=response), patch.object(cf, "urlopen") as call:
                call.return_value.__enter__.return_value = io.StringIO(
                    json.dumps(
                        {
                            "success": True,
                            "result": {"response": response, "usage": {"total_tokens": 9}},
                        }
                    )
                )
                self.assertEqual(
                    cf.generate("data", "test-token", "a" * 32), (answer, {"total_tokens": 9})
                )
                call.assert_called_once()
                request = call.call_args.args[0]
                self.assertIn("api.cloudflare.com/client/v4/accounts/", request.full_url)
                payload = json.loads(request.data)
                self.assertNotIn("tools", payload)
                self.assertEqual(payload["max_tokens"], 8192)

    def test_provider_errors_exclude_sensitive_body_and_do_not_retry(self):
        body = io.BytesIO(b'{"errors":[{"code":3040,"message":"secret-value"}]}')
        error = HTTPError("https://example.org", 503, "private", {}, body)
        with patch.object(cf, "urlopen", side_effect=error) as call:
            with self.assertRaisesRegex(
                cf.CloudflareError, "HTTP 503; Cloudflare codes: 3040"
            ) as raised:
                cf.generate("data", "test-token", "a" * 32)
            self.assertNotIn("secret-value", str(raised.exception))
            call.assert_called_once()

    def test_unsuccessful_envelope_rejected(self):
        with patch.object(cf, "urlopen") as call:
            call.return_value.__enter__.return_value = io.StringIO('{"success":false}')
            with self.assertRaises(cf.CloudflareError):
                cf.generate("data", "test-token", "a" * 32)

    def test_missing_credentials_make_no_request(self):
        with patch.object(cf, "urlopen") as call:
            for token, account in (("", "a" * 32), ("token", "invalid/path")):
                with self.assertRaises(ValueError):
                    cf.generate("data", token, account)
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
