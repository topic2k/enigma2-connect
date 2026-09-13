# SPDX-License-Identifier: Apache-2.0
"""Run an explicit, read-only receiver acceptance in an isolated Home Assistant."""

import argparse
import contextlib
import getpass
import hashlib
import io
import json
import os
import platform
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

READS = {
    "/api/about": set(),
    "/api/statusinfo": set(),
    "/api/getcurrent": set(),
    "/api/signal": set(),
    "/api/bouquets": {"stype"},
    "/api/getservices": {"sRef"},
    "/api/timerlist": set(),
    "/api/movielist": {"recursive"},
}


def check_request(path, params):
    """Reject commands, image generation and unexpected parameters before transport."""
    if path not in READS or not set(params or {}) <= READS[path]:
        raise RuntimeError("Request blocked by read-only acceptance guard")


async def check_receiver(hass, config, report):
    """Exercise real HA setup against the selected transport; export only summaries."""
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import entity_registry as er
    from homeassistant.setup import async_setup_component

    from custom_components.enigma2_connect.const import DOMAIN
    from custom_components.enigma2_connect.diagnostics import async_get_config_entry_diagnostics

    report["stage"] = "setup"
    assert await async_setup_component(hass, DOMAIN, {})
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=config
    )
    assert flow["type"] == "create_entry"
    entry = flow["result"]
    try:
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        coordinator = entry.runtime_data
        report["receiver"] = {
            key: coordinator.info.get(key)
            for key in ("brand", "model", "webifver", "imagever", "distro", "enigmaver")
        }
        report["stage"] = "entities"
        entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        report["platforms"] = sorted({entity.domain for entity in entities})
        assert len(report["platforms"]) == 9
        signal = [e for e in entities if e.translation_key in {"signal", "snr", "ber"}]
        assert len(signal) == 3
        assert all(e.disabled_by is er.RegistryEntryDisabler.INTEGRATION for e in signal)
        enabled = [e for e in entities if e.disabled_by is None]
        assert all(hass.states.get(e.entity_id) is not None for e in enabled)
        report["enabled_entities"] = len(enabled)
        report["disabled_signal_entities"] = len(signal)
        report["unavailable_entities"] = sum(
            hass.states.get(e.entity_id).state == "unavailable" for e in enabled
        )
        report["stage"] = "refresh"
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        report["diagnostics"] = await async_get_config_entry_diagnostics(hass, entry)
        report["stage"] = "duplicate_setup"
        duplicate = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=config
        )
        assert duplicate["type"] == "abort" and duplicate["reason"] == "already_configured"
    finally:
        unloaded = await hass.config_entries.async_unload(entry.entry_id)
        report["unloaded"] = unloaded and entry.state is ConfigEntryState.NOT_LOADED
    assert report["unloaded"]
    report["stage"] = "complete"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int)
    parser.add_argument("--https", action="store_true")
    parser.add_argument("--username", default="")
    parser.add_argument("--password-env", help="Read the password from this environment variable")
    parser.add_argument("--output", type=Path, default=Path(".work/receiver-acceptance.json"))
    args = parser.parse_args()
    if args.password_env and args.password_env not in os.environ:
        parser.error("Password environment variable is not set")
    password = (
        os.environ[args.password_env]
        if args.password_env
        else getpass.getpass("OpenWebif password: ")
        if args.username
        else ""
    )
    config = {
        "host": args.host,
        "port": args.port or (443 if args.https else 80),
        "username": args.username,
        "password": password,
        "use_https": args.https,
        "verify_ssl": True,
    }
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    import pytest
    from homeassistant.const import __version__ as ha_version

    component = root / "custom_components/enigma2_connect"
    source_hash = hashlib.sha256()
    for path in sorted(component.rglob("*")):
        if path.is_file() and (
            path.suffix in {".py", ".json", ".yaml", ".js", ".png"} or path.name == "py.typed"
        ):
            source_hash.update(path.relative_to(component).as_posix().encode() + b"\0")
            source_hash.update(path.read_bytes() + b"\0")
    report = {
        "at": datetime.now(UTC).isoformat(),
        "mode": "receiver_http_isolated_ha_read_only",
        "home_assistant": ha_version,
        "python": platform.python_version(),
        "integration": json.loads(
            (root / "custom_components/enigma2_connect/manifest.json").read_text()
        )["version"],
        "source_sha256": source_hash.hexdigest(),
        "stage": "initialization",
    }

    class Session:
        @pytest.fixture
        def receiver_acceptance_session(self):
            return config, report

    # HA storage is mocked by the acceptance fixture; pytest output stays in memory.
    # Never emit raw pytest logs: exceptions can contain URLs or authentication data.
    with tempfile.TemporaryDirectory(prefix="enigma2-acceptance-") as temporary:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = pytest.main(
                [
                    str(root / "scripts/acceptance/test_receiver.py"),
                    "--capture=sys",
                    "--basetemp=" + temporary + "/pytest",
                    "-p",
                    "no:cacheprovider",
                ],
                plugins=[Session()],
            )
    config.clear()
    report["pytest_exit_code"] = int(code)
    report["passed"] = code == 0 and report["stage"] == "complete"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return int(code) if code else (0 if report["passed"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
