#!/usr/bin/env python3
"""Read the annotations on a head's check runs within the shared REST budget.

One budget is shared (ai-config#5045): runs are read one at a time with a
--pause, and the read stops above --floor (GET /rate_limit is free). Messages
are grouped; a group is known only if every member is, and each unknown
member's path:line is printed. Last line: ids for --annotations-read.
Exit 0 all read; 2 a failed, unfinished or short read; 3 stopped at the floor."""
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
    # Runner-wide notices (ai-config#5045): path .github, at a line that varies by job.
    ("ubuntu-latest migration notice", r'^\.github:\d+: "?The ubuntu-latest label will migrate to Ubuntu'),
    # .github/workflows/jules-review.yml, "Pin Node 24" step comment.
    ("Node.js 20 deprecation", r"^\.github:\d+: Node\.js 20 is deprecated\. "),
    # gha check-markdown splice check (memories/gha-reusable-workflows.md).
    ("list-item splice skip", r"Skipping list-item merge splice check"),
    # Negative controls in check-leadin-counts.py and check-reviewer-placeholders.py.
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


def known_label(ann):
    key = f"{ann['path']}:{ann.get('start_line')}: {ann['message']}"
    for label, pattern in KNOWN:
        if re.search(pattern, key):
            return label
    return None


def main(argv=None, api=gh_api, sleep=time.sleep):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", required=True, help="OWNER/REPO")
    p.add_argument("--sha", required=True, help="head commit; reads every run with annotations")
    p.add_argument("--pause", type=float, default=1.0, help="seconds between runs (default 1)")
    p.add_argument("--floor", type=int, default=500,
                   help="stop before the core budget would fall below this (default 500)")
    args = p.parse_args(argv)
    groups = collections.defaultdict(lambda: {"n": 0, "labels": set(), "unknown": []})
    done, bad, stopped = [], [], None
    try:
        runs = [r for r in pages(api, f"repos/{args.repo}/commits/{args.sha}/check-runs",
                                 "check_runs")
                if (r.get("output") or {}).get("annotations_count")]
        bad = [f"run {r['id']} is {r.get('status')}; its annotations may not exist yet"
               for r in runs if r.get("status") != "completed"]
        for n, run in enumerate(r for r in runs if r.get("status") == "completed"):
            rid, count = run["id"], run["output"]["annotations_count"]
            if n:
                sleep(args.pause)
            remaining, reset = core_budget(api)
            if remaining - -(-count // PER_PAGE) < args.floor:
                stopped = (remaining, reset)
                break
            anns = pages(api, f"repos/{args.repo}/check-runs/{rid}/annotations")
            for ann in anns:
                g = groups[(ann["annotation_level"], (ann["message"] or "").split("\n")[0][:200])]
                g["n"] += 1
                label = known_label(ann)
                if label:
                    g["labels"].add(label)
                else:
                    g["unknown"].append(f"{ann['path']}:{ann.get('start_line')}")
            if len(anns) != count:
                bad.append(f"run {rid}: read {len(anns)} annotations, GitHub reports {count}")
            else:
                done.append(rid)
    except (ReadError, KeyError, ValueError) as exc:
        print(f"ERROR: incomplete read: {exc}", file=sys.stderr)
        return 2
    print(f"read {len(done)} of {len(runs)} run(s), "
          f"{sum(g['n'] for g in groups.values())} annotation(s) in {len(groups)} group(s)")
    for (level, msg), g in sorted(groups.items(), key=lambda kv: (not kv[1]["unknown"], -kv[1]["n"])):
        tag = "UNKNOWN" if g["unknown"] else "known: " + ", ".join(sorted(g["labels"]))
        print(f"{g['n']:5d}  {level:8s} [{tag}] {msg}")
        for where in g["unknown"]:
            print(f"         at {where}")
    for why in bad:
        print(f"INCOMPLETE: {why}; not listed for --annotations-read", file=sys.stderr)
    if stopped:
        print(f"STOPPED: {stopped[0]} core request(s) left, floor {args.floor}; "
              f"budget resets at {stopped[1]}; {len(runs) - len(done) - len(bad)} run(s) unread",
              file=sys.stderr)
    print(",".join(str(r) for r in done))
    return 3 if stopped else 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
