#!/usr/bin/env python3
"""Print a Markdown digest of new commits in tracked outside repositories.

ai-config#2231, #2067.  Lists the commits since each `github` row's `baseline`
(or the state marker of the `--previous` digest) and the manual rows.  Any API or
input error exits 2, so no source is reported quiet because it was unreadable.
"""

import argparse
import csv
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = re.compile(r"<!-- tracked-sources-state: (\{.*?\}) -->")
SHA = re.compile(r"[0-9a-f]{40}")


class DigestError(Exception):
    """An input or API error that must stop the run."""


def http_fetch(api: str, token: str):
    def fetch(path: str) -> dict:
        req = urllib.request.Request(api.rstrip("/") + path)
        req.add_header("Accept", "application/vnd.github+json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except (urllib.error.URLError, http.client.HTTPException, ValueError) as exc:
            raise DigestError(f"GET {path} failed: {exc}") from exc
    return fetch


def footer_state(text: str) -> dict | None:
    """The state in a digest body's footer: its last marker, since an earlier one could only
    come from outside text.  None when the body has no marker."""
    markers = STATE.findall(text)
    return json.loads(markers[-1]) if markers else None


def read_sources(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for n, row in enumerate(rows, start=2):
        if row["kind"] == "github" and not (row["branch"] and SHA.fullmatch(row["baseline"])):
            raise DigestError(f"{path}:{n}: a github row needs a branch and a full-sha baseline")
        if row["kind"] != "github" and row["fetch"] != "manual":
            raise DigestError(f"{path}:{n}: only a github row can be fetched; mark others manual")
    return rows


MAX_SUBJECT = 200
MAX_BODY = 60000  # GitHub refuses an issue body over 65536 characters.


def inert(subject: str) -> str:
    """Render an outside commit subject so it can neither mention anyone, forge the state marker,
    nor grow past MAX_SUBJECT characters (the whole body is checked against MAX_BODY in main)."""
    if len(subject) > MAX_SUBJECT:
        subject = subject[:MAX_SUBJECT] + "..."
    return subject.replace("`", "'").replace("<!--", "< !--")


def review(row: dict, base: str, fetch, max_subjects: int) -> dict:
    repo = row["source"]
    head = fetch(f"/repos/{repo}/commits/{row['branch']}")["sha"]
    out = {"repo": repo, "head": head, "count": 0, "moved": head != base}
    if head != base:
        cmp = fetch(f"/repos/{repo}/compare/{base}...{head}")
        # An empty commit message has no first line; show it as an empty subject.
        subjects = [(c["commit"]["message"].splitlines() or [""])[0] for c in cmp["commits"]]
        out.update(count=cmp["ahead_by"], status=cmp["status"], url=cmp["html_url"],
                   subjects=subjects[-max_subjects:] if max_subjects else [])
    return out


def digest(rows: list[dict], state: dict, fetch, max_subjects: int) -> tuple[str, int, int]:
    repos = [r for r in rows if r["kind"] == "github"]
    manual = [r for r in rows if r["kind"] != "github"]
    results = [review(r, state.get(r["source"], r["baseline"]), fetch, max_subjects) for r in repos]
    total = sum(r["count"] for r in results)
    moved = [r for r in results if r["moved"]]
    lines = ["New commits in `memories/tracked-sources.csv`. Sift them into issues for ideas worth "
             "adopting, then close this issue as completed.", "",
             f"Examined {len(results)} repositories ({len(moved)} moved, {total} new commits); "
             f"listed {len(manual)} manual sources.", ""]
    # A head that moved back (status "behind") has no new commits but is still listed.
    for r in moved:
        lines.append(f"### [{r['repo']}]({r['url']}): {r['count']} new commits ({r['status']})")
        lines += [f"- `{inert(s)}`" for s in r["subjects"]]
        if r["count"] > len(r["subjects"]):
            lines.append(f"- ... and {r['count'] - len(r['subjects'])} more; see the compare link.")
        lines.append("")
    if manual:
        lines.append("### Manual sources (not fetched)")
        lines += [f"- {m['source']} ({m['fetch']}): {m['note']}" for m in manual] + [""]
    new_state = json.dumps({r["repo"]: r["head"] for r in results}, sort_keys=True)
    lines.append(f"<!-- tracked-sources-state: {new_state} -->")
    return "\n".join(lines) + "\n", total, len(moved)


def main(argv: list[str] | None = None, fetch=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sources", type=Path, default=ROOT / "memories" / "tracked-sources.csv")
    ap.add_argument("--previous", type=Path, help="body of the previous digest issue")
    ap.add_argument("--api", default="https://api.github.com")
    ap.add_argument("--token-env", default="GH_TOKEN", help="variable holding the API token")
    ap.add_argument("--max-subjects", type=int, default=20)
    ap.add_argument("--footer", type=Path,
                    help="print the footer state of this digest body as sorted JSON (empty if none) and exit")
    ap.add_argument("--github-output", type=Path,
                    help="append new_commits=<n> and moved=<repositories> to this file")
    args = ap.parse_args(argv)
    if args.max_subjects < 0:
        ap.error("--max-subjects must be 0 or more")
    try:
        if args.footer:
            found = footer_state(args.footer.read_text(encoding="utf-8"))
            print("" if found is None else json.dumps(found, sort_keys=True))
            return 0
        rows = read_sources(args.sources)
        state = footer_state(args.previous.read_text(encoding="utf-8")) if args.previous else {}
        if state is None:
            raise DigestError("the previous digest has no tracked-sources-state marker")
        bad = sorted(k for k, v in state.items() if not (isinstance(v, str) and SHA.fullmatch(v)))
        if bad:
            raise DigestError(f"the previous digest's state has a non-sha head for {bad}")
        fetch = fetch or http_fetch(args.api, os.environ.get(args.token_env, ""))
        text, total, moved = digest(rows, state, fetch, args.max_subjects)
        if len(text) > MAX_BODY:
            raise DigestError(f"the digest is {len(text)} characters, over {MAX_BODY}; "
                              "lower --max-subjects")
    except (DigestError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"tracked-sources-digest: {exc!r}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"new_commits={total}\nmoved={moved}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
