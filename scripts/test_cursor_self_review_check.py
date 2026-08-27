#!/usr/bin/env python3
"""Tests for scripts/cursor-self-review-check.py (ai-config#2299, #2310).

The verdict cases exercise the CLI end to end (subprocess), so what is
tested is the shipped interface, not an importable approximation. The gates
cases run against a throwaway git repository with a file:// remote, so no
network and no real forge is touched.

Run: python3 scripts/test_cursor_self_review_check.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "cursor-self-review-check.py"

passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS: {name}")
    else:
        failed += 1
        print(f"FAIL: {name}" + (f" -- {detail}" if detail else ""))


def run_cli(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True, text=True, cwd=cwd,
    )


SHA = "abc123def4567890abc123def4567890abc123de"

CLEAN_REPORT = (
    "### Summary of Changes\nOne commit.\n\n"
    "### Findings\nNo actionable findings identified.\n\n"
    "### Verdict: Ready for merge\n\n"
    f"Reviewed-Commit: {SHA}\n"
)

NEEDS_WORK_REPORT = CLEAN_REPORT.replace(
    "### Verdict: Ready for merge", "### Verdict: Needs more work"
)


def with_report(body: str):
    tf = tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    )
    tf.write(body)
    tf.close()
    return tf.name


# --- verdict: report files --------------------------------------------------

path = with_report(CLEAN_REPORT)
r = run_cli("verdict", "--report", path, "--expect-head", SHA)
check("clean report at expected head exits 0", r.returncode == 0, r.stdout)
check("clean report prints the verdict", "verdict: clean" in r.stdout, r.stdout)

r = run_cli("verdict", "--report", path, "--expect-head", "9" * 40)
check("fingerprint mismatch refuses (exit 1)", r.returncode == 1, r.stdout)

r = run_cli("verdict", "--report", path, "--expect-head", SHA[:12])
check("abbreviated expected head still matches", r.returncode == 0, r.stdout)
os.unlink(path)

path = with_report(NEEDS_WORK_REPORT)
r = run_cli("verdict", "--report", path, "--expect-head", SHA)
check("needs-work report refuses (exit 1)", r.returncode == 1, r.stdout)
os.unlink(path)

path = with_report("### Summary\n\n### Findings\n\n### Verdict\n(none)\n")
r = run_cli("verdict", "--report", path)
check("verdictless report refuses (exit 1)", r.returncode == 1, r.stdout)
os.unlink(path)

path = with_report(
    "A restated brief with the four headings but no verdict line.\n"
    "```\nVerdict: Ready for merge\n"  # unclosed fence: parse_report refuses
)
r = run_cli("verdict", "--report", path)
check("unclosed fence refuses (exit 1)", r.returncode == 1, r.stdout)
os.unlink(path)

r = run_cli("verdict", "--report", "/nonexistent/x.md")
check("missing report file is an environment error (exit 2)",
      r.returncode == 2, r.stderr)

r = run_cli("verdict")
check("neither --report nor --transcript is usage (exit 2)",
      r.returncode == 2, r.stderr)

# --- verdict: transcripts ---------------------------------------------------

transcript = {
    "messages": [
        {"role": "user", "text": "review this"},
        {"role": "assistant", "text": "Working on it. Verdict: pending."},
        {"role": "assistant", "text": CLEAN_REPORT},
    ]
}
tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                 encoding="utf-8")
json.dump(transcript, tf)
tf.close()
r = run_cli("verdict", "--transcript", tf.name, "--expect-head", SHA)
check("transcript: last assistant text wins and passes",
      r.returncode == 0, r.stdout)
os.unlink(tf.name)

tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                 encoding="utf-8")
tf.write("not json")
tf.close()
r = run_cli("verdict", "--transcript", tf.name)
check("invalid transcript JSON is an environment error (exit 2)",
      r.returncode == 2, r.stderr)
os.unlink(tf.name)

tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                 encoding="utf-8")
json.dump({"messages": [{"role": "user", "text": "hi"}]}, tf)
tf.close()
r = run_cli("verdict", "--transcript", tf.name)
check("transcript with no assistant text is an environment error (exit 2)",
      r.returncode == 2, r.stderr)
os.unlink(tf.name)

# --- gates ------------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    remote = Path(tmp) / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    work = Path(tmp) / "work"
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

    def git(*a, cwd=str(work)):
        return subprocess.run(["git", *a], cwd=cwd, env=env,
                              capture_output=True, text=True, check=False)

    subprocess.run(["git", "clone", "-q", str(remote), str(work)],
                   env=env, check=True)
    (work / "f.txt").write_text("one\n")
    git("add", "f.txt")
    git("commit", "-q", "-m", "init")
    git("branch", "-M", "main")
    git("push", "-q", "-u", "origin", "main")
    git("checkout", "-q", "-b", "feature")
    (work / "f.txt").write_text("two\n")
    git("commit", "-q", "-am", "change")
    head = git("rev-parse", "HEAD").stdout.strip()

    r = run_cli("gates", "--recorded-head", head,
                "--recorded-branch", "feature", "-C", str(work))
    check("gates: all pass on a clean matching checkout",
          r.returncode == 0, r.stdout + r.stderr)
    check("gates: carve-out note names a non-empty diff",
          "a review is owed" in r.stdout, r.stdout)

    (work / "dirty.txt").write_text("x\n")
    r = run_cli("gates", "--recorded-head", head,
                "--recorded-branch", "feature", "-C", str(work))
    check("gates: dirty tree refuses (exit 1)", r.returncode == 1, r.stdout)
    (work / "dirty.txt").unlink()

    r = run_cli("gates", "--recorded-head", "0" * 40,
                "--recorded-branch", "feature", "-C", str(work))
    check("gates: wrong recorded head refuses (exit 1)",
          r.returncode == 1, r.stdout)

    r = run_cli("gates", "--recorded-head", head,
                "--recorded-branch", "other-branch", "-C", str(work),
                "--refspec", "feature")
    check("gates: source branch differing from the recorded one fails gate 4",
          r.returncode == 1 and "FAIL gate 4" in r.stdout, r.stdout)

    r = run_cli("gates", "--recorded-head", head,
                "--recorded-branch", "other-branch", "-C", str(work))
    check("gates: refspec HEAD satisfies gate 4 whatever the recorded branch",
          r.returncode == 0, r.stdout)

    r = run_cli("gates", "--recorded-head", head,
                "--recorded-branch", "feature", "-C", str(work),
                "--refspec", "main")
    check("gates: pushing a different ref than HEAD fails gate 3 (exit 1)",
          r.returncode == 1 and "gate 3" in r.stdout, r.stdout)

    r = run_cli("gates", "--recorded-head", head,
                "--recorded-branch", "feature", "-C", str(work),
                "--skip-dry-run")
    check("gates: --skip-dry-run passes without a remote round trip",
          r.returncode == 0 and "SKIP gates 3-4" in r.stdout, r.stdout)

    r = run_cli("gates", "--recorded-head", "zzz",
                "--recorded-branch", "feature", "-C", str(work))
    check("gates: non-hex recorded head is usage (exit 2)",
          r.returncode == 2, r.stderr)

    r = run_cli("gates", "--recorded-head", head,
                "--recorded-branch", "feature", "-C", tmp)
    check("gates: non-repo directory is an environment error (exit 2)",
          r.returncode == 2, r.stderr)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
