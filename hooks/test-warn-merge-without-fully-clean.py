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
    return {"cmd": cmd, "out": out, "is_error": is_error, "sidechain": sidechain,
            "tool": "Bash"}


def mcp_step(tool):
    """A non-Bash tool call (e.g. an MCP push) with an empty result."""
    return {"cmd": "", "out": "ok", "is_error": False, "sidechain": False,
            "tool": tool}


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
                                         "name": s["tool"],
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
    check("warns on a global `gh -R repo-B pr merge 12` after a clean repo-A run",
          run("gh -R other/repo pr merge 12", [clean()])[0])
    check("silent on a global `gh --repo o/r pr merge 12` with a matching run",
          not run("gh --repo Morrison-Lab/ai-config pr merge 12", [clean()])[0])
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
    check("warns: instrument && other && merge (only the strict form discharges)",
          run(INSTR + " && echo ok && " + MERGE, [])[0])
    NL = chr(10)
    check("silent: newline after && is allowed",
          not run(INSTR + " &&" + NL + MERGE, [])[0])
    check("silent: cd <path> && instrument && merge",
          not run("cd /tmp/wt && " + INSTR + " && " + MERGE, [])[0])
    check("silent: path-prefixed script",
          not run("python3 /w/scripts/check-pr-fully-clean.py 12 -R Morrison-Lab/ai-config"
                  " && " + MERGE, [])[0])
    check("silent: instrument without -R, merge with -R",
          not run("python3 scripts/check-pr-fully-clean.py 12 && " + MERGE, [])[0])
    check("warns: a newline BETWEEN them is a separator, not &&",
          run(INSTR + NL + MERGE, [])[0])
    check("warns: leading || before the instrument",
          run("false || " + INSTR + " && " + MERGE, [])[0])
    check("warns: --help instead of a number",
          run("python3 scripts/check-pr-fully-clean.py --help && " + MERGE, [])[0])
    check("warns: instrument with NO number",
          run("python3 scripts/check-pr-fully-clean.py -R Morrison-Lab/ai-config && "
              + MERGE, [])[0])
    check("warns: merge names no number",
          run(INSTR + " && gh pr merge --squash", [])[0])
    check("warns: an extra segment after the merge",
          run(INSTR + " && " + MERGE + " && echo done", [])[0])
    check("warns: an extra segment before cd",
          run("echo hi && cd /x && " + INSTR + " && " + MERGE, [])[0])
    check("warns: a trailing command on a new line after the merge",
          run(INSTR + " && " + MERGE + NL + "rm -rf x", [])[0])
    check("warns: a ; after the merge (extra segment)",
          run(INSTR + " && " + MERGE + " ; echo x", [])[0])
    check("warns: a pipe after the merge",
          run(INSTR + " && " + MERGE + " | tee log", [])[0])
    check("warns: a || after the merge",
          run(INSTR + " && " + MERGE + " || true", [])[0])
    check("warns: a two-token non-cd prefix segment",
          run("echo hi && " + INSTR + " && " + MERGE, [])[0])
    check("warns: bare `cd` with no path",
          run("cd && " + INSTR + " && " + MERGE, [])[0])
    check("warns: `cd` with two paths",
          run("cd a b && " + INSTR + " && " + MERGE, [])[0])
    check("warns: a flag other than -R after the instrument number",
          run("python3 scripts/check-pr-fully-clean.py 12 -X Morrison-Lab/ai-config"
              " && " + MERGE, [])[0])
    check("warns: gh api merge after the instrument is not the strict form",
          run(INSTR + " && gh api -X PUT repos/Morrison-Lab/ai-config/pulls/12/merge",
              [])[0])
    check("warns: strict form but merge for a DIFFERENT number",
          run(INSTR + " && gh pr merge 13 -R Morrison-Lab/ai-config", [])[0])
    check("warns: wrong interpreter (python, not python3)",
          run("python scripts/check-pr-fully-clean.py 12 -R Morrison-Lab/ai-config"
              " && " + MERGE, [])[0])
    check("warns: script outside scripts/",
          run("python3 tools/check-pr-fully-clean.py 12 -R Morrison-Lab/ai-config"
              " && " + MERGE, [])[0])

    # --- push and run in ONE command (item 4) -----------------------------
    P2 = lambda cmd: run(MERGE, [step(cmd, CLEAN_OUT)])[0]
    check("silent: `git push && check` credits the run as after the push",
          not P2("git push origin b && " + INSTR))
    check("warns: `check && git push` leaves the run stale",
          P2(INSTR + " && git push origin b"))
    check("silent: check && push && check (the last run is after the push)",
          not P2(INSTR + " && git push origin b && " + INSTR))

    # --- round 3 -----------------------------------------------------------
    IC = "python3 scripts/check-pr-fully-clean.py "
    R = " -R Morrison-Lab/ai-config"
    OUT5 = "Morrison-Lab/ai-config#5 is FULLY CLEAN on HEAD aaaa1111!"
    OUT6 = "Morrison-Lab/ai-config#6 is FULLY CLEAN on HEAD bbbb2222!"
    M5 = "gh pr merge 5 -R Morrison-Lab/ai-config"
    M6 = "gh pr merge 6 -R Morrison-Lab/ai-config"
    # item 1: the merge's own command pushes first
    check("warns: `git push && gh pr merge` after an earlier clean run",
          run("git push origin b && " + M5, [step(IC + "5" + R, OUT5)])[0])
    check("warns: push then merge joined by ; also stales earlier runs",
          run("git push origin b ; " + M5, [step(IC + "5" + R, OUT5)])[0])
    check("silent: merge then push in one command keeps the earlier run",
          not run(M5 + " && git push origin b", [step(IC + "5" + R, OUT5)])[0])
    check("silent: earlier clean run, merge command with no push",
          not run(M5, [step(IC + "5" + R, OUT5)])[0])
    # item 2: several runs in one command
    TWO = step(IC + "5" + R + " && " + IC + "6" + R, OUT5 + chr(10) + OUT6)
    check("silent: `check 5 && check 6` credits #5", not run(M5, [TWO])[0])
    check("silent: `check 5 && check 6` credits #6", not run(M6, [TWO])[0])
    check("warns: `check 5 && check 6` does not credit #7",
          run("gh pr merge 7 -R Morrison-Lab/ai-config", [TWO])[0])
    ONLY6 = step(IC + "5" + R + " && " + IC + "6" + R, OUT6)
    check("warns: only #6 named in the output, so #5 is not credited",
          run(M5, [ONLY6])[0])
    check("silent: only #6 named in the output credits #6", not run(M6, [ONLY6])[0])
    check("silent: no per-PR naming, no NOT-clean line: all explicit runs credited",
          not run(M5, [step(IC + "5" + R + " && " + IC + "6" + R,
                            "ok is FULLY CLEAN")])[0])
    check("warns: no per-PR naming but a NOT-clean line present",
          run(M5, [step(IC + "5" + R + " && " + IC + "6" + R,
                        "ok is FULLY CLEAN" + chr(10) + "NOT fully clean")])[0])
    check("silent: failing #6 does not veto the attributed clean #5",
          not run(M5, [step(IC + "5" + R + " && " + IC + "6" + R,
                            OUT5 + chr(10) + "PR is NOT fully clean")])[0])
    # item 3: shell-variable or missing run number
    check("warns: run number is a shell variable and output names nothing",
          run(M5, [step(IC + "$PR" + R, "is FULLY CLEAN")])[0])
    check("warns: run number missing and output names nothing",
          run(M5, [step(IC + R.strip(), "is FULLY CLEAN")])[0])
    check("silent: variable run number but the output names #5",
          not run(M5, [step(IC + "$PR" + R, OUT5)])[0])
    check("warns: variable run number, output names #6 only",
          run(M5, [step(IC + "$PR" + R, OUT6)])[0])
    # item 4: strict-chain spellings
    check("silent: strict chain with --repo o/r",
          not run(IC + "5 --repo Morrison-Lab/ai-config && " + M5, [])[0])
    check("silent: strict chain with --repo=o/r",
          not run(IC + "5 --repo=Morrison-Lab/ai-config && " + M5, [])[0])
    check("silent: strict chain with a trailing 2>&1 on the instrument",
          not run(IC + "5" + R + " 2>&1 && " + M5, [])[0])
    check("warns: strict chain, --repo for a DIFFERENT repo",
          run(IC + "5 --repo=other/repo && " + M5, [])[0])
    check("warns: env-prefixed instrument is not the strict form",
          run("FOO=1 " + IC + "5" + R + " && " + M5, [])[0])
    check("warns: 2>&1 on the merge side only is not on the instrument",
          run(IC + "5" + R + " && " + M5 + " 2>&1 ; echo x", [])[0])

    # --- round 4 -----------------------------------------------------------
    # item 1: the instrument's own value flags
    check("silent: `--quorum 2 5` is PR 5 (the value 2 is not the PR)",
          not run(M5, [step(IC + "--quorum 2 5" + R, OUT5)])[0])
    check("warns: `--quorum 2 5` run does NOT cover PR 2",
          run("gh pr merge 2 -R Morrison-Lab/ai-config",
              [step(IC + "--quorum 2 5" + R, OUT5)])[0])
    check("silent: --from-json FILE then the number",
          not run(M5, [step(IC + "--from-json /tmp/p.json 5" + R, OUT5)])[0])
    check("silent: -R value before the number",
          not run(M5, [step(IC + "-R Morrison-Lab/ai-config 5", OUT5)])[0])
    # the set is derived from the script, not remembered
    import importlib.util
    import argparse
    spec = importlib.util.spec_from_file_location(
        "hook_under_test", HOOK)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    script = os.path.join(os.path.dirname(HOOKS_DIR), "scripts",
                          "check-pr-fully-clean.py")
    spec2 = importlib.util.spec_from_file_location("instr_under_test", script)
    instr = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(instr)
    seen = []
    real = argparse.ArgumentParser.add_argument

    def spy(self, *names, **kw):
        if names and names[0].startswith("-") and kw.get("action") not in (
                "store_true", "store_false", "count", "help", "version"):
            seen.extend(names)
        return real(self, *names, **kw)

    argparse.ArgumentParser.add_argument = spy
    try:
        instr.parse_args(["5"])
    finally:
        argparse.ArgumentParser.add_argument = real
    check("INSTRUMENT_VALUE_FLAGS equals the script's value-taking options",
          set(seen) == set(hook.INSTRUMENT_VALUE_FLAGS))

    # item 2: pushes made through MCP stale earlier runs
    for tool in ("mcp__github__push_files", "mcp__github__create_or_update_file",
                 "mcp__github__delete_file",
                 "mcp__github__update_pull_request_branch"):
        check("warns: " + tool + " after a clean run",
              run(M5, [step(IC + "5" + R, OUT5), mcp_step(tool)])[0])
        check("silent: " + tool + " BEFORE the clean run",
              not run(M5, [mcp_step(tool), step(IC + "5" + R, OUT5)])[0])
    check("silent: an unrelated MCP read after a clean run is not a push",
          not run(M5, [step(IC + "5" + R, OUT5),
                       mcp_step("mcp__github__get_file_contents")])[0])

    # --- placeholders (item 6) ---------------------------------------------
    check("silent: {owner}/{repo} placeholder repo on the merge matches any",
          not run("gh pr merge 12 -R '{owner}/{repo}'", [clean()])[0])
    check("silent: placeholder repo on the instrument run matches any",
          not run(MERGE, [clean(repo="-R '{owner}/{repo}'")])[0])
    check("warns: placeholder merge but NO run at all",
          run("gh pr merge 12 -R '{owner}/{repo}'", [])[0])
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
    check("warns on gh api merge with a trailing slash",
          run(API + "/", [])[0])
    check("warns on gh api merge with a query string",
          run(API + "?x=1", [])[0])
    check("silent on gh api merge with a query string after a clean run",
          not run(API + "?x=1", [clean()])[0])
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
