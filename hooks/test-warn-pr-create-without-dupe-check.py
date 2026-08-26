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


def write_transcript(commands, tool_name="Bash"):
    """Build a transcript file whose tool_use blocks carry `commands`.

    A command of None writes a bare tool_use with no input, which is how an
    MCP call appears --- a name and nothing to pattern-match.
    """
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8")
    for cmd in commands:
        block = {"type": "tool_use", "name": tool_name, "input": {}}
        if cmd is not None:
            block["input"] = {"command": cmd}
        fh.write(json.dumps({"message": {"content": [block]}}) + "\n")
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
# Command substitution and grouping are command positions too; capturing the
# new PR's URL via $(...) is the idiomatic shape (#1749).
check("inside command substitution",
      hook.creates_pr("URL=$(gh pr create --fill)"), True)
check("inside a brace group",
      hook.creates_pr("{ gh pr create --fill; }"), True)
check("inside a subshell",
      hook.creates_pr("(gh pr create --fill)"), True)

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
with_mcp = write_transcript([None], "mcp__github__list_pull_requests")
with_mcp_read = write_transcript([None], "mcp__github__pull_request_read")
# Prose that merely QUOTES a discharging command must not discharge it: an
# unanchored discharge silences the guard for the whole session (#1749).
prose_list = write_transcript(["echo 'run gh pr list first'"])
prose_commit = write_transcript(["git commit -m 'mention gh pr view here'"])
prose_heredoc = write_transcript(
    ["cat > /tmp/x.md <<'EOF'\ngh pr list --repo o/r\nEOF"])
chained_real = write_transcript(["git fetch && gh pr list --state open"])
# A parenthetical aside inside a quoted argument must not discharge. `(` and
# `{` are deliberately absent from RX_DISCHARGE's separator class for this
# reason: they are ordinary in prose, unlike `;`/`&`/`|`/newline, and a false
# discharge silences the guard for the session (#1749, third round).
paren_prose = write_transcript(
    ['git commit -m "fix: document (gh pr list) usage in the hook"'])
brace_prose = write_transcript(['echo "note {gh pr view} usage"'])
unrelated_mcp = write_transcript([None], "mcp__github__get_me")

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
check("unrelated mcp tool does not discharge",
      hook.transcript_has_dupe_check(unrelated_mcp), False)
check("prose quoting gh pr list does not discharge",
      hook.transcript_has_dupe_check(prose_list), False)
check("prose in a commit message does not discharge",
      hook.transcript_has_dupe_check(prose_commit), False)
check("prose in a heredoc body does not discharge",
      hook.transcript_has_dupe_check(prose_heredoc), False)
check("a chained real gh pr list still discharges",
      hook.transcript_has_dupe_check(chained_real), True)
check("a parenthetical aside in a commit message does not discharge",
      hook.transcript_has_dupe_check(paren_prose), False)
check("a brace aside in a quoted argument does not discharge",
      hook.transcript_has_dupe_check(brace_prose), False)

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

# The MCP creation tool must trip the guard, since MCP reads discharge it.
mcp_payload = json.dumps({
    "tool_name": "mcp__github__create_pull_request",
    "tool_input": {"title": "x"},
    "transcript_path": no_check,
})
proc = subprocess.run([sys.executable, HOOK], input=mcp_payload,
                      capture_output=True, text=True, timeout=10)
check("mcp create fires without a dupe check", bool(proc.stdout.strip()), True)

mcp_payload_ok = json.dumps({
    "tool_name": "mcp__github__create_pull_request",
    "tool_input": {"title": "x"},
    "transcript_path": with_mcp,
})
proc = subprocess.run([sys.executable, HOOK], input=mcp_payload_ok,
                      capture_output=True, text=True, timeout=10)
check("mcp create silent when discharged", proc.stdout.strip(), "")

# MCP create-issue tools must trip the issue half, not the PR half.
mcp_issue_payload = json.dumps({
    "tool_name": "mcp__github__create_issue",
    "tool_input": {"title": "x"},
    "transcript_path": no_check,
})
proc = subprocess.run([sys.executable, HOOK], input=mcp_issue_payload,
                      capture_output=True, text=True, timeout=10)
check("mcp create_issue fires without a dupe check",
      bool(proc.stdout.strip()), True)
if proc.stdout.strip():
    try:
        ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        check("mcp create_issue warning names the issue query",
              "gh issue list" in ctx, True)
        check("mcp create_issue warning requires --state all",
              "--state all" in ctx, True)
    except (ValueError, KeyError) as exc:
        failures.append(f"mcp create_issue output not well-formed: {exc}")

mcp_write_create = json.dumps({
    "tool_name": "mcp__github__issue_write",
    "tool_input": {"method": "create", "title": "x"},
    "transcript_path": no_check,
})
proc = subprocess.run([sys.executable, HOOK], input=mcp_write_create,
                      capture_output=True, text=True, timeout=10)
check("mcp issue_write method=create fires", bool(proc.stdout.strip()), True)

mcp_write_update = json.dumps({
    "tool_name": "mcp__github__issue_write",
    "tool_input": {"method": "update", "issue_number": 1},
    "transcript_path": no_check,
})
proc = subprocess.run([sys.executable, HOOK], input=mcp_write_update,
                      capture_output=True, text=True, timeout=10)
check("mcp issue_write method=update is silent", proc.stdout.strip(), "")

# ---------------------------------------------------------------- issue create

check("plain gh issue create",
      hook.creates_issue("gh issue create --title x"), True)
check("glab issue create", hook.creates_issue("glab issue create"), True)
check("issue create after &&",
      hook.creates_issue("true && gh issue create --title x"), True)
check("issue create after newline",
      hook.creates_issue("true\ngh issue create --title x"), True)
check("issue create with env prefix",
      hook.creates_issue("GH_TOKEN=x gh issue create --title x"), True)
check("issue create inside command substitution",
      hook.creates_issue("URL=$(gh issue create --title x)"), True)
check("issue create inside a brace group",
      hook.creates_issue("{ gh issue create --title x; }"), True)
check("pr create is not issue create",
      hook.creates_issue("gh pr create --fill"), False)
check("issue create is not pr create",
      hook.creates_pr("gh issue create --title x"), False)
check("prose mentioning issue create mid-sentence",
      hook.creates_issue("echo 'run gh issue create when ready'"), False)
check("heredoc body quoting issue create at line start",
      hook.creates_issue(
          "cat > /tmp/body.md <<'EOF'\n"
          "gh issue create --title x\n"
          "EOF"),
      False)
check("issue create chained after the opener with &&",
      hook.creates_issue(
          "cat <<'EOF' > /tmp/b.md && gh issue create --body-file /tmp/b.md\n"
          "body\n"
          "EOF"),
      True)
check("unrelated gh issue command",
      hook.creates_issue("gh issue list"), False)
check("issue create as a substring of another word",
      hook.creates_issue("gh issue createfoo"), False)

# ------------------------------------------------------- issue discharge

with_issue_all = write_transcript(
    ['gh issue list --state all --search "cp1252"'])
with_issue_all_eq = write_transcript(
    ['gh issue list --search=cp1252 --state=all'])
with_issue_all_short = write_transcript(
    ["gh issue list -s all -S cp1252"])
with_issue_open = write_transcript(
    ['gh issue list --state open --search "cp1252"'])
with_issue_all_no_search = write_transcript(
    ["gh issue list --state all"])
with_issue_search_only = write_transcript(
    ['gh issue list --search "cp1252"'])
with_gh_search_issues = write_transcript(
    ["gh search issues --owner o 'cp1252'"])
with_gh_search_issues_open = write_transcript(
    ["gh search issues --state open --owner o 'cp1252'"])
with_glab_issue_all = write_transcript(
    ['glab issue list --all --search "cp1252"'])
with_glab_issue_all_short = write_transcript(
    ['glab issue list -A --search "cp1252"'])
with_glab_issue_gh_flags = write_transcript(
    ['glab issue list --state all --search "cp1252"'])
with_mcp_issue_search = write_transcript(
    [None], "mcp__github__search_issues")
with_mcp_issue_list = write_transcript(
    [None], "mcp__github__list_issues")
with_pr_list_for_issue = write_transcript(["gh pr list --repo o/r"])
prose_issue_list = write_transcript(
    ['echo \'run gh issue list --state all --search "x" first\''])
quoted_state_in_search = write_transcript(
    ['gh issue list --state open --search "--state all"'])


def write_mcp_input(tool_name, payload):
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8")
    block = {"type": "tool_use", "name": tool_name, "input": payload}
    fh.write(json.dumps({"message": {"content": [block]}}) + "\n")
    fh.close()
    return fh.name


with_mcp_issue_list_all = write_mcp_input(
    "mcp__github__list_issues", {"state": "all"})

check("gh issue list --state all --search discharges",
      hook.transcript_has_issue_dupe_check(with_issue_all), True)
check("flag order --search then --state=all discharges",
      hook.transcript_has_issue_dupe_check(with_issue_all_eq), True)
check("gh short flags -s all -S discharge",
      hook.transcript_has_issue_dupe_check(with_issue_all_short), True)
check("--state open --search does not discharge",
      hook.transcript_has_issue_dupe_check(with_issue_open), False)
check("--state all without --search does not discharge",
      hook.transcript_has_issue_dupe_check(with_issue_all_no_search), False)
check("--search without --state all does not discharge",
      hook.transcript_has_issue_dupe_check(with_issue_search_only), False)
check("gh search issues discharges",
      hook.transcript_has_issue_dupe_check(with_gh_search_issues), True)
check("gh search issues --state open does not discharge",
      hook.transcript_has_issue_dupe_check(with_gh_search_issues_open), False)
check("glab issue list --all --search discharges",
      hook.transcript_has_issue_dupe_check(with_glab_issue_all), True)
check("glab issue list -A --search discharges",
      hook.transcript_has_issue_dupe_check(with_glab_issue_all_short), True)
check("glab issue list with gh --state all flags does not discharge",
      hook.transcript_has_issue_dupe_check(with_glab_issue_gh_flags), False)
check("mcp search_issues discharges",
      hook.transcript_has_issue_dupe_check(with_mcp_issue_search), True)
check("mcp list_issues does not discharge",
      hook.transcript_has_issue_dupe_check(with_mcp_issue_list), False)
check("mcp list_issues with state=all still does not discharge",
      hook.transcript_has_issue_dupe_check(with_mcp_issue_list_all), False)
check("gh pr list does not discharge issue create",
      hook.transcript_has_issue_dupe_check(with_pr_list_for_issue), False)
check("gh issue list does not discharge PR create",
      hook.transcript_has_dupe_check(with_issue_all), False)
check("prose quoting the qualifying issue list does not discharge",
      hook.transcript_has_issue_dupe_check(prose_issue_list), False)
check("quoted --state all inside --search does not discharge",
      hook.transcript_has_issue_dupe_check(quoted_state_in_search), False)

# Direct matcher for the command-has helper.
check("command_has_issue_dupe_check: qualifying list",
      hook.command_has_issue_dupe_check(
          'gh issue list -R o/r --state all --search "x"'), True)
check("command_has_issue_dupe_check: open state",
      hook.command_has_issue_dupe_check(
          'gh issue list --state open --search "x"'), False)
check("command_has_issue_dupe_check: gh search issues",
      hook.command_has_issue_dupe_check("gh search issues 'x'"), True)
check("command_has_issue_dupe_check: gh search issues --state open",
      hook.command_has_issue_dupe_check(
          "gh search issues --state open 'x'"), False)
check("command_has_issue_dupe_check: gh search issues --state \"open\"",
      hook.command_has_issue_dupe_check(
          'gh search issues --state "open" x'), False)
check("command_has_issue_dupe_check: gh search issues --state=OPEN",
      hook.command_has_issue_dupe_check(
          "gh search issues --state=OPEN x"), False)
check("command_has_issue_dupe_check: glab --all --search",
      hook.command_has_issue_dupe_check(
          'glab issue list --all --search "x"'), True)
check("command_has_issue_dupe_check: glab gh-shaped flags",
      hook.command_has_issue_dupe_check(
          'glab issue list --state all --search "x"'), False)

# ------------------------------------------ review findings, ai-config#2324

check("gh search issues: bare state:open qualifier does not discharge",
      hook.command_has_issue_dupe_check(
          "gh search issues state:open foo"), False)
check("gh search issues: bare is:closed qualifier does not discharge",
      hook.command_has_issue_dupe_check(
          "gh search issues is:closed foo"), False)
check("gh search issues: --state=all is invalid and does not discharge",
      hook.command_has_issue_dupe_check(
          "gh search issues --state=all foo"), False)
check("gh issue list: --search value carrying is:open does not discharge",
      hook.command_has_issue_dupe_check(
          'gh issue list --state all --search "is:open foo"'), False)
check("glab issue list: --all=false does not discharge",
      hook.command_has_issue_dupe_check(
          'glab issue list --all=false --search "x"'), False)
check("gh issue list: --search with no value does not discharge",
      hook.command_has_issue_dupe_check(
          "gh issue list --state all --search"), False)
check("gh issue list: --search followed by another flag does not discharge",
      hook.command_has_issue_dupe_check(
          "gh issue list --state all --search --limit 10"), False)
check("gh issue ls (alias) discharges like gh issue list",
      hook.command_has_issue_dupe_check(
          'gh issue ls --state all --search "x"'), True)
check("glab issue ls (alias) discharges like glab issue list",
      hook.command_has_issue_dupe_check(
          'glab issue ls --all --search "x"'), True)
check("escaped quote in search term does not falsely discharge open search",
      hook.command_has_issue_dupe_check(
          'gh issue list --search "x \\" --state all" --state open'), False)
check("semicolon inside a quoted search term keeps the trailing flags",
      hook.command_has_issue_dupe_check(
          'gh issue list --search "foo; bar" --state all'), True)

check("mcp search_issues query carrying is:open does not discharge",
      hook._mcp_is_issue_search("mcp__github__search_issues",
                                 {"query": "repo:o/r is:open cp1252"}),
      False)
check("mcp search_issues with a plain query still discharges",
      hook._mcp_is_issue_search("mcp__github__search_issues",
                                 {"query": "repo:o/r cp1252"}),
      True)

chained_pr_and_issue_create = write_transcript(["gh pr list --state all"])
chained_payload = json.dumps({
    "tool_name": "Bash",
    "tool_input": {
        "command": "gh pr list; gh issue create --title x "
                   "&& gh pr create --title y",
    },
    "transcript_path": chained_pr_and_issue_create,
})
proc = subprocess.run([sys.executable, HOOK], input=chained_payload,
                      capture_output=True, text=True, timeout=10)
_out = json.loads(proc.stdout) if proc.stdout.strip() else {}
_note = _out.get("hookSpecificOutput", {}).get("additionalContext", "")
check("chained pr+issue create: PR-discharged transcript still warns issue",
      "this issue creation" in _note, True)
check("chained pr+issue create: PR half correctly discharged, silent",
      "this PR creation" in _note, False)
os.unlink(chained_pr_and_issue_create)
check("command_has_issue_dupe_check: prose",
      hook.command_has_issue_dupe_check(
          'echo gh issue list --state all --search x'), False)

issue_fires = run_hook("gh issue create --title x", no_check)
check("end-to-end issue create fires without a dupe check",
      bool(issue_fires), True)
if issue_fires:
    try:
        payload = json.loads(issue_fires)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        check("issue warning names --state all", "--state all" in ctx, True)
        check("issue warning names gh issue list", "gh issue list" in ctx, True)
        check("issue warning is not the PR warning",
              "open PRs" in ctx, False)
    except (ValueError, KeyError) as exc:
        failures.append(f"issue end-to-end output not well-formed: {exc}")

check("end-to-end issue silent when discharged with --state all",
      run_hook("gh issue create --title x", with_issue_all), "")
check("end-to-end issue still warns after --state open search",
      bool(run_hook("gh issue create --title x", with_issue_open)), True)
check("end-to-end issue silent after gh search issues",
      run_hook("gh issue create --title x", with_gh_search_issues), "")
check("end-to-end issue still warns after gh search issues --state open",
      bool(run_hook("gh issue create --title x", with_gh_search_issues_open)),
      True)
check("end-to-end issue silent after glab --all --search",
      run_hook("glab issue create --title x", with_glab_issue_all), "")
check("PR create still fires when only an issue search ran",
      bool(run_hook("gh pr create --fill", with_issue_all)), True)
check("issue create still fires when only a PR list ran",
      bool(run_hook("gh issue create --title x", with_list)), True)

mcp_issue_ok = json.dumps({
    "tool_name": "mcp__github__create_issue",
    "tool_input": {"title": "x"},
    "transcript_path": with_mcp_issue_search,
})
proc = subprocess.run([sys.executable, HOOK], input=mcp_issue_ok,
                      capture_output=True, text=True, timeout=10)
check("mcp create_issue silent when search_issues ran",
      proc.stdout.strip(), "")

mcp_write_ok = json.dumps({
    "tool_name": "mcp__github__issue_write",
    "tool_input": {"method": "create", "title": "x"},
    "transcript_path": with_mcp_issue_search,
})
proc = subprocess.run([sys.executable, HOOK], input=mcp_write_ok,
                      capture_output=True, text=True, timeout=10)
check("mcp issue_write create silent when search_issues ran",
      proc.stdout.strip(), "")

mcp_write_list = json.dumps({
    "tool_name": "mcp__github__issue_write",
    "tool_input": {"method": "create", "title": "x"},
    "transcript_path": with_mcp_issue_list_all,
})
proc = subprocess.run([sys.executable, HOOK], input=mcp_write_list,
                      capture_output=True, text=True, timeout=10)
check("mcp issue_write create still fires after list_issues",
      bool(proc.stdout.strip()), True)

for path in (no_check, with_list, with_view, with_search, with_mcp,
             with_mcp_read, prose_list, prose_commit, prose_heredoc,
             chained_real, unrelated_mcp, with_issue_all, with_issue_all_eq,
             with_issue_all_short, with_issue_open, with_issue_all_no_search,
             with_issue_search_only, with_gh_search_issues,
             with_gh_search_issues_open, with_glab_issue_all,
             with_glab_issue_all_short, with_glab_issue_gh_flags,
             with_mcp_issue_search, with_mcp_issue_list,
             with_pr_list_for_issue, prose_issue_list, quoted_state_in_search,
             with_mcp_issue_list_all):
    os.unlink(path)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
