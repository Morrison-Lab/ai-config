#!/usr/bin/env python3
"""Tests for hooks/warn-merge-without-cross-harness-review.py (ai-config#3099).

Each case drives the hook as the harness does: a JSON payload on stdin and a
real transcript on disk, reading the exit status first so a crash cannot pass
as "silent".
"""
import json
import os
import subprocess
import sys
import tempfile

HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HOOKS_DIR, "warn-merge-without-cross-harness-review.py")

PASSED = []
FAILED = []


def step(cmd, out="ok", is_error=False, sidechain=False, tool="Bash",
         tool_input=None):
    return {"cmd": cmd, "out": out, "is_error": is_error,
            "sidechain": sidechain, "tool": tool,
            "input": tool_input if tool_input is not None else {"command": cmd}}


def skill(name, **kw):
    return step("", tool="Skill", tool_input={"skill": name}, **kw)


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
                                         "input": s["input"]}]},
            }) + "\n")
            fh.write(json.dumps({
                "type": "user",
                "message": {"content": [{
                    "type": "tool_result", "tool_use_id": tid,
                    "is_error": s["is_error"],
                    "content": [{"type": "text", "text": s["out"]}]}]},
            }) + "\n")
    return path


def run(command, steps, tool_name="Bash", tool_input=None, env_extra=None):
    """Return (fired, payload_or_none). Raises on a crashed hook."""
    path = transcript(steps)
    try:
        payload = {"tool_name": tool_name,
                   "tool_input": tool_input or {"command": command},
                   "transcript_path": path}
        env = dict(os.environ)
        env.pop("ANTIGRAVITY_AGENT", None)
        env.update(env_extra or {})
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
MCP_MERGE = {"owner": "Morrison-Lab", "repo": "ai-config", "pullNumber": 12}
PUSH = step("git push origin my-branch")
CODEX = step("codex exec 'review the diff against origin/main'")
OPENCODE = step("opencode run 'adversarial review'")
AGENT = step("", tool="Agent",
             tool_input={"subagent_type": "adversarial-reviewer",
                         "prompt": "codex review"})


def main():
    # --- warns ------------------------------------------------------------
    fired, out = run(MERGE, [])
    check("warns on a merge with no reviewer run at all", fired)
    ctx = ((out or {}).get("hookSpecificOutput") or {}).get(
        "additionalContext", "")
    check("...naming the PR and the gate fragment",
          "PR #12" in ctx and "adversarial-self-review.md" in ctx)
    check("...as a PreToolUse systemMessage too",
          bool((out or {}).get("systemMessage"))
          and out["hookSpecificOutput"]["hookEventName"] == "PreToolUse")
    check("warns when only a Claude Agent subagent reviewed",
          run(MERGE, [AGENT])[0])
    check("warns when the cross-harness run predates the last push",
          run(MERGE, [CODEX, PUSH])[0])
    check("warns when the last push was an MCP push tool",
          run(MERGE, [CODEX, step("", tool="mcp__github__push_files",
                                  tool_input={})])[0])
    check("warns when the reviewer call errored",
          run(MERGE, [step("codex exec review", is_error=True)])[0])
    check("warns when the reviewer ran only in a sidechain",
          run(MERGE, [step("codex exec review", sidechain=True)])[0])
    check("warns when the merge command pushes first",
          run("git push origin b && gh pr merge 12 --squash", [CODEX])[0])
    check("warns on the MCP merge tool",
          run("", [], tool_name="mcp__github__merge_pull_request",
              tool_input=MCP_MERGE)[0])
    check("warns on arming auto-merge through MCP",
          run("", [], tool_name="mcp__github__enable_pr_auto_merge",
              tool_input=MCP_MERGE)[0])
    check("warns on the long-form MCP auto-merge tool name",
          run("", [], tool_name="mcp__github__enable_pull_request_auto_merge",
              tool_input=MCP_MERGE)[0])
    check("warns on a REST merge",
          run("gh api -X PUT repos/Morrison-Lab/ai-config/pulls/12/merge",
              [])[0])
    check("warns when a claude CLI run is this harness's own",
          run(MERGE, [step("claude -p 'review'")])[0])
    check("warns when the reviewer word is only echoed",
          run(MERGE, [step("echo codex exec review")])[0])
    check("warns when a skill was only loaded, with no reviewer call",
          run(MERGE, [skill("dtc")])[0])
    check("warns when the CLI only printed its version",
          run(MERGE, [step("codex --version")])[0])
    check("warns when the CLI was only logged in",
          run(MERGE, [step("opencode auth login")])[0])
    check("warns on a bare CLI word with no arguments",
          run(MERGE, [step("gemini")])[0])
    check("warns when one command reviews and then pushes",
          run(MERGE, [step("codex exec review && git push origin b")])[0])
    check("warns on a reviewer launched from a background script",
          run(MERGE, [step("nohup bash /tmp/w/run.sh > /tmp/w/log 2>&1 &")])[0])
    check("warns when timeout wraps only a --version call",
          run(MERGE, [step("timeout 30 codex --version")])[0])
    check("warns when a nested bash -c review precedes a push",
          run(MERGE, [step("bash -c 'codex exec review' && git push origin b")])[0])
    check("warns when the push and review sit in different expansions",
          run(MERGE, [step("bash -c 'git push origin b' && codex exec review")])[0])
    check("warns when a subcommand only printed its help",
          run(MERGE, [step("codex exec --help")])[0])
    check("warns on a PowerShell-keyed merge that pushes first",
          run("", [CODEX], tool_input={
              "CommandLine": "git push origin b; gh pr merge 12 --squash"})[0])
    check("warns on the instrument-then-merge chain the sibling discharges",
          run("python3 scripts/check-pr-fully-clean.py 12 && gh pr merge 12",
              [])[0])
    fired, out = run("gh pr merge 12 --squash && gh pr merge 13 --squash", [])
    check("warns naming every PR a compound merge targets",
          fired and "PR #12, #13" in (out or {}).get("systemMessage", ""))

    # --- silent -----------------------------------------------------------
    check("silent after a codex run following the last push",
          not run(MERGE, [PUSH, CODEX])[0])
    check("silent after an opencode run",
          not run(MERGE, [OPENCODE])[0])
    check("silent after the dtc skill plus the codex call it makes",
          not run(MERGE, [skill("dtc"), CODEX])[0])
    check("silent after an env-prefixed codex call",
          not run(MERGE, [step("OPENAI_API_KEY=x codex exec review")])[0])
    check("silent when one command pushes and then reviews",
          not run(MERGE, [step("git push origin b && codex exec review")])[0])
    check("silent after a timeout-wrapped codex call",
          not run(MERGE, [step("timeout -k 5 300 codex exec review")])[0])
    check("silent after a nohup-wrapped opencode call",
          not run(MERGE, [step("nohup opencode run 'review' &")])[0])
    check("silent on the MCP merge tool after a codex run",
          not run("", [CODEX], tool_name="mcp__github__merge_pull_request",
                  tool_input=MCP_MERGE)[0])
    check("silent after a claude CLI run from an Antigravity session",
          not run(MERGE, [step("claude -p 'review'")],
                  env_extra={"ANTIGRAVITY_AGENT": "1"})[0])
    check("silent after a PowerShell-keyed reviewer call in the transcript",
          not run(MERGE, [step("", tool_input={
              "CommandLine": "codex exec review"})])[0])
    check("silent after a timeout call with no duration",
          not run(MERGE, [step("timeout codex exec review")])[0])
    check("silent on disabling auto-merge through MCP",
          not run("", [], tool_name="mcp__github__disable_pr_auto_merge",
                  tool_input=MCP_MERGE)[0])
    check("silent on a command that is not a merge",
          not run("git status", [])[0])
    check("silent when a heredoc body names the merge",
          not run("cat <<'EOF'\ngh pr merge 12\nEOF", [])[0])
    check("silent on an unrelated MCP tool",
          not run("", [], tool_name="mcp__github__get_me", tool_input={})[0])

    # --- robustness -------------------------------------------------------
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
