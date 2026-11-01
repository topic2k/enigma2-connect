# SPDX-License-Identifier: Apache-2.0
"""Offline checks for resuming HA onboarding without resetting existing accounts."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError

from scripts import ha_dev


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.access = Path(directory) / "access.json"
        self.enterContext(patch.object(ha_dev, "ACCESS", self.access))
        self.client = Mock()
        self.enterContext(patch.object(ha_dev, "HAClient", return_value=self.client))
        self.login = self.enterContext(
            patch.object(ha_dev, "login", return_value={"access_token": "private-test-token"})
        )
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.client.request.return_value = {"type": "form", "step_id": "user", "flow_id": "test"}

    def test_partial_onboarding_reuses_existing_credentials(self):
        saved = {"url": ha_dev.URL, "username": "existing", "password": "private"}
        self.access.write_text(json.dumps(saved))
        self.client.wait.return_value = [
            {"step": "user", "done": True},
            {"step": "core_config", "done": True},
            {"step": "analytics", "done": False},
            {"step": "integration", "done": False},
        ]
        ha_dev.bootstrap()
        self.assertEqual(self.login.call_args.args[1]["username"], "existing")
        requests = self.client.request.call_args_list
        self.assertIn(call("/api/onboarding/analytics", {}), requests)
        self.assertFalse(any(c.args[0] == "/api/onboarding/users" for c in requests))
        self.assertFalse(any(c.args[0] == "/api/onboarding/core_config" for c in requests))
        self.assertEqual(json.loads(self.access.read_text())["password"], "private")
        self.assertNotIn("private", self.output.getvalue())

    def test_fresh_account_credentials_saved_before_user_creation(self):
        self.client.wait.return_value = []

        def request(path, *args, **kwargs):
            if path == "/api/onboarding/users":
                self.assertEqual(json.loads(self.access.read_text())["username"], "enigma2connect")
                return {"auth_code": "code"}
            return {"type": "form", "step_id": "user", "flow_id": "test"}

        self.client.request.side_effect = request
        ha_dev.bootstrap()
        self.assertEqual(self.login.call_args.args[2], "code")
        self.client.request.assert_any_call("/api/config/config_entries/flow/test", method="DELETE")

    def test_credentials_for_another_lab_are_rejected_before_login(self):
        self.access.write_text(json.dumps({"url": "http://127.0.0.1:18123"}))
        self.client.wait.return_value = [{"step": "user", "done": True}]
        with self.assertRaisesRegex(RuntimeError, "another lab"):
            ha_dev.bootstrap()
        self.login.assert_not_called()
        self.client.request.assert_not_called()

    def test_unexpected_form_is_reported_and_flow_cleaned_up(self):
        self.client.wait.return_value = [{"step": "user", "done": True}]
        self.client.request.return_value = {"type": "form", "step_id": "other", "flow_id": "test"}
        with self.assertRaisesRegex(RuntimeError, "setup form unavailable"):
            ha_dev.bootstrap()
        self.client.request.assert_any_call("/api/config/config_entries/flow/test", method="DELETE")


class LoginTests(unittest.TestCase):
    def test_invalid_refresh_token_falls_back_to_saved_login(self):
        client = Mock()
        client.request.side_effect = [
            HTTPError(ha_dev.URL, 400, "invalid grant", {}, None),
            {"flow_id": "login"},
            {"type": "create_entry", "result": "code"},
            {"access_token": "new-token"},
        ]
        result = ha_dev.login(
            client, {"refresh_token": "old", "username": "existing", "password": "private"}
        )
        self.assertEqual(result, {"access_token": "new-token"})
        self.assertEqual(client.request.call_args_list[2].args[1]["username"], "existing")

    def test_completed_onboarding_endpoint_can_be_missing(self):
        client = ha_dev.HAClient()
        with patch.object(
            client, "request", side_effect=HTTPError(ha_dev.URL, 404, "not found", {}, None)
        ):
            self.assertEqual(client.wait("/api/onboarding", missing=["complete"]), ["complete"])


if __name__ == "__main__":
    unittest.main()
