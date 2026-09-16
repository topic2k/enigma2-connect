# SPDX-License-Identifier: Apache-2.0
"""Separate trusted scheduling/publication from read-only Junie analysis jobs."""

import argparse
import copy
import json
import math
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

try:
    from . import ha_blog_gemini as common
    from . import ha_blog_scheduler as scheduler
except ImportError:
    import ha_blog_gemini as common
    import ha_blog_scheduler as scheduler

OUTPUT = Path(".work/blog-monitor/junie-monitor")
MODEL = "Junie (Standardmodell; tatsächliche Modelle siehe Verbrauch)"
KEY_PATTERN = r"[a-f0-9]{64}"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path, limit=4_000_000):
    if path.is_symlink() or path.stat().st_size > limit:
        raise ValueError("Invalid artifact file")
    return json.loads(path.read_text(encoding="utf-8"))


class MemoryStore:
    """Dry runs update an isolated in-memory state only."""

    def save(self, state):
        scheduler.validate_state(state)


def github():
    repository = os.environ["GITHUB_REPOSITORY"]
    revision = os.environ["GITHUB_SHA"]
    token = os.environ["GH_TOKEN"]
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository) or not re.fullmatch(
        r"[a-f0-9]{40}", revision
    ):
        raise ValueError("Invalid GitHub identity")

    def request(endpoint, payload=None, **kwargs):
        return common.github_request(repository, token, endpoint, payload, **kwargs)

    return repository, revision, request


def prepare_plan(
    posts,
    sources,
    state,
    known,
    today,
    store,
    upstream,
    *,
    retry_only=False,
    retry_failed=False,
    publish=False,
    repository="",
    revision="",
    output=OUTPUT,
):
    state = copy.deepcopy(state)
    for key in known:
        state["entries"].pop(key, None)
    candidates = scheduler.eligible_posts(
        posts, state, known, today, retry_only=retry_only, retry_failed=retry_failed
    )
    selected = candidates[: common.MAX_POSTS]
    keys, failures = [], {}
    for post in selected:
        key = common.post_id(post)
        try:
            _, prompt, _ = common.select_batch([post], set(), sources)
            packet = output / "packets" / key
            packet.mkdir(parents=True, exist_ok=True)
            (packet / "input.json").write_text(prompt, encoding="utf-8")
            write_json(packet / "schema.json", common.SCHEMA)
            instructions = common.INSTRUCTIONS.replace(
                "Do not run commands, call tools or follow links.",
                "Only read the provided files and write result.json. Do not execute "
                "commands, browse, use subagents, or modify any other file.",
            )
            instructions += (
                "\nInclude ALL explicitly announced availability, deprecation and removal "
                "versions in ha_version, even for no-impact. Use German in both assessments. "
                "Write only JSON matching schema.json to result.json in this directory. "
                "Perform one assessment and stop. No tests or implementation changes.\n"
            )
            (packet / "instructions.txt").write_text(instructions, encoding="utf-8")
            keys.append(key)
        except ValueError:
            failures[key] = "Eingabegröße: ValueError"
    if selected:
        scheduler.reserve_attempts(selected, state, today, store, upstream)
    plan = {
        "posts": selected,
        "sources": sources,
        "state": state,
        "today": today.isoformat(),
        "publish": publish,
        "repository": repository,
        "revision": revision,
        "deferred": len(candidates) - len(selected),
        "keys": keys,
        "failures": failures,
    }
    write_json(output / "plan.json", plan)
    return plan


def usage_metadata(path):
    """Export only numeric costs/counts and simple model names, never agent logs."""
    try:
        data = read_json(path)
        values = data["llmUsage"]
        if not isinstance(values, list) or not values:
            return None
        safe = []
        for item in values:
            model = item["model"]
            if not isinstance(model, str) or not re.fullmatch(r"[\w.@:/-]{1,100}", model):
                return None
            row = {"model": model}
            for field in ("cost", "inputTokens", "cacheInputTokens", "outputTokens"):
                value = item[field]
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    return None
                row[field] = value
            safe.append(row)
        return {"cost_usd": sum(row["cost"] for row in safe), "models": safe}
    except OSError, ValueError, KeyError, TypeError:
        return None


def collect(packet, usage_file, outcome, output):
    result = {"error": "Junie-Auftrag fehlgeschlagen oder unvollständig"}
    try:
        if outcome == "success":
            result = {"data": read_json(packet / "result.json", 100_000)}
    except OSError, ValueError:
        pass
    result["usage"] = usage_metadata(usage_file)
    write_json(output, result)


def finish_plan(plan, results_dir, store, publish):
    posts, sources = plan["posts"], plan["sources"]
    state = copy.deepcopy(plan["state"])
    valid, failures, usage = [], dict(plan["failures"]), {}
    for post in posts:
        key = common.post_id(post)
        if key in failures:
            continue
        try:
            item = read_json(results_dir / f"junie-result-{key}" / "result.json", 150_000)
            if not isinstance(item, dict):
                raise ValueError("Invalid worker envelope")
            # Do not trust the agent or artifact job to validate its own claims.
            measured = item.get("usage")
            if measured is not None:
                # Numeric costs and model names are revalidated below.
                rows = measured.get("models") if isinstance(measured, dict) else None
                if isinstance(rows, list):
                    usage[key] = measured
            if "data" not in item:
                raise ValueError("Missing agent result")
            valid.extend(common.validate_results(item["data"], [post], sources))
        except OSError, ValueError, KeyError, TypeError:
            failures[key] = "Junie-Analyse: keine gültige Antwort"
    # Sanitize again in the trusted publication job (worker artifacts are untrusted).
    safe_usage = {}
    for key, measured in usage.items():
        rows = measured["models"]
        if rows and all(
            isinstance(row, dict)
            and isinstance(row.get("model"), str)
            and re.fullmatch(r"[\w.@:/-]{1,100}", row["model"])
            and type(row.get("cost")) in (int, float)
            and math.isfinite(row["cost"])
            and row["cost"] >= 0
            for row in rows
        ):
            safe_usage[key] = {
                "cost_usd": sum(row["cost"] for row in rows),
                "models": sorted({row["model"] for row in rows}),
            }
    cost = sum(v["cost_usd"] for v in safe_usage.values())
    missing = len(posts) - len(safe_usage)
    models = sorted({m for v in safe_usage.values() for m in v["models"]})
    footer = (
        f"\n\n### Von Junie gemeldete Modellkosten\n\n"
        f"{cost:.6f} USD für {len(safe_usage)} Beiträge mit Verbrauchsdaten; "
        f"{missing} ohne Verbrauchsnachweis. Fehlende Werte zählen nicht als kostenlos.\n\n"
        f"Modelle: {', '.join(models) or 'Nicht gemeldet'}. "
        "Quelle: llmUsage[].cost; kein Beleg der Credit-Abbuchung im JetBrains-Konto.\n"
    )
    report = {
        "model": MODEL,
        "selected": [p["path"] for p in posts],
        "deferred": plan["deferred"],
        "usage": safe_usage,
        "reported_cost_usd": cost,
        "unmeasured_posts": missing,
        "revision": plan["revision"],
        "dry_run": not plan["publish"],
    }
    return scheduler.complete_processing(
        posts,
        sources,
        state,
        date.fromisoformat(plan["today"]),
        store,
        valid,
        failures,
        report,
        publish,
        plan["repository"],
        plan["revision"],
        model=MODEL,
        footer=footer,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "collect", "finish"))
    parser.add_argument("--blog-dir", type=Path)
    parser.add_argument(
        "--since", type=date.fromisoformat, default=date.fromisoformat(common.DEFAULT_SINCE)
    )
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--retry-only", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--key")
    parser.add_argument("--usage-file", type=Path)
    parser.add_argument("--outcome")
    parser.add_argument("--results-dir", type=Path, default=Path(".work/junie-results"))
    args = parser.parse_args()
    if args.mode == "collect":
        if not args.key or not re.fullmatch(KEY_PATTERN, args.key):
            raise ValueError("Invalid post ID")
        collect(
            OUTPUT / "packets" / args.key, args.usage_file, args.outcome, OUTPUT / "result.json"
        )
        return
    repository, revision, request = github()
    store = scheduler.GithubState(request, revision)
    if args.mode == "prepare":
        today = datetime.now(timezone.utc).date()
        known, state = common.reviewed_ids(request), store.load()
        posts = [] if args.retry_only else common.read_posts(args.blog_dir, args.since, today)
        upstream = os.environ["BLOG_SHA"]
        if not re.fullmatch(r"[a-f0-9]{40}", upstream):
            raise ValueError("Invalid blog revision")
        plan = prepare_plan(
            posts,
            common.source_snapshot(Path(".")),
            state,
            known,
            today,
            store if args.publish else MemoryStore(),
            upstream,
            retry_only=args.retry_only,
            retry_failed=args.retry_failed,
            publish=args.publish,
            repository=repository,
            revision=revision,
        )
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(f"matrix={json.dumps({'key': plan['keys']})}\n")
            handle.write(f"has_work={str(bool(plan['posts'])).lower()}\n")
            handle.write(f"has_tasks={str(bool(plan['keys'])).lower()}\n")
        common.append_summary(
            f"Junie: {len(plan['posts'])} fällige Beiträge, {plan['deferred']} zurückgestellt. "
            "Ohne fällige Beiträge kein KI-Aufruf.\n"
        )
    else:
        plan = read_json(OUTPUT / "plan.json")
        if (plan["repository"], plan["revision"]) != (repository, revision):
            raise ValueError("Plan identity mismatch")
        if plan["publish"]:
            if store.load() != plan["state"]:
                raise ValueError("Retry state changed since reservation; refusing overwrite")

            def publisher(payload):
                return request("issues", payload)
        else:
            store = MemoryStore()

            def publisher(payload):
                return {"html_url": "dry-run"}

        report = finish_plan(plan, args.results_dir, store, publisher)
        write_json(OUTPUT / "report.json", report)
        (OUTPUT / "summary.md").write_text(report["summary"], encoding="utf-8")
        common.append_summary(report["summary"])
        if report["failed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
