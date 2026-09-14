# SPDX-License-Identifier: Apache-2.0
"""Conservative, dependency-free triage of the HA developer blog against local code."""

import argparse
import ast
import hashlib
import html
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

UPSTREAM = "https://github.com/home-assistant/developers.home-assistant"
DEFAULT_SINCE = "2026-09-01"
# Broad topics deliberately favor review over silently dismissing cross-cutting changes.
TOPICS = {
    "config entries": (r"config[ _-]entr(?:y|ies)|config[ _-]flows?", "config_flow.py"),
    "device registry": (r"device[ _-]registry|DeviceInfo", "entity.py"),
    "entity registry": (r"entity[ _-]registry", "entity.py"),
    "coordinator": (r"coordinator", "coordinator.py"),
    "media": (r"media[ _-](?:player|source)|BrowseMedia", "media_player.py"),
    "selectors": (r"selectors?", "config_flow.py"),
    "translations": (r"translations?|localization", "strings.json"),
    "Python": (r"\bPython\b", "manifest.json"),
    "integration requirements": (
        r"custom integrations?|all integrations?|quality scale|hassfest|manifest\.json",
        "manifest.json",
    ),
}


def inline(value):
    """Keep external titles inert in Markdown and avoid mention notifications."""
    value = " ".join(value.split())
    value = html.escape(value).replace("@", "&#64;")
    return re.sub(r"([\\`*_[\]{}|])", r"\\\1", value)


def code_index(root):
    """Index HA imports and member names, including original names behind aliases."""
    index = defaultdict(set)
    component = root / "custom_components/enigma2_connect"
    files = sorted(component.rglob("*.py"))
    if not files:
        raise ValueError("No integration Python files found")
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("homeassistant"):
                names = [node.module]
                for alias in node.names:
                    names.extend((alias.name, f"{node.module}.{alias.name}"))
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names if a.name.startswith("homeassistant")]
            elif isinstance(node, ast.Attribute):
                names = [node.attr]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names = [node.name]
            for name in names:
                # Avoid noisy common Python words such as 'get', 'name', or 'state'.
                if len(name) >= 6 and ("_" in name or "." in name or name[0].isupper()):
                    index[name].add((relative, node.lineno))
    return index


def read_posts(blog, since, today):
    """Read complete upstream Markdown files; never execute upstream content."""
    paths = sorted(p for p in blog.rglob("*") if p.suffix in {".md", ".mdx"})
    if not paths:
        raise ValueError("No upstream blog files found")
    posts = []
    dated = 0
    for path in paths:
        relative = path.relative_to(blog).as_posix()
        match = re.match(r"(\d{4}-\d{2}-\d{2})[-/]", relative)
        if not match:
            continue
        dated += 1
        published = date.fromisoformat(match[1])
        if not since <= published <= today:
            continue
        raw = path.read_text(encoding="utf-8")
        front = re.match(r"\A---\s*\n(.*?)\n---\s*\n", raw, re.S)
        if not front:
            raise ValueError(f"Missing blog metadata: {relative}")
        if re.search(r"^draft:\s*true\s*$", front[1], re.M | re.I):
            continue
        title = re.search(r"^title:\s*(.+)$", front[1], re.M)
        if not title or title[1].strip() in {"|", ">"}:
            raise ValueError(f"Unsupported blog title: {relative}")
        posts.append(
            {
                "path": relative,
                "date": published.isoformat(),
                "title": title[1].strip().strip("\"'"),
                "text": raw[front.end() :],
            }
        )
    if not dated:
        raise ValueError("Upstream blog date format is no longer recognized")
    return posts


def assess(post, index, root):
    """Return evidence, not a claim that compatibility is proven or broken."""
    text = post["title"] + "\n" + post["text"]
    # A Markdown code-fence language is not a Python runtime announcement.
    text = re.sub(r"(?m)^\s*(?:```|~~~)[^\n]*$", "", text)
    hits = []
    for symbol, locations in sorted(index.items()):
        if re.search(r"(?<![\w])" + re.escape(symbol) + r"(?![\w])", text):
            for path, line in sorted(locations)[:3]:
                hits.append({"reason": symbol, "path": path, "line": line})
    topics = []
    for topic, (pattern, filename) in TOPICS.items():
        path = "custom_components/enigma2_connect/" + filename
        if re.search(r"\b(?:" + pattern + r")\b", text, re.I) and (root / path).exists():
            topics.append({"reason": topic, "path": path, "line": None})
    card = "www/enigma2-connect-remote-card.js"
    if re.search(r"frontend|custom cards?|Lovelace", text, re.I) and (root / card).exists():
        topics.append({"reason": "frontend", "path": card, "line": None})
    for platform in (
        "sensor",
        "binary_sensor",
        "button",
        "calendar",
        "camera",
        "notify",
        "remote",
        "select",
    ):
        path = f"custom_components/enigma2_connect/{platform}.py"
        pattern = r"\b" + platform.replace("_", "[ _-]") + r"s?\b"
        if (root / path).exists() and re.search(pattern, text, re.I):
            topics.append({"reason": platform, "path": path, "line": None})
    return {
        "status": "code-match" if hits else "topic-review" if topics else "no-match",
        "evidence": hits + topics,
    }


def marker(path):
    return "<!-- ha-developer-blog:" + hashlib.sha256(path.encode()).hexdigest() + " -->"


def github_request(repository, token, endpoint, payload=None, *, method=None):
    request = Request(
        f"https://api.github.com/repos/{repository}/{endpoint}",
        data=None if payload is None else json.dumps(payload).encode(),
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "enigma2-connect-ha-blog-monitor",
        },
    )
    # Do not retry POST: an ambiguous response must be reconciled on the next run.
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def existing_markers(request):
    found = set()
    page = 1
    while True:
        issues = request(f"issues?state=all&per_page=100&page={page}")
        if not isinstance(issues, list):
            raise ValueError("Unexpected GitHub issue response")
        for issue in issues:
            if "pull_request" not in issue:
                found.update(
                    re.findall(r"<!-- ha-developer-blog:[a-f0-9]{64} -->", issue.get("body") or "")
                )
        if len(issues) < 100:
            return found
        page += 1


def issue_body(post, result, repository, revision, upstream_revision):
    source = f"{UPSTREAM}/blob/{upstream_revision}/blog/{quote(post['path'])}"
    lines = [
        marker(post["path"]),
        f"[Home-Assistant-Entwicklerblog: {inline(post['title'])}]({source})",
        "",
        f"Datum: {post['date']} · Geprüfter Integrationsstand: `{revision}`",
        "",
        f"Automatische Vorprüfung: **{result['status']}**.",
        "Code-Treffer belegen eine Namensüberschneidung; Thementreffer einen möglichen Bezug.",
        "Dies ist keine bestätigte Inkompatibilität und keine KI-Analyse.",
        "",
        "### Fundstellen",
        "",
    ]
    for item in result["evidence"][:30]:
        suffix = f"#L{item['line']}" if item["line"] else ""
        kind = "blob" if item["line"] or Path(item["path"]).suffix else "tree"
        link = f"https://github.com/{repository}/{kind}/{revision}/{item['path']}{suffix}"
        lines.append(f"- {inline(item['reason'])}: [{item['path']}]({link})")
    if len(result["evidence"]) > 30:
        lines.append("- Weitere Fundstellen stehen im Workflow-Bericht.")
    lines.extend(
        [
            "",
            "### Manuell prüfen",
            "",
            "- [ ] Änderung, betroffene HA-Version und gegebenenfalls Migrationsfrist im Beitrag prüfen.",
            "- [ ] Fundstellen auf tatsächliche Auswirkungen untersuchen; Fehlalarm begründen.",
            "- [ ] Bei Bedarf Code/Tests anpassen und gegen die betreffende HA-Version prüfen.",
            "- [ ] Ergebnis dokumentieren und Issue schließen.",
        ]
    )
    return "\n".join(lines)


def process(posts, index, root, request, repository, revision, upstream_revision, limit):
    # Read every page before writing anything. Closed issues also suppress duplicates.
    known = existing_markers(request) if request else set()
    results = []
    created = 0
    for post in posts:
        result = {"path": post["path"], "title": post["title"], **assess(post, index, root)}
        key = marker(post["path"])
        if key in known:
            result["action"] = "existing-issue"
        elif result["status"] == "no-match":
            result["action"] = "report-only"
        elif request is None:
            result["action"] = "would-create"
        elif created >= limit:
            result["action"] = "deferred"
        else:
            issue = request(
                "issues",
                {
                    "title": ("[HA-Blog] Prüfen: " + post["title"].replace("@", ""))[:200],
                    "body": issue_body(post, result, repository, revision, upstream_revision),
                },
            )
            result["action"] = "created"
            result["issue_url"] = issue["html_url"]
            known.add(key)
            created += 1
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blog-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--since", type=date.fromisoformat, default=date.fromisoformat(DEFAULT_SINCE)
    )
    parser.add_argument("--output-dir", type=Path, default=Path(".work/blog-monitor/report"))
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--max-issues", type=int, default=5)
    args = parser.parse_args()
    repository = os.environ.get("GITHUB_REPOSITORY", "topic2k/enigma2-connect")
    revision = os.environ.get("GITHUB_SHA", "local")
    upstream_revision = os.environ.get("BLOG_SHA", "master")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        parser.error("Invalid repository")
    if args.max_issues < 1:
        parser.error("--max-issues must be positive")
    request = None
    if args.publish:
        token = os.environ.get("GH_TOKEN")
        if not token or not re.fullmatch(r"[a-f0-9]{40}", revision):
            parser.error("Publishing requires GH_TOKEN and a full GITHUB_SHA")
        if not re.fullmatch(r"[a-f0-9]{40}", upstream_revision):
            parser.error("Publishing requires a full BLOG_SHA")

        def request(endpoint, payload=None):
            return github_request(repository, token, endpoint, payload)

    posts = read_posts(args.blog_dir, args.since, datetime.now(timezone.utc).date())
    results = process(
        posts,
        code_index(args.root),
        args.root,
        request,
        repository,
        revision,
        upstream_revision,
        args.max_issues,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "since": str(args.since),
        "revision": revision,
        "upstream_revision": upstream_revision,
        "dry_run": not args.publish,
        "results": results,
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = [
        "## Home Assistant developer blog",
        "",
        f"Since {args.since}; {len(results)} posts; dry run: {not args.publish}.",
        "Heuristic triage only. No match does not prove compatibility.",
        "",
        "| Post | Assessment | Action |",
        "| --- | --- | --- |",
    ]
    for item in results:
        source = f"{UPSTREAM}/blob/{upstream_revision}/blog/{quote(item['path'])}"
        summary.append(
            f"| [{inline(item['title'])}]({source}) | {item['status']} | {item['action']} |"
        )
    markdown = "\n".join(summary) + "\n"
    (args.output_dir / "summary.md").write_text(markdown, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            stream.write(markdown)
    print(f"Assessed {len(results)} posts. Report: {args.output_dir}")


if __name__ == "__main__":
    main()
