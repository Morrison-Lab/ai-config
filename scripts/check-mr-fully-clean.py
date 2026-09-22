#!/usr/bin/env python3
"""Verify the GitLab equivalent of the fully-clean merge gate.

The instrument checks the current MR head, every pipeline on that SHA,
current-head automated verdicts, unresolved diff notes, and base currency.
It accepts a pre-fetched JSON payload so remote sessions can gather through
their GitLab connector while this script remains the single verdict authority.

Exit codes match ``check-pr-fully-clean.py``: 0 is fully clean, 1 is a real
not-clean verdict, and 2 is an unusable invocation or incomplete payload.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

USAGE_EXIT = 2
HERE = Path(__file__).resolve().parent


def _load_pr_checker():
    path = HERE / "check-pr-fully-clean.py"
    spec = importlib.util.spec_from_file_location("check_pr_fully_clean", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PR = _load_pr_checker()


def die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(USAGE_EXIT)


def _run_glab(args: list[str]) -> object:
    try:
        result = subprocess.run(
            ["glab", "api", *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        die("glab is required unless --from-json supplies a payload")
    except subprocess.CalledProcessError as exc:
        die(f"glab api failed: {exc.stderr.strip() or exc.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        die(f"glab returned invalid JSON: {exc}")


def _pages(path: str, query: list[str] | None = None) -> list[dict]:
    """Read every page without relying on glab's concatenated JSON output."""
    base = list(query or [])
    result: list[dict] = []
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        page_path = f"{path}{separator}per_page=100&page={page}"
        value = _run_glab([page_path, *base])
        if not isinstance(value, list):
            die(f"GitLab endpoint did not return a list: {path}")
        result.extend(value)
        if len(value) < 100:
            return result
        page += 1


def _payload_value(payload: dict, key: str, expected: type):
    value = payload.get(key)
    if not isinstance(value, expected):
        die(f"payload key {key!r} is missing or has the wrong type")
    return value


def _head_is_named(body: str, sha: str, position: dict | None) -> bool:
    short = sha[:8]
    return sha in body or short in body or (position or {}).get("head_sha") == sha


def _is_clean(body: str, author: str) -> bool:
    return _PR.classify_verdict(body, "", author) == "clean"


def _identity(body: str, author: str) -> str:
    return _PR._reviewer_identity(body, author)


def _note_time(note: dict) -> str:
    return str(note.get("created_at") or "")


def _note_author(note: dict) -> str:
    author = note.get("author") or {}
    return str(author.get("username") or author.get("name") or "unknown")


def _check_pipelines(pipelines: list[dict], sha: str) -> list[str]:
    if not pipelines:
        return [f"No GitLab pipelines found for HEAD SHA {sha[:8]}."]
    matching = [pipeline for pipeline in pipelines if pipeline.get("sha") in (None, sha)]
    if not matching:
        return [f"No GitLab pipelines found for HEAD SHA {sha[:8]}."]
    issues = []
    allowed = {"success", "skipped"}
    for pipeline in matching:
        status = str(pipeline.get("status") or "unknown")
        if pipeline.get("sha") not in (None, sha):
            continue
        if status not in allowed:
            issues.append(
                f"Pipeline {pipeline.get('id', '?')} for HEAD {sha[:8]} is {status}."
            )
    return issues


def _check_notes(notes: list[dict], discussions: list[dict], sha: str, quorum: int) -> list[str]:
    issues: list[str] = []
    current_clean: set[str] = set()
    latest: dict[str, tuple[str, str]] = {}

    for note in notes:
        body = str(note.get("body") or "")
        author = _note_author(note)
        identity = _identity(body, author)
        verdict = _PR.classify_verdict(body, "", author)
        if verdict in ("clean", "not-clean"):
            prior = latest.get(identity)
            stamp = _note_time(note)
            if prior is None or stamp >= prior[1]:
                latest[identity] = (verdict, stamp)
        if verdict == "clean" and _head_is_named(body, sha, note.get("position")):
            current_clean.add(identity)

    unresolved = []
    for note in notes:
        if note.get("resolvable") and not note.get("resolved"):
            body = str(note.get("body") or "")
            author = _note_author(note)
            # GitLab marks an automated clean summary as resolvable too.
            # An unresolved clean verdict is not an actionable finding; an
            # unresolved note with no clean verdict remains blocking.
            if not _is_clean(body, author):
                unresolved.append(str(note.get("id", "unknown")))
    for discussion in discussions:
        for note in discussion.get("notes") or []:
            if note.get("resolvable") and not note.get("resolved"):
                body = str(note.get("body") or "")
                author = _note_author(note)
                if not _is_clean(body, author):
                    unresolved.append(str(note.get("id", "unknown")))
    if unresolved:
        issues.append("Unresolved GitLab diff note(s): " + ", ".join(unresolved) + ".")

    standing = [identity for identity, (verdict, _) in latest.items() if verdict != "clean"]
    if standing:
        issues.append("Standing reviewer verdict(s) are not clean: " + ", ".join(sorted(standing)) + ".")
    if len(current_clean) < quorum:
        issues.append(
            f"Clean current-head quorum not met: expected {quorum}, found {len(current_clean)}."
        )
    return issues


def _check_currency(payload: dict, sha: str) -> list[str]:
    if "base_ancestor" not in payload:
        die("payload key 'base_ancestor' is required; currency must fail closed")
    if payload["base_ancestor"] is not True:
        return ["Target branch tip is not an ancestor of the MR head."]
    return []


def _live_payload(project: str, iid: str) -> dict:
    encoded = quote(project, safe="")
    mr = _run_glab([f"projects/{encoded}/merge_requests/{iid}"])
    if not isinstance(mr, dict):
        die("GitLab merge request response is not an object")
    sha = mr.get("sha")
    if not isinstance(sha, str) or not sha:
        die("GitLab merge request has no current head SHA")
    pipelines = _pages(f"projects/{encoded}/pipelines?sha={quote(sha, safe='')}")
    notes = _pages(f"projects/{encoded}/merge_requests/{iid}/notes")
    discussions = _pages(f"projects/{encoded}/merge_requests/{iid}/discussions")
    return {"project": project, "iid": iid, "mr": mr, "pipelines": pipelines,
            "notes": notes, "discussions": discussions}


def _local_base_ancestor(target_branch: str, sha: str) -> bool:
    """Prove target currency from a local checkout, failing closed if absent."""
    refs = [target_branch, f"origin/{target_branch}", f"refs/remotes/origin/{target_branch}"]
    for ref in refs:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ref, sha],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True
        if result.returncode == 1:
            return False
    die(
        f"cannot prove that target branch {target_branch!r} is an ancestor of {sha[:8]}; "
        "fetch the target branch or pass a gathered payload"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="check-mr-fully-clean.py")
    parser.add_argument("iid", help="GitLab merge request IID")
    parser.add_argument("--project", "-p", required=True, help="GitLab project ID or URL-encoded path")
    parser.add_argument("--quorum", type=int, default=1)
    parser.add_argument("--from-json", default="", metavar="FILE")
    parser.add_argument(
        "--base-ancestor", choices=("yes", "no"),
        help="Override the local currency result from merge-base",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.quorum < 0:
        die("quorum must be >= 0")
    if args.from_json:
        try:
            payload = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            die(f"--from-json payload is unusable: {exc}")
    else:
        payload = _live_payload(args.project, args.iid)

    mr = _payload_value(payload, "mr", dict)
    sha = mr.get("sha")
    if not isinstance(sha, str) or not sha:
        die("payload mr.sha is required")
    if str(mr.get("iid")) != str(args.iid):
        die("payload MR IID does not match the requested IID")
    if mr.get("state") not in ("opened", "reopened"):
        return _report(1, f"MR is not open (state={mr.get('state')!r}).")
    if mr.get("draft"):
        return _report(1, "MR is still a draft.")
    if mr.get("has_conflicts") is True:
        return _report(1, "MR has merge conflicts.")
    if mr.get("detailed_merge_status") in {"conflict", "broken_status", "not_open"}:
        return _report(1, f"MR detailed merge status is {mr['detailed_merge_status']}.")

    if not args.from_json:
        if args.base_ancestor is None:
            target = mr.get("target_branch")
            if not isinstance(target, str) or not target:
                die("GitLab merge request has no target branch for the currency check")
            payload["base_ancestor"] = _local_base_ancestor(target, sha)
        else:
            payload["base_ancestor"] = args.base_ancestor == "yes"

    issues = []
    issues.extend(_check_pipelines(_payload_value(payload, "pipelines", list), sha))
    issues.extend(_check_notes(
        _payload_value(payload, "notes", list),
        _payload_value(payload, "discussions", list), sha, args.quorum,
    ))
    issues.extend(_check_currency(payload, sha))

    # A live caller must re-read the head after all checks. Payload callers
    # must provide the same proof explicitly rather than pretending a stale
    # read is current.
    if args.from_json:
        if payload.get("head_rechecked") is not True:
            issues.append("MR head was not re-read after the clean checks.")
        if payload.get("head_rechecked_sha") not in (None, sha):
            issues.append("MR head changed during the clean checks.")
    else:
        final_mr = _run_glab([f"projects/{quote(args.project, safe='')}/merge_requests/{args.iid}"])
        if not isinstance(final_mr, dict) or final_mr.get("sha") != sha:
            issues.append("MR head changed during the clean checks.")

    if issues:
        print(f"MR !{args.iid} is NOT fully clean on HEAD {sha[:8]}:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(f"MR !{args.iid} is FULLY CLEAN on HEAD {sha[:8]}.")
    print(f"Pinned merge SHA: {sha}")
    return 0


def _report(code: int, message: str) -> int:
    print(message)
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail closed as payload/forge data, not verdict
        die(f"instrument failed closed: {type(exc).__name__}: {exc}")
