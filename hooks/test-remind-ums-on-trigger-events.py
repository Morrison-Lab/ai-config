#!/usr/bin/env python3
"""Tests for hooks/remind-ums-on-trigger-events.py (ai-config#4480)."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "remind-ums-on-trigger-events.py")
failures = 0


def run(payload, tmp=None):
    tmp = tmp or tempfile.mkdtemp()
    p = subprocess.run([sys.executable, HOOK], input=payload if isinstance(payload, str) else json.dumps(payload),
                       capture_output=True, text=True, env=dict(os.environ, TMPDIR=tmp))
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def check(desc, ok):
    global failures
    failures += not ok
    print(f"  {'ok' if ok else 'WRONG':<6} {desc}")


def relay(reason, note):
    attr = f' reason="{reason}"' if reason else ""
    return (f'<coordinator-relay><relay from="coordinator" session="s"{attr}>'
            f"<note>{note}</note></relay></coordinator-relay>")


ups = lambda p: {"hook_event_name": "UserPromptSubmit", "prompt": p, "transcript_path": "/t"}
check("coordinator correction note reminds",
      "coordinator" in run(ups(relay("", "Install TinyTeX; do not defer to CI."))))
check("a spawn brief does not", run(ups(relay("spawn", "Fix the bug."))) == "")
check("a relay with an empty note does not", run(ups(relay("", "  "))) == "")
for grant in ("daytb", "yes, do it", "Your call.", "rec?"):
    check(f"grant {grant!r} reminds", "grant" in run(ups(grant)))
check("a grant inside a task sentence does not", run(ups("please do it in R and render the page")) == "")
check("'ums' reminds in both places", "BOTH" in run(ups("ums")) and "ai-config and/or" in run(ups("ums please")))
check("'sums' and '/ums' are silent", run(ups("the sums of squares")) == "" and run(ups("/ai-config:ums")) == "")
check("coordinator note names both places", "ai-config and/or" in run(ups(relay("", "Fix X."))))
check("plain prompt is silent", run(ups("fix the failing test")) == "")
check("compaction reminds", "compacted" in run({"hook_event_name": "SessionStart", "source": "compact", "session_id": "a"}))
check("startup does not", run({"hook_event_name": "SessionStart", "source": "startup", "session_id": "a"}) == "")
for cmd in ("git revert abc123", "cd r && git reset --hard origin/main"):
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}})
    check(f"{cmd!r} adds context", "additionalContext" in out and "deny" not in out)
check("git status is silent",
      run({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status"}}) == "")
tmp = tempfile.mkdtemp()
note = ups(relay("", "same note"))
check("fires once per distinct note", run(note, tmp) != "" and run(note, tmp) == "")
for raw in ("", "not json", "[1]"):
    check(f"malformed {raw!r} is silent", run(raw) == "")
# A cp1252 console used to drop a note holding curly quotes: the hook read the
# UTF-8 payload as cp1252 and stayed silent (ai-config#5462).
curly = relay("", f"Don{chr(0x2019)}t defer {chr(0x201C)}this{chr(0x201D)} to CI.")
fresh = tempfile.mkdtemp()  # all three, as scripts/test_hooks.py sets them
p = subprocess.run([sys.executable, HOOK], capture_output=True, timeout=30,
                   input=json.dumps(ups(curly), ensure_ascii=False).encode("utf-8"),
                   env=dict(os.environ, PYTHONIOENCODING="cp1252", TMPDIR=fresh, TEMP=fresh, TMP=fresh))
check("a curly-quoted note reminds under cp1252", p.returncode == 0 and b"coordinator" in p.stdout)


# tool-error (ai-config#5630): the newest tool result is an error.
def transcript(command, result, is_error=True, name="Bash"):
    path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
    use = {"type": "tool_use", "id": "tu1", "name": name, "input": {"command": command}}
    res = {"type": "tool_result", "tool_use_id": "tu1", "is_error": is_error, "content": result}
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "assistant", "message": {"content": [use]}}) + "\n")
        fh.write(json.dumps({"type": "user", "message": {"content": [res]}}) + "\n")
    return path


def pre(path, tmp=None, tool="Bash", command="ls"):
    return run({"hook_event_name": "PreToolUse", "tool_name": tool,
                "tool_input": {"command": command}, "transcript_path": path}, tmp)


out = pre(transcript("gh api search/issues -f q=x", "Exit code 1\ngh: Query must include 'is:issue'"))
check("a failed command reminds on the next call", "Query must include" in out and "UMS" in out)
check("the reminder is context, not a deny", "additionalContext" in out and '"deny"' not in out)
hook_denied = [{"type": "text", "text": "PreToolUse:Bash hook error: Refused: a heredoc"}]
check("a hook denial (list content) reminds", "Refused" in pre(transcript("python3 - <<EOF", hook_denied)))
check("an MCP tool error reminds on any next tool",
      "mcp__github__issue_write" in pre(transcript("", "InputValidationError: bad", name="mcp__github__issue_write"),
                                       tool="mcp__hearthbot__post_message"))
check("a successful result is silent", pre(transcript("ls", "a\nb", is_error=False)) == "")
same = transcript("gh pr view x", "Exit code 1\nunknown flag: --x")
tmp = tempfile.mkdtemp()
check("fires once per error", pre(same, tmp) != "" and pre(same, tmp) == "")
for cmd, res in (("grep -n foo bar.txt", "Exit code 1"), ("rg foo", "Exit code 1"),
                 ("test -f x", "Exit code 1"), ("[ -d x ]", "Exit code 1"), ("diff a b", "Exit code 1\n1c1"),
                 ("git diff --quiet", "Exit code 1"), ("EXPECT_FAIL=1 make check", "Exit code 2\nboom"),
                 ("pytest -k bad  # expect-fail", "Exit code 1\nFAILED")):
    check(f"expected error {cmd!r} is silent", pre(transcript(cmd, res)) == "")
check("grep that errors (exit 2) still reminds",
      "No such file" in pre(transcript("grep foo missing.txt", "Exit code 2\ngrep: missing.txt: No such file")))
check("grep exit 1 with stderr still reminds",
      "unmatched" in pre(transcript("grep '(' f", "Exit code 1\ngrep: unmatched (")))
for cmd, res in (("cd r && grep foo f", "Exit code 1"), ("ls; grep foo f", "Exit code 1"),
                 ("git -C r grep foo", "Exit code 1"), ("grep -c foo f", "Exit code 1\n0"),
                 ("cat f | rg foo", "Exit code 1"), ("git -C repo diff --exit-code", "Exit code 1")):
    check(f"expected error in a compound {cmd!r} is silent", pre(transcript(cmd, res)) == "")
# shlex keeps a quoted operator inside its stage, and skips an empty last stage.
for cmd in ('rg "foo|bar" file', 'grep -E "a|b" f', "grep foo f;", "grep 'x && y' f", "cd r && grep foo f ;", "grep foo f 2>&1"):
    check(f"a quoted or trailing operator in {cmd!r} is still an expected no-match",
          pre(transcript(cmd, "Exit code 1")) == "")
for cmd in ('echo "x" | grep "a;b" f && make', "python3 - <<EOF\ngrep x\nEOF", "echo \"unbalanced; grep x",
            "python runner.py git diff --quiet"):
    check(f"{cmd!r}, whose last stage is not a search, still reminds",
          "UMS" in pre(transcript(cmd, "Exit code 1")))
check("an expect-fail phrase inside a commit message still reminds",
      "boom" in pre(transcript("git commit -m 'no # expected fail here' && false", "Exit code 1\nboom")))
check("grep followed by a failing stage still reminds",
      "nope" in pre(transcript("grep foo f && make", "Exit code 2\nnope")))
check("a call the user declined is silent",
      pre(transcript("rm -rf x", "The user doesn't want to proceed with this tool use.")) == "")


def parallel(results, pending=False):
    """Calls made in one turn with the given (is_error, text) results, then optionally a pending call."""
    path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
    uses = [{"type": "tool_use", "id": f"p{i}", "name": "Bash", "input": {"command": f"cmd{i}"}}
            for i in range(len(results))]
    res = [{"type": "tool_result", "tool_use_id": f"p{i}", "is_error": err, "content": text}
           for i, (err, text) in enumerate(results)]
    entries = [{"type": "assistant", "message": {"content": [u]}} for u in uses]
    entries += [{"type": "user", "message": {"content": [r]}} for r in res]
    if pending:
        entries.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "next", "name": "Bash", "input": {"command": "ls"}}]}})
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(e) + "\n" for e in entries)
    return path


check("an error before a success in a parallel batch reminds",
      "first broke" in pre(parallel([(True, "Exit code 2\nfirst broke"), (False, "ok")])))
check("the pending call's own tool_use does not hide the batch's error",
      "first broke" in pre(parallel([(True, "Exit code 2\nfirst broke"), (False, "ok")], pending=True)))
old_batch = parallel([(True, "Exit code 2\nold")])
with open(old_batch, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "q", "name": "Bash", "input": {"command": "ls"}}]}}) + "\n")
    fh.write(json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "q", "is_error": False, "content": "a"}]}}) + "\n")
check("an error from an earlier batch is silent once a later batch succeeds", pre(old_batch) == "")
# A tail cut before an old call leaves its error result with no call; it must
# not count as the newest batch.
orphan = os.path.join(tempfile.mkdtemp(), "t.jsonl")
with open(orphan, "w", encoding="utf-8") as fh:
    fh.write(json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "gone", "is_error": True, "content": "Exit code 2\nancient"}]}}) + "\n")
    fh.write(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "r", "name": "Bash", "input": {"command": "ls"}}]}}) + "\n")
    fh.write(json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "r", "is_error": False, "content": "a"}]}}) + "\n")
check("an error whose call fell before the tail is silent", pre(orphan) == "")
check("a missing transcript is silent", pre("/nonexistent/t.jsonl") == "")


# ci-failure (ai-config#1100): the newest result shows a failed check run.
def runs(*conclusions):
    return json.dumps({"total_count": len(conclusions), "check_runs": [
        {"id": i, "name": f"job{i}", "status": "completed", "conclusion": c} for i, c in enumerate(conclusions)]})


out = pre(transcript("", runs("success", "failure"), is_error=False, name="mcp__github__pull_request_read"))
check("a failed check run reminds and names it", "failed CI check" in out and "job1" in out and "job0" not in out)
check("the ci-failure reminder is context, not a deny", "additionalContext" in out and '"deny"' not in out)
for c in ("timed_out", "startup_failure"):
    check(f"conclusion {c!r} reminds", "failed CI check" in pre(transcript("", runs(c), is_error=False)))
check("a workflow run (actions_get shape) reminds",
      "validate" in pre(transcript("", json.dumps({"id": 9, "name": "validate", "conclusion": "failure"}),
                                   is_error=False)))
for c in ("success", "skipped", "cancelled", "neutral", None):
    check(f"conclusion {c!r} is silent", pre(transcript("", runs(c), is_error=False)) == "")
check("prose mentioning a failure conclusion is silent",
      pre(transcript("", 'the run had "conclusion": "failure" earlier', is_error=False)) == "")
same_ci = transcript("", runs("failure"), is_error=False)
tmp = tempfile.mkdtemp()
check("fires once per set of failed checks", pre(same_ci, tmp) != "" and pre(same_ci, tmp) == "")
print(f"\n{'FAILED' if failures else 'all passed'}: {failures} wrong")
sys.exit(1 if failures else 0)
