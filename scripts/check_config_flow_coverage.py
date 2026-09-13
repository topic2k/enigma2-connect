# SPDX-License-Identifier: Apache-2.0
"""Enforce complete config-flow coverage using a coverage.py JSON report."""

import json
import sys
from pathlib import Path


def main() -> None:
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if not report["meta"]["branch_coverage"]:
        raise SystemExit("Config-flow coverage must be measured with --cov-branch")
    files = [
        data
        for name, data in report["files"].items()
        if name.replace("\\", "/").endswith("custom_components/enigma2_connect/config_flow.py")
    ]
    if len(files) != 1:
        raise SystemExit("Expected exactly one enigma2_connect/config_flow.py coverage result")
    data = files[0]
    if data["missing_lines"] or data["missing_branches"]:
        raise SystemExit(
            f"Incomplete config-flow coverage: lines={data['missing_lines']}, "
            f"branches={data['missing_branches']}"
        )
    print("Config flow: 100% statement and branch coverage")
    if "--silver" in sys.argv[2:]:
        root = Path(__file__).resolve().parents[1]
        expected = {path.name for path in (root / "custom_components/enigma2_connect").glob("*.py")}
        measured = {}
        for name, result in report["files"].items():
            normalized = name.replace("\\", "/")
            if "/enigma2_connect/" in normalized:
                measured[normalized.rsplit("/", 1)[1]] = result["summary"]
        if missing := expected - measured.keys():
            raise SystemExit(f"Missing integration coverage: {sorted(missing)}")
        below = {
            name: summary["percent_covered"]
            for name, summary in measured.items()
            if summary["percent_covered"] <= 95
        }
        if below:
            raise SystemExit(f"Silver requires above 95% combined coverage per module: {below}")
        print(f"Silver: all {len(expected)} modules above 95% combined statement/branch coverage")


if __name__ == "__main__":
    main()
