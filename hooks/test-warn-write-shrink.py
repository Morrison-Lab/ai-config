#!/usr/bin/env python3
"""Tests for hooks/warn-write-shrink.py (the `gh` lookup is stubbed).

Run: python3 hooks/test-warn-write-shrink.py [hook-path]
"""

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
HOOK = (
    pathlib.Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else HERE / "warn-write-shrink.py"
)
CREATE = "mcp__github__create_or_update_file"
PUSH = "mcp__github__push_files"
failures = []

# Stub `gh`: size table keyed by path suffix; "ERR" -> exit 1; missing -> 404.
STUB = """#!PYTHON
import json, os, sys, time
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
time.sleep(float(os.environ.get("STUB_SLEEP", "0")))
sizes = json.loads(os.environ["STUB_SIZES"])
api = sys.argv[2].split("?")[0]
for key, val in sizes.items():
    if api.endswith("/contents/" + key):
        if val == "ERR":
            sys.stderr.write("HTTP 500 boom")
            sys.exit(1)
        print(val)
        sys.exit(0)
sys.stderr.write("gh: Not Found (HTTP 404)")
sys.exit(1)
"""


def run(tool, tool_input, sizes, gh_on_path=True, extra_env=None, calls=None):
    with tempfile.TemporaryDirectory() as d:
        gh = pathlib.Path(d) / "gh"
        gh.write_text(STUB.replace("PYTHON", sys.executable, 1), encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ)
        env.pop("ANTIGRAVITY_AGENT", None)
        env["STUB_SIZES"] = json.dumps(sizes)
        logf = pathlib.Path(d) / "calls.log"
        env["STUB_LOG"] = str(logf)
        env.update(extra_env or {})
        # Absolute interpreter path, so PATH can omit the stub dir entirely.
        env["PATH"] = (d + os.pathsep if gh_on_path else "") + "/nonexistent"
        payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
        )
        logf_text = logf.read_text(encoding="utf-8") if logf.exists() else ""
    if calls is not None and logf_text is not None:
        calls.extend(json.loads(x) for x in logf_text.splitlines())
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


def text(out):
    return out["hookSpecificOutput"]["additionalContext"] if out else ""


base = {"owner": "o", "repo": "r", "branch": "b"}


def big(n):
    return "x" * n


out = run(CREATE, {**base, "path": "a.md", "content": big(40000)}, {"a.md": 187000})
check("big shrink warns", "SHRINK WARNING" in text(out) and "a.md" in text(out))
check("warning carries systemMessage", bool(out and out.get("systemMessage")))
check(
    "small edit silent",
    run(CREATE, {**base, "path": "a.md", "content": big(4000)}, {"a.md": 4200}) is None,
)
check(
    "growth silent",
    run(CREATE, {**base, "path": "a.md", "content": big(9000)}, {"a.md": 4200}) is None,
)
check(
    "new file silent",
    run(CREATE, {**base, "path": "new.md", "content": big(10)}, {}) is None,
)
check(
    "20% shrink of small file silent",
    run(CREATE, {**base, "path": "a.md", "content": big(4000)}, {"a.md": 5000}) is None,
)
check(
    "25% shrink of 20KB file warns",
    "SHRINK WARNING"
    in text(run(CREATE, {**base, "path": "a.md", "content": big(15000)}, {"a.md": 20000})),
)
check(
    "tiny file ignored",
    run(CREATE, {**base, "path": "a.md", "content": ""}, {"a.md": 100}) is None,
)
out = run(CREATE, {**base, "path": "a.md", "content": big(10)}, {"a.md": "ERR"})
check(
    "lookup failure fails open with note",
    out and "could not fully run" in text(out) and "SHRINK WARNING" not in text(out),
)
out = run(
    CREATE, {**base, "path": "a.md", "content": big(10)}, {"a.md": 9000}, gh_on_path=False
)
check("missing gh fails open with note", out and "could not fully run" in text(out))
out = run(
    PUSH,
    {
        **base,
        "files": [
            {"path": "ok.md", "content": big(990)},
            {"path": "cut.md", "content": big(100)},
            {"path": "new.md", "content": "n"},
        ],
    },
    {"ok.md": 1000, "cut.md": 5000},
)
check(
    "push_files flags only the shrunk file",
    "cut.md" in text(out) and "ok.md" not in text(out) and "new.md" not in text(out),
)
check(
    "non-ASCII counted in bytes",
    run(CREATE, {**base, "path": "a.md", "content": "é" * 600}, {"a.md": 1200})
    is None,
)
check(
    "other tool ignored",
    run("mcp__github__get_file_contents", {**base, "path": "a.md", "content": ""}, {"a.md": 9000})
    is None,
)
check("bad payload fails open", run(CREATE, {"path": 3}, {}) is None)


# --- query string, encoding, caps, deadline, boundaries
def argv_api(calls):
    return [c[1] for c in calls]


calls = []
run(CREATE, {**base, "path": "a.md", "content": "x"}, {"a.md": 9000}, calls=calls)
check("?ref sent when branch given", argv_api(calls) == ["repos/o/r/contents/a.md?ref=b"])
calls = []
nb = {"owner": "o", "repo": "r"}
run(CREATE, {**nb, "path": "a.md", "content": "x"}, {"a.md": 9000}, calls=calls)
check("no ?ref when branch omitted", argv_api(calls) == ["repos/o/r/contents/a.md"])
calls = []
run(CREATE, {**base, "path": "d/a b?c#d%e.md", "content": "x"}, {}, calls=calls)
check(
    "path percent-encoded",
    argv_api(calls) == ["repos/o/r/contents/d/a%20b%3Fc%23d%25e.md?ref=b"],
)
calls = []
run(CREATE, {**base, "branch": "feat/x y#1", "path": "a.md", "content": "x"}, {}, calls=calls)
check(
    "branch percent-encoded",
    argv_api(calls) == ["repos/o/r/contents/a.md?ref=feat%2Fx%20y%231"],
)
files = [{"path": f"f{i}.md", "content": "x"} for i in range(5)]
calls = []
out = run(PUSH, {**base, "files": files}, {}, extra_env={"WRITE_SHRINK_MAX_LOOKUPS": "2"}, calls=calls)
check(
    "MAX_LOOKUPS cap stops lookups and emits note",
    len(calls) == 2 and "only the first 2 files were checked" in text(out),
)
calls = []
out = run(
    PUSH,
    {**base, "files": files[:3]},
    {},
    extra_env={"WRITE_SHRINK_BUDGET": "0.3", "STUB_SLEEP": "5"},
    calls=calls,
)
check(
    "subprocess timeout fails open with note",
    "lookup failed (TimeoutExpired)" in text(out) and "SHRINK WARNING" not in text(out),
)
check(
    "exhausted deadline stops lookups and emits note",
    len(calls) == 1 and "time budget exhausted; 2 file(s) not checked" in text(out),
)
check(
    "exactly 50% shrink of 4000 does not warn",
    run(CREATE, {**base, "path": "a.md", "content": big(2000)}, {"a.md": 4000}) is None,
)
check(
    "just over 50% shrink warns",
    "SHRINK WARNING" in text(run(CREATE, {**base, "path": "a.md", "content": big(1999)}, {"a.md": 4000})),
)
check(
    "exactly 20% shrink above 10KB does not warn",
    run(CREATE, {**base, "path": "a.md", "content": big(16000)}, {"a.md": 20000}) is None,
)
check(
    "live size exactly 512 is checked",
    "SHRINK WARNING" in text(run(CREATE, {**base, "path": "a.md", "content": big(100)}, {"a.md": 512})),
)
check(
    "live size 511 is ignored",
    run(CREATE, {**base, "path": "a.md", "content": big(10)}, {"a.md": 511}) is None,
)

sys.exit(1 if failures else 0)
