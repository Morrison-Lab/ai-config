#!/usr/bin/env python3
"""Tests for diff-annotations-vs-base.py; the fake API pages like GitHub."""
import contextlib
import importlib.util
import io
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "dav", Path(__file__).parent / "diff-annotations-vs-base.py")
dav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dav)

passes = failures = 0


def check(name, condition):
    global passes, failures
    print(("PASS: " if condition else "FAIL: ") + name)
    passes += bool(condition)
    failures += not condition


def ann(msg, path=".github", level="failure"):
    return {"annotation_level": level, "path": path, "message": msg}


def fake_api(commits, report_runs=None, report_anns=None, status="completed"):
    """commits: {sha: [(run name, [annotations])]}; ids are assigned here."""
    runs, anns, rid = {}, {}, 1000
    for sha, spec_runs in commits.items():
        runs[sha] = []
        for name, items in spec_runs:
            rid += 1
            count = len(items) if report_anns is None else report_anns
            runs[sha].append({"id": rid, "name": name, "status": status,
                              "output": {"annotations_count": count}})
            anns[rid] = items

    def api(path):
        query = dict(kv.split("=") for kv in path.split("?")[1].split("&"))
        page, per = int(query["page"]), int(query["per_page"])
        window = slice((page - 1) * per, page * per)
        if "/commits/" in path:
            sha = path.split("/commits/")[1].split("/")[0]
            total = len(runs[sha]) if report_runs is None else report_runs
            return {"total_count": total, "check_runs": runs[sha][window]}
        return anns[int(path.split("/check-runs/")[1].split("/")[0])][window]
    return api


def run(argv, api):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = dav.main(argv, api=api)
    return code, out.getvalue()


ARGS = ["--repo", "o/r", "--base", "b" * 40, "--head", "a" * 40]

# Same 150 runs in a different order: page 1 alone covers different subsets.
many = [(f"job-{i}", [ann(f"err {i}")]) for i in range(150)]
code, out = run(ARGS, fake_api({"b" * 40: many, "a" * 40: many[::-1]}))
check("every page of check runs is read", code == 0 and "150 runs" in out)

big = [ann(f"line {i}") for i in range(250)]
lint = {"b" * 40: [("lint", big)], "a" * 40: [("lint", big[:249] + [ann("new")])]}
code, out = run(ARGS, fake_api(lint))
check("every page of annotations is read", "250 annotations" in out)
check("a changed annotation on page 3 is untraced", code == 1 and "+head 1" in out)
code, out = run(ARGS + ["--explained", "lint"], fake_api(lint))
check("--explained traces a named difference", code == 0 and "(explained)" in out)

base = [("lock", [ann("waited for /tmp/tmp.rMPYwP4ngD/lock")]),
        ("drops", [ann("Merge d698235d3b56 dropped 1 line")]),
        ("orphans", [ann("orphan-# unused", path="fx/orphan-42911084766.png")])]
head = [("lock", [ann("waited for /tmp/tmp.jS4UtPnKW3/lock")]),
        ("drops", [ann("Merge 4db68a868bcd dropped 1 line")]),
        ("orphans", [ann("orphan-# unused", path="fx/orphan-42912425115.png")])]
code, out = run(ARGS, fake_api({"b" * 40: base, "a" * 40: head}))
check("the three gha#1825 run-to-run values normalize away", code == 0)

check("a hex-letter word is not read as a sha",
      dav.normalize("added faced decade", dav.DEFAULT_NORMALIZERS) == "added faced decade")

code, out = run(ARGS + ["--levels", "failure"],
                fake_api({"b" * 40: [("x", [ann("w", level="warning")])],
                          "a" * 40: [("x", [])]}))
check("levels outside --levels are not compared", code == 0)

code, out = run(ARGS, fake_api({"b" * 40: [("x", [])], "a" * 40: [("x", [])]},
                               report_runs=5))
check("a short check-run read exits 2", code == 2 and "incomplete read" in out)

code, out = run(ARGS, fake_api({"b" * 40: [("x", [ann("e")])], "a" * 40: [("x", [ann("e")])]},
                               report_anns=3))
check("a short annotation read exits 2", code == 2 and "incomplete read" in out)

code, out = run(ARGS, fake_api({"b" * 40: [("x", [ann("e")])], "a" * 40: []}))
check("a run name missing on head is a difference", code == 1 and "-head 1" in out)

code, out = run(ARGS + ["--levels", "failures"], fake_api({"b" * 40: [], "a" * 40: []}))
check("an unknown level exits 2 instead of comparing nothing", code == 2)
code, out = run(ARGS, fake_api({"b" * 40: [("x", [])], "a" * 40: [("x", [])]},
                               status="in_progress"))
check("a run not yet completed exits 2", code == 2 and "not completed" in out)

drift = {"b" * 40: [("x", [ann("took 31s")])], "a" * 40: [("x", [ann("took 47s")])]}
check("--normalize hides a value you name",
      run(ARGS, fake_api(drift))[0] == 1
      and run(ARGS + ["--normalize", r"\d+s"], fake_api(drift))[0] == 0)

ids = {"b" * 40: [("x", [ann("size 1234567890")])],
       "a" * 40: [("x", [ann("size 1234567891")])]}
check("--no-default-normalizers keeps a large number",
      run(ARGS, fake_api(ids))[0] == 0
      and run(ARGS + ["--no-default-normalizers"], fake_api(ids))[0] == 1)


def failing_api(path):
    raise dav.ReadError(f"gh api {path} failed: HTTP 502")


code, out = run(ARGS, failing_api)
check("a failed gh call exits 2", code == 2 and "HTTP 502" in out)

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
