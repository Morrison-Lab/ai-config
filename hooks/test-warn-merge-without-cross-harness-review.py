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
                "type": "user", **s.get("rec", {}),
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
        "permissionDecisionReason", "")
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
    fired, out = run("gh pr merge 12 --squash || gh pr merge 12 --merge", [])
    check("warns naming a repeated PR once",
          fired and "PR #12 " in (out or {}).get("systemMessage", ""))
    ctx = ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")
    check("warns with clean un-duplicated text naming the gate",
          fired and "Then the gate is waived" in ctx)
    check("warns after an opencode.ai install script curl",
          run(MERGE, [step("curl -fsSL https://opencode.ai/install | bash")])[0])
    check("warns after an opencode.ai models endpoint curl",
          run(MERGE, [step("curl -s https://opencode.ai/zen/go/v1/models")])[0])
    check("warns after an opencode.ai docs endpoint curl",
          run(MERGE, [step("curl https://opencode.ai/docs")])[0])
    check("warns after a look-alike host curl",
          run(MERGE, [step("curl -s https://opencode.ai.example.com/zen/go/v1/chat/completions -d '{\"model\":\"kimi-k3\"}'")])[0])
    check("warns after an opencode.ai curl with --help",
          run(MERGE, [step("curl --help https://opencode.ai/zen/go/v1/chat/completions -d '{\"model\":\"kimi-k3\"}'")])[0])
    check("warns after an opencode.ai curl with no payload",
          run(MERGE, [step("curl -s https://opencode.ai/zen/go/v1/chat/completions")])[0])

    # --- silent -----------------------------------------------------------
    # Cancelling an auto-merge or asking for help merges nothing, so it needs
    # no review (ai-config#5406), as the MCP disable-auto-merge tool does not.
    check("silent on `gh pr merge N --disable-auto` with no reviewer run",
          not run("gh pr merge 12 --disable-auto", [])[0])
    check("silent on `gh pr merge --help` with no reviewer run",
          not run("gh pr merge --help", [])[0])
    check("silent after a codex run following the last push",
          not run(MERGE, [PUSH, CODEX])[0])
    check("silent after an opencode run",
          not run(MERGE, [OPENCODE])[0])
    check("silent after a curl call to opencode.ai chat completions",
          not run(MERGE, [step("curl -s https://opencode.ai/zen/go/v1/chat/completions -d '{\"model\":\"kimi-k3\"}'")])[0])
    check("silent after a curl call with --json to opencode.ai",
          not run(MERGE, [step("curl -s https://opencode.ai/zen/go/v1/chat/completions --json '{\"model\":\"kimi-k3\"}'")])[0])
    check("silent after a curl call with combined -sd flags to opencode.ai",
          not run(MERGE, [step("curl -sd '{\"model\":\"kimi-k3\"}' https://opencode.ai/zen/go/v1/chat/completions")])[0])
    check("silent after a timeout-wrapped curl call to opencode.ai",
          not run(MERGE, [step("timeout 900 curl -s https://opencode.ai/zen/go/v1/chat/completions -d '{\"model\":\"kimi-k3\"}'")])[0])
    check("silent after a timeout call with no duration on curl",
          not run(MERGE, [step("timeout curl -s https://opencode.ai/zen/go/v1/chat/completions -d '{\"model\":\"kimi-k3\"}'")])[0])
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
    # ai-config#5383: only a listed review form counts, never housekeeping.
    for cmd in ("opencode stats", "opencode session list", "codex completion bash",
                "codex apply", "gemini extensions list", "cursor-agent ls",
                "agy models", "codex -m o3", "gemini 'review'"):
        check("warns after housekeeping: " + cmd, run(MERGE, [step(cmd)])[0])
    for cmd in ("codex e 'review'", "codex review", "codex exec -m o3 'review'",
                "opencode run -m x 'review'", "agy --print 'review'", "agy -p 'review'",
                "gemini -p 'review'", "gemini --prompt='review'",
                "cursor-agent -p 'review'", "cursor-agent --print 'review'"):
        check("silent after a review call: " + cmd,
              not run(MERGE, [step(cmd)])[0])
    for cmd in ("agy -p='review' --mode plan", "agy -preview", "codex exec -- --help"):
        check("silent after a review call: " + cmd, not run(MERGE, [step(cmd)])[0])
    check("warns when the print flag only follows --",
          run(MERGE, [step("cursor-agent -- -p")])[0])
    check("silent on disabling auto-merge through MCP",
          not run("", [], tool_name="mcp__github__disable_pr_auto_merge",
                  tool_input=MCP_MERGE)[0])
    check("silent on a command that is not a merge",
          not run("git status", [])[0])
    check("silent when a heredoc body names the merge",
          not run("cat <<'EOF'\ngh pr merge 12\nEOF", [])[0])
    check("silent on an unrelated MCP tool",
          not run("", [], tool_name="mcp__github__get_me", tool_input={})[0])

    # --- Antigravity transcript schema & harness detection (#4653) -------
    def run_agy(records_list, command=MERGE, env_extra=None,
                subdir="brain/conv-1/.system_generated/logs"):
        import shutil
        tdir = tempfile.mkdtemp()
        try:
            ldir = os.path.join(tdir, subdir)
            os.makedirs(ldir, exist_ok=True)
            path = os.path.join(ldir, "transcript.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for rec in records_list:
                    fh.write(json.dumps(rec) + "\n")
            payload = {
                "tool_name": "run_command",
                "tool_input": {"CommandLine": command},
                "transcript_path": path,
            }
            env = dict(os.environ)
            env.pop("ANTIGRAVITY_AGENT", None)
            env.update(env_extra or {})
            proc = subprocess.run([sys.executable, HOOK],
                                  input=json.dumps(payload),
                                  capture_output=True, text=True, env=env)
            if proc.returncode != 0:
                raise AssertionError(
                    "FATAL: hook exited %s on %r\nstderr: %s"
                    % (proc.returncode, command, proc.stderr))
            out = proc.stdout.strip()
            return (True, json.loads(out)) if out else (False, None)
        finally:
            shutil.rmtree(tdir, ignore_errors=True)

    agy_claude_call = {
        "type": "PLANNER_RESPONSE",
        "tool_calls": [{
            "name": "run_command",
            "args": {"CommandLine": json.dumps("claude -p --permission-mode plan 'review'")},
        }],
    }
    agy_ok_out = {
        "type": "GENERIC",
        "status": "DONE",
        "content": (
            "Created At: 2026-10-27T16:29:10-07:00\n"
            "Completed At: 2026-10-27T16:29:22-07:00\n"
            "Command exited with code 0.\n\nCommand output:\nVerdict: Ready to merge"
        ),
    }
    check("silent after a claude -p run in an Antigravity transcript (even without ANTIGRAVITY_AGENT env)",
          not run_agy([agy_claude_call, agy_ok_out])[0])
    check("silent after a backgrounded claude -p run finishing via SYSTEM_MESSAGE in Antigravity",
          not run_agy([
              agy_claude_call,
              {"type": "GENERIC", "status": "DONE",
               "content": "Tool is running as a background task with task id: conv/task-9"},
              {"type": "SYSTEM_MESSAGE", "status": "DONE",
               "content": ('The following is a <SYSTEM_MESSAGE> not actually sent by the user.\n'
                           '<SYSTEM_MESSAGE>\nTask id "conv/task-9" finished with result:\n'
                           'Command exited with code 0.\n\nCommand output:\nok\n</SYSTEM_MESSAGE>')},
          ])[0])
    check("warns when an older-format Antigravity claude -p run exited non-zero ('The command exited with code 1.')",
          run_agy([
              agy_claude_call,
              {"type": "GENERIC", "status": "DONE",
               "content": (
                   "Created At: 2026-10-19T12:00:00Z\n"
                   "Completed At: 2026-10-19T12:00:02Z\n"
                   "The command exited with code 1.\nOutput:\nerror"
               )},
          ])[0])
    check("silent when a zero-exit claude -p review mentions 'command exited with code 1' in its output body",
          not run_agy([
              agy_claude_call,
              {"type": "GENERIC", "status": "DONE",
               "content": (
                   "Created At: 2026-10-27T16:29:10-07:00\n"
                   "Completed At: 2026-10-27T16:29:22-07:00\n"
                   "Command exited with code 0.\n\nCommand output:\n"
                   "command exited with code 1 in earlier test"
               )},
          ])[0])
    agy_out = lambda code: {"type": "GENERIC", "status": "DONE", "content": (
        "Created At: 2026-11-11T10:00:00Z\nCommand exited with code %d.\n\nCommand output:\n" % code)}
    agy_cmd = lambda c: {"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": json.dumps(c)}}]}
    agy_pass = [agy_cmd("command -v claude codex cursor-agent"), agy_out(1), agy_cmd("opencode run x"), agy_out(1)]
    check("silent after an Antigravity probe pass", not run_agy(agy_pass)[0] and run_agy(agy_pass[:1] + [agy_out(2)] + agy_pass[2:])[0])
    check("warns when out-of-order step_index has view_file succeed (step 8) and claude -p fail (step 9)",
          run_agy([
              {"step_index": 8, "type": "GENERIC", "status": "DONE",
               "content": "Showing lines 1-10 of foo.py"},
              {"step_index": 7, "type": "PLANNER_RESPONSE",
               "tool_calls": [
                   {"name": "view_file", "args": {"Path": "/tmp/foo.py"}},
                   {"name": "run_command", "args": {"CommandLine": "claude -p 'review'"}},
               ]},
              {"step_index": 9, "type": "GENERIC", "status": "DONE",
               "content": (
                   "Created At: 2026-10-27T16:29:10-07:00\n"
                   "Completed At: 2026-10-27T16:29:22-07:00\n"
                   "Command exited with code 1.\n\nCommand output:\nfailed"
               )},
          ])[0])
    check("silent when out-of-order step_index has view_file (step 8) before planner (step 7) and claude -p succeed (step 9)",
          not run_agy([
              {"step_index": 8, "type": "GENERIC", "status": "DONE",
               "content": "Showing lines 1-10 of foo.py"},
              {"step_index": 7, "type": "PLANNER_RESPONSE",
               "tool_calls": [
                   {"name": "view_file", "args": {"Path": "/tmp/foo.py"}},
                   {"name": "run_command", "args": {"CommandLine": "claude -p 'review'"}},
               ]},
              {"step_index": 9, "type": "GENERIC", "status": "DONE",
               "content": (
                   "Created At: 2026-10-27T16:29:10-07:00\n"
                   "Completed At: 2026-10-27T16:29:22-07:00\n"
                   "Command exited with code 0.\n\nCommand output:\nVerdict: Ready to merge"
               )},
          ])[0])
    fired_agy, out_agy = run_agy([
        {"type": "PLANNER_RESPONSE",
         "tool_calls": [{"name": "run_command",
                         "args": {"CommandLine": json.dumps("gemini -p 'review'")}}]},
        agy_ok_out,
    ])
    ctx_agy = ((out_agy or {}).get("hookSpecificOutput") or {}).get(
        "permissionDecisionReason", "")
    check("warns when an Antigravity session only ran gemini (same model family) and lists claude among qualifying CLIs",
          fired_agy and "claude" in ctx_agy and "agy," not in ctx_agy
          and "gemini" not in ctx_agy)
    check("warns when an Antigravity claude -p run exited non-zero",
          run_agy([
              agy_claude_call,
              {"type": "GENERIC", "status": "DONE",
               "content": (
                   "Created At: 2026-10-27T16:29:10-07:00\n"
                   "Completed At: 2026-10-27T16:29:22-07:00\n"
                   "Command exited with code 1.\n\nCommand output:\nerror"
               )},
          ])[0])

    # --- deny shape and the probe-pass waiver (ai-config#5290, #4849) -----
    fired, out = run(MERGE, [])
    hso = (out or {}).get("hookSpecificOutput") or {}
    check("warns as a deny, not a note riding on the merge",
          fired and hso.get("permissionDecision") == "deny"
          and "additionalContext" not in hso)
    clis4 = "codex agy gemini cursor-agent"

    def probe(cmd, out="Exit code 1", err=True):
        return step(cmd, out=out, is_error=err)
    oc = [probe("curl -sS https://opencode.ai/zen/go/v1/chat/completions"
                " -d @req.json", out="Exit code 56\ncurl: (56) CONNECT 403")]
    probe_all = [probe("command -v " + clis4)] + oc
    check("silent after every route was probed and found unrunnable", not run(MERGE, probe_all)[0]
          and not run(MERGE, [probe("command -v " + clis4, "\\nExit code 1"), dict(oc[0], out="Command timed out after 2m")])[0])
    check("warns when the probe pass skipped the opencode attempt",
          run(MERGE, probe_all[:1] + [probe("command -v opencode")])[0])
    check("warns when a probe found the CLI installed", run(MERGE, [probe(
        "command -v " + clis4, "Exit code 1\n/usr/local/bin/codex")] + oc)[0] and run(
        MERGE, [probe("command -v " + clis4, "Exit code 1\nalias codex='npx codex'")] + oc)[0]
          and all(run(MERGE, [probe("which " + clis4, o)] + oc)[0] for o in ("Exit code 1\ncodex: aliased to npx", "Exit code 1\ncodex () {", "Exit code 1\ncodex")))
    check("warns when which reports a CLI under a path", run(MERGE, [
        probe("which codex agy", "Exit code 1\n/usr/bin/codex"),
        probe("command -v agy gemini cursor-agent")] + oc)[0])
    check("warns when a later probe finds a CLI shown absent earlier", run(MERGE, probe_all + [probe("command -v codex", "/usr/bin/codex", False)])[0])
    check("warns when the probe was refused and never ran", run(MERGE, [dict(
        probe("command -v " + clis4), rec={"toolDenialKind": "permission-rule"})] + oc)[0] and run(
        MERGE, [probe("command -v " + clis4, "\\n\n Permission for this action was denied")] + oc)[0])
    check("warns when the opencode attempt was refused", run(MERGE, probe_all[:1] + [
        dict(oc[0], out="The user doesn't want to proceed with this tool use")])[0] and run(
        MERGE, probe_all[:1] + [dict(oc[0], rec={"toolDenialKind": "automode-blocked"})])[0])
    check("warns when the probe shares its call or exits other than 1", run(MERGE, [probe(
        "cd /nope && command -v " + clis4)] + oc)[0] and run(MERGE, [probe("command -v " + clis4, "Exit code 2")] + oc)[0]
          and all(run(MERGE, [probe(p + clis4)] + oc)[0] for p in ("which -s ", "command -V ")) and run(MERGE, [probe("which %s 2 > f" % clis4)] + oc)[0])
    check("silent when an installed CLI was attempted and errored", not run(
        MERGE, [probe("command -v agy gemini cursor-agent"),
                probe("codex exec 'review the diff'", "Exit code 1\nbackend down")] + oc)[0])
    check("warns when the probe's stdout was redirected away", run(
        MERGE, [probe("command -v %s >/dev/null" % clis4)] + oc)[0])
    check("warns when the probe exited 0 with empty output", run(
        MERGE, [probe("command -v %s || true" % clis4, "", False)] + oc)[0])
    check("warns when the probe pass predates the last push",
          run(MERGE, probe_all + [step("git push origin HEAD")])[0])
    check("warns when the probe pass ran only in a sidechain",
          run(MERGE, [dict(s, sidechain=True) for s in probe_all])[0])
    check("warns when a probe shares a call with a later push",
          run(MERGE, probe_all[1:] + [step(
              "command -v codex agy gemini cursor-agent; git push",
              out="Exit code 1", is_error=True)])[0])
    check("silent after a curl call to Ollama Cloud's chat API",
          not run(MERGE, [step("curl -sS https://k:s@api.ollama.com/api/chat"
                               " -d @req.json")])[0])
    check("warns after an Ollama Cloud curl forced to GET",
          run(MERGE, [step("curl -sS -X GET https://api.ollama.com/api/chat"
                           " -d @req.json")])[0])
    # ai-config#5363: a bundle holding X, G or I is not a POST either.
    for form in ("-XGET", "--request=GET", "-G", "-I", "-sSXGET", "-sSX GET",
                 "-sI", "-sG", "-LsI"):
        check("warns after an Ollama Cloud curl with " + form,
              run(MERGE, [step("curl -sS %s -d @req.json"
                               " https://api.ollama.com/api/chat" % form)])[0])
    check("warns when the Ollama URL is only the data payload",
          run(MERGE, [step("curl -sS https://example.com"
                           " -d https://api.ollama.com/api/chat")])[0] and run(MERGE, [step("curl --form-string https://api.ollama.com/api/chat https://example.com")])[0]
          and run(MERGE, [step("curl --data-ascii https://api.ollama.com/api/chat https://x.org")])[0])
    # ai-config#5383: every curl option that takes a value, not a short list.
    for opt in ("-w", "--write-out", "-o", "--output", "-e", "--referer",
                "--trace", "-sw", "-so"):
        check("warns when the Ollama URL is the value of " + opt,
              run(MERGE, [step("curl -d @x %s https://api.ollama.com/api/chat"
                               " https://example.com" % opt)])[0])
    check("silent when --url names the Ollama chat API",
          not run(MERGE, [step("curl -sS -d @req.json"
                               " --url https://api.ollama.com/api/chat")])[0])
    for opt in ("-4w", "-#o", "--proxy1.0", "--ech", "--haproxy-clientip",
                "--expand-header", "--expand-data"):
        check("warns when the Ollama URL is the value of " + opt,
              run(MERGE, [step("curl -d @x %s https://api.ollama.com/api/chat"
                               " https://example.com" % opt)])[0])
    # A value attached to its letter is self-contained, so the next word is the URL.
    # `-oGI` writes to a file named GI, so its G and I set no method.
    for opt in ("-XPOST", "-sXPOST", "-oout", "-uuser", "-fsSLoout", "-4", "-L1",
                "-sSXPOST", "-oGI", "-sSuGI:x"):
        check("silent after %s before the Ollama URL" % opt,
              not run(MERGE, [step("curl -d @x %s"
                                   " https://api.ollama.com/api/chat" % opt)])[0])
    check("silent after -XPOST before the opencode.ai URL",
          not run(MERGE, [step("curl -d @x -XPOST"
                               " https://opencode.ai/zen/go/v1/chat/completions")])[0])
    check("warns when the Ollama URL is only a --write-out= value",
          run(MERGE, [step("curl -d @x --write-out=https://api.ollama.com/api/chat"
                           " https://example.com")])[0])
    check("silent when the Ollama URL follows --",
          not run(MERGE, [step("curl -d @x -- https://api.ollama.com/api/chat")])[0])
    for cmd in ("-d -e", "--data -t", "-d x -H -x"):
        check("silent when an option value looks like an option: " + cmd,
              not run(MERGE, [step("curl %s https://api.ollama.com/api/chat" % cmd)])[0])
    check("silent when a bundled flag takes no value before the URL",
          not run(MERGE, [step("curl -sS -d @req.json -sS"
                               " https://api.ollama.com/api/chat")])[0])
    check("silent after an explicit -X POST to Ollama Cloud",
          not run(MERGE, [step("curl -sS -X POST https://api.ollama.com/api/chat"
                               " -d @req.json")])[0])
    check("warns when the probe word itself was not installed",
          run(MERGE, [step("which codex agy gemini cursor-agent",
                           out="Exit code 127\nbash: which: command not found",
                           is_error=True)] + probe_all[1:])[0])
    check("warns after an Ollama Cloud curl with no payload",
          run(MERGE, [step("curl -sS https://api.ollama.com/api/chat")])[0])

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
