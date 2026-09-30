# SPDX-License-Identifier: Apache-2.0
"""Collect bounded source edits and publish draft PRs from a fresh trusted job."""

import argparse
import base64
import html
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
REPORT_LIMIT = 6000
TARGET_FILES = {"AGENTS.md": "Home Assistant ab ", "AGENTS.en.md": "Home Assistant "}
ALLOWED_ROOT_FILES = {
    "README.md",
    "CHANGELOG.md",
    "CHANGELOG.en.md",
    "pyproject.toml",
    "uv.lock",
    "hacs.json",
}


def validate_report(report):
    if not isinstance(report, dict) or set(report) != {"status", "summary", "reason", "tests"}:
        raise ValueError("Invalid implementation report")
    if not isinstance(report["status"], str) or report["status"] not in {
        "ready",
        "no_changes",
        "failed",
    }:
        raise ValueError("Invalid implementation status")
    for field in ("summary", "reason", "tests"):
        value = report[field]
        if not isinstance(value, str) or not value.strip() or len(value) > REPORT_LIMIT:
            raise ValueError("Missing or oversized implementation explanation")
        if any(ord(char) < 32 and char not in "\n\t\r" for char in value):
            raise ValueError("Invalid implementation explanation")
    return report


def failure_report(reason):
    return {
        "status": "failed",
        "summary": "Kein veröffentlichbarer Umsetzungsvorschlag.",
        "reason": reason,
        "tests": "Keine bestandenen Prüfungen durch diesen Ablauf belegt.",
    }


def report_markdown(report):
    # Render agent text as inert text, not HTML, mentions or forged Markdown links.
    def quoted(value):
        value = html.escape(value).replace("@", "@\u200b")
        value = re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", value)
        return "\n".join(f"> {line}" for line in value.splitlines())

    return "\n\n".join(
        f"**{label}**\n\n{quoted(report[field])}"
        for field, label in (
            ("summary", "Abschlussbericht der Umsetzung"),
            ("reason", "Begründung"),
            ("tests", "Von Junie gemeldete Prüfungen (nicht unabhängig bestätigt)"),
        )
    )


def comment_once(request, number, marker, body):
    page = 1
    while True:
        comments = request(f"issues/{number}/comments?per_page=100&page={page}")
        if any(marker in (item.get("body") or "") for item in comments):
            return
        if len(comments) < 100:
            break
        page += 1
    request(f"issues/{number}/comments", {"body": f"{marker}\n\n{body}"})


def no_pr(request, number, key, run_url, report, *, uncertain=False):
    message = (
        "PR-Veröffentlichung nicht abgeschlossen; Ergebnis bitte im Lauf prüfen."
        if uncertain
        else "Kein Entwurfs-PR erstellt; Issue bleibt zur Prüfung offen."
    )
    body = f"{message}\n\n{report_markdown(report)}\n\n[Analyse und Umsetzung]({run_url})."
    comment_once(
        request, number, f"<!-- ha-blog-no-pr:{key}:{run_url.rsplit('/', 1)[-1]} -->", body
    )
    return body


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
        if (
            not isinstance(path, str)
            or (not allowed_path(path) and path not in TARGET_FILES)
            or path in seen
        ):
            raise ValueError("Disallowed or duplicate path")
        if content is not None and (not isinstance(content, str) or "\0" in content):
            raise ValueError("Only UTF-8 text edits are supported")
        seen.add(path)
    if seen.intersection(TARGET_FILES) and "hacs.json" not in seen:
        raise ValueError("Project instructions require a matching HA minimum change")
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
        if not allowed_path(name) and name not in TARGET_FILES:
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


def collect_outcome(root, base, output, outcome):
    """Always retain a bounded explanation, even after a failed agent or rejected edits."""
    data = {"base": base, "changes": []}
    report_path = root / ".work/implementation-report.json"
    try:
        if (
            report_path.is_symlink()
            or not report_path.resolve().is_relative_to(root.resolve())
            or report_path.stat().st_size > REPORT_LIMIT * 12
        ):
            raise ValueError("Invalid report file")
        report = validate_report(json.loads(report_path.read_text(encoding="utf-8")))
    except OSError, ValueError:
        report = failure_report(
            "Junies strukturierter Abschlussbericht fehlt oder ist ungültig. "
            "Die inhaltliche Begründung ist nicht verfügbar."
        )
    if outcome == "not_requested":
        report = {
            "status": "no_changes",
            "summary": "Keine automatische Umsetzung beauftragt.",
            "reason": "Die Kompatibilitäts- oder Verbesserungsbewertung ist unklar (uncertain). "
            "Das Issue muss zunächst manuell konkretisiert werden.",
            "tests": "Kein Umsetzungsauftrag und keine Tests ausgeführt.",
        }
    elif outcome != "success":
        report = {
            **report,
            "status": "failed",
            "reason": f"Umsetzungsauftrag nicht erfolgreich abgeschlossen (Status: {outcome}).\n"
            + report["reason"],
        }
    if report["status"] != "failed" and outcome != "not_requested":
        try:
            collect(root, base, output)
            data = json.loads(output.read_text(encoding="utf-8"))
            if (report["status"] == "ready") != bool(data["changes"]):
                raise ValueError("Report and changes disagree")
        except OSError, ValueError, subprocess.SubprocessError:
            data = {"base": base, "changes": []}
            report = {
                **report,
                "status": "failed",
                "reason": "Dateiänderungen nicht zulässig oder widersprüchlich zum Abschlussbericht.\n"
                + report["reason"],
            }
    data["report"] = report
    report["reason"] = report["reason"][:REPORT_LIMIT]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (output.parent / "report.md").write_text(report_markdown(report), encoding="utf-8")


def minimum_version_notice(request, base, changes):
    changed = next((item for item in changes if item["path"] == "hacs.json"), None)
    if changed is None:
        if any(item["path"] in TARGET_FILES for item in changes):
            raise ValueError("Project instructions may only track a changed HA minimum")
        return ""
    previous = request(f"contents/hacs.json?ref={base}")
    old = json.loads(base64.b64decode(previous["content"]))
    new = json.loads(changed["content"] or "null")
    if not isinstance(new, dict) or set(old) != set(new):
        raise ValueError("Invalid HACS configuration change")
    if any(old[key] != new[key] for key in old if key != "homeassistant"):
        raise ValueError("Only the HA minimum may change in HACS configuration")
    before, after = old["homeassistant"], new["homeassistant"]
    if not all(
        isinstance(v, str) and re.fullmatch(r"\d{4}\.\d{1,2}\.\d+", v) for v in (before, after)
    ):
        raise ValueError("Invalid HA minimum version")
    if tuple(map(int, after.split("."))) < tuple(map(int, before.split("."))):
        raise ValueError("HA minimum must not be lowered")
    for item in changes:
        if item["path"] in TARGET_FILES:
            source = request(f"contents/{item['path']}?ref={base}")
            original = base64.b64decode(source["content"]).decode("utf-8")
            prefix = TARGET_FILES[item["path"]]
            old_target = prefix + before.removesuffix(".0")
            new_target = prefix + after.removesuffix(".0")
            if (
                before == after
                or original.count(old_target) != 1
                or item["content"] != original.replace(old_target, new_target, 1)
            ):
                raise ValueError("Protected project instructions changed beyond the HA target")
    if before == after:
        return ""
    return (
        f"**Home-Assistant-Mindestversion angehoben: `{before}` → `{after}`.**\n\n"
        "Dies ist die Mindestversion, die Enigma2 Connect nach Übernahme dieses PR voraussetzt. "
        "Ältere Home-Assistant-Versionen werden damit nicht mehr unterstützt. "
        "Vor Übernahme sind API-Verfügbarkeit, passende Testabhängigkeiten und die "
        "Dokumentation zu prüfen. Kein automatischer Merge."
    )


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
    try:
        changes = validate_changes(data, base)
        report = validate_report(data.get("report"))
        notice = minimum_version_notice(request, base, changes)
        return publish_validated(
            request, base, issue_number, key, changes, report, notice, issue, run_url
        )
    except (ValueError, HTTPError) as error:
        reason = (
            "Die Veröffentlichung wurde durch die Validierung abgelehnt: " + str(error)
            if isinstance(error, ValueError)
            else f"GitHub-API-Fehler bei der Veröffentlichung (HTTP {error.code}). "
            "Der Lauf kann bereits einen Branch oder PR angelegt haben; bitte prüfen."
        )
        no_pr(
            request,
            issue_number,
            key,
            run_url,
            failure_report(reason),
            uncertain=isinstance(error, HTTPError),
        )
        raise


def publish_validated(request, base, issue_number, key, changes, report, notice, issue, run_url):
    pr_marker = f"<!-- ha-blog-implementation:{issue_number}:{key} -->"
    page = 1
    while True:
        existing = request(f"pulls?state=all&base=develop&per_page=100&page={page}")
        for pr in existing:
            if pr_marker in (pr.get("body") or ""):
                if notice:
                    comment_once(
                        request, pr["number"], f"<!-- ha-blog-ha-minimum:{key} -->", notice
                    )
                return f"Vorhandener PR bleibt unverändert: {pr['html_url']}"
        if len(existing) < 100:
            break
        page += 1
    if report["status"] != "ready" or not changes:
        if changes:
            raise ValueError("Unfinished implementation contains edits")
        return no_pr(request, issue_number, key, run_url, report)
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
        return no_pr(
            request,
            issue_number,
            key,
            run_url,
            {**report, "reason": "Keine Quelländerung gegenüber develop.\n" + report["reason"]},
        )
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
        f"\n{report_markdown(report)}\n\n{notice}\n"
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
    if notice:
        try:
            comment_once(request, pr["number"], f"<!-- ha-blog-ha-minimum:{key} -->", notice)
        except HTTPError as error:
            raise RuntimeError("Draft PR exists, but its HA minimum comment failed") from error
    return f"Entwurfs-PR: {pr['html_url']}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "publish"))
    parser.add_argument("--root", type=Path, default=Path("implementation"))
    parser.add_argument("--file", type=Path, default=Path("proposal/changes.json"))
    args = parser.parse_args()
    base = os.environ["IMPLEMENTATION_BASE"]
    if args.mode == "collect":
        outcome = os.environ.get("IMPLEMENTATION_OUTCOME", "skipped")
        if outcome not in {"success", "failure", "cancelled", "skipped"}:
            outcome = "failure"
        if os.environ.get("IMPLEMENTATION_REQUESTED") == "false":
            outcome = "not_requested"
        collect_outcome(args.root, base, args.file, outcome)
        return
    try:
        if args.file.is_symlink() or args.file.stat().st_size > MAX_BYTES:
            raise ValueError("Invalid proposal artifact")
        data = json.loads(args.file.read_text(encoding="utf-8"))
    except OSError, ValueError:
        data = {
            "base": base,
            "changes": [],
            "report": failure_report(
                "Das Ergebnisartefakt fehlt oder ist ungültig. Details stehen im implement-Job "
                "dieses Laufs; eine inhaltliche Junie-Begründung ist nicht verfügbar."
            ),
        }
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
    if data["report"]["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
