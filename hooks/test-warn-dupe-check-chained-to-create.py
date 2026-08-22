#!/usr/bin/env python3
"""Tests for warn-dupe-check-chained-to-create.py.

The negative cases carry most of the weight, and they are the reason the hook
is safe to ship on one measured incident. This corpus writes `gh issue list`
and `gh issue create` constantly --- in fragments, in issue bodies, in PR
comments, and in the hook's own docstring --- so a matcher that fired on prose
about the rule would fire on every session that discusses it.

Each negative below names the shape it protects rather than merely asserting
None, so a later reader can tell a deliberate exclusion from an accident.
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "warn-dupe-check-chained-to-create.py")

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def fires(command):
    """True when the matcher finds an offending check/create pair."""
    return hook.find_chained_pair(command) is not None


def run_hook(command, tool_name="Bash"):
    """Run the hook end-to-end; return its stdout."""
    payload = json.dumps({
        "tool_name": tool_name,
        "tool_input": {"command": command},
    })
    proc = subprocess.run([sys.executable, HOOK], input=payload,
                          capture_output=True, text=True, timeout=10)
    return proc.stdout.strip()


# --------------------------------------------------------------- must fire

# The measured incident (ai-config#1954): a list, a heredoc, then the create.
check("the measured incident shape",
      fires(
          "gh issue list --repo O/R --state open --search \"x\" "
          "--json number,title --limit 10; cat > /tmp/body.md <<'BODY'\n"
          "some issue body\n"
          "BODY\n"
          "gh issue create -R O/R --title \"t\" --body-file /tmp/body.md"),
      True)
check("semicolon separated",
      fires("gh issue list -R o/r; gh issue create -R o/r --title t"), True)
check("newline separated",
      fires("gh issue list -R o/r\ngh issue create -R o/r --title t"), True)
check("&& separated",
      fires("gh issue list -R o/r && gh issue create -R o/r"), True)
check("|| separated",
      fires("gh issue list -R o/r || gh issue create -R o/r"), True)
check("piped check then create",
      fires("gh issue list -R o/r | head -5; gh issue create -R o/r"), True)
check("pr half",
      fires("gh pr list -R o/r --state open; gh pr create --fill"), True)
check("glab issue half",
      fires("glab issue list; glab issue create --title t"), True)
check("glab mr half",
      fires("glab mr list; glab mr create --fill"), True)
check("gh search issues gates gh issue create",
      fires("gh search issues --owner o 'x'; gh issue create -R o/r"), True)
check("gh search prs gates gh pr create",
      fires("gh search prs --owner o 'x'; gh pr create --fill"), True)
check("env-assignment prefixes on both halves",
      fires("GH_TOKEN=x gh issue list -R o/r; GH_TOKEN=x gh issue create"),
      True)
check("extra whitespace between words",
      fires("gh   issue   list -R o/r ;  gh   issue   create"), True)
# The heredoc strip must keep the opener line's tail, which is still shell and
# routinely carries the create itself (the failure ai-config#1749 measured on
# the sibling hook).
check("create chained onto a heredoc opener line",
      fires(
          "gh issue list -R o/r; cat <<'EOF' > /tmp/b.md && "
          "gh issue create --body-file /tmp/b.md\n"
          "body\n"
          "EOF"),
      True)
check("heredoc piped straight into the create",
      fires(
          "gh issue list -R o/r; cat <<'EOF' | gh issue create --body-file -\n"
          "body\n"
          "EOF"),
      True)
check("<<- with a tab-indented terminator",
      fires(
          "gh issue list -R o/r; cat <<-'EOF' > /tmp/b.md\n"
          "body\n"
          "\tEOF\n"
          "gh issue create --body-file /tmp/b.md"),
      True)
# A cross-kind create between the two must not mask the same-kind pair.
check("an interleaved cross-kind create does not mask the real pair",
      fires("gh issue list -R o/r; gh pr create --fill; gh issue create"),
      True)

# The reported pair identifies both halves and the object kind.
pair = hook.find_chained_pair(
    "gh issue list -R o/r --search \"x\"; gh issue create -R o/r --title t")
check("reported pair", pair, ("gh issue list", "gh issue create", "issue"))

# ----------------------------------------------------- must NOT fire

# 1. A create with no search anywhere in the call. The commonest shape there
#    is, and the one the sibling hook (not this one) is responsible for.
check("create alone", fires("gh issue create -R o/r --title t"), False)
check("create alone after a push",
      fires("git push -u origin HEAD; gh pr create --fill"), False)

# 2. A search with no create. `gh issue list` as a plain report.
check("search alone", fires("gh issue list -R o/r --state open"), False)
check("search piped into a report",
      fires("gh issue list -R o/r --json number,title | jq -r '.[].title'"),
      False)

# 3. A search and a create for DIFFERENT object kinds. A PR search does not
#    gate an issue creation, so the pairing asserts nothing to check.
check("pr search then issue create",
      fires("gh pr list -R o/r; gh issue create -R o/r --title t"), False)
check("issue search then pr create",
      fires("gh issue list -R o/r; gh pr create --fill"), False)
check("glab mr search then glab issue create",
      fires("glab mr list; glab issue create --title t"), False)
check("gh search prs then gh issue create",
      fires("gh search prs --owner o 'x'; gh issue create -R o/r"), False)

# 4. Create BEFORE check: create-then-verify is legitimate.
check("create then verify",
      fires("gh issue create -R o/r --title t; gh issue list -R o/r"), False)

# 5. Both commands quoted rather than run. Position anchoring alone cannot see
#    a newline-separated pair inside one argument, which is why quoted spans
#    are stripped.
check("both inside a single-quoted argument",
      fires("echo 'gh issue list -R o/r; gh issue create -R o/r'"), False)
check("both inside a multi-line double-quoted comment body",
      fires(
          'gh issue comment 1954 -R o/r -b "The defect is:\n'
          'gh issue list -R o/r\n'
          'gh issue create -R o/r\n'
          'Run them separately."'),
      False)
check("both quoted in a commit message",
      fires("git commit -m 'ran gh issue list; then gh issue create'"), False)
check("prose mentioning both mid-sentence",
      fires('echo "run gh issue list before gh issue create"'), False)

# 6. Both commands in a heredoc BODY, which is prose rather than shell.
check("both inside a heredoc body",
      fires(
          "cat > /tmp/body.md <<'EOF'\n"
          "gh issue list -R o/r\n"
          "gh issue create -R o/r\n"
          "EOF"),
      False)
check("both inside an unquoted heredoc body",
      fires(
          "cat <<EOF > /tmp/b.md\n"
          "gh issue list -R o/r\n"
          "gh issue create -R o/r\n"
          "EOF"),
      False)

# 7. Subcommands the table deliberately does not name.
check("gh issue view is not a check",
      fires("gh issue view 12 -R o/r; gh issue create -R o/r"), False)
check("gh pr view is not a check",
      fires("gh pr view 12 --json state; gh pr create --fill"), False)
check("gh search repos is not a check",
      fires("gh search repos foo; gh issue create -R o/r"), False)
check("glab mr merge is neither half",
      fires("glab mr list; glab mr merge 3"), False)

# 8. Word-boundary near-misses.
check("listfoo / createbar are not the commands",
      fires("gh issue listfoo; gh issue createbar"), False)
check("a longer word ending in the verb",
      fires("gh issue list; gh issue recreate"), False)

# 9. Degenerate inputs.
check("empty command", fires(""), False)
check("whitespace only", fires("   \n  "), False)
check("unrelated command", fires("git status --short"), False)

# ------------------------------------------------------------ normalization

check("heredoc strip keeps the opener tail",
      "gh issue create" in hook.normalize(
          "cat <<'EOF' > /tmp/b.md && gh issue create\nbody\nEOF"),
      True)
check("heredoc strip drops the body",
      "gh issue list" in hook.normalize(
          "cat <<'EOF' > /tmp/b.md\ngh issue list\nEOF"),
      False)
check("quote strip drops a quoted span",
      "gh issue list" in hook.normalize("echo 'gh issue list'"), False)
check("quote strip preserves an unquoted separator",
      ";" in hook.normalize('gh issue list --search "x"; gh issue create'),
      True)
# An unterminated quote must not swallow a real command that follows it. The
# span regex simply fails to match, leaving the text alone.
check("unterminated quote leaves the text alone",
      fires("gh issue list -R o/r --search \"unclosed\ngh issue create"), True)

# --------------------------------------------------------------- end-to-end

out = run_hook(
    "gh issue list -R o/r --search \"x\"; gh issue create -R o/r --title t")
check("end-to-end fires on a chained pair", bool(out), True)
if out:
    try:
        payload = json.loads(out)
        hook_out = payload["hookSpecificOutput"]
        check("event name is PreToolUse", hook_out["hookEventName"],
              "PreToolUse")
        ctx = hook_out["additionalContext"]
        check("additionalContext names the check", "gh issue list" in ctx, True)
        check("additionalContext names the create",
              "gh issue create" in ctx, True)
        check("systemMessage is present and non-empty",
              bool(payload.get("systemMessage")), True)
        check("systemMessage names the defect",
              "gates nothing" in payload["systemMessage"], True)
        # Warn-only: no decision key of any kind may appear.
        check("no permissionDecision emitted",
              "permissionDecision" in json.dumps(payload), False)
        check("no decision emitted", "decision" in json.dumps(payload), False)
    except (ValueError, KeyError) as exc:
        failures.append(f"end-to-end output not well-formed: {exc}")

check("end-to-end silent on a create alone",
      run_hook("gh issue create -R o/r --title t"), "")
check("end-to-end silent on a search alone",
      run_hook("gh issue list -R o/r"), "")
check("end-to-end silent on prose",
      run_hook("echo 'gh issue list; gh issue create'"), "")
check("end-to-end silent on an unrelated command",
      run_hook("git status"), "")
check("non-Bash tool ignored",
      run_hook("gh issue list; gh issue create", tool_name="Read"), "")

# The MCP creation tool is deliberately NOT covered: an MCP call carries one
# operation, so the "two commands in one call" shape cannot arise there.
proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "mcp__github__create_issue",
                      "tool_input": {"title": "x"}}),
    capture_output=True, text=True, timeout=10)
check("mcp create tool ignored", proc.stdout.strip(), "")

# ---------------------------------------------------------------- fail open

proc = subprocess.run([sys.executable, HOOK], input="not json",
                      capture_output=True, text=True, timeout=10)
check("malformed input exits 0", proc.returncode, 0)
check("malformed input prints nothing to stdout", proc.stdout.strip(), "")

for literal in ("123", "null", "[1,2]", '"a string"'):
    proc = subprocess.run([sys.executable, HOOK], input=literal,
                          capture_output=True, text=True, timeout=10)
    check(f"non-dict payload {literal} exits 0", proc.returncode, 0)
    check(f"non-dict payload {literal} prints no traceback",
          "Traceback" in proc.stderr, False)
    check(f"non-dict payload {literal} prints nothing to stdout",
          proc.stdout.strip(), "")

proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash", "tool_input": "oops"}),
    capture_output=True, text=True, timeout=10)
check("non-dict tool_input exits 0", proc.returncode, 0)
check("non-dict tool_input prints no traceback",
      "Traceback" in proc.stderr, False)

proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash", "tool_input": {"command": 42}}),
    capture_output=True, text=True, timeout=10)
check("non-string command exits 0", proc.returncode, 0)
check("non-string command prints nothing to stdout", proc.stdout.strip(), "")

proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash", "tool_input": {}}),
    capture_output=True, text=True, timeout=10)
check("missing command exits 0", proc.returncode, 0)
check("missing command prints nothing to stdout", proc.stdout.strip(), "")

# A payload with no tool_name at all must not crash.
proc = subprocess.run([sys.executable, HOOK], input=json.dumps({}),
                      capture_output=True, text=True, timeout=10)
check("empty object exits 0", proc.returncode, 0)
check("empty object prints nothing to stdout", proc.stdout.strip(), "")

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
