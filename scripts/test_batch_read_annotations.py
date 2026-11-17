#!/usr/bin/env python3
"""Tests for batch-read-annotations.py, against a fake API (ai-config#5045)."""
import contextlib
import importlib.util
import io
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "bra", Path(__file__).parent / "batch-read-annotations.py")
bra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bra)

passes = failures = 0


def check(name, condition):
    global passes, failures
    print(("PASS: " if condition else "FAIL: ") + name)
    passes += bool(condition)
    failures += not condition


def ann(msg, path=".github", line=1, level="notice"):
    return {"annotation_level": level, "path": path, "start_line": line, "message": msg}


def fake_api(anns, remaining=4000, status=None, report=None, fail=False):
    """anns: {run id: [annotation]}; status/report override per run id."""
    calls, budget = [], {"left": remaining}
    runs = [{"id": i, "status": (status or {}).get(i, "completed"),
             "output": {"annotations_count": (report or {}).get(i, len(a))}}
            for i, a in anns.items()]

    def api(path):
        calls.append(path)
        if fail:
            raise bra.ReadError("HTTP 403")
        if path == "rate_limit":
            return {"resources": {"core": {"remaining": budget["left"], "reset": 0}}}
        budget["left"] -= 1
        query = dict(kv.split("=") for kv in path.split("?")[1].split("&"))
        window = slice((int(query["page"]) - 1) * 100, int(query["page"]) * 100)
        if "/commits/" in path:
            return {"check_runs": runs[window]}
        return anns[int(path.split("/check-runs/")[1].split("/")[0])][window]
    return api, calls


def run(argv, api, sleeps=None):
    out, err, sleeps = io.StringIO(), io.StringIO(), [] if sleeps is None else sleeps
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = bra.main(["--repo", "o/r", "--sha", "a" * 40] + argv, api=api, sleep=sleeps.append)
    return code, out.getvalue(), err.getvalue()


UBUNTU = '"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026."'
NODE = ("Node.js 20 is deprecated. The following actions target Node.js 20 "
        "but are being forced to run on Node.js 24")
LEADIN = "lead-in says two but 3 item(s) follow"
RUNS = {
    11: [ann(UBUNTU)] * 3,
    12: [ann(NODE, line=3), ann(LEADIN, path="bad.md", line=5, level="failure")],
    13: [ann("Skipping list-item merge splice check"),
         ann("examined 0 files -- the check did not run", level="failure"),
         ann("real problem here", level="warning")],
    14: [ann("x")] * 150,
}

api, calls = fake_api(RUNS)
sleeps = []
code, out, err = run(["--pause", "0.25"], api, sleeps)
check("a full read exits 0, ends with the ids, and groups and counts identical messages",
      code == 0 and out.strip().splitlines()[-1] == "11,12,13,14"
      and "    3  notice   [known: ubuntu-latest migration notice]" in out)
check("every recorded notice and fixture is known; an unrecorded one is UNKNOWN at path:line",
      all(f"known: {label}" in out for label, _ in bra.KNOWN)
      and "[UNKNOWN] real problem here\n         at .github:1\n" in out and out.index("[UNKNOWN]") < out.index("[known:"))
check("runs are paused between, budget read before each, 150 annotations over two pages",
      sleeps == [0.25] * 3 and calls.count("rate_limit") == 4
      and sum("/check-runs/14/" in c for c in calls) == 2)
check("a workflow-file warning about Node.js 20 is not the runner notice",
      bra.known_label(ann(NODE, path=".github/workflows/ci.yml", line=9)) is None)

# The fixture on bad.md:5 must not excuse the same message in a real file.
api, _ = fake_api({21: [ann(LEADIN, path="docs/x.md", line=5), ann(LEADIN, path="bad.md", line=5)]})
code, out, _ = run([], api)
check("a group is known only when every member matches",
      f"[UNKNOWN] {LEADIN}\n         at docs/x.md:5\n" in out and "known:" not in out)

# An unfinished run and a short read are named and left out of the id list.
api, calls = fake_api({31: [ann("a")], 32: [ann("b")], 33: [ann("c")]},
                      status={31: "in_progress"}, report={32: 2})
code, out, err = run([], api, sleeps := [])
check("unfinished and short-read runs exit 2, named, only complete runs listed, one pause",
      code == 2 and out.strip().splitlines()[-1] == "33"
      and "run 31 is in_progress" in err and "run 32: read 1 annotations, GitHub reports 2" in err
      and not any("/check-runs/31/" in c for c in calls) and sleeps == [1.0])

# 503 - listing - run 11 - run 12 = 500; run 13 would leave 499, below the floor.
api, calls = fake_api(RUNS, remaining=503, status={14: "in_progress"})
code, out, err = run(["--floor", "500"], api)
check("the floor stops the read (exit 3), names budget, reset and the unfinished run",
      code == 3 and "STOPPED: 500 core request(s) left, floor 500" in err
      and "run 14 is in_progress" in err and "1 run(s) unread" in err
      and "00:00 UTC" in err and out.strip().splitlines()[-1] == "11,12"
      and not any("/check-runs/13/" in c for c in calls))
code, out, err = run([], fake_api(RUNS, fail=True)[0])
check("a failed read exits 2 and prints no id list", code == 2 and out == "" and "HTTP 403" in err)

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
