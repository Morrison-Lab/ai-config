#!/usr/bin/env python3
"""Tests for hooks/warn-merge-without-fully-clean.py (ai-config#4399).

Every case drives the hook the way the harness does: a JSON payload on stdin
and a real transcript file on disk, reading the EXIT STATUS first so a crash
cannot pass as "silent".
"""
import json
import os
import subprocess
import sys
import tempfile

HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HOOKS_DIR, "warn-merge-without-fully-clean.py")

PASSED = []
FAILED = []

CLEAN_OUT = "all checks pass\n\n[ok] Morrison-Lab/ai-config#12 is FULLY CLEAN on HEAD abcd1234!"
DIRTY_OUT = "Exit code 1\n\nPR is NOT fully clean:\n - finding"


def step(cmd, out="", is_error=False, sidechain=False):
    return {"cmd": cmd, "out": out, "is_error": is_error, "sidechain": sidechain}


def clean(n=12, repo="-R Morrison-Lab/ai-config", out=CLEAN_OUT, **kw):
    return step(f"python3 scripts/check-pr-fully-clean.py {n} {repo}".strip(),
                out, **kw)


def transcript(steps):
    """One assistant tool_use record + one user tool_result record per step."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for i, s in enumerate(steps):
            tid = f"toolu_{i}"
            fh.write(json.dumps({
                "type": "assistant", "isSidechain": s["sidechain"],
                "message": {"content": [{"type": "tool_use", "id": tid,
                                         "name": "Bash",
                                         "input": {"command": s["cmd"]}}]},
            }) + "\n")
            fh.write(json.dumps({
                "type": "user",
                "message": {"content": [{
                    "type": "tool_result", "tool_use_id": tid,
                    "is_error": s["is_error"],
                    "content": [{"type": "text", "text": s["out"]}]}]},
            }) + "\n")
    return path


def run(command, steps, tool_name="Bash", tool_input=None):
    """Return (fired, payload_or_none). Raises on a crashed hook."""
    path = transcript(steps)
    try:
        payload = {"tool_name": tool_name,
                   "tool_input": tool_input or {"command": command},
                   "transcript_path": path}
        env = dict(os.environ)
        env.pop("ANTIGRAVITY_AGENT", None)
        proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise AssertionError("FATAL: hook exited %s on %r\nstderr: %s"
                                 % (proc.returncode, command, proc.stderr))
        out = proc.stdout.strip()
        return (True, json.loads(out)) if out else (False, None)
    finally:
        os.unlink(path)


def check(label, cond):
    (PASSED if cond else FAILED).append(label)
    print(("PASS: " if cond else "FAIL: ") + label)


MERGE = "gh pr merge 12 -R Morrison-Lab/ai-config --squash"
PUSH = step("git push origin my-branch")


def main():
    # --- positive: warns -------------------------------------------------
    fired, out = run(MERGE, [])
    check("warns on a merge with no instrument run at all", fired)
    ctx = ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")
    check("...naming the instrument and the PR in the context",
          "check-pr-fully-clean.py 12" in ctx and "-R Morrison-Lab/ai-config" in ctx)
    check("...as a PreToolUse systemMessage too",
          bool((out or {}).get("systemMessage"))
          and out["hookSpecificOutput"]["hookEventName"] == "PreToolUse")
    check("warns when the run exited non-zero (NOT fully clean)",
          run(MERGE, [clean(out=DIRTY_OUT, is_error=True)])[0])
    check("warns when the only run came BEFORE the last push",
          run(MERGE, [clean(), PUSH])[0])
    check("warns when the run is for a DIFFERENT PR number",
          run(MERGE, [clean(n=99)])[0])
    check("warns when the run is for a DIFFERENT repo",
          run(MERGE, [clean(repo="-R other/repo")])[0])
    check("warns on a bare `gh pr merge N` with no -R",
          run("gh pr merge 12", [])[0])
    check("warns on a merge buried in a && chain",
          run("echo go && gh pr merge 12 --squash", [])[0])
    check("a subagent's (sidechain) clean run is not this session's reading",
          run(MERGE, [clean(sidechain=True)])[0])
    check("a command merely containing the words `pr merge` is not a gh merge",
          not run("grep pr merge 12 notes.txt", [])[0])
    check("warns when the run is flagged is_error even with no marker text",
          run(MERGE, [clean(out="boom", is_error=True)])[0])
    check("warns on an `Exit code 2` result not flagged is_error",
          run(MERGE, [clean(out="Exit code 2" + chr(10) + "boom")])[0])
    check("`python3 -c <script path>` evaluates text and is not a run",
          run(MERGE, [step("python3 -c scripts/check-pr-fully-clean.py 12 "
                           "-R Morrison-Lab/ai-config", CLEAN_OUT)])[0])
    check("`cat <instrument path> 12` is not a run (head is not a runner)",
          run(MERGE, [step("cat scripts/check-pr-fully-clean.py 12 "
                           "-R Morrison-Lab/ai-config", CLEAN_OUT)])[0])
    check("a grep NAMING the instrument is not a run of it",
          run(MERGE, [step("grep -n x scripts/check-pr-fully-clean.py 12",
                           CLEAN_OUT)])[0])
    check("a NOT-fully-clean line vetoes a zero-looking result",
          run(MERGE, [clean(out="NOT fully clean\nwhatever")])[0])
    check("warns on the MCP merge tool with no run",
          run("", [], tool_name="mcp__github__merge_pull_request",
              tool_input={"owner": "Morrison-Lab", "repo": "ai-config",
                          "pullNumber": 12})[0])

    # --- negative: silent ------------------------------------------------
    check("silent after a clean run (FULLY CLEAN line)", not run(MERGE, [clean()])[0])
    check("a NOT-fully-clean line vetoes even beside a FULLY CLEAN line",
          run(MERGE, [clean(out=CLEAN_OUT + chr(10) + "NOT fully clean")])[0])
    check("warns after a result with no FULLY CLEAN line, however quiet",
          run(MERGE, [clean(out="done")])[0])
    check("warns after a run with EMPTY output",
          run(MERGE, [clean(out="")])[0])
    check("warns after a BACKGROUNDED run (no verdict yet)",
          run(MERGE, [clean(out="Command running in background with ID: bx1")])[0])
    check("silent when a backgrounded run was later followed by a clean one",
          not run(MERGE, [clean(out="Command running in background with ID: bx1"),
                          clean()])[0])

    # --- same-command `&&` chain (item 1) ---------------------------------
    INSTR = "python3 scripts/check-pr-fully-clean.py 12 -R Morrison-Lab/ai-config"
    check("silent: instrument && merge in ONE command",
          not run(INSTR + " && " + MERGE, [])[0])
    check("silent: instrument && other && merge",
          not run(INSTR + " && echo ok && " + MERGE, [])[0])
    check("warns: instrument ; merge (a `;` join does not discharge)",
          run(INSTR + " ; " + MERGE, [])[0])
    check("warns: instrument || merge (a `||` join does not discharge)",
          run(INSTR + " || " + MERGE, [])[0])
    check("warns: instrument && X ; merge (chain broken by `;`)",
          run(INSTR + " && echo ok ; " + MERGE, [])[0])
    check("warns: merge && instrument (instrument AFTER the merge)",
          run(MERGE + " && " + INSTR, [])[0])
    check("warns: chained instrument for a DIFFERENT PR",
          run("python3 scripts/check-pr-fully-clean.py 99 -R Morrison-Lab/ai-config"
              " && " + MERGE, [])[0])
    check("warns: chained instrument for a DIFFERENT repo",
          run("python3 scripts/check-pr-fully-clean.py 12 -R other/repo && " + MERGE,
              [])[0])
    check("warns: a git push between the chained instrument and the merge",
          run(INSTR + " && git push origin b && " + MERGE, [])[0])
    check("warns: instrument piped to tail then merge (pipe masks status)",
          run(INSTR + " | tail -3 && " + MERGE, [])[0])
    check("warns: only a quoted/echoed instrument precedes the merge",
          run("echo '" + INSTR + "' && " + MERGE, [])[0])

    # --- gh api merge (item 3) ---------------------------------------------
    API = "gh api -X PUT repos/Morrison-Lab/ai-config/pulls/12/merge"
    check("warns on gh api -X PUT .../pulls/N/merge", run(API, [])[0])
    check("warns on gh api --method PUT .../merge",
          run("gh api --method PUT repos/Morrison-Lab/ai-config/pulls/12/merge", [])[0])
    check("warns on gh api -XPUT /repos/.../merge",
          run("gh api -XPUT /repos/Morrison-Lab/ai-config/pulls/12/merge", [])[0])
    check("silent on gh api GET .../pulls/N/merge (a read)",
          not run("gh api repos/Morrison-Lab/ai-config/pulls/12/merge", [])[0])
    check("silent on gh api PUT to a non-merge endpoint",
          not run("gh api -X PUT repos/Morrison-Lab/ai-config/pulls/12/labels", [])[0])
    check("silent on gh api merge after a clean run for that PR",
          not run(API, [clean()])[0])
    check("warns on gh api merge after a clean run for ANOTHER PR",
          run(API, [clean(n=99)])[0])
    check("silent when the clean run came AFTER the last push",
          not run(MERGE, [PUSH, clean()])[0])
    check("silent when both the run and the merge omit -R",
          not run("gh pr merge 12", [clean(repo="")])[0])
    check("silent for a merge with no -R when the run had -R",
          not run("gh pr merge 12", [clean()])[0])
    check("silent when an earlier failing run was followed by a clean one",
          not run(MERGE, [clean(out=DIRTY_OUT, is_error=True), clean()])[0])
    check("silent for an interpreter-less direct invocation",
          not run(MERGE, [step("./scripts/check-pr-fully-clean.py 12 "
                               "-R Morrison-Lab/ai-config", CLEAN_OUT)])[0])
    check("silent on the MCP merge tool after a clean run",
          not run("", [clean()], tool_name="mcp__github__merge_pull_request",
                  tool_input={"owner": "Morrison-Lab", "repo": "ai-config",
                              "pullNumber": 12})[0])
    check("silent for an unrelated command", not run("git status", [])[0])
    check("silent for gh pr view", not run("gh pr view 12", [])[0])
    check("silent for a non-Bash tool", not run(MERGE, [], tool_name="Read")[0])

    # --- quote cases -----------------------------------------------------
    check("silent when the merge is only echoed",
          not run('echo "gh pr merge 12 -R Morrison-Lab/ai-config"', [])[0])
    check("silent when the merge is inside a commit message",
          not run("git commit -m 'run gh pr merge 12 later'", [])[0])
    check("silent when a grep pattern names the merge",
          not run("grep -rn 'gh pr merge 12' memories/", [])[0])
    check("silent when a heredoc body names the merge",
          not run("cat <<'EOF'\ngh pr merge 12\nEOF", [])[0])

    # --- robustness ------------------------------------------------------
    proc = subprocess.run([sys.executable, HOOK], input="not json",
                          capture_output=True, text=True)
    check("fails open on a malformed payload",
          proc.returncode == 0 and not proc.stdout.strip())
    proc = subprocess.run(
        [sys.executable, HOOK], capture_output=True, text=True,
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": MERGE},
                          "transcript_path": "/nonexistent"}))
    check("fails open when the transcript is missing",
          proc.returncode == 0 and not proc.stdout.strip())

    check("negative control: both outcomes were exercised",
          any(lbl.startswith("warns") for lbl in PASSED)
          and any(lbl.startswith("silent") for lbl in PASSED))

    print("\n%d passed, %d failed" % (len(PASSED), len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
