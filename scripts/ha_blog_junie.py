# SPDX-License-Identifier: Apache-2.0
"""Prepare and validate one manual Junie trial; never call AI or publish state."""

import argparse
import json
import os
from pathlib import Path

try:
    from . import ha_blog_gemini as common
    from .ha_blog_scheduler import validate_state
except ImportError:
    import ha_blog_gemini as common
    from ha_blog_scheduler import validate_state

POST = "2026-09-02-modbus-get-hub-deprecation.md"
OUTPUT = Path(".work/blog-monitor/junie-report")


def prepare(state_path, root, output):
    state = validate_state(json.loads(state_path.read_text(encoding="utf-8")))
    matches = [e for e in state["entries"].values() if e["post"]["path"] == POST]
    if len(matches) != 1:
        raise ValueError("Expected exactly one stored Modbus post")
    entry = matches[0]
    sources = common.source_snapshot(root)
    _, prompt, _ = common.select_batch([entry["post"]], set(), sources)
    output.mkdir(parents=True, exist_ok=True)
    (output / "input.json").write_text(prompt, encoding="utf-8")
    (output / "schema.json").write_text(json.dumps(common.SCHEMA), encoding="utf-8")
    instructions = common.INSTRUCTIONS.replace(
        "Do not run commands, call tools or follow links.",
        "Use tools only to read these supplied files and write result.json. "
        "Do not execute commands, browse, use subagents, or change repository code.",
    )
    instructions += (
        "\nInclude ALL explicitly stated availability, deprecation and removal versions "
        "in ha_version, even for no-impact. Use German in both assessments. "
        "Write only JSON matching schema.json to result.json in this directory. "
        "Perform a single assessment, then stop. Do not run tests or implement changes.\n"
    )
    (output / "instructions.txt").write_text(instructions, encoding="utf-8")
    context = {"post": entry["post"], "upstream": entry["upstream"], "sources": sources}
    (output / "context.json").write_text(json.dumps(context), encoding="utf-8")


def finish(output):
    context = json.loads((output / "context.json").read_text(encoding="utf-8"))
    data = json.loads((output / "result.json").read_text(encoding="utf-8"))
    post = context["post"]
    results = common.validate_results(data, [post], context["sources"])
    summary = common.render_report(
        [post],
        results,
        os.environ["GITHUB_REPOSITORY"],
        os.environ["GITHUB_SHA"],
        {common.post_id(post): context["upstream"]},
        0,
        model="Junie (default model)",
    )
    summary = "Junie-Einzeltest: nur Analyse; inhaltliche Prüfung noch erforderlich.\n\n" + summary
    (output / "summary.md").write_text(summary, encoding="utf-8")
    common.append_summary(summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "finish"))
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        if args.state is None:
            parser.error("prepare requires --state")
        prepare(args.state, Path("."), OUTPUT)
    else:
        finish(OUTPUT)


if __name__ == "__main__":
    main()
