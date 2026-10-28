#!/usr/bin/env python3
"""Tests for hooks/block-merge-without-clean-checker.py.

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
HOOK = os.path.join(HOOKS_DIR, "block-merge-without-clean-checker.py")

PASSED = []
FAILED = []

SHA = "6ebf005" + "a" * 33          # the head being merged (40 hex)
OTHER = "f450d6f" + "b" * 33        # a different head
REPO = "Morrison-Lab/psw"
MCP = "mcp__github__merge_pull_request"


def line(sha=SHA, n=354, repo=REPO):
    return f"✅ {repo}#{n} is FULLY CLEAN on HEAD {sha[:8]}!"


def bash(cmd, out="", sidechain=False):
    return {"kind": "tool", "tool": "Bash", "input": {"command": cmd},
            "out": out, "sidechain": sidechain}


def checker(n=354, repo=REPO, out=None, **kw):
    return bash(f"python3 scripts/check-pr-fully-clean.py {n} -R {repo}",
                line() if out is None else out, **kw)


def relay_tool(name, out):
    return {"kind": "tool", "tool": name, "input": {}, "out": out,
            "sidechain": False}


def user_text(text):
    return {"kind": "user", "text": text}


def assistant_text(text):
    return {"kind": "assistant", "text": text}


def agy_checker(n=354, repo=REPO, out=None, status="DONE"):
    return {"kind": "agy", "cmd": f"python3 scripts/check-pr-fully-clean.py {n} -R {repo}",
            "out": line() if out is None else out, "status": status}


def agy_user_text(text):
    return {"kind": "agy_user", "text": text}


def transcript(steps):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for i, s in enumerate(steps):
            if s["kind"] == "user":
                fh.write(json.dumps({"type": "user", "message": {
                    "role": "user", "content": s["text"]}}) + "\n")
            elif s["kind"] == "agy_user":
                fh.write(json.dumps({"type": "USER_INPUT", "content": s["text"]}) + "\n")
            elif s["kind"] == "agy":
                fh.write(json.dumps({
                    "step_index": i * 2,
                    "type": "PLANNER_RESPONSE",
                    "tool_calls": [{
                        "id": f"agy_{i}",
                        "name": "run_command",
                        "args": {"CommandLine": json.dumps(s["cmd"])},
                    }],
                }) + "\n")
                fh.write(json.dumps({
                    "step_index": i * 2 + 1,
                    "type": "GENERIC",
                    "status": s["status"],
                    "content": (
                        "Created At: 2026-10-27T23:39:27-07:00\n"
                        "Completed At: 2026-10-27T23:39:29-07:00\n"
                        "Command exited with code 0.\n\n"
                        "Command output:\n" + s["out"]
                    ),
                }) + "\n")
            elif s["kind"] == "assistant":
                fh.write(json.dumps({"type": "assistant", "message": {
                    "content": [{"type": "text", "text": s["text"]}]}}) + "\n")
            else:
                tid = f"toolu_{i}"
                fh.write(json.dumps({
                    "type": "assistant", "isSidechain": s["sidechain"],
                    "message": {"content": [{
                        "type": "tool_use", "id": tid, "name": s["tool"],
                        "input": s["input"]}]}}) + "\n")
                fh.write(json.dumps({
                    "type": "user", "isSidechain": s["sidechain"],
                    "message": {"content": [{
                        "type": "tool_result", "tool_use_id": tid,
                        "content": [{"type": "text", "text": s["out"]}]}]},
                }) + "\n")
    return path


def run(tool, tool_input, steps):
    """Return (denied, output_or_none). Raises on a crashed hook."""
    path = transcript(steps)
    try:
        payload = {"tool_name": tool, "tool_input": tool_input,
                   "transcript_path": path}
        proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError("FATAL: hook exited %s\nstderr: %s"
                                 % (proc.returncode, proc.stderr))
        out = proc.stdout.strip()
        if not out:
            return False, None
        data = json.loads(out)
        return (data["hookSpecificOutput"]["permissionDecision"] == "deny"), data
    finally:
        os.unlink(path)


def mcp(steps, sha=SHA, n=354, repo="psw"):
    inp = {"owner": "Morrison-Lab", "repo": repo, "pullNumber": n}
    if sha is not None:
        inp["expectedHeadSha"] = sha
    return run(MCP, inp, steps)


def gh(cmd, steps):
    return run("Bash", {"command": cmd}, steps)


def check(label, cond):
    (PASSED if cond else FAILED).append(label)
    print(("PASS: " if cond else "FAIL: ") + label)


GH_OK = f"gh pr merge 354 -R {REPO} --squash --match-head-commit {SHA}"


def main():
    # --- denies ----------------------------------------------------------
    denied, out = mcp([])
    check("denies an MCP merge with no checker evidence", denied)
    check("...naming the repo, PR and the checker command",
          out and f"{REPO}#354" in out["reason"]
          and "check-pr-fully-clean.py 354" in out["reason"])
    check("...and pointing the cloud case at Remote Control",
          out and "Remote Control" in out["reason"])
    check("denies when the only run was for a DIFFERENT head (psw#354 case)",
          mcp([bash(f"python3 scripts/check-pr-fully-clean.py 354 -R {REPO}",
                    line(OTHER))])[0])
    check("denies when the run was for a DIFFERENT PR number",
          mcp([checker(out=line(n=99))])[0])
    check("denies when the run was for a DIFFERENT repo",
          mcp([checker(out=line(repo="Morrison-Lab/gha"))])[0])
    check("denies when the merge pins no head sha",
          mcp([checker()], sha=None)[0])
    check("denies when the pinned sha is abbreviated",
          mcp([checker()], sha=SHA[:8])[0])
    check("denies on a NOT-fully-clean veto beside a clean line",
          mcp([checker(out=line() + "\nPR is NOT fully clean:\n - x")])[0])
    check("denies a subagent's (sidechain) checker run",
          mcp([checker(sidechain=True)])[0])
    check("denies a line the model only SAID in its own prose",
          mcp([assistant_text(line())])[0])
    check("denies a line merely ECHOED by Bash",
          mcp([bash(f"echo '{line()}'", line())])[0])
    check("denies a line printed by a command that also names the checker",
          mcp([bash("python3 scripts/check-pr-fully-clean.py --help; "
                    f"echo '{line()}'", line())])[0])
    check("denies a grep that names the checker",
          mcp([bash("grep -n x scripts/check-pr-fully-clean.py", line())])[0])
    check("denies a checker run whose result has no FULLY CLEAN line",
          mcp([checker(out="PR is NOT fully clean:\n - x")])[0])
    check("denies a backgrounded checker run (silence is not success)",
          mcp([checker(out="Command running in background with ID: b1")])[0])
    check("denies a merge naming no repository",
          run(MCP, {"pullNumber": 354, "expectedHeadSha": SHA}, [checker()])[0])

    # --- allows: local / Bash evidence ------------------------------------
    check("allows an MCP merge after a matching checker run",
          not mcp([checker()])[0])
    check("allows with the full 40-char sha matching the 8-char printed prefix",
          not mcp([checker()], sha=SHA.upper())[0])
    check("allows when the checker ran via `cd X && python3 ...`",
          not mcp([bash(f"cd /home/user/ai-config && python3 "
                        f"scripts/check-pr-fully-clean.py 354 -R {REPO}",
                        line())])[0])
    check("allows when the checker ran with --from-json (cloud payload)",
          not mcp([bash(f"python3 scripts/check-pr-fully-clean.py "
                        f"--from-json /tmp/p.json -R {REPO} 354",
                        line())])[0])
    check("allows an Antigravity PLANNER_RESPONSE + GENERIC checker run",
          not gh(GH_OK, [agy_checker()])[0])
    check("denies an Antigravity checker run with status=ERROR",
          gh(GH_OK, [agy_checker(status="ERROR")])[0])
    check("allows a RELAYED line in an Antigravity USER_INPUT record",
          not gh(GH_OK, [agy_user_text("RC result:\n" + line())])[0])

    # --- allows: relayed evidence (cloud) ---------------------------------
    check("allows a RELAYED line in a user-role message (RC session output)",
          not mcp([user_text("RC result:\n" + line())])[0])
    check("allows a RELAYED line from ReadNotifications",
          not mcp([relay_tool("ReadNotifications", line())])[0])
    check("allows a RELAYED line from a hearthbot read",
          not mcp([relay_tool("mcp__hearthbot__read_thread", line())])[0])
    check("a relayed line for another head still denies",
          mcp([user_text(line(OTHER))])[0])
    check("a line in an unrelated tool's result does not count",
          mcp([relay_tool("Read", line())])[0])

    # --- other merge routes ------------------------------------------------
    check("denies `gh pr merge` with no evidence",
          gh(GH_OK, [])[0])
    check("allows `gh pr merge` with evidence and --match-head-commit",
          not gh(GH_OK, [checker()])[0])
    check("denies `gh pr merge` without --match-head-commit",
          gh(f"gh pr merge 354 -R {REPO} --squash", [checker()])[0])
    check("denies `gh pr merge` with no PR number",
          gh(f"gh pr merge -R {REPO} --match-head-commit {SHA}", [checker()])[0])
    check("denies `gh pr merge` in a && chain with no prior evidence",
          gh(f"python3 scripts/check-pr-fully-clean.py 354 -R {REPO} && "
             + GH_OK, [])[0])
    check("denies a merge hidden in a `bash -c` string",
          gh(f"bash -c '{GH_OK}'", [])[0])
    api = (f"gh api -X PUT repos/{REPO}/pulls/354/merge -f sha={SHA}")
    check("denies `gh api -X PUT .../merge` with no evidence", gh(api, [])[0])
    check("allows `gh api -X PUT .../merge -f sha=` with evidence",
          not gh(api, [checker()])[0])
    check("denies `gh api -X PUT .../merge` without a sha",
          gh(f"gh api -X PUT repos/{REPO}/pulls/354/merge", [checker()])[0])
    curl = (f"curl -X PUT https://api.github.com/repos/{REPO}/pulls/354/merge "
            f"-d '{{\"sha\":\"{SHA}\"}}'")
    check("denies a curl REST merge with no evidence", gh(curl, [])[0])
    check("allows a curl REST merge with evidence and a body sha",
          not gh(curl, [checker()])[0])
    check("denies a GraphQL mergePullRequest even after a clean run",
          gh("gh api graphql -f query='mutation { mergePullRequest(input: "
             "{pullRequestId: \"X\"}) { clientMutationId } }'", [checker()])[0])
    check("a merge in a gh -R global flag position is parsed",
          gh(f"gh -R {REPO} pr merge 354 --match-head-commit {SHA}",
             [checker()])[0] is False)

    # --- inert: not a merge ----------------------------------------------
    check("silent for a curl GET of .../merge (the is-merged probe)",
          not gh(f"curl https://api.github.com/repos/{REPO}/pulls/354/merge",
                 [])[0])
    check("silent for an unrelated command", not gh("git status", [])[0])
    check("silent for gh pr view", not gh("gh pr view 354", [])[0])
    check("silent when the merge is only echoed",
          not gh(f'echo "{GH_OK}"', [])[0])
    check("silent when the merge is inside a commit message",
          not gh("git commit -m 'run gh pr merge 12 later'", [])[0])
    check("silent when a heredoc body names the merge",
          not gh(f"cat <<'EOF'\n{GH_OK}\nEOF", [])[0])
    check("silent for another MCP tool",
          not run("mcp__github__get_commit", {"owner": "a"}, [])[0])
    check("silent for a non-shell tool", not run("Read", {"file_path": "x"}, [])[0])

    # --- robustness --------------------------------------------------------
    proc = subprocess.run([sys.executable, HOOK], input="not json",
                          capture_output=True, text=True)
    check("fails open on a malformed payload",
          proc.returncode == 0 and not proc.stdout.strip())
    proc = subprocess.run(
        [sys.executable, HOOK], capture_output=True, text=True,
        input=json.dumps({"tool_name": MCP, "transcript_path": "/nonexistent",
                          "tool_input": {"owner": "a", "repo": "b",
                                         "pullNumber": 1,
                                         "expectedHeadSha": SHA}}))
    check("fails open when the transcript is missing",
          proc.returncode == 0 and not proc.stdout.strip())

    check("negative control: both outcomes were exercised",
          any("allows" in lbl for lbl in PASSED)
          and any("denies" in lbl for lbl in PASSED))

    print("\n%d passed, %d failed" % (len(PASSED), len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
