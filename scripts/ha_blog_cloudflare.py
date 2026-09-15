# SPDX-License-Identifier: Apache-2.0
"""Read-only Cloudflare trial of stored blog entries; never publishes or updates state."""

import argparse
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from . import ha_blog_gemini as common
    from .ha_blog_scheduler import validate_state
except ImportError:
    import ha_blog_gemini as common
    from ha_blog_scheduler import validate_state

MODEL = "@cf/openai/gpt-oss-120b"
OUTPUT_RULES = """Final output requirements, supplied by the application:
Write reason and next_steps in German for BOTH compatibility and opportunity.
Copy any explicitly announced Home Assistant version or removal deadline into ha_version,
even when the change does not affect this integration. Use Nicht angegeben only if absent.
Assess optional improvements independently; do not merely repeat the compatibility reason.
Evidence must actually support the explanation. Never cite license headers, comments,
blank lines or unrelated code as evidence. An empty evidence array is valid and preferred
for no-impact/none when no relevant positive code evidence exists. Never invent evidence.
Return only the JSON object matching the schema, with one result for every supplied post.
"""


class CloudflareError(ValueError):
    """Provider failure containing only numeric diagnostic codes."""


def provider_codes(data):
    if not isinstance(data, dict) or not isinstance(data.get("errors"), list):
        return "unknown"
    codes = [
        str(e["code"]) for e in data["errors"] if isinstance(e, dict) and type(e.get("code")) is int
    ]
    return ",".join(codes[:5]) or "unknown"


def generate(prompt, token, account, *, output_dir=None):
    """Make one bounded request to the fixed Cloudflare model, without fallback."""
    if not token or not re.fullmatch(r"[a-f0-9]{32}", account):
        raise ValueError("Missing token or invalid account ID")
    if len((common.INSTRUCTIONS + prompt + OUTPUT_RULES).encode()) > common.MAX_INPUT_BYTES:
        raise ValueError("Cloudflare input exceeds size limit")
    payload = {
        "messages": [
            {"role": "system", "content": common.INSTRUCTIONS},
            {"role": "user", "content": prompt + "\n\n" + OUTPUT_RULES},
        ],
        "max_tokens": common.MAX_OUTPUT_TOKENS,
        "response_format": {"type": "json_schema", "json_schema": common.SCHEMA},
    }
    request = Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=180) as response:
            data = json.load(response)
    except HTTPError as error:
        try:
            codes = provider_codes(json.loads(error.read(65536)))
        except ValueError, OSError:
            codes = "unknown"
        raise CloudflareError(f"HTTP {error.code}; Cloudflare codes: {codes}") from None
    if not isinstance(data, dict) or data.get("success") is not True:
        raise CloudflareError(f"Cloudflare codes: {provider_codes(data)}")
    if output_dir is not None:
        # Preserve provider output for offline parser diagnosis without another AI call.
        safe = json.dumps(data, ensure_ascii=False, indent=2).replace(token, "[REDACTED]")
        (output_dir / "provider-response.json").write_text(safe, encoding="utf-8")
    result = data["result"]
    return parse_result(result)


def parse_result(result):
    """Accept the observed chat-completion envelope and documented JSON-mode form."""
    if "choices" in result:
        choices = result["choices"]
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("Missing or ambiguous completion")
        choice = choices[0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("Incomplete or blocked completion")
        message = choice["message"]
        if message.get("refusal") or message.get("tool_calls") or message.get("function_call"):
            raise ValueError("Refused or unexpected tool response")
        answer = message["content"]
    else:
        answer = result["response"]
    if isinstance(answer, str):
        answer = json.loads(answer)
    if not isinstance(answer, dict):
        raise ValueError("Invalid structured response")
    return answer, result.get("usage", {})


def run(args):
    if args.smoke:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        generate(
            'Return {"results": []}. This is a connection test without blog posts.',
            os.environ.get("CLOUDFLARE_API_TOKEN", ""),
            os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
            output_dir=args.output_dir,
        )
        return
    state = validate_state(json.loads(args.state.read_text(encoding="utf-8")))
    entries = state["entries"]
    sources = common.source_snapshot(args.root)
    pending = [entry["post"] for entry in entries.values()]
    if args.post:
        pending = [post for post in pending if post["path"] == args.post]
        if not pending:
            raise ValueError("Requested post is not in stored state")
    if args.individual:
        return run_individual(args, pending, sources, entries)
    posts, prompt, deferred = common.select_batch(pending, set(), sources)
    report = {
        "model": MODEL,
        "dry_run": True,
        "selected": [p["path"] for p in posts],
        "deferred": deferred,
        "input_bytes": len((common.INSTRUCTIONS + prompt + OUTPUT_RULES).encode()),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "request-info.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    if not posts:
        raise ValueError("No stored posts to test")
    data, usage = generate(
        prompt,
        os.environ.get("CLOUDFLARE_API_TOKEN", ""),
        os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
        output_dir=args.output_dir,
    )
    results = common.validate_results(data, posts, sources)
    report.update(results=results, usage=usage)
    summary = common.render_report(
        posts,
        results,
        os.environ["GITHUB_REPOSITORY"],
        os.environ["GITHUB_SHA"],
        {key: entry["upstream"] for key, entry in entries.items()},
        deferred,
        model=MODEL,
    )
    summary = "Cloudflare-Probelauf: keine Issues oder Statusänderungen.\n\n" + summary
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "summary.md").write_text(summary, encoding="utf-8")
    common.append_summary(summary)


def run_individual(args, posts, sources, entries):
    """Send exactly one post per request, preserving completed reports if a later call fails."""
    if not posts:
        raise ValueError("No stored posts to test")
    selected = posts[: common.MAX_POSTS]
    report = {
        "model": MODEL,
        "dry_run": True,
        "mode": "individual",
        "selected": [p["path"] for p in selected],
        "deferred": len(posts) - len(selected),
        "results": [],
        "requests": [],
        "usage": {},
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for post in selected:
        key = common.post_id(post)
        post_dir = args.output_dir / key
        post_dir.mkdir(exist_ok=True)
        _, prompt, _ = common.select_batch([post], set(), sources)
        request_info = {
            "post": post["path"],
            "id": key,
            "input_bytes": len((common.INSTRUCTIONS + prompt + OUTPUT_RULES).encode()),
        }
        report["requests"].append(request_info)
        (post_dir / "request-info.json").write_text(
            json.dumps(request_info, indent=2), encoding="utf-8"
        )
        try:
            data, usage = generate(
                prompt,
                os.environ.get("CLOUDFLARE_API_TOKEN", ""),
                os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
                output_dir=post_dir,
            )
            request_info["usage"] = usage
            for metric in ("prompt_tokens", "completion_tokens", "total_tokens", "neurons"):
                value = usage.get(metric)
                if type(value) in (int, float):
                    report["usage"][metric] = report["usage"].get(metric, 0) + value
            results = common.validate_results(data, [post], sources)
            report["results"].extend(results)
            request_info["status"] = "validated"
        except (ValueError, OSError, URLError, KeyError, TypeError) as error:
            request_info["status"] = "failed"
            request_info["error"] = (
                str(error) if isinstance(error, CloudflareError) else type(error).__name__
            )
            raise
        finally:
            (args.output_dir / "report.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            completed = [
                p for p in selected if common.post_id(p) in {r["id"] for r in report["results"]}
            ]
            summary = "Cloudflare-Einzelprüfung: keine Issues oder Statusänderungen.\n\n"
            if completed:
                summary += common.render_report(
                    completed,
                    report["results"],
                    os.environ["GITHUB_REPOSITORY"],
                    os.environ["GITHUB_SHA"],
                    {k: e["upstream"] for k, e in entries.items()},
                    len(posts) - len(completed),
                    model=MODEL,
                )
            summary += "\n\nVerbrauch dieser Einzelprüfungen: " + json.dumps(report["usage"]) + "\n"
            (args.output_dir / "summary.md").write_text(summary, encoding="utf-8")
    common.append_summary(summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--individual", action="store_true")
    parser.add_argument("--post", help="Test only this exact stored blog filename")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path(".work/blog-monitor/cloudflare-report")
    )
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError, URLError, KeyError, TypeError) as error:
        detail = str(error) if isinstance(error, CloudflareError) else type(error).__name__
        summary = f"Cloudflare-Probelauf fehlgeschlagen: {detail}. Status unverändert.\n"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "error.md").write_text(summary, encoding="utf-8")
        common.append_summary(summary)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
