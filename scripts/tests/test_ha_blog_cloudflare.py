# SPDX-License-Identifier: Apache-2.0
"""Offline checks of the read-only Cloudflare adapter."""

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import ha_blog_cloudflare as cf


class CloudflareTests(unittest.TestCase):
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
