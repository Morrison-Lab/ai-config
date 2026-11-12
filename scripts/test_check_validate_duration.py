#!/usr/bin/env python3
"""Tests for scripts/check-validate-duration.py (ai-config#3384)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_validate_duration", Path(__file__).resolve().parent / "check-validate-duration.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["check_validate_duration"] = mod
spec.loader.exec_module(mod)

failures = 0
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures, total
    total += 1
    print(("PASS: " if ok else "FAIL: ") + name + ("" if ok else f" -- {detail}"))
    failures += 0 if ok else 1


def runs(job_seconds: list[float], hook_seconds: list[float]) -> list[dict]:
    return [{"job": j, "steps": {"Run enforcement-hook tests": h, "Lint": 10.0}}
            for j, h in zip(job_seconds, hook_seconds)]


def judge(now: list[dict], old: list[dict], ratio: float = 1.5) -> tuple[int, str]:
    return mod.judge(now, old, recent=5, baseline=25, ratio=ratio)


old = runs([700] * 25, [500] * 25)
code, report = judge(runs([700] * 5, [500] * 5), old)
check("steady durations pass", code == 0, report)

code, report = judge(runs([1100] * 5, [800] * 5), old)
check("a 1.57x slowdown fails", code == 1, report)
check("the report names the step that grew", "Run enforcement-hook tests: 500s -> 800s" in report, report)
check("a step that did not grow is listed after it",
      report.index("enforcement-hook") < report.index("Lint"), report)

check("exactly at the limit passes", judge(runs([1050] * 5, [500] * 5), old)[0] == 0)
check("just past the limit fails", judge(runs([1051] * 5, [500] * 5), old)[0] == 1)
check("a zero baseline median is judged, not a crash", judge(runs([1] * 5, [0] * 5), runs([0] * 25, [0] * 25))[0] == 1)

code, report = judge(runs([3000, 700, 700, 700, 700], [500] * 5), old)
check("one 50-minute stall does not fail the check", code == 0, report)

code, report = judge(runs([700] * 5 + [2000] * 5, [500] * 10), old + runs([100] * 25, [500] * 25))
check("only the first RECENT and BASELINE runs count", code == 0, report)

added = [{"job": 1100, "steps": {"Run enforcement-hook tests": 500, "Lint": 10, "New slow step": 300}}] * 5
code, report = judge(added, old)
check("a step new since the baseline is named first", code == 1
      and report.splitlines()[2] == "  New slow step: 0s -> 300s", report)

removed = [{"job": 700, "steps": {"Run enforcement-hook tests": 500, "Lint": 10, "Old step": 50}}] * 25
code, report = judge(runs([1100] * 5, [800] * 5), removed)
check("a step dropped since the baseline is listed", "  Old step: 50s -> 0s" in report, report)

code, report = judge(runs([700] * 5, [500] * 5), old[:10])
check("too few baseline runs exits 4", code == 4 and "10 baseline runs" in report, report)
code, report = judge(runs([700] * 3, [500] * 3), old)
check("too few recent runs exits 4", code == 4 and "3 recent" in report, report)

check("seconds() reads GitHub timestamps",
      mod.seconds({"started_at": "2026-11-12T05:00:00Z", "completed_at": "2026-11-12T05:11:32Z"}) == 692.0)
check("seconds() is None for an unfinished job", mod.seconds({"started_at": "x", "completed_at": None}) is None)


def step(name: str, done: str | None) -> dict:
    return {"name": name, "started_at": "2026-11-12T05:00:00Z", "completed_at": done}


calls: list[str] = []


def fake_api(path: str) -> dict:
    calls.append(path)
    if "/workflows/" in path:
        return {"workflow_runs": [{"id": 1}, {"id": 2}]}
    if path.endswith("/runs/1/jobs?per_page=100"):
        return {"jobs": [
            {"name": "lint-qmd", "started_at": "2026-11-12T05:00:00Z", "completed_at": "2026-11-12T05:01:00Z"},
            {"name": "validate", "started_at": "2026-11-12T05:00:00Z", "completed_at": "2026-11-12T05:10:00Z",
             "steps": [step("Lint", "2026-11-12T05:00:10Z"), step("Skipped", None)]}]}
    return {"jobs": [{"name": "validate", "started_at": "2026-11-12T05:00:00Z", "completed_at": None}]}


got = mod.fetch(30, created="2026-10-15", api=fake_api)
check("fetch keeps only the finished validate job", got == [{"job": 600.0, "steps": {"Lint": 10.0}}], str(got))
check("fetch asks for successful push runs on main before the cutoff",
      "branch=main&event=push&status=success&per_page=30&created=<=2026-10-15" in calls[0], calls[0])

calls.clear()
code = mod.run([], api=fake_api, now=mod.datetime(2026, 11, 12, 6, 30, tzinfo=mod.timezone.utc))
check("run() reports too few runs from the fixture", code == 4, str(code))
check("only the baseline query carries the cutoff, to the second, 28 days back",
      "created" not in calls[0] and "&created=<=2026-10-15T06:30:00Z" in calls[3], str(calls))
check("run() asks for 5 recent and 25 baseline runs by default",
      "per_page=5&" in calls[0] + "&" and "per_page=25&" in calls[3], str(calls))

calls.clear()
mod.run(["--lag-days", "7", "--repo", "o/r"], api=fake_api,
        now=mod.datetime(2026, 11, 12, 6, 30, tzinfo=mod.timezone.utc))
check("--lag-days moves the cutoff", "&created=<=2026-11-05T06:30:00Z" in calls[3], str(calls))
check("--repo names the repository queried", all(c.startswith("repos/o/r/") for c in calls), str(calls))


def failing_api(path: str) -> dict:
    raise mod.subprocess.CalledProcessError(1, ["gh", "api", path])


check("an API failure exits 3", mod.run([], api=failing_api) == 3)
for name, bad in (("count_arg", "0"), ("count_arg", "101"), ("lag_arg", "0"), ("ratio_arg", "1"), ("ratio_arg", "0.9")):
    try:
        getattr(mod, name)(bad)
        rejected = False
    except mod.argparse.ArgumentTypeError:
        rejected = True
    check(f"{name} rejects {bad}", rejected)


def timed_api(recent_seconds: int):
    """Recent runs take `recent_seconds`, baseline runs (those with a cutoff) 700 s."""
    def api(path: str) -> dict:
        if "/workflows/" in path:
            base = 1000 if "created" in path else 0
            return {"workflow_runs": [{"id": base + i} for i in range(25 if base else 5)]}
        took = 700 if int(path.split("/runs/")[1].split("/")[0]) >= 1000 else recent_seconds
        end = mod.datetime(2026, 11, 12, 5, 0, tzinfo=mod.timezone.utc) + mod.timedelta(seconds=took)
        return {"jobs": [{"name": "validate", "started_at": "2026-11-12T05:00:00Z",
                          "completed_at": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "steps": []}]}
    return api


check("the default ratio is 1.5: 1050 s against 700 s passes", mod.run([], api=timed_api(1050)) == 0)
check("the default ratio is 1.5: 1051 s against 700 s fails", mod.run([], api=timed_api(1051)) == 1)
mod.run, real_run = (lambda: 1 / 0), mod.run
check("an unexpected error exits 3, not 1", mod.main() == 3)
mod.run = real_run
sys.argv, real_argv = ["check-validate-duration.py", "--recent", "0"], sys.argv
check("a usage error exits 3, not argparse's 2", mod.main() == 3)
sys.argv = real_argv

print(f"\n{total - failures} passed, {failures} failed")
sys.exit(1 if failures else 0)
