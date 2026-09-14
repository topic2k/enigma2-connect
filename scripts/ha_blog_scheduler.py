# SPDX-License-Identifier: Apache-2.0
"""Weekly blog review with durable, per-content retries on the following UTC day."""

import argparse
import base64
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

try:
    from . import ha_blog_gemini as gemini
except ImportError:
    import ha_blog_gemini as gemini

STATE_BRANCH = "ha-blog-monitor-state"
STATE_PATH = ".github/ha-blog-state.json"
MAX_STATE_BYTES = 1_000_000
ERRORS = (HTTPError, URLError, ValueError, OSError, KeyError, TypeError)


class InfrastructureError(Exception):
    """A prerequisite failed before durable per-post processing was possible."""


def error_detail(stage, error):
    """Use only fixed stage names and error codes, never server bodies or secrets."""
    detail = f"HTTP {error.code}" if isinstance(error, HTTPError) else type(error).__name__
    return f"{stage}: {detail}"


def validate_state(state):
    if not isinstance(state, dict) or state.get("version") != 1:
        raise ValueError("Unsupported retry state")
    entries = state.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("Invalid retry entries")
    for key, entry in entries.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("post"), dict):
            raise ValueError("Invalid retry entry")
        post = entry["post"]
        if any(not isinstance(post.get(field), str) for field in ("path", "title", "text", "date")):
            raise ValueError("Invalid stored post")
        if key != gemini.post_id(post) or not re.fullmatch(
            r"[a-f0-9]{40}", entry.get("upstream", "")
        ):
            raise ValueError("Invalid stored source identity")
        if type(entry.get("attempts")) is not int or entry["attempts"] < 1:
            raise ValueError("Invalid attempt count")
        last = date.fromisoformat(entry["last_attempt"])
        if entry["attempts"] == 1:
            if date.fromisoformat(entry["due"]) != last + timedelta(days=1):
                raise ValueError("Invalid retry date")
        elif entry.get("due") is not None:
            raise ValueError("Exhausted entry cannot have a retry date")
    return state


class GithubState:
    """Store only retry metadata and public blog text on a dedicated branch."""

    def __init__(self, request, revision):
        self.request = request
        self.revision = revision
        self.sha = None
        self.branch_exists = True

    def load(self):
        try:
            response = self.request(f"contents/{STATE_PATH}?ref={STATE_BRANCH}")
        except HTTPError as error:
            if error.code != 404:
                raise
            try:
                self.request(f"git/ref/heads/{STATE_BRANCH}")
            except HTTPError as branch_error:
                if branch_error.code != 404:
                    raise
                self.branch_exists = False
            return {"version": 1, "entries": {}}
        self.sha = response["sha"]
        raw = base64.b64decode(response["content"])
        if len(raw) > MAX_STATE_BYTES:
            raise ValueError("Retry state exceeds size limit")
        return validate_state(json.loads(raw))

    def save(self, state):
        validate_state(state)
        raw = json.dumps(state, ensure_ascii=False, indent=2).encode()
        if len(raw) > MAX_STATE_BYTES:
            raise ValueError("Retry state exceeds size limit")
        if not self.branch_exists:
            self.request("git/refs", {"ref": f"refs/heads/{STATE_BRANCH}", "sha": self.revision})
            self.branch_exists = True
        payload = {
            "message": "Update Home Assistant blog retry state [skip ci]",
            "branch": STATE_BRANCH,
            "content": base64.b64encode(raw).decode(),
        }
        if self.sha:
            payload["sha"] = self.sha
        response = self.request(f"contents/{STATE_PATH}", payload, method="PUT")
        self.sha = response["content"]["sha"]


def eligible_posts(posts, state, known, today, *, retry_only=False, retry_failed=False):
    """Retry stored content first; daily wake-ups never admit unseen posts."""
    entries = state["entries"]
    candidates = []
    for key, entry in sorted(entries.items(), key=lambda item: (item[1]["last_attempt"], item[0])):
        if key in known:
            continue
        if entry["attempts"] == 1 and date.fromisoformat(entry["due"]) <= today:
            candidates.append(entry["post"])
        elif retry_failed and entry["attempts"] >= 2:
            candidates.append(entry["post"])
    if not retry_only:
        candidates.extend(
            p for p in posts if gemini.post_id(p) not in entries and gemini.post_id(p) not in known
        )
    return candidates


def partial_results(data, posts, sources):
    """Keep independently valid answers even if another post is missing or invalid."""
    values = data.get("results") if isinstance(data, dict) else None
    if not isinstance(values, list):
        return [], {
            gemini.post_id(p): "Antwortvalidierung: fehlender Ergebnisstapel" for p in posts
        }
    valid, failures = [], {}
    for post in posts:
        key = gemini.post_id(post)
        matches = [v for v in values if isinstance(v, dict) and v.get("id") == key]
        try:
            valid.extend(gemini.validate_results({"results": matches}, [post], sources))
        except ERRORS as error:
            failures[key] = error_detail("Antwortvalidierung", error)
    return valid, failures


def process(
    posts,
    sources,
    state,
    known,
    today,
    store,
    generate,
    publish,
    repository,
    revision,
    upstream,
    *,
    retry_only=False,
    retry_failed=False,
):
    """One bounded AI request; persist attempts before work to survive interrupted runs."""
    for key in known:
        state["entries"].pop(key, None)
    candidates = eligible_posts(
        posts, state, known, today, retry_only=retry_only, retry_failed=retry_failed
    )
    selection_error = None
    try:
        selected, prompt, deferred = gemini.select_batch(candidates, set(), sources)
    except ValueError as error:
        # A single oversized post must get the same next-day policy, without an AI call.
        selected, prompt, deferred = candidates[:1], "", max(len(candidates) - 1, 0)
        selection_error = error
    if not selected:
        return {
            "results": [],
            "retry_pending": [],
            "failed": [],
            "selected": [],
            "deferred": 0,
            "summary": "Keine fälligen Beiträge; keine Gemini-Anfrage.\n",
        }
    # Reserve each attempt durably. A same-day rerun must not consume another attempt.
    for post in selected:
        key = gemini.post_id(post)
        old = state["entries"].get(key, {})
        attempts = old.get("attempts", 0) + 1
        state["entries"][key] = {
            "post": post,
            "upstream": old.get("upstream", upstream),
            "attempts": attempts,
            "last_attempt": today.isoformat(),
            "due": (today + timedelta(days=1)).isoformat() if attempts == 1 else None,
            "error": "Versuch gestartet; Abschluss noch nicht gespeichert",
        }
    try:
        store.save(state)
    except ERRORS as error:
        raise InfrastructureError(error_detail("GitHub-Status speichern", error)) from None
    report = {
        "model": gemini.MODEL,
        "selected": [p["path"] for p in selected],
        "input_bytes": len((gemini.INSTRUCTIONS + prompt).encode()),
        "deferred": deferred,
        "revision": revision,
        "results": [],
        "usage": {},
    }
    try:
        if selection_error:
            raise selection_error
        data, usage = generate(prompt)
        results, failures = partial_results(data, selected, sources)
        report.update(results=results, usage=usage)
    except ERRORS as error:
        results = []
        stage = "Eingabegröße" if selection_error else "Gemini-Anfrage"
        failures = {gemini.post_id(p): error_detail(stage, error) for p in selected}
    summaries = []
    if results:
        successful = {r["id"] for r in results}
        valid_posts = [p for p in selected if gemini.post_id(p) in successful]
        # Retries use the original blog revision so their stored text and source link agree.
        revisions = {
            gemini.post_id(p): state["entries"][gemini.post_id(p)]["upstream"] for p in valid_posts
        }
        try:
            summary = gemini.render_report(
                valid_posts, results, repository, revision, revisions, deferred
            )
            issue = publish(
                {
                    "title": f"[HA-Blog] Prüfung {today}: {len(valid_posts)} Beiträge",
                    "body": summary,
                }
            )
            report["issue_url"] = issue["html_url"]
            summaries.append(summary)
            for key in successful:
                del state["entries"][key]
        except ERRORS as error:
            failures.update(
                {key: error_detail("GitHub-Bericht veröffentlichen", error) for key in successful}
            )
    pending, failed = [], []
    for post in selected:
        key = gemini.post_id(post)
        if key not in failures:
            continue
        entry = state["entries"][key]
        entry["error"] = failures[key]
        item = {
            "id": key,
            "path": post["path"],
            "attempts": entry["attempts"],
            "due": entry["due"],
            "error": failures[key],
        }
        (pending if entry["attempts"] == 1 else failed).append(item)
    try:
        store.save(state)
    except ERRORS as error:
        raise InfrastructureError(error_detail("GitHub-Status speichern", error)) from None
    for title, items in (
        ("Wiederholung am Folgetag vorgemerkt", pending),
        ("Erneut fehlgeschlagen – manuell prüfen", failed),
    ):
        if items:
            summaries.extend(["", f"## {title}", ""])
            for item in items:
                due = f"; fällig ab {item['due']} UTC" if item["due"] else ""
                summaries.append(
                    f"- {gemini.inline(item['path'])}: Versuch {item['attempts']}, {item['error']}{due}"
                )
    report.update(retry_pending=pending, failed=failed, summary="\n".join(summaries) + "\n")
    return report


def run(args):
    # Manual dry runs keep the existing side-effect-free behavior and do not spend retry attempts.
    if not args.publish:
        if args.retry_only or args.retry_failed:
            raise ValueError("Retry mode requires publishing")
        return gemini.run(args)
    repository = os.environ.get("GITHUB_REPOSITORY", "topic2k/enigma2-connect")
    token = os.environ.get("GH_TOKEN")
    revision, upstream = os.environ.get("GITHUB_SHA", ""), os.environ.get("BLOG_SHA", "")
    if (
        not token
        or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository)
        or not all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (revision, upstream))
    ):
        raise InfrastructureError("GitHub-Konfiguration: Token oder Commit-Identität fehlt")

    def request(endpoint, payload=None, **kwargs):
        return gemini.github_request(repository, token, endpoint, payload, **kwargs)

    today = datetime.now(timezone.utc).date()
    store = GithubState(request, revision)
    try:
        known = gemini.reviewed_ids(request)
        state = store.load()
    except ERRORS as error:
        raise InfrastructureError(error_detail("GitHub-Status lesen", error)) from None
    # Daily retries work from saved blog text, including posts since edited or deleted upstream.
    posts = [] if args.retry_only else gemini.read_posts(args.blog_dir, args.since, today)
    sources = gemini.source_snapshot(args.root)

    def generate(prompt):
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("Missing Gemini key")
        return gemini.generate(prompt, key)

    report = process(
        posts,
        sources,
        state,
        known,
        today,
        store,
        generate,
        lambda payload: request("issues", payload),
        repository,
        revision,
        upstream,
        retry_only=args.retry_only,
        retry_failed=args.retry_failed,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "summary.md").write_text(report["summary"], encoding="utf-8")
    gemini.append_summary(report["summary"])
    if report["failed"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blog-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--since", type=date.fromisoformat, default=date.fromisoformat(gemini.DEFAULT_SINCE)
    )
    parser.add_argument("--output-dir", type=Path, default=Path(".work/blog-monitor/gemini-report"))
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--retry-only", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    args.prepare_only = False
    try:
        run(args)
    except (InfrastructureError, *ERRORS) as error:
        detail = (
            str(error)
            if isinstance(error, InfrastructureError)
            else error_detail("Vorbereitung", error)
        )
        summary = f"Blogprüfung konnte keinen verlässlichen Bearbeitungsstand sichern ({detail}).\n"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "error.md").write_text(summary, encoding="utf-8")
        gemini.append_summary(summary)
        print(summary)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
