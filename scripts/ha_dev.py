# SPDX-License-Identifier: Apache-2.0
"""Install the current integration and manage an isolated Home Assistant Container."""

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ("docker", "compose", "-f", str(ROOT / "dev/ha/compose.yaml"))
URL = "http://127.0.0.1:18124"
ACCESS = ROOT / ".work/ha-dev-access.json"
# Public credentials, exclusively for the loopback-only development instance.
TEST_LOGIN = {"username": "enigma2connect", "password": "notsecret"}

INSTALL = """
import shutil
import sys
from pathlib import Path

root = Path('/config')
stage = root / sys.argv[1]
target = root / 'custom_components/enigma2_connect'
if target.exists():
    shutil.rmtree(target)
shutil.copytree(stage / 'enigma2_connect', target)
shutil.copyfile(stage / 'configuration.yaml', root / 'configuration.yaml')
shutil.rmtree(stage)
"""


def run(*args, capture=False):
    """Run without a shell, including on Windows and paths containing spaces."""
    return subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    ).stdout


class HAClient:
    """Local HA API client; never send lab credentials through system proxies."""

    def __init__(self):
        self.token = None
        self.opener = build_opener(ProxyHandler({}))

    def request(self, path, data=None, *, method=None, form=False):
        headers = {}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        body = None
        if data is not None:
            headers["Content-Type"] = (
                "application/x-www-form-urlencoded" if form else "application/json"
            )
            body = (urlencode(data) if form else json.dumps(data)).encode("utf-8")
        with self.opener.open(
            Request(URL + path, body, headers, method=method), timeout=10
        ) as reply:
            return json.load(reply)

    def wait(self, path, *, ready=lambda result: True, missing=None, timeout=180):
        deadline = time.monotonic() + timeout
        while True:
            try:
                result = self.request(path)
                if ready(result):
                    return result
            except HTTPError as error:
                status = error.code
                error.close()
                if status == 404 and missing is not None:
                    return missing
                if status not in (404, 502, 503):
                    raise
            except URLError, TimeoutError, ConnectionError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f"HA not ready at {path}; run python scripts/ha_dev.py logs")
            time.sleep(2)


def save_access(access):
    """Save immediately so interrupted onboarding can resume without resetting HA."""
    ACCESS.parent.mkdir(parents=True, exist_ok=True)
    temporary = ACCESS.with_suffix(".tmp")
    temporary.write_text(json.dumps(access, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(ACCESS)


def login(client, access, code=None):
    if code is None and access.get("refresh_token"):
        try:
            return client.request(
                "/auth/token",
                {
                    "grant_type": "refresh_token",
                    "client_id": URL + "/",
                    "refresh_token": access["refresh_token"],
                },
                form=True,
            )
        except HTTPError as error:
            status = error.code
            error.close()
            if status != 400:
                raise
    if code is None:
        flow = client.request(
            "/auth/login_flow",
            {
                "client_id": URL + "/",
                "handler": ["homeassistant", None],
                "redirect_uri": URL + "/?auth_callback=1",
            },
        )
        result = client.request(
            "/auth/login_flow/" + flow["flow_id"],
            {
                "client_id": URL + "/",
                "username": access["username"],
                "password": access["password"],
            },
        )
        if result.get("type") != "create_entry":
            raise RuntimeError(f"Lab login failed; check {ACCESS}. Existing users are never reset.")
        code = result["result"]
    return client.request(
        "/auth/token",
        {"grant_type": "authorization_code", "client_id": URL + "/", "code": code},
        form=True,
    )


def bootstrap():
    """Finish onboarding, then verify the setup form without contacting a receiver."""
    client = HAClient()
    # Completed installations no longer register the onboarding endpoint.
    complete = [
        {"step": step, "done": True} for step in ("user", "core_config", "analytics", "integration")
    ]
    steps = client.wait("/api/onboarding", missing=complete)
    done = {step["step"] for step in steps if step["done"]}
    access = dict(TEST_LOGIN, url=URL)
    code = None
    if "user" not in done:
        save_access(access)
        result = client.request(
            "/api/onboarding/users",
            {
                **TEST_LOGIN,
                "name": "Enigma2 Connect Testlabor",
                "language": "de",
                "client_id": URL + "/",
            },
        )
        code = result["auth_code"]
    elif ACCESS.exists():
        access = json.loads(ACCESS.read_text(encoding="utf-8"))
        if access.get("url") != URL:
            raise RuntimeError("Saved credentials belong to another lab URL")
    tokens = login(client, access, code)
    access.update(tokens)
    client.token = access["access_token"]
    save_access(access)
    for step in ("core_config", "analytics", "integration"):
        if step not in done:
            data = {"client_id": URL + "/", "redirect_uri": URL + "/?auth_callback=1"}
            client.request("/api/onboarding/" + step, data if step == "integration" else {})
    client.wait("/api/config", ready=lambda result: result["state"] == "RUNNING")
    flow = client.request("/api/config/config_entries/flow", {"handler": "enigma2_connect"})
    try:
        if flow.get("type") != "form" or flow.get("step_id") != "user":
            raise RuntimeError("Enigma2 Connect setup form unavailable; inspect the lab logs")
    finally:
        if "flow_id" in flow:
            client.request("/api/config/config_entries/flow/" + flow["flow_id"], method="DELETE")
    print(f"HA ready; Enigma2 Connect setup form verified. Login: {access['username']}")
    print(f"Local credentials: {ACCESS}")


def start():
    """Replace only integration files and the lab YAML while HA is stopped."""
    work = ROOT / ".work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ha-dev-stage-", dir=work) as directory:
        stage = Path(directory)
        shutil.copyfile(ROOT / "dev/ha/configuration.yaml", stage / "configuration.yaml")
        shutil.copytree(
            ROOT / "custom_components/enigma2_connect",
            stage / "enigma2_connect",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        run(*COMPOSE, "stop")
        run(*COMPOSE, "create")
        container = run(*COMPOSE, "ps", "--all", "--quiet", "homeassistant", capture=True).strip()
        if not container or "\n" in container:
            raise RuntimeError("Expected exactly one Enigma2 Connect lab container")
        # Docker cp also works with Windows drive mappings that cannot be bind-mounted.
        run("docker", "cp", str(stage), container + ":/config/" + stage.name)
        run(
            *COMPOSE,
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "python",
            "homeassistant",
            "-c",
            INSTALL,
            stage.name,
        )
    run(*COMPOSE, "start")
    bootstrap()
    manifest = json.loads((ROOT / "custom_components/enigma2_connect/manifest.json").read_text())
    print(f"Enigma2 Connect {manifest['version']} test instance: {URL}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "logs", "check"))
    command = parser.parse_args().command
    if command == "start":
        start()
    elif command == "stop":
        run(*COMPOSE, "stop")
    elif command == "logs":
        run(*COMPOSE, "logs", "--tail", "100")
    else:
        run(
            *COMPOSE,
            "exec",
            "-T",
            "homeassistant",
            "python",
            "-m",
            "homeassistant",
            "--script",
            "check_config",
            "--config",
            "/config",
        )


if __name__ == "__main__":
    main()
