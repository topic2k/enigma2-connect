# SPDX-License-Identifier: Apache-2.0
"""Durable per-post assessments and deterministic Atom publication."""

import argparse
import base64
import copy
import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.parse import quote

try:
    from . import ha_blog_gemini as common
    from . import ha_blog_scheduler as scheduler
except ImportError:
    import ha_blog_gemini as common
    import ha_blog_scheduler as scheduler

PREFIX = ".github/ha-blog-feed/"
INDEX = PREFIX + "index.json"
PUBLIC_BRANCH = "ha-blog-feed"
UPSTREAM = "home-assistant/developers.home-assistant"
ATOM = "http://www.w3.org/2005/Atom"
MAX_FILE_BYTES = 2_000_000
HEX = r"[a-f0-9]{64}"
STATUSES = {"started", "completed", "failed", "cancelled", "historical"}
IMPLEMENTATIONS = {
    "pending",
    "draft",
    "existing",
    "no_changes",
    "failed",
    "not_requested",
    "uncertain",
}


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def check_time(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ):
        raise ValueError("Expected UTC timestamp")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def text_value(value, limit=20000):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or any(
            not (
                c in "\n\r\t"
                or 0x20 <= ord(c) <= 0xD7FF
                or 0xE000 <= ord(c) <= 0xFFFD
                or 0x10000 <= ord(c) <= 0x10FFFF
            )
            for c in value
        )
    ):
        raise ValueError("Invalid public text")
    return value


def post_path(value):
    text_value(value, 500)
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or str(path) != value
        or ".." in path.parts
        or "\\" in value
        or ":" in value
        or path.suffix not in {".md", ".mdx"}
    ):
        raise ValueError("Invalid blog path")
    return value


def identity(path):
    return hashlib.sha256(f"{UPSTREAM}/blog/{post_path(path)}".encode()).hexdigest()


def article_url(post):
    # Share the existing slug logic without parsing generated Markdown.
    published = datetime.fromisoformat(post["date"]).strftime("%Y/%m/%d")
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}[-/]", "", post_path(post["path"]))
    slug = slug.removesuffix(".mdx").removesuffix(".md").removesuffix("/index")
    return f"https://developers.home-assistant.io/blog/{published}/{quote(slug, safe='/')}/"


def check_link(value, repository, kind):
    patterns = {
        "run": rf"https://github\.com/{re.escape(repository)}/actions/runs/[0-9]+(?:/attempts/[0-9]+)?",
        "issue": rf"https://github\.com/{re.escape(repository)}/issues/[0-9]+",
        "pr": rf"https://github\.com/{re.escape(repository)}/pull/[0-9]+",
    }
    if value is not None and (
        not isinstance(value, str) or not re.fullmatch(patterns[kind], value)
    ):
        raise ValueError("Invalid provenance link")
    return value


def validate_record(record, repository):
    if not isinstance(record, dict) or record.get("version") != 1:
        raise ValueError("Unsupported assessment record")
    if record.get("id") != identity(record["path"]):
        raise ValueError("Assessment identity mismatch")
    text_value(record["title"], 1000)
    datetime.fromisoformat(record["date"])
    check_time(record["published"])
    check_time(record["updated"])
    events = record["attempts"]
    if not isinstance(events, list) or not events:
        raise ValueError("Missing assessment history")
    seen = set()
    for event in events:
        key = text_value(event["id"], 200)
        if key in seen or event["status"] not in STATUSES:
            raise ValueError("Invalid or duplicate attempt")
        seen.add(key)
        if not re.fullmatch(HEX, event["content_id"]):
            raise ValueError("Invalid content identity")
        for field in ("revision", "upstream"):
            value = event.get(field)
            if value is not None and not re.fullmatch(r"[a-f0-9]{40}", value):
                raise ValueError("Invalid source revision")
        check_time(event["started"])
        check_time(event["updated"])
        check_link(event.get("run_url"), repository, "run")
        check_link(event.get("issue_url"), repository, "issue")
        text_value(event.get("error", ""), 2000)
        if event.get("due") is not None:
            datetime.fromisoformat(event["due"])
        if event.get("publication") not in {None, "not_required", "published", "failed", "unknown"}:
            raise ValueError("Invalid publication status")
        result = event.get("result")
        if result is not None:
            if result.get("id") != event["content_id"] or result.get("assessment") not in {
                "impacted",
                "no-impact",
                "uncertain",
            }:
                raise ValueError("Invalid stored assessment")
            for part in (result, result["opportunity"]):
                for field in ("reason", "next_steps"):
                    text_value(part[field], 1800)
                evidence = part["evidence"]
                if not isinstance(evidence, list) or len(evidence) > 5:
                    raise ValueError("Invalid stored evidence")
                for item in evidence:
                    path = PurePosixPath(text_value(item["path"], 500))
                    if path.is_absolute() or ".." in path.parts or "\\" in str(path):
                        raise ValueError("Invalid source path")
                    if type(item["line"]) is not int or item["line"] < 1:
                        raise ValueError("Invalid source line")
                    text_value(item["quote"])
            text_value(result["ha_version"], 1800)
            if result["opportunity"]["assessment"] not in {"recommended", "none", "uncertain"}:
                raise ValueError("Invalid stored opportunity")
        for item in event.get("implementations", []):
            if item["status"] not in IMPLEMENTATIONS:
                raise ValueError("Invalid implementation state")
            check_time(item["updated"])
            check_link(item.get("pr_url"), repository, "pr")
            check_link(item.get("run_url"), repository, "run")
            for field in ("summary", "reason", "tests"):
                text_value(item.get(field, ""), 6000)
    return record


def json_text(value):
    raw = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if len(raw.encode()) > MAX_FILE_BYTES:
        raise ValueError("Assessment file exceeds size limit; preserve history before archiving")
    return raw


class Branch:
    """Pinned Git snapshot, preserving unrelated files and rejecting stale writes."""

    def __init__(self, request, branch, revision):
        self.request, self.branch, self.revision = request, branch, revision
        self.head = self.tree = None
        self.files = {}

    def load(self):
        try:
            self.head = self.request(f"git/ref/heads/{self.branch}")["object"]["sha"]
        except HTTPError as error:
            if error.code != 404:
                raise
            self.head = None
            return
        self.tree = self.request(f"git/commits/{self.head}")["tree"]["sha"]
        tree = self.request(f"git/trees/{self.tree}?recursive=1")
        if tree.get("truncated"):
            raise ValueError("Incomplete state tree")
        self.files = {item["path"]: item for item in tree["tree"]}

    def read(self, path):
        item = self.files.get(path)
        if item is None:
            return None
        if (
            item["type"] != "blob"
            or item["mode"] != "100644"
            or item.get("size", 0) > MAX_FILE_BYTES
        ):
            raise ValueError("Invalid state file")
        blob = self.request(f"git/blobs/{item['sha']}")
        if blob.get("encoding") != "base64":
            raise ValueError("Unsupported state encoding")
        raw = base64.b64decode(blob["content"])
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("State file exceeds size limit")
        return raw.decode("utf-8")

    def commit(self, files, message):
        if not files:
            return False
        try:
            current = self.request(f"git/ref/heads/{self.branch}")["object"]["sha"]
        except HTTPError as error:
            if error.code != 404:
                raise
            current = None
        if current != self.head:
            raise ValueError("State branch changed; refusing stale write")
        tree = self.request(
            "git/trees",
            {
                **({"base_tree": self.tree} if self.tree else {}),
                "tree": [
                    {"path": path, "mode": "100644", "type": "blob", "content": content}
                    for path, content in sorted(files.items())
                ],
            },
        )
        if tree["sha"] == self.tree:
            return False
        commit = self.request(
            "git/commits",
            {
                "message": message,
                "tree": tree["sha"],
                "parents": [self.head] if self.head else [],
            },
        )
        if self.head:
            self.request(
                f"git/refs/heads/{self.branch}",
                {"sha": commit["sha"], "force": False},
                method="PATCH",
            )
        else:
            self.request("git/refs", {"ref": f"refs/heads/{self.branch}", "sha": commit["sha"]})
        self.head, self.tree = commit["sha"], tree["sha"]
        return True


class FeedState:
    """Commit retry state and assessment events in the same Git transaction."""

    def __init__(self, request, revision, repository):
        self.branch = Branch(request, scheduler.STATE_BRANCH, revision)
        self.repository, self.revision = repository, revision
        self.records, self.original = {}, {}

    def load(self):
        self.branch.load()
        raw = self.branch.read(scheduler.STATE_PATH)
        state = scheduler.validate_state(json.loads(raw)) if raw else {"version": 1, "entries": {}}
        index_raw = self.branch.read(INDEX)
        index = json.loads(index_raw) if index_raw else {"version": 1, "posts": {}}
        if index.get("version") != 1 or not isinstance(index.get("posts"), dict):
            raise ValueError("Invalid assessment index")
        self.records = {}
        for key, path in index["posts"].items():
            if key != identity(path):
                raise ValueError("Index identity mismatch")
            raw = self.branch.read(f"{PREFIX}posts/{key}.json")
            if raw is None:
                raise ValueError("Missing assessment record")
            record = validate_record(json.loads(raw), self.repository)
            if record["id"] != key or record["path"] != path:
                raise ValueError("Index record mismatch")
            self.records[key] = record
        self.original = copy.deepcopy(self.records)
        return state

    def record(self, post, at):
        key = identity(post["path"])
        if key not in self.records:
            self.records[key] = {
                "version": 1,
                "id": key,
                "path": post_path(post["path"]),
                "title": text_value(post["title"], 1000),
                "date": post["date"],
                "published": at,
                "updated": at,
                "attempts": [],
            }
        record = self.records[key]
        record.update(title=post["title"], date=post["date"])
        return record

    def reserve(self, state):
        for content_id, entry in state["entries"].items():
            if not entry.get("run_id"):
                continue
            at = entry["started"]
            record = self.record(entry["post"], at)
            attempt_id = f"{entry['run_id']}:{entry['run_attempt']}:{content_id}"
            if any(e["id"] == attempt_id for e in record["attempts"]):
                continue
            record["attempts"].append(
                {
                    "id": attempt_id,
                    "content_id": content_id,
                    "started": at,
                    "updated": at,
                    "status": "started",
                    "revision": self.revision,
                    "upstream": entry["upstream"],
                    "run_url": f"https://github.com/{self.repository}/actions/runs/{entry['run_id']}/attempts/{entry['run_attempt']}",
                    "attempts": entry["attempts"],
                    "due": entry["due"],
                }
            )
            record["updated"] = at

    def record_completion(self, selected, results, failures, report, state):
        at = timestamp()
        by_id = {r["id"]: r for r in results}
        issues = {i["key"]: i for i in report["issues"]}
        for post in selected:
            content_id = common.post_id(post)
            record = self.records.get(identity(post["path"]))
            if not record:
                raise ValueError("Missing reserved assessment")
            run_id = os.environ.get("GITHUB_RUN_ID", "")
            run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
            attempt_id = f"{run_id}:{run_attempt}:{content_id}"
            event = next((e for e in record["attempts"] if e["id"] == attempt_id), None)
            if event is None:
                raise ValueError("Missing reserved attempt")
            result, issue = by_id.get(content_id), issues.get(content_id)
            event.update(status="completed" if result else "failed", updated=at)
            if result:
                event["result"] = copy.deepcopy(result)
                event["publication"] = (
                    "published" if issue else "failed" if content_id in failures else "not_required"
                )
            if issue:
                event["issue_url"] = check_link(issue["url"], self.repository, "issue")
                event["issue_number"] = issue["number"]
                event["implementations"] = [{"status": "pending", "updated": at}]
            if content_id in failures:
                event["error"] = failures[content_id]
                event["due"] = state["entries"][content_id]["due"]
            else:
                event["due"] = None
            record["updated"] = at

    def save(self, state):
        scheduler.validate_state(state)
        self.reserve(state)
        state_text = json_text(state)
        if len(state_text.encode()) > scheduler.MAX_STATE_BYTES:
            raise ValueError("Retry state exceeds size limit")
        files = {scheduler.STATE_PATH: state_text}
        for key, record in self.records.items():
            validate_record(record, self.repository)
            if self.original.get(key) != record:
                files[f"{PREFIX}posts/{key}.json"] = json_text(record)
        files[INDEX] = json_text(
            {"version": 1, "posts": {key: r["path"] for key, r in sorted(self.records.items())}}
        )
        self.branch.commit(files, "Update Home Assistant blog assessment state [skip ci]")
        self.original = copy.deepcopy(self.records)

    def reconcile(self):
        """Only terminal GitHub run attempts establish that a reservation was interrupted."""
        checked = {}
        for record in self.records.values():
            for event in record["attempts"]:
                if event["status"] != "started":
                    continue
                run_id, attempt, _ = event["id"].split(":", 2)
                if (run_id, attempt) not in checked:
                    checked[run_id, attempt] = self.branch.request(
                        f"actions/runs/{run_id}/attempts/{attempt}"
                    )
                run = checked[run_id, attempt]
                if run.get("status") != "completed":
                    continue
                at = check_time(run["updated_at"])
                event.update(
                    status="cancelled" if run.get("conclusion") == "cancelled" else "failed",
                    error="Lauf beendet; kein vollständiges Prüfergebnis gespeichert",
                    updated=at,
                )
                record["updated"] = max(record["updated"], at)

    def reconcile_implementations(self):
        pending = [
            (record, event)
            for record in self.records.values()
            for event in record["attempts"]
            if any(item["status"] == "pending" for item in event.get("implementations", []))
        ]
        prs = None
        for record, event in pending:
            run_id, attempt, _ = event["id"].split(":", 2)
            finishing = (
                os.environ.get("FINISHING_RUN") == "true"
                and run_id == os.environ.get("GITHUB_RUN_ID")
                and attempt == os.environ.get("GITHUB_RUN_ATTEMPT", "1")
            )
            run = self.branch.request(f"actions/runs/{run_id}/attempts/{attempt}")
            if run.get("status") != "completed" and not finishing:
                continue
            if prs is None:
                prs, page = [], 1
                while True:
                    batch = self.branch.request(
                        f"pulls?state=all&base=develop&per_page=100&page={page}"
                    )
                    prs.extend(batch)
                    if len(batch) < 100:
                        break
                    page += 1
            marker = (
                f"<!-- ha-blog-implementation:{event['issue_number']}:{event['content_id']} -->"
            )
            pr = next((pr for pr in prs if marker in (pr.get("body") or "")), None)
            at = timestamp() if finishing else check_time(run["updated_at"])
            item = {
                "status": "existing" if pr else "failed",
                "updated": at,
                "run_url": event["run_url"],
                "summary": "Vorhandener PR gefunden."
                if pr
                else "Kein gespeicherter Umsetzungsabschluss verfügbar.",
                "reason": "Aus GitHub abgeglichen; vollständiger Abschlussbericht fehlt.",
                "tests": "Keine unabhängig bestätigten Prüfungen.",
            }
            if pr:
                item["pr_url"] = check_link(pr["html_url"], self.repository, "pr")
            event["implementations"] = [item]
            record["updated"] = max(record["updated"], at)


def import_history(store, state, posts, reports, issues, prs=()):
    """Import only exact content matches; keep incomplete historical receipts explicit."""
    by_content = {common.post_id(p): p for p in posts}
    by_content.update({key: e["post"] for key, e in state["entries"].items()})
    unmatched = []
    issue_by_content = {}
    for issue in issues:
        if "pull_request" in issue:
            continue
        for key in re.findall(r"<!-- ha-blog-gemini:([a-f0-9]{64}) -->", issue.get("body") or ""):
            issue_by_content.setdefault(key, []).append(issue)
    for envelope in sorted(
        reports, key=lambda e: (e["created_at"], e["id"], e.get("run_attempt", 1))
    ):
        report, at = envelope["report"], check_time(envelope["created_at"])
        if report.get("dry_run", True):
            continue
        results = {r["id"]: r for r in report.get("results", [])}
        failures = {f["id"]: f for f in report.get("retry_pending", []) + report.get("failed", [])}
        for key in results.keys() | failures.keys():
            post = by_content.get(key)
            if post is None:
                unmatched.append({"content_id": key, "run_id": envelope["id"]})
                continue
            record = store.record(post, at)
            event_id = f"{envelope['id']}:{envelope.get('run_attempt', 1)}:{key}"
            if any(e["id"] == event_id for e in record["attempts"]):
                continue
            matches = [i for i in report.get("issues", []) if i["key"] == key]
            event = {
                "id": event_id,
                "content_id": key,
                "started": at,
                "updated": at,
                "status": "completed" if key in results else "failed",
                "revision": report.get("revision"),
                "run_url": f"https://github.com/{store.repository}/actions/runs/{envelope['id']}/attempts/{envelope.get('run_attempt', 1)}",
            }
            if key in results:
                event["result"] = copy.deepcopy(results[key])
                event["publication"] = (
                    "published" if matches else "failed" if key in failures else "not_required"
                )
            if matches:
                event.update(issue_url=matches[0]["url"], issue_number=matches[0]["number"])
            if key in failures:
                event.update(
                    {field: failures[key][field] for field in ("error", "due", "attempts")}
                )
            record["attempts"].append(event)
            record["published"] = min(record["published"], at)
            record["updated"] = max(record["updated"], at)
            validate_record(record, store.repository)
    receipts = {
        **state.get("reviewed", {}),
        **{key: e["last_attempt"] for key, e in state["entries"].items()},
    }
    for key, day in sorted(receipts.items()):
        post = by_content.get(key)
        if post is None:
            unmatched.append({"content_id": key})
            continue
        record = store.records.get(identity(post["path"]))
        if record and any(e["content_id"] == key for e in record["attempts"]):
            continue
        at = day + "T00:00:00Z"
        record = store.record(post, at)
        entry = state["entries"].get(key)
        event = {
            "id": f"historical:{key}",
            "content_id": key,
            "started": at,
            "updated": at,
            "status": "failed" if entry else "historical",
            "publication": "unknown",
        }
        if entry:
            event.update(
                {field: entry[field] for field in ("error", "due", "attempts", "upstream")}
            )
        if issue_by_content.get(key):
            issue = issue_by_content[key][-1]
            event.update(issue_url=issue["html_url"], issue_number=issue["number"])
        record["attempts"].append(event)
        record["updated"] = max(record["updated"], at)
        validate_record(record, store.repository)
    for record in store.records.values():
        record["attempts"].sort(key=lambda e: (e["started"], e["id"]))
        for event in record["attempts"]:
            if not event.get("issue_number") or event.get("implementations"):
                continue
            marker = (
                f"<!-- ha-blog-implementation:{event['issue_number']}:{event['content_id']} -->"
            )
            pr = next((p for p in prs if marker in (p.get("body") or "")), None)
            if pr:
                at = check_time(pr["updated_at"])
                event["implementations"] = [
                    {
                        "status": "existing",
                        "updated": at,
                        "pr_url": check_link(pr["html_url"], store.repository, "pr"),
                        "summary": "Historisch vorhandener Umsetzungsvorschlag.",
                        "reason": "PR anhand der Analysekennung zugeordnet.",
                        "tests": "Keine unabhängig bestätigten Prüfungen.",
                    }
                ]
                record["updated"] = max(record["updated"], at)
                validate_record(record, store.repository)
    return {"unmatched": unmatched, "posts": len(store.records)}


def apply_implementation(store, item):
    """Merge only a validated outcome from the trusted publication job."""
    if not isinstance(item, dict) or item.get("version") != 1:
        raise ValueError("Invalid implementation envelope")
    content_id = item.get("content_id")
    if not isinstance(content_id, str) or not re.fullmatch(HEX, content_id):
        raise ValueError("Invalid implementation content identity")
    number = item.get("issue_number")
    if type(number) is not int or number < 1:
        raise ValueError("Invalid issue number")
    outcome = item["outcome"]
    if not isinstance(outcome, dict) or outcome.get("status") not in IMPLEMENTATIONS:
        raise ValueError("Invalid implementation outcome")
    check_time(outcome["updated"])
    for record in store.records.values():
        for event in record["attempts"]:
            if event["content_id"] != content_id or event.get("issue_number") != number:
                continue
            items = event.setdefault("implementations", [])
            old = next((v for v in items if v.get("run_url") == outcome.get("run_url")), None)
            if old == outcome:
                return
            if old:
                old.update(outcome)
            else:
                items[:] = [v for v in items if v["status"] != "pending"]
                items.append(copy.deepcopy(outcome))
            record["updated"] = max(record["updated"], outcome["updated"])
            validate_record(record, store.repository)
            return
    raise ValueError("Implementation does not match a persisted issue assessment")


def summary(event):
    if event["status"] == "historical":
        return "Früher geprüft; vollständige Detailbewertung nicht mehr verfügbar"
    if event["status"] == "started":
        return "Prüfung gestartet; Abschluss ausstehend"
    if event["status"] in {"failed", "cancelled"}:
        label = (
            "Prüfung abgebrochen" if event["status"] == "cancelled" else "Prüfung fehlgeschlagen"
        )
        return label + (
            " – Wiederholung vorgemerkt" if event.get("due") else " – manuelle Prüfung nötig"
        )
    result = event["result"]
    impact = {
        "impacted": "Anpassung erforderlich",
        "no-impact": "Keine notwendige Anpassung",
        "uncertain": "Anpassungsbedarf unklar",
    }
    opportunity = {
        "recommended": "Verbesserung empfohlen",
        "none": "Keine Verbesserung vorgeschlagen",
        "uncertain": "Verbesserungsmöglichkeit unklar",
    }
    if result["assessment"] == "no-impact" and result["opportunity"]["assessment"] == "none":
        label = "Ohne Handlungsbedarf"
    else:
        label = (
            impact[result["assessment"]] + "; " + opportunity[result["opportunity"]["assessment"]]
        )
    if event.get("publication") == "failed":
        label += "; Issue-Veröffentlichung fehlgeschlagen"
    return label


def render_content(record, repository):
    esc = html.escape
    paragraphs = [f"<p>Blogdatum: {esc(record['date'])}</p>"]
    links = [(article_url(record), "Originalbeitrag")]
    for event in reversed(record["attempts"]):
        paragraphs.append(f"<h3>{esc(event['updated'])}: {esc(summary(event))}</h3>")
        if event.get("attempts"):
            paragraphs.append(f"<p>Versuch: {int(event['attempts'])}</p>")
        for field, label in (("run_url", "Actions-Lauf"), ("issue_url", "Issue")):
            if event.get(field):
                links.append((event[field], label))
        if event.get("upstream"):
            links.append(
                (
                    f"https://github.com/{UPSTREAM}/blob/{event['upstream']}/blog/{quote(record['path'], safe='/')}",
                    "Analysierter Blogtext",
                )
            )
        if event.get("revision"):
            links.append(
                (f"https://github.com/{repository}/tree/{event['revision']}", "Integrationsstand")
            )
        result = event.get("result")
        if result:
            paragraphs.append(f"<p>HA-Versionen und Fristen: {esc(result['ha_version'])}</p>")
            for part, label in (
                (result, "Notwendige Anpassungen"),
                (result["opportunity"], "Ergänzungen und Verbesserungen"),
            ):
                paragraphs.extend(
                    [
                        f"<h4>{label}</h4><p>{esc(part['reason'])}</p>",
                        f"<p>Nächste Schritte: {esc(part['next_steps'])}</p>",
                    ]
                )
                for evidence in part["evidence"]:
                    paragraphs.append(f"<pre>{esc(evidence['quote'])}</pre>")
                    if event.get("revision"):
                        links.append(
                            (
                                f"https://github.com/{repository}/blob/{event['revision']}/{quote(evidence['path'], safe='/')}#L{evidence['line']}",
                                f"{evidence['path']}:{evidence['line']}",
                            )
                        )
        if event.get("error"):
            paragraphs.append(f"<p>{esc(event['error'])}</p>")
        if event.get("due"):
            paragraphs.append(f"<p>Wiederholung fällig ab {esc(event['due'])} UTC</p>")
        for item in event.get("implementations", []):
            label = {
                "pending": "Umsetzungsvorschlag ausstehend",
                "draft": "Entwurfs-PR erstellt",
                "existing": "Vorhandener PR",
                "no_changes": "Keine Änderungen vorgeschlagen",
                "failed": "Umsetzungsvorschlag fehlgeschlagen",
                "not_requested": "Keine automatische Umsetzung",
                "uncertain": "Veröffentlichungsstand unklar",
            }[item["status"]]
            paragraphs.append(f"<h4>{label}</h4>")
            for field in ("summary", "reason", "tests"):
                if item.get(field):
                    prefix = (
                        "Von Junie gemeldete Prüfungen (nicht unabhängig bestätigt): "
                        if field == "tests"
                        else ""
                    )
                    paragraphs.append(f"<p>{prefix}{esc(item[field])}</p>")
            for field, label in (("pr_url", "Entwurfs-PR"), ("run_url", "Umsetzungslauf")):
                if item.get(field):
                    links.append((item[field], label))
    paragraphs.append(
        "<p>Automatische KI-Einschätzung; keine Bestätigung ausgeführter Kompatibilitätstests.</p>"
    )
    paragraphs.extend(
        f'<p><a href="{esc(url, quote=True)}">{esc(label)}</a></p>'
        for url, label in dict.fromkeys(links)
    )
    return "\n".join(paragraphs)


def render_atom(records, repository, base_url):
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~-]+)*/", base_url):
        raise ValueError("Expected canonical HTTPS Pages URL with trailing slash")
    ET.register_namespace("", ATOM)
    ET.register_namespace("xml", "http://www.w3.org/XML/1998/namespace")
    root = ET.Element(f"{{{ATOM}}}feed", {"{http://www.w3.org/XML/1998/namespace}lang": "de"})

    def add(parent, tag, value=None, **attrs):
        element = ET.SubElement(parent, f"{{{ATOM}}}{tag}", attrs)
        if value is not None:
            element.text = value
        return element

    ordered = sorted(records.values(), key=lambda r: (r["updated"], r["id"]), reverse=True)
    add(root, "id", f"urn:github:{repository}:ha-blog-assessments")
    add(root, "title", "Enigma2 Connect – Home-Assistant-Blogprüfung")
    add(root, "updated", max((r["updated"] for r in ordered), default="1970-01-01T00:00:00Z"))
    add(add(root, "author"), "name", "Enigma2 Connect Blog-Monitor")
    add(root, "link", href=base_url + "atom.xml", rel="self", type="application/atom+xml")
    add(root, "link", href=base_url, rel="alternate", type="text/html")
    for record in ordered:
        validate_record(record, repository)
        entry = add(root, "entry")
        event = record["attempts"][-1]
        add(entry, "id", f"urn:sha256:{record['id']}")
        add(entry, "title", record["title"])
        add(entry, "published", record["published"])
        add(entry, "updated", record["updated"])
        add(entry, "link", href=article_url(record), rel="alternate", type="text/html")
        add(entry, "summary", summary(event), type="text")
        add(entry, "category", term=event["status"])
        if event.get("result"):
            add(
                entry,
                "category",
                term=event["result"]["assessment"],
                scheme="urn:enigma2-connect:impact",
            )
            add(
                entry,
                "category",
                term=event["result"]["opportunity"]["assessment"],
                scheme="urn:enigma2-connect:opportunity",
            )
        add(entry, "content", render_content(record, repository), type="html")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode() + "\n"


def public_files(records, repository, base_url):
    feed = render_atom(records, repository, base_url)
    updated = max((r["updated"] for r in records.values()), default="1970-01-01T00:00:00Z")
    page = (
        '<!doctype html><html lang="de"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex">'
        '<link rel="alternate" type="application/atom+xml" href="atom.xml">'
        "<title>Enigma2 Connect Blogprüfung</title><body>"
        '<h1>Home-Assistant-Blogprüfung</h1><p><a href="atom.xml">Atom-Feed abonnieren</a></p>'
        f"<p>{len(records)} Beiträge. Letzte Datenänderung: {html.escape(updated)}</p>"
        "<p>Der Feed enthält Bewertungen, Ergebnisse ohne Handlungsbedarf, Fehler und "
        "Wiederholungen. Bestehende Einträge werden aktualisiert. "
        "Automatische Bewertungen ersetzen keine Kompatibilitätsprüfung.</p></body></html>\n"
    )
    return {"atom.xml": feed, "index.html": page, ".nojekyll": ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, default=Path(".work/blog-monitor/feed"))
    parser.add_argument("--implementations", type=Path)
    parser.add_argument("--history-dir", type=Path)
    args = parser.parse_args()
    repository, revision = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"]
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository) or not re.fullmatch(
        r"[a-f0-9]{40}", revision
    ):
        raise ValueError("Invalid repository identity")

    def request(endpoint, payload=None, **kwargs):
        return common.github_request(
            repository, os.environ["GH_TOKEN"], endpoint, payload, **kwargs
        )

    store = FeedState(request, revision, repository)
    state = store.load()
    if args.history_dir:
        directory = args.history_dir
        imported = import_history(
            store,
            state,
            json.loads((directory / "posts.json").read_text(encoding="utf-8")),
            [
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((directory / "reports").glob("*.json"))
            ],
            json.loads((directory / "issues.json").read_text(encoding="utf-8")),
            json.loads((directory / "prs.json").read_text(encoding="utf-8"))
            if (directory / "prs.json").exists()
            else (),
        )
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "import-report.json").write_text(json_text(imported), encoding="utf-8")
    store.reconcile()
    if args.implementations:
        for path in sorted(args.implementations.glob("publication-*.json")):
            if path.is_symlink() or path.stat().st_size > 30000:
                raise ValueError("Invalid publication artifact")
            apply_implementation(store, json.loads(path.read_text(encoding="utf-8")))
    store.reconcile_implementations()
    # Render and validate everything before changing either branch.
    files = public_files(store.records, repository, args.base_url)
    args.output.mkdir(parents=True, exist_ok=True)
    for path, value in files.items():
        (args.output / path).write_text(value, encoding="utf-8")
    if args.publish:
        if os.environ.get("GITHUB_REF_NAME") != os.environ.get("DEFAULT_BRANCH", "main"):
            raise ValueError("Feed publication requires the default branch")
        store.save(state)
        branch = Branch(request, PUBLIC_BRANCH, revision)
        branch.load()
        branch.commit(files, "Update Home Assistant blog Atom feed [skip ci]")
        pages = request("pages")
        if (
            pages.get("source") != {"branch": PUBLIC_BRANCH, "path": "/"}
            or pages.get("build_type") != "legacy"
        ):
            raise ValueError("Pages source does not match the feed branch")
        # GITHUB_TOKEN commits do not start Pages builds implicitly.
        request("pages/builds", {}, method="POST")
    print(f"{len(store.records)} Beiträge im Atom-Feed")


if __name__ == "__main__":
    main()
