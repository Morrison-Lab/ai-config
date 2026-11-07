#!/usr/bin/env python3
"""Tests for scripts/check-stop-hook-shapes.py (ai-config#5055).

Run: python3 scripts/test_check_stop_hook_shapes.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-stop-hook-shapes.py"
spec = importlib.util.spec_from_file_location("cshs", SCRIPT)
cshs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cshs)

FAILS = []


def check(name, got, want):
    ok = got == want
    print(("  ok      " if ok else "  FAIL    ") + name)
    if not ok:
        print(f"          got {got!r}, want {want!r}")
        FAILS.append(name)


# The shape of the pre-#5052 announced-start hook: it read the last assistant
# TEXT block and nothing else, so a post_message reply never reached it.
TEXT_ONLY = '''
import json, sys
payload = json.load(sys.stdin)
for line in open(payload["transcript_path"]):
    m = json.loads(line)
    if m.get("type") == "assistant":
        pass
'''
HANDLES_BOTH = TEXT_ONLY + '\n# reads mcp__hearthbot__post_message and PLANNER_RESPONSE\n'
DECLARES_BOTH = TEXT_ONLY + (
    '\n# transcript-shapes-skip: post_message -- Claude Code only\n'
    '# transcript-shapes-skip: antigravity -- not run there\n')
UNRELATED = 'print("no transcript read here")\n'


def repo_with(hook_source, baseline=""):
    """A throwaway repo root holding one Stop hook, evaluated against *baseline*."""
    root = Path(tempfile.mkdtemp())
    (root / "hooks").mkdir()
    (root / "hooks" / "h.py").write_text(hook_source, encoding="utf-8")
    cfg = {"hooks": {"Stop": [{"hooks": [{"command": "python3 hooks/h.py"}]}]}}
    (root / "hooks" / "hooks.json").write_text(json.dumps(cfg), encoding="utf-8")
    pairs = {tuple(line.split()) for line in baseline.splitlines() if line.strip()}
    return cshs.evaluate(root, pairs)


v, stale, n = repo_with(TEXT_ONLY)
check("text-only hook (the pre-#5052 shape) is flagged for both shapes", sorted(v),
      [("h.py", "antigravity"), ("h.py", "post_message")])
check("it is counted as reading the final message", n, 1)

v, stale, n = repo_with(HANDLES_BOTH)
check("a hook naming both shapes passes", (v, stale), ([], []))

v, stale, n = repo_with(DECLARES_BOTH)
check("a hook declaring both skips with a reason passes", (v, stale), ([], []))

v, stale, n = repo_with(TEXT_ONLY + "\n# transcript-shapes-skip: post_message --\n")
check("a skip with no reason does not count", ("h.py", "post_message") in v, True)

v, stale, n = repo_with(UNRELATED)
check("a Stop hook that never reads the transcript is not examined", (v, n), ([], 0))

v, stale, n = repo_with(TEXT_ONLY, "h.py post_message\nh.py antigravity\n")
check("baselined violations pass", (v, stale), ([], []))

v, stale, n = repo_with(HANDLES_BOTH, "h.py post_message\n")
check("a baseline entry the hook now satisfies is stale", (v, stale), ([], [("h.py", "post_message")]))

v, stale, n = repo_with(TEXT_ONLY, "h.py post_message\n")
check("a new shape gap outside the baseline is flagged", v, [("h.py", "antigravity")])

# Negative control on the live repository: the scan examines real hooks, and the
# fixed announced-start hook is not among the violations.
live_v, live_stale, live_n = cshs.evaluate(cshs.REPO, cshs.load_baseline(cshs.BASELINE))
check("live repo examines Stop hooks", live_n > 0, True)
check("live repo is clean against its baseline", (live_v, live_stale), ([], []))
check("announced-start hook handles post_message",
      ("no-announced-start-without-starting.py", "post_message") in
      {(h, s) for h, s in live_v} | cshs.load_baseline(cshs.BASELINE), False)

out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
check("script exits 0 on the live repo", out.returncode, 0)

print(f"\n{len(FAILS)} failure(s)")
sys.exit(1 if FAILS else 0)
