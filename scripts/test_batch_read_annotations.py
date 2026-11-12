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


def fake_api(anns, remaining=4000):
    """anns: {run id: [annotation]}. Records every call; /rate_limit is free."""
    calls, budget = [], {"left": remaining}

    def api(path):
        calls.append(path)
        if path == "rate_limit":
            return {"resources": {"core": {"remaining": budget["left"], "reset": 0}}}
        budget["left"] -= 1
        query = dict(kv.split("=") for kv in path.split("?")[1].split("&"))
        page, per = int(query["page"]), int(query["per_page"])
        window = slice((page - 1) * per, page * per)
        if "/commits/" in path:
            runs = [{"id": i, "output": {"annotations_count": len(a)}} for i, a in anns.items()]
            return {"check_runs": runs[window]}
        return anns[int(path.split("/check-runs/")[1].split("/")[0])][window]
    return api, calls


def run(argv, api, sleeps=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = bra.main(["--repo", "o/r"] + argv, api=api,
                        sleep=(sleeps.append if sleeps is not None else lambda s: None))
    return code, out.getvalue(), err.getvalue()


RUNS = {
    11: [ann("ubuntu-latest pipelines will use ubuntu-24.04 soon")] * 3,
    12: [ann("Node.js 20 actions are deprecated. Please update"),
         ann("lead-in says two but 3 item(s) follow", path="bad.md", line=5, level="failure")],
    13: [ann("Skipping list-item merge splice check"),
         ann("examined 0 files -- the check did not run", level="failure"),
         ann("real problem here", level="warning")],
    14: [ann("x")] * 150,
}

api, calls = fake_api(RUNS)
sleeps = []
code, out, err = run(["--sha", "a" * 40, "--pause", "0.25"], api, sleeps)
check("a full read exits 0", code == 0)
check("the last line is the comma-separated ids for --annotations-read",
      out.strip().splitlines()[-1] == "11,12,13,14")
check("identical messages are grouped and counted",
      "    3  notice   [known: ubuntu-latest migration notice]" in out)
check("every recorded runner notice and fixture is marked known",
      all(f"known: {label}" in out for label, _ in bra.KNOWN))
check("an unrecorded message stays UNKNOWN", "[UNKNOWN] real problem here" in out)
check("the fixture pattern needs bad.md line 5, not any lead-in finding",
      bra.known_label(ann("lead-in says two", path="bad.md", line=6)) is None)
check("runs are paused between, not before the first", sleeps == [0.25, 0.25, 0.25])
check("a 150-annotation run is read over two pages",
      sum("/check-runs/14/" in c for c in calls) == 2)
check("the budget is read before every run", calls.count("rate_limit") == 4)

# 503 - listing - run 11 - run 12 = 500; run 13 would leave 499, below the floor.
api, calls = fake_api(RUNS, remaining=503)
code, out, err = run(["--sha", "a" * 40, "--floor", "500"], api)
check("stopping at the floor exits 3 and names the budget and the reset time", code == 3
      and "STOPPED: 500 core request(s) left, floor 500" in err and "00:00 UTC" in err)
check("only fully read runs are listed, and nothing is read past the floor",
      out.strip().splitlines()[-1] == "11,12"
      and not any("/check-runs/13/" in c for c in calls))

api, calls = fake_api(RUNS)
code, out, _ = run(["--runs", "13,11"], api)
check("--runs reads only the listed ids, in order",
      code == 0 and out.strip().splitlines()[-1] == "13,11"
      and not any("/commits/" in c for c in calls))


def failing(path):
    raise bra.ReadError("HTTP 403")


code, out, err = run(["--runs", "11"], failing)
check("a failed read exits 2 and prints no id list", code == 2 and out == "" and "HTTP 403" in err)

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
