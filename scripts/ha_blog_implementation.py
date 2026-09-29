# SPDX-License-Identifier: Apache-2.0
"""Collect bounded source edits and publish draft PRs from a fresh trusted job."""

import argparse
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError

try:
    from .ha_blog_monitor import github_request
except ImportError:
    from ha_blog_monitor import github_request

MAX_BYTES = 2_000_000
MAX_FILES = 80
ALLOWED_ROOT_FILES = {
    "README.md",
    "CHANGELOG.md",
    "CHANGELOG.en.md",
    "pyproject.toml",
    "uv.lock",
}


def allowed_path(value):
    if not isinstance(value, str) or "\\" in value or any(ord(c) < 32 for c in value):
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or ".." in path.parts:
        return False
    if any(part.startswith(".") for part in path.parts):
        return False
    if path.name in {"AGENTS.md", "AGENTS.en.md", "quality_scale.yaml"}:
        return False
    return value in ALLOWED_ROOT_FILES or (
        path.suffix in {".py", ".js", ".cjs", ".json", ".yaml", ".md"}
        and (
            value.startswith("custom_components/enigma2_connect/")
            or path.parts[0] in {"tests", "docs", "www"}
        )
    )


def validate_changes(data, base):
    if (
        not isinstance(data, dict)
        or not re.fullmatch(r"[a-f0-9]{40}", base)
        or data.get("base") != base
    ):
        raise ValueError("Implementation base mismatch")
    changes = data.get("changes")
    if not isinstance(changes, list) or len(changes) > MAX_FILES:
        raise ValueError("Invalid changed files")
    seen = set()
    for item in changes:
        if not isinstance(item, dict) or set(item) != {"path", "content"}:
            raise ValueError("Invalid file record")
        path, content = item["path"], item["content"]
        if not allowed_path(path) or path in seen:
            raise ValueError("Disallowed or duplicate path")
        if content is not None and (not isinstance(content, str) or "\0" in content):
            raise ValueError("Only UTF-8 text edits are supported")
        seen.add(path)
    if len(json.dumps(data, ensure_ascii=False).encode()) > MAX_BYTES:
        raise ValueError("Implementation exceeds size limit")
    return changes


def collect(root, base, output):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args]).decode()

    paths = set(git("diff", "--name-only", "-z", base).split("\0"))
    paths.update(git("ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    paths.discard("")
    changes = []
    for name in sorted(paths):
        # Work files are ignored by git; reject any other disallowed changes.
        if not allowed_path(name):
            raise ValueError("Implementation changed a protected path")
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Implementation path escapes checkout")
        if path.exists() and path.stat().st_size > MAX_BYTES:
            raise ValueError("File exceeds size limit")
        changes.append(
            {"path": name, "content": path.read_text(encoding="utf-8") if path.exists() else None}
        )
    data = {"base": base, "changes": changes}
    validate_changes(data, base)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def branch_name(title, issue_number):
    topic = title.removeprefix("[HA-Blog] ").replace("ß", "ss")
    topic = unicodedata.normalize("NFKD", topic).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", topic).strip("-")[:60].rstrip("-")
    return f"ha-blog/{slug or f'issue-{issue_number}'}"


def available_branch(request, title, issue_number):
    name = branch_name(title, issue_number)
    for candidate in (name, f"{name}-{issue_number}"):
        try:
            request(f"git/ref/heads/{candidate}")
        except HTTPError as error:
            if error.code == 404:
                return candidate
            raise
    raise ValueError("Both topic branches already exist; refusing to overwrite")


def publish(request, repository, base, issue_number, key, data, run_url):
    changes = validate_changes(data, base)
    if not changes:
        return "Keine umsetzbare Änderung erzeugt; Issue bleibt zur manuellen Prüfung offen."
    if type(issue_number) is not int or issue_number < 1 or not re.fullmatch(r"[a-f0-9]{64}", key):
        raise ValueError("Invalid issue identity")
    issue = request(f"issues/{issue_number}")
    marker = f"<!-- ha-blog-gemini:{key} -->"
    if (
        issue.get("state") != "open"
        or "pull_request" in issue
        or not issue.get("title", "").startswith("[HA-Blog] ")
        or marker not in (issue.get("body") or "")
    ):
        raise ValueError("Issue no longer matches the implementation task")
    pr_marker = f"<!-- ha-blog-implementation:{issue_number}:{key} -->"
    page = 1
    while True:
        existing = request(f"pulls?state=all&base=develop&per_page=100&page={page}")
        for pr in existing:
            if pr_marker in (pr.get("body") or ""):
                return f"Vorhandener PR bleibt unverändert: {pr['html_url']}"
        if len(existing) < 100:
            break
        page += 1
    branch = available_branch(request, issue["title"], issue_number)
    current = request("git/ref/heads/develop")["object"]["sha"]
    if current != base:
        raise ValueError("develop changed during implementation; refusing stale proposal")
    commit = request(f"git/commits/{base}")
    tree_sha = commit["tree"]["sha"]
    tree = request(f"git/trees/{tree_sha}?recursive=1")
    if tree.get("truncated"):
        raise ValueError("Incomplete base tree")
    original = {item["path"]: item for item in tree["tree"]}
    edits = []
    for item in changes:
        previous = original.get(item["path"])
        if previous and previous["mode"] not in {"100644", "100755"}:
            raise ValueError("Only regular source files may be changed")
        edit = {
            "path": item["path"],
            "mode": previous["mode"] if previous else "100644",
            "type": "blob",
        }
        if item["content"] is None:
            if not previous:
                raise ValueError("Cannot delete unknown source file")
            edit["sha"] = None
        else:
            edit["content"] = item["content"]
        edits.append(edit)
    new_tree = request("git/trees", {"base_tree": tree_sha, "tree": edits})
    if new_tree["sha"] == tree_sha:
        return "Keine Quelländerung; kein leerer PR erstellt."
    new_commit = request(
        "git/commits",
        {
            "message": f"Implement HA blog issue #{issue_number}",
            "tree": new_tree["sha"],
            "parents": [base],
        },
    )
    # Never overwrite an existing branch. An interrupted publication needs manual recovery.
    request("git/refs", {"ref": f"refs/heads/{branch}", "sha": new_commit["sha"]})
    body = (
        f"{pr_marker}\n\n"
        f"Umsetzungsvorschlag für #{issue_number}.\n\n"
        f"Ursprung und Analyse: {issue['html_url']}\n\n"
        f"[Automatische Blog-Analyse und Umsetzung]({run_url}).\n\n"
        "Automatisch erzeugter Entwurf gegen develop. Inhaltliche Prüfung, aktuelle CI "
        "und betroffene Qualitäts-/Praxisnachweise sind vor einer Übernahme erforderlich. "
        "Dieser Ablauf bescheinigt keine bestandenen Tests. Falls GitHub die CI zurückhält, "
        "Approve workflows to run im PR wählen. Kein automatischer Merge.\n\n"
        "Das Issue erst nach geprüfter Übernahme der Umsetzung schließen.\n"
    )
    pr = request(
        "pulls",
        {
            "title": issue["title"][:250],
            "head": branch,
            "base": "develop",
            "draft": True,
            "body": body,
        },
    )
    return f"Entwurfs-PR: {pr['html_url']}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "publish"))
    parser.add_argument("--root", type=Path, default=Path("implementation"))
    parser.add_argument("--file", type=Path, default=Path("proposal/changes.json"))
    args = parser.parse_args()
    base = os.environ["IMPLEMENTATION_BASE"]
    if args.mode == "collect":
        collect(args.root, base, args.file)
        return
    if args.file.is_symlink() or args.file.stat().st_size > MAX_BYTES:
        raise ValueError("Invalid proposal artifact")
    data = json.loads(args.file.read_text(encoding="utf-8"))
    repository = os.environ["GITHUB_REPOSITORY"]

    def request(endpoint, payload=None):
        return github_request(repository, os.environ["GH_TOKEN"], endpoint, payload)

    message = publish(
        request,
        repository,
        base,
        int(os.environ["ISSUE_NUMBER"]),
        os.environ["POST_KEY"],
        data,
        f"https://github.com/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
    )
    print(message)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


if __name__ == "__main__":
    main()
