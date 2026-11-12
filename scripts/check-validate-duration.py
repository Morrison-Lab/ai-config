#!/usr/bin/env python3
"""Fail when the `validate` job on main has slowed down (ai-config#3384).

Compares the median wall time of the `validate` job over the latest RECENT
successful push runs of `validate.yml` on main with its median over BASELINE
such runs from at least LAG_DAYS earlier. It exits 1 when the recent median
is more than RATIO times the baseline median, and names the steps whose
medians grew most, so the report says where the time went.

The baseline is anchored LAG_DAYS back because main runs validate several
times an hour: a baseline of the runs just before the recent ones spans a few
hours, moves with any gradual drift, and would never have caught "Run
enforcement-hook tests" doubling between September and November 2026. With a
28-day lag, a slowdown is caught once it exceeds RATIO within four weeks.

RATIO 1.5 was set from runs measured on 2026-11-12. Over the 60 latest runs,
about a day of ordinary merges, the job's median was 708 s and its 5-run
rolling median ranged from 0.75 to 1.20 times that. Comparing with a baseline
four weeks older adds month-to-month runner variation that was not measured,
so the limit leaves room above 1.20. It still catches the rise that went
unnoticed: the same day, 25 runs from before 2026-09-15 had a median of 484 s
and 25 from before 2026-10-15 one of 925 s, 1.9 times as long. A 5-run median
also absorbs a single stalled run (#3384 records stalls of 20 to 40 minutes).

Exit codes: 0 no regression, 1 regression, 3 the check itself failed (the
GitHub API could not be read, or an unexpected error), 4 too few runs to judge.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone

DEFAULT_REPO = "Morrison-Lab/ai-config"
JOB = "validate"


def seconds(item: dict) -> float | None:
    """Wall time of a job or step from its timestamps, or None if unfinished."""
    if not item.get("started_at") or not item.get("completed_at"):
        return None
    start = datetime.fromisoformat(item["started_at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(item["completed_at"].replace("Z", "+00:00"))
    return (end - start).total_seconds()


def judge(now_runs: list[dict], old_runs: list[dict], recent: int, baseline: int,
          ratio: float) -> tuple[int, str]:
    """Compare medians; each run is {"job": seconds, "steps": {name: seconds}}."""
    if len(now_runs) < recent or len(old_runs) < baseline:
        return 4, (f"{len(now_runs)} recent and {len(old_runs)} baseline runs with a finished "
                   f"{JOB} job; need {recent} and {baseline}")
    now_runs, old_runs = now_runs[:recent], old_runs[:baseline]
    now = statistics.median(r["job"] for r in now_runs)
    before = statistics.median(r["job"] for r in old_runs)
    head = (f"{JOB} job: median of the last {recent} runs {now:.0f}s, "
            f"of {baseline} baseline runs {before:.0f}s ({now / before:.2f}x; limit {ratio}x)")
    if now <= before * ratio:
        return 0, head
    names = {name for r in now_runs + old_runs for name in r["steps"]}
    growth = []
    for name in names:  # a step missing from one side counts as 0 s there
        new = statistics.median(r["steps"].get(name, 0.0) for r in now_runs)
        old = statistics.median(r["steps"].get(name, 0.0) for r in old_runs)
        growth.append((new - old, name, old, new))
    growth.sort(reverse=True)
    lines = [f"  {name}: {old:.0f}s -> {new:.0f}s" for _, name, old, new in growth[:5]]
    return 1, "\n".join([head, "Steps that grew most:", *lines])


def gh_api(path: str) -> dict:
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def fetch(count: int, created: str = "", api=gh_api,
          repo: str = DEFAULT_REPO) -> list[dict]:
    """The `validate` job of the newest `count` successful push runs on main."""
    query = f"branch=main&event=push&status=success&per_page={count}"
    if created:
        query += f"&created=<={created}"
    runs = api(f"repos/{repo}/actions/workflows/validate.yml/runs?{query}")["workflow_runs"]
    out = []
    for run in runs:
        for job in api(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]:
            took = seconds(job)
            if job["name"] == JOB and took is not None:
                steps = {s["name"]: d for s in job.get("steps", []) if (d := seconds(s)) is not None}
                out.append({"job": took, "steps": steps})
    return out


def bounded(cast, ok, why: str):
    """An argparse type that casts its text and rejects a value `ok` refuses."""
    def parse(text: str):
        value = cast(text)
        if not ok(value):
            raise argparse.ArgumentTypeError(why)
        return value
    return parse


count_arg = bounded(int, lambda v: 1 <= v <= 100, "must be 1 to 100, the runs endpoint's page limit")
lag_arg = bounded(int, lambda v: v >= 1, "must be at least 1; a lag of 0 compares main with itself")
ratio_arg = bounded(float, lambda v: v > 1, "must be greater than 1; a lower limit flags ordinary noise")


def run(argv: list[str] | None = None, api=gh_api, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--recent", type=count_arg, default=5)
    parser.add_argument("--baseline", type=count_arg, default=25)
    parser.add_argument("--lag-days", type=lag_arg, default=28)
    parser.add_argument("--ratio", type=ratio_arg, default=1.5)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO)
    args = parser.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=args.lag_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        now_runs = fetch(args.recent, api=api, repo=args.repo)
        old_runs = fetch(args.baseline, created=cutoff, api=api, repo=args.repo)
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as err:
        print(f"could not read validate runs from the GitHub API: {err}", file=sys.stderr)
        return 3
    code, report = judge(now_runs, old_runs, args.recent, args.baseline, args.ratio)
    print(report)
    return code


def main() -> int:
    """Exit 3 on any failure of the check itself, never 1, which means a regression."""
    try:
        return run()
    except SystemExit as stop:  # argparse usage errors exit 2
        return 3 if stop.code else 0
    except Exception:  # noqa: BLE001 -- reported below and mapped to exit 3, not hidden
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
