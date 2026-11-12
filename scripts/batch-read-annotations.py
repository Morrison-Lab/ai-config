#!/usr/bin/env python3
"""Read the annotations on a head's check runs within the shared REST budget.

Every agent shares one core budget (ai-config#5045), so this reads runs one at
a time with a --pause, checks GET /rate_limit (free) before each, and stops
before the budget would fall below --floor, naming the reset time. Identical
messages are grouped and counted; known runner notices and fixtures are marked.
Last line: the run ids read in full, for check-pr-fully-clean.py's
--annotations-read. Exit 0 all read, 2 a failed read, 3 stopped at the floor.
"""
import argparse
import collections
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

PER_PAGE = 100

# Each pattern matches "path:line: message" and cites where it is recorded.
KNOWN = [
    # Runner-wide notice GitHub puts on every Actions job (ai-config#5045).
    ("ubuntu-latest migration notice", r"ubuntu-latest\b.*(migrat|will use ubuntu-\d)"),
    # .github/workflows/jules-review.yml, "Pin Node 24" step comment.
    ("Node.js 20 deprecation", r"Node\.js 20\b.*deprecated"),
    # gha check-markdown splice check (memories/gha-reusable-workflows.md).
    ("list-item splice skip", r"Skipping list-item merge splice check"),
    # Empty-population negative controls in check-leadin-counts.py and
    # check-reviewer-placeholders.py, exercised by their validate.yml tests.
    ("examined-0 negative control", r"examined 0 files -- the (check|gate) did not run"),
    # NEGATIVE_CONTROL fixture in scripts/test_check_leadin_counts.py.
    ("bad.md:5 lead-in fixture", r"(^|/)bad\.md:5: lead-in says"),
]


class ReadError(Exception):
    pass


def gh_api(path):
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ReadError(f"gh api {path} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def core_budget(api):
    """Return (remaining, reset as 'HH:MM UTC') from GET /rate_limit."""
    core = api("rate_limit")["resources"]["core"]
    reset = datetime.fromtimestamp(core["reset"], tz=timezone.utc)
    return core["remaining"], reset.strftime("%H:%M UTC")


def pages(api, path, key=None):
    """Every page of *path*, paged by hand (`--paginate` 403s in CCR, gha#1432)."""
    out, page = [], 1
    while True:
        data = api(f"{path}?per_page={PER_PAGE}&page={page}")
        batch = data[key] if key else data
        out += batch
        if len(batch) < PER_PAGE:
            return out
        page += 1


def annotated_runs(api, repo, sha):
    runs = pages(api, f"repos/{repo}/commits/{sha}/check-runs", "check_runs")
    return [(r["id"], r["output"]["annotations_count"]) for r in runs
            if (r.get("output") or {}).get("annotations_count")]


def known_label(ann):
    key = f"{ann['path']}:{ann.get('start_line')}: {ann['message']}"
    for label, pattern in KNOWN:
        if re.search(pattern, key):
            return label
    return None


def main(argv=None, api=gh_api, sleep=time.sleep):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", required=True, help="OWNER/REPO")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--sha", help="head commit; reads every run with annotations")
    src.add_argument("--runs", help="comma-separated check-run ids the checker listed")
    p.add_argument("--pause", type=float, default=1.0, help="seconds between runs (default 1)")
    p.add_argument("--floor", type=int, default=500,
                   help="stop before the core budget would fall below this (default 500)")
    args = p.parse_args(argv)
    try:
        if args.sha:
            runs = annotated_runs(api, args.repo, args.sha)
        else:
            runs = [(int(i), None) for i in args.runs.split(",") if i]
        groups, known, done, stopped = collections.Counter(), {}, [], None
        for n, (rid, count) in enumerate(runs):
            if n:
                sleep(args.pause)
            remaining, reset = core_budget(api)
            need = -(-count // PER_PAGE) if count else 1
            if remaining - need < args.floor:
                stopped = (remaining, reset)
                break
            for ann in pages(api, f"repos/{args.repo}/check-runs/{rid}/annotations"):
                first = (ann["message"] or "").split("\n")[0][:200]
                key = (ann["annotation_level"], first)
                groups[key] += 1
                known[key] = known.get(key) or known_label(ann)
            done.append(rid)
    except (ReadError, KeyError, ValueError) as exc:
        print(f"ERROR: incomplete read: {exc}", file=sys.stderr)
        return 2
    print(f"read {len(done)} of {len(runs)} run(s), "
          f"{sum(groups.values())} annotation(s) in {len(groups)} group(s)")
    for (level, msg), n in sorted(groups.items(), key=lambda kv: (bool(known[kv[0]]), -kv[1])):
        tag = f"known: {known[(level, msg)]}" if known[(level, msg)] else "UNKNOWN"
        print(f"{n:5d}  {level:8s} [{tag}] {msg}")
    if stopped:
        print(f"STOPPED: {stopped[0]} core request(s) left, floor {args.floor}; "
              f"budget resets at {stopped[1]}; {len(runs) - len(done)} run(s) unread",
              file=sys.stderr)
    print(",".join(str(r) for r in done))
    return 3 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
