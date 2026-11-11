#!/usr/bin/env python3
"""Compare a head commit's check-run annotations with a base commit's.

A bare total is not evidence (ai-config#5281): on gha#1825 a first-page count
gave 174 against 168; over every page, per check-run name, both had 249.
This walks `&page=N` (`--paginate` 403s in CCR sessions) for check runs and
annotations on both commits, checks the counts GitHub reports, normalizes
run-to-run values, and diffs per check-run name (same-name runs pooled).
The default normalizers also hide 9+ digit numbers and hex words of 7-40
characters; pass --no-default-normalizers when that matters.

Exit 0: no difference, or every differing name passed with --explained.
Exit 1: an untraced difference. Exit 2: a failed or incomplete read, an
unfinished run on either commit, or an unknown --levels value.
"""
import argparse
import collections
import json
import re
import subprocess
import sys

PER_PAGE = 100
DEFAULT_NORMALIZERS = [
    r"\btmp\.[A-Za-z0-9]{6,}",  # mktemp directories
    r"\btmp[a-z0-9_]{8}\b",  # Python tempfile names
    r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b",  # commit shas
    r"\d{9,}",  # run, job and check-run ids
]
LEVELS = {"notice", "warning", "failure"}


class ReadError(Exception):
    pass


def gh_api(path):
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ReadError(f"gh api {path} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def check_runs(api, repo, sha):
    runs, total, page = [], None, 1
    while True:
        data = api(f"repos/{repo}/commits/{sha}/check-runs"
                   f"?per_page={PER_PAGE}&page={page}")
        total = data["total_count"]
        runs += data["check_runs"]
        if len(data["check_runs"]) < PER_PAGE:
            break
        page += 1
    if len(runs) != total:
        raise ReadError(f"{sha}: read {len(runs)} check runs, GitHub reports {total}")
    pending = [r["name"] for r in runs if r.get("status") != "completed"]
    if pending:
        raise ReadError(f"{sha}: {len(pending)} run(s) not completed, "
                        f"e.g. {pending[0]}; their annotations may not exist yet")
    return runs


def annotations(api, repo, run):
    out, page = [], 1
    while True:
        batch = api(f"repos/{repo}/check-runs/{run['id']}/annotations"
                    f"?per_page={PER_PAGE}&page={page}")
        out += batch
        if len(batch) < PER_PAGE:
            break
        page += 1
    expected = (run.get("output") or {}).get("annotations_count") or 0
    if len(out) != expected:
        raise ReadError(f"run {run['id']} ({run['name']}): read {len(out)} "
                        f"annotations, GitHub reports {expected}")
    return out


def normalize(text, patterns):
    for pattern in patterns:
        text = re.sub(pattern, "#", text)
    return text


def collect(api, repo, sha, levels, patterns):
    """Return ({name: Counter of (path, message)}, runs read, annotations read)."""
    by_name = collections.defaultdict(collections.Counter)
    runs = check_runs(api, repo, sha)
    n_ann = 0
    for run in runs:
        if not (run.get("output") or {}).get("annotations_count"):
            continue
        for ann in annotations(api, repo, run):
            n_ann += 1
            if ann["annotation_level"] in levels:
                key = (normalize(ann["path"], patterns),
                       normalize(ann["message"], patterns))
                by_name[run["name"]][key] += 1
    return by_name, len(runs), n_ann


def diff(base, head):
    """Return {name: (only on head, only on base)} for names that differ."""
    out = {}
    for name in sorted(set(base) | set(head)):
        b, h = base.get(name, collections.Counter()), head.get(name, collections.Counter())
        if b != h:
            out[name] = (h - b, b - h)
    return out


def total(by_name):
    return sum(sum(c.values()) for c in by_name.values())


def main(argv=None, api=gh_api):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", required=True, help="OWNER/REPO")
    p.add_argument("--head", required=True, help="head commit sha")
    p.add_argument("--base", required=True, help="base commit sha, e.g. main's tip")
    p.add_argument("--levels", default="failure",
                   help="comma-separated annotation levels to compare (default: failure)")
    p.add_argument("--normalize", action="append", default=[], metavar="REGEX",
                   help="extra regex whose matches vary from run to run")
    p.add_argument("--no-default-normalizers", action="store_true",
                   help="apply only --normalize patterns")
    p.add_argument("--explained", action="append", default=[], metavar="NAME",
                   help="check-run name whose difference you traced and stated in the PR")
    args = p.parse_args(argv)
    levels = set(args.levels.split(","))
    if not levels <= LEVELS:
        print(f"ERROR: unknown level(s) {sorted(levels - LEVELS)}; "
              f"use {sorted(LEVELS)}", file=sys.stderr)
        return 2
    defaults = [] if args.no_default_normalizers else DEFAULT_NORMALIZERS
    patterns = defaults + args.normalize
    try:
        base, b_runs, b_ann = collect(api, args.repo, args.base, levels, patterns)
        head, h_runs, h_ann = collect(api, args.repo, args.head, levels, patterns)
    except (ReadError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: incomplete read: {exc}", file=sys.stderr)
        return 2
    print(f"examined base {args.base[:12]}: {b_runs} runs, {b_ann} annotations, "
          f"{total(base)} at {args.levels}")
    print(f"examined head {args.head[:12]}: {h_runs} runs, {h_ann} annotations, "
          f"{total(head)} at {args.levels}")
    untraced = 0
    for name, (extra, missing) in diff(base, head).items():
        traced = name in args.explained
        untraced += not traced
        print(f"== {name}" + (" (explained)" if traced else ""))
        for (path, msg), n in extra.items():
            print(f"  +head {n} {path}: {msg}")
        for (path, msg), n in missing.items():
            print(f"  -head {n} {path}: {msg}")
    print(f"{untraced} untraced differing check-run name(s)")
    return 1 if untraced else 0


if __name__ == "__main__":
    sys.exit(main())
