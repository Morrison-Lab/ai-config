#!/usr/bin/env python3
"""Tests for lib/annotation_cache.py, against a fake API (ai-config#6032)."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import annotation_cache as ac  # noqa: E402

passes = failures = 0


def check(name, condition):
    global passes, failures
    print(("PASS: " if condition else "FAIL: ") + name)
    passes += bool(condition)
    failures += not condition


def ann(msg, level="warning", path="a.qmd"):
    return {"annotation_level": level, "path": path, "message": msg}


def fake_api(runs, anns, calls):
    """runs: list of check-run dicts; anns: {run id: [annotation]}."""

    def api(path):
        calls.append(path)
        query = dict(kv.split("=") for kv in path.split("?")[1].split("&"))
        page, per = int(query["page"]), int(query["per_page"])
        lo, hi = (page - 1) * per, page * per
        if "/commits/" in path:
            return {"check_runs": runs[lo:hi]}
        rid = int(path.split("/check-runs/")[1].split("/")[0])
        return anns[rid][lo:hi]
    return api


def run(rid, n, status="completed"):
    return {"id": rid, "status": status, "output": {"annotations_count": n}}


# 150 runs, so check runs span two pages; only two carry annotations,
# one of them on page two, and run 7 has 150 annotations (two pages).
RUNS = [run(i, 0) for i in range(1, 151)]
RUNS[6] = run(7, 150)
RUNS[139] = run(140, 1)
ANNS = {7: [ann(f"w{i}\nsecond line") for i in range(150)], 140: [ann("x\ty")]}

with tempfile.TemporaryDirectory() as cache:
    calls = []
    got = list(ac.rows(fake_api(RUNS, ANNS, calls), "o/r", "a" * 40, cache))
    check("rows pages both the check runs and the annotations",
          len(got) == 151 and {r[0] for r in got} == {"7", "140"})
    check("rows keeps only the first line of a message", got[0][3] == "w0")
    first = sum("/annotations" in c for c in calls)
    calls.clear()
    again = list(ac.rows(fake_api(RUNS, ANNS, calls), "o/r", "a" * 40, cache))
    check("a cached re-read spends no annotation calls",
          again == got and first == 3 and not any("/annotations" in c for c in calls))

    out = io.StringIO()
    ac_gh, ac.gh_api = ac.gh_api, fake_api(RUNS, ANNS, [])
    old_env = ac.default_cache_dir
    ac.default_cache_dir = lambda: Path(cache)
    try:
        with contextlib.redirect_stdout(out):
            code = ac.main(["rows", "o/r", "a" * 40])
    finally:
        ac.gh_api, ac.default_cache_dir = ac_gh, old_env
    lines = out.getvalue().splitlines()
    check("the CLI prints one tab-separated row per annotation, tabs in fields replaced",
          code == 0 and len(lines) == 151 and lines[-1] == "140\twarning\ta.qmd\tx y")

    def broken(path):
        raise RuntimeError("HTTP 403")
    err = io.StringIO()
    ac.gh_api = broken
    try:
        with contextlib.redirect_stderr(err):
            code = ac.main(["rows", "o/r", "b" * 40])
    finally:
        ac.gh_api = ac_gh
    check("a failed read exits 2 instead of printing a partial list",
          code == 2 and "incomplete read" in err.getvalue())
    # Run 140 claims two annotations but the API returns one: a short read,
    # on the second annotated run, after run 7 has read in full.
    short_runs = list(RUNS)
    short_runs[139] = run(140, 2)
    out, err = io.StringIO(), io.StringIO()
    ac.gh_api = fake_api(short_runs, ANNS, [])
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ac.main(["rows", "o/r", "c" * 40])
    finally:
        ac.gh_api = ac_gh
    check("a short read exits 2 and prints no rows, not even the complete earlier run",
          code == 2 and out.getvalue() == "" and "read 1 of 2" in err.getvalue())
    with contextlib.redirect_stderr(io.StringIO()):
        code = ac.main(["x"])
    check("a bad call prints usage and exits 2", code == 2)

    path = ac.cache_path(cache, "o/r", 7)
    check("the cache file holds the full list", len(json.loads(path.read_text(encoding="utf-8"))) == 150)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
