#!/usr/bin/env python3
"""Tests for warn-pr-create-without-dupe-check.py.

The negative cases carry most of the weight. A reminder that fires on prose
about PR creation would fire on this corpus constantly, since fragments,
issue bodies, and the hook's own docstring all quote `gh pr create`.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "warn-pr-create-without-dupe-check.py")

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def write_transcript(commands):
    """Build a transcript file whose tool_use blocks carry `commands`."""
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8")
    for cmd in commands:
        fh.write(json.dumps({
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Bash",
                     "input": {"command": cmd}}
                ]
            }
        }) + "\n")
    fh.close()
    return fh.name


def run_hook(command, transcript_path=""):
    """Run the hook end-to-end; return its stdout."""
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "transcript_path": transcript_path,
    })
    proc = subprocess.run([sys.executable, HOOK], input=payload,
                          capture_output=True, text=True, timeout=10)
    return proc.stdout.strip()


# ---------------------------------------------------------------- creates_pr

check("plain gh pr create", hook.creates_pr("gh pr create --title x"), True)
check("glab mr create", hook.creates_pr("glab mr create"), True)
check("after &&",
      hook.creates_pr("git push && gh pr create --fill"), True)
check("after newline",
      hook.creates_pr("git push\ngh pr create --fill"), True)
check("after semicolon",
      hook.creates_pr("git push; gh pr create"), True)
check("with env prefix",
      hook.creates_pr("GH_TOKEN=x gh pr create --fill"), True)
check("after pipe",
      hook.creates_pr("echo hi | gh pr create --body-file -"), True)

# The self-reference trap: prose that quotes the command must NOT fire.
check("prose mentioning the command mid-sentence",
      hook.creates_pr("echo 'run gh pr create when ready'"), False)
check("backticked in a comment",
      hook.creates_pr("git commit -m 'document `gh pr create` usage'"), False)
check("heredoc body quoting it at line start",
      hook.creates_pr(
          "cat > /tmp/body.md <<'EOF'\n"
          "gh pr create --fill\n"
          "EOF"),
      False)
check("heredoc body quoting it after &&",
      hook.creates_pr(
          "cat > /tmp/x.md <<'MD'\n"
          "git push && gh pr create\n"
          "MD"),
      False)
# The opener may PRECEDE the redirect; an earlier revision only handled the
# other order, and the tests only covered the order that worked (#1749).
check("heredoc with redirect after the opener",
      hook.creates_pr(
          "cat <<'EOF' > /tmp/b.md\n"
          "gh pr create --fill\n"
          "EOF"),
      False)
check("heredoc piped to tee",
      hook.creates_pr(
          "cat <<'EOF' | tee /tmp/b.md\n"
          "gh pr create --fill\n"
          "EOF"),
      False)
check("<<- with a tab-indented terminator",
      hook.creates_pr(
          "cat <<-'EOF' > /tmp/b.md\n"
          "gh pr create --fill\n"
          "\tEOF"),
      False)
check("unquoted heredoc word",
      hook.creates_pr(
          "cat <<EOF > /tmp/b.md\n"
          "gh pr create --fill\n"
          "EOF"),
      False)
# A real creation CHAINED ONTO THE OPENER LINE must still fire. Widening the
# opener match to handle `cat <<'EOF' > file` first suppressed these, which is
# the false-negative direction and the one this hook exists to catch (#1749).
check("creation chained after the opener with &&",
      hook.creates_pr(
          "cat <<'EOF' > /tmp/b.md && gh pr create --body-file /tmp/b.md\n"
          "body\n"
          "EOF"),
      True)
check("creation chained after the opener with ;",
      hook.creates_pr(
          "cat <<'EOF' >> /tmp/b.md ; gh pr create --fill\n"
          "body\n"
          "EOF"),
      True)
check("heredoc piped straight into the creation",
      hook.creates_pr(
          "cat <<'EOF' | gh pr create --body-file -\n"
          "body\n"
          "EOF"),
      True)

# A real creation AFTER a heredoc block must still fire.
check("real creation following a heredoc still fires",
      hook.creates_pr(
          "cat <<'EOF' > /tmp/b.md\n"
          "some body text\n"
          "EOF\n"
          "gh pr create --body-file /tmp/b.md"),
      True)
check("unrelated gh command", hook.creates_pr("gh pr list"), False)
check("pr create as a substring of another word",
      hook.creates_pr("gh pr createfoo"), False)
check("empty", hook.creates_pr(""), False)

# ------------------------------------------------------- discharge detection

no_check = write_transcript(["git status", "git push"])
with_list = write_transcript(["gh pr list --repo o/r", "git push"])
with_view = write_transcript(["gh pr view 12 --json state"])
with_search = write_transcript(["gh search prs --owner o 'em dash'"])
with_mcp = write_transcript(["mcp__github__list_pull_requests"])
with_mcp_read = write_transcript(["mcp__github__pull_request_read"])

check("no dupe check in transcript",
      hook.transcript_has_dupe_check(no_check), False)
check("gh pr list discharges",
      hook.transcript_has_dupe_check(with_list), True)
check("gh pr view discharges",
      hook.transcript_has_dupe_check(with_view), True)
check("gh search prs discharges",
      hook.transcript_has_dupe_check(with_search), True)
check("mcp list discharges",
      hook.transcript_has_dupe_check(with_mcp), True)
check("mcp pull_request_read discharges",
      hook.transcript_has_dupe_check(with_mcp_read), True)

# Fail-open cases.
check("missing transcript path fails open",
      hook.transcript_has_dupe_check(""), True)
check("nonexistent transcript fails open",
      hook.transcript_has_dupe_check("/nonexistent/xyz.jsonl"), True)

# --------------------------------------------------------------- end-to-end

fires = run_hook("gh pr create --fill", no_check)
check("end-to-end fires without a dupe check", bool(fires), True)
if fires:
    try:
        payload = json.loads(fires)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        check("warning names the query", "gh pr list" in ctx, True)
        check("event name is PreToolUse",
              payload["hookSpecificOutput"]["hookEventName"], "PreToolUse")
    except (ValueError, KeyError) as exc:
        failures.append(f"end-to-end output not well-formed: {exc}")

check("end-to-end silent when discharged",
      run_hook("gh pr create --fill", with_list), "")
check("end-to-end silent on unrelated command",
      run_hook("git status", no_check), "")
check("end-to-end silent on prose",
      run_hook("echo 'gh pr create'", no_check), "")

# A truthy non-dict tool_input must not crash either (#1749).
proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash", "tool_input": "oops"}),
    capture_output=True, text=True, timeout=10)
check("non-dict tool_input exits 0", proc.returncode, 0)
check("non-dict tool_input prints no traceback",
      "Traceback" in proc.stderr, False)

# A non-Bash tool must be ignored outright.
proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Read", "tool_input": {}}),
    capture_output=True, text=True, timeout=10)
check("non-Bash tool ignored", proc.stdout.strip(), "")

# Malformed stdin must fail open (exit 0, nothing on stdout).
proc = subprocess.run([sys.executable, HOOK], input="not json",
                      capture_output=True, text=True, timeout=10)
check("malformed input exits 0", proc.returncode, 0)
check("malformed input prints nothing to stdout", proc.stdout.strip(), "")

# A well-formed but non-dict payload must also fail open, not traceback (#1749).
for literal in ("123", "null", "[1,2]", '"a string"'):
    proc = subprocess.run([sys.executable, HOOK], input=literal,
                          capture_output=True, text=True, timeout=10)
    check(f"non-dict payload {literal} exits 0", proc.returncode, 0)
    check(f"non-dict payload {literal} prints no traceback",
          "Traceback" in proc.stderr, False)

for path in (no_check, with_list, with_view, with_search, with_mcp,
             with_mcp_read):
    os.unlink(path)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
