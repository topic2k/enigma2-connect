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
    payload = {
        "messages": [
            {"role": "system", "content": common.INSTRUCTIONS},
            {"role": "user", "content": prompt},
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
    posts, prompt, deferred = common.select_batch(
        [entry["post"] for entry in entries.values()], set(), sources
    )
    report = {
        "model": MODEL,
        "dry_run": True,
        "selected": [p["path"] for p in posts],
        "deferred": deferred,
        "input_bytes": len((common.INSTRUCTIONS + prompt).encode()),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
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
