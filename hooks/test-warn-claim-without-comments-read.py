#!/usr/bin/env python3
"""Tests for warn-claim-without-comments-read.py.

The core case is the one that motivated this hook: `gh issue view N` with NO
`--comments`/`--json comments` must NOT discharge the reminder. Reading the
body alone is exactly the failure Lacaedemon/sparta#1544 measured.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "warn-claim-without-comments-read.py")

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
    MCP call with no command text appears -- combine with `mcp_input` when
    the block needs a real payload dict.
    """
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8")
    for cmd in commands:
        block = {"type": "tool_use", "name": tool_name, "input": {}}
        if isinstance(cmd, tuple):
            block["input"] = cmd[1]
        elif cmd is not None:
            block["input"] = {"command": cmd}
        fh.write(json.dumps({"message": {"content": [block]}}) + "\n")
    fh.close()
    return fh.name


def write_mcp_transcript(entries):
    """entries: list of (tool_name, input_dict)."""
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8")
    for name, inp in entries:
        block = {"type": "tool_use", "name": name, "input": inp}
        fh.write(json.dumps({"message": {"content": [block]}}) + "\n")
    fh.close()
    return fh.name


def run_hook(command, transcript_path="", cwd=None):
    """Run the hook end-to-end; return its stdout."""
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "transcript_path": transcript_path,
        "cwd": cwd or HERE,
    })
    proc = subprocess.run([sys.executable, HOOK], input=payload,
                          capture_output=True, text=True, timeout=10)
    return proc.stdout.strip()


CLAIM_BODY = ("Claude Code CLI (local session) is working on this --- "
              "please hold off until I'm done.")
NON_CLAIM_BODY = "Thanks for the report, this looks like a duplicate of #12."

# --------------------------------------------------------------- find_claim_targets

check("gh issue comment matches, captures number",
      [t[:2] for t in hook.find_claim_targets(
          f'gh issue comment 1544 --body "{CLAIM_BODY}"')],
      [("1544", "gh")])
check("glab issue note matches, captures number",
      [t[:2] for t in hook.find_claim_targets(
          f'glab issue note 1544 --message "{CLAIM_BODY}"')],
      [("1544", "glab")])
check("gh pr comment does not match (out of scope)",
      list(hook.find_claim_targets('gh pr comment 5 --body "hi"')), [])
check("prose mentioning the command mid-sentence does not match",
      list(hook.find_claim_targets("echo 'run gh issue comment 5 when ready'")),
      [])
check("heredoc body quoting it at line start does not match",
      list(hook.find_claim_targets(
          "cat > /tmp/body.md <<'EOF'\n"
          "gh issue comment 5 --body x\n"
          "EOF")),
      [])
check("issue comment as substring of another word does not match",
      list(hook.find_claim_targets("gh issue commentfoo 5")), [])
check("no number present does not match",
      list(hook.find_claim_targets('gh issue comment "$N" --body x')), [])
check("-R owner/repo between the verb and the number still matches",
      [t[:2] for t in hook.find_claim_targets(
          'gh issue comment -R owner/repo 1544 --body "hi"')],
      [("1544", "gh")])
check("--repo owner/repo between the verb and the number still matches",
      [t[:2] for t in hook.find_claim_targets(
          'gh issue comment --repo owner/repo 1544 --body "hi"')],
      [("1544", "gh")])
check("glab -R owner/repo between the verb and the number still matches",
      [t[:2] for t in hook.find_claim_targets(
          'glab issue note -R owner/repo 1544 --message "hi"')],
      [("1544", "glab")])
check("two claim-posts in one chained command both surface",
      [t[:2] for t in hook.find_claim_targets(
          'gh issue comment 1544 --body "x" && glab issue note 999 --message "y"')],
      [("1544", "gh"), ("999", "glab")])

# ------------------------------------------------------------- CLAIM_CUE

check("claim wording: is working on this",
      bool(hook.CLAIM_CUE.search(CLAIM_BODY)), True)
check("claim wording: claiming this",
      bool(hook.CLAIM_CUE.search("Claiming this issue, will start shortly.")),
      True)
check("claim wording: picking this up",
      bool(hook.CLAIM_CUE.search("Picking this up now.")), True)
check("claim wording: grabbing this",
      bool(hook.CLAIM_CUE.search("Grabbing this one.")), True)
check("claim wording: taking this",
      bool(hook.CLAIM_CUE.search("I'm taking this issue.")), True)
check("claim wording: please hold off",
      bool(hook.CLAIM_CUE.search("please hold off on pushing")), True)
check("non-claim body does not match cue",
      bool(hook.CLAIM_CUE.search(NON_CLAIM_BODY)), False)
check("plain status update does not match cue",
      bool(hook.CLAIM_CUE.search("Fixed in the latest push, tests are green.")),
      False)

# --------------------------------------------------------- extract_glab_note_body

# Direct unit coverage for the glab body extractor: a mutation that made it
# always return None (unreadable) passed the end-to-end suite below silently,
# because an unreadable body still warns regardless of content -- only a
# correctly-extracted NON-claim body proves the extractor actually read the
# text rather than defaulting to "can't tell".
check("glab -m literal extracts the claim body",
      hook.extract_glab_note_body(f'-m "{CLAIM_BODY}"', HERE), CLAIM_BODY)
check("glab --message literal extracts a non-claim body",
      hook.extract_glab_note_body(f'--message "{NON_CLAIM_BODY}"', HERE),
      NON_CLAIM_BODY)
_glab_file_fh = tempfile.NamedTemporaryFile(
    "w", suffix=".md", delete=False, encoding="utf-8")
_glab_file_fh.write(NON_CLAIM_BODY)
_glab_file_fh.close()
check("glab -F <file> reads the body from disk",
      hook.extract_glab_note_body(f"-F {_glab_file_fh.name}",
                                   os.path.dirname(_glab_file_fh.name)),
      NON_CLAIM_BODY)
os.unlink(_glab_file_fh.name)
check("glab -F - (stdin) is unreadable",
      hook.extract_glab_note_body("-F -", HERE), None)
check("glab with no body flag at all is unreadable",
      hook.extract_glab_note_body("--yes", HERE), None)

# ------------------------------------------------------- command_reads_comments

check("gh issue view --comments discharges",
      hook.command_reads_comments("gh issue view 1544 --comments", "1544"),
      True)
check("gh issue view with NO --comments does NOT discharge (core case)",
      hook.command_reads_comments("gh issue view 1544", "1544"),
      False)
check("gh issue view --json comments discharges",
      hook.command_reads_comments(
          'gh issue view 1544 --json comments', "1544"),
      True)
check("gh issue view --json title,comments discharges (field order)",
      hook.command_reads_comments(
          'gh issue view 1544 --json title,comments', "1544"),
      True)
check("gh issue view --json comments,title discharges (field order)",
      hook.command_reads_comments(
          'gh issue view 1544 --json comments,title', "1544"),
      True)
check("gh issue view --json bodyComments does NOT discharge (substring trap)",
      hook.command_reads_comments(
          'gh issue view 1544 --json bodyComments', "1544"),
      False)
check("gh issue view --json state does NOT discharge",
      hook.command_reads_comments('gh issue view 1544 --json state', "1544"),
      False)
check("gh issue view for a DIFFERENT issue number does not discharge",
      hook.command_reads_comments("gh issue view 999 --comments", "1544"),
      False)
check("glab issue view --comments discharges",
      hook.command_reads_comments("glab issue view 1544 --comments", "1544"),
      True)
check("glab issue show --comments discharges (documented alias)",
      hook.command_reads_comments("glab issue show 1544 --comments", "1544"),
      True)
check("glab issue view with no --comments does NOT discharge",
      hook.command_reads_comments("glab issue view 1544", "1544"),
      False)
check("gh api .../issues/N/comments GET discharges",
      hook.command_reads_comments(
          "gh api repos/o/r/issues/1544/comments", "1544"),
      True)
check("gh api .../issues/N/comments with a body flag does NOT discharge "
      "(that's a POST, not a GET)",
      hook.command_reads_comments(
          'gh api repos/o/r/issues/1544/comments -f body="hi"', "1544"),
      False)
check("-R owner/repo between gh issue view and the number still discharges",
      hook.command_reads_comments(
          "gh issue view -R owner/repo 1544 --comments", "1544"),
      True)
check("--repo owner/repo between glab issue view and the number still "
      "discharges",
      hook.command_reads_comments(
          "glab issue view --repo owner/repo 1544 --comments", "1544"),
      True)
check("gh api --paginate before the endpoint still discharges",
      hook.command_reads_comments(
          "gh api --paginate repos/o/r/issues/1544/comments", "1544"),
      True)
check("prose quoting the qualifying view does not discharge",
      hook.command_reads_comments(
          "echo 'run gh issue view 1544 --comments first'", "1544"),
      False)
check("empty command does not discharge",
      hook.command_reads_comments("", "1544"), False)

# ------------------------------------------------------------- mcp_reads_comments

check("mcp issue_read method=get_comments, matching /issues/N path discharges",
      hook.mcp_reads_comments(
          "mcp__github__issue_read",
          {"method": "get_comments", "owner": "o", "repo": "r",
           "issue_number": 1544},
          "1544"),
      True)
check("mcp issue_read method=get (plain view) does NOT discharge",
      hook.mcp_reads_comments(
          "mcp__github__issue_read",
          {"method": "get", "issue_number": 1544},
          "1544"),
      False)
check("mcp issue_read for a different issue number does not discharge",
      hook.mcp_reads_comments(
          "mcp__github__issue_read",
          {"method": "get_comments", "issue_number": 999},
          "1544"),
      False)
check("cursor-mapped name ending in issue_read discharges",
      hook.mcp_reads_comments(
          "some_prefix_issue_read",
          {"method": "get_comments", "number": 1544},
          "1544"),
      True)
check("unrelated mcp tool does not discharge",
      hook.mcp_reads_comments("mcp__github__get_me", {}, "1544"), False)

# --------------------------------------------------------- transcript_has_comments_read

no_read = write_transcript(["git status", "gh issue view 1544"])
with_comments = write_transcript(["gh issue view 1544 --comments"])
with_json_comments = write_transcript(
    ['gh issue view 1544 --json comments,title'])
with_glab_comments = write_transcript(["glab issue view 1544 --comments"])
with_api_get = write_transcript(["gh api repos/o/r/issues/1544/comments"])
with_wrong_number = write_transcript(["gh issue view 999 --comments"])
with_mcp_comments = write_mcp_transcript(
    [("mcp__github__issue_read",
      {"method": "get_comments", "issue_number": 1544})])
with_mcp_plain_view = write_mcp_transcript(
    [("mcp__github__issue_read", {"method": "get", "issue_number": 1544})])
prose_comments = write_transcript(
    ["echo 'remember to run gh issue view 1544 --comments'"])

check("no qualifying read in transcript",
      hook.transcript_has_comments_read(no_read, "1544"), False)
check("gh issue view --comments in transcript discharges",
      hook.transcript_has_comments_read(with_comments, "1544"), True)
check("gh issue view --json comments in transcript discharges",
      hook.transcript_has_comments_read(with_json_comments, "1544"), True)
check("glab issue view --comments in transcript discharges",
      hook.transcript_has_comments_read(with_glab_comments, "1544"), True)
check("gh api GET in transcript discharges",
      hook.transcript_has_comments_read(with_api_get, "1544"), True)
check("a read of a DIFFERENT issue number does not discharge",
      hook.transcript_has_comments_read(with_wrong_number, "1544"), False)
check("mcp get_comments in transcript discharges",
      hook.transcript_has_comments_read(with_mcp_comments, "1544"), True)
check("mcp plain get (view, not comments) does NOT discharge",
      hook.transcript_has_comments_read(with_mcp_plain_view, "1544"), False)
check("prose quoting the qualifying read does not discharge",
      hook.transcript_has_comments_read(prose_comments, "1544"), False)

# Fail-open cases.
check("missing transcript path fails open",
      hook.transcript_has_comments_read("", "1544"), True)
check("nonexistent transcript fails open",
      hook.transcript_has_comments_read("/nonexistent/xyz.jsonl", "1544"),
      True)

# --------------------------------------------------------------- end-to-end

fires = run_hook(f'gh issue comment 1544 --body "{CLAIM_BODY}"', no_read)
check("end-to-end fires: claim posted, only the BODY was read (core case)",
      bool(fires), True)
if fires:
    try:
        payload = json.loads(fires)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        check("warning names the issue number", "#1544" in ctx, True)
        check("warning names the comments query",
              "gh issue view 1544 --comments" in ctx, True)
        check("event name is PreToolUse",
              payload["hookSpecificOutput"]["hookEventName"], "PreToolUse")
    except (ValueError, KeyError) as exc:
        failures.append(f"end-to-end output not well-formed: {exc}")

check("end-to-end silent when comments were read",
      run_hook(f'gh issue comment 1544 --body "{CLAIM_BODY}"', with_comments),
      "")
check("end-to-end silent on a non-claim comment even with no prior read",
      run_hook(f'gh issue comment 1544 --body "{NON_CLAIM_BODY}"', no_read),
      "")
check("end-to-end silent on an unrelated command",
      run_hook("git status", no_read), "")
check("end-to-end silent on prose merely mentioning the command",
      run_hook("echo 'gh issue comment 1544 --body hi'", no_read), "")
check("end-to-end silent when only a DIFFERENT issue's comments were read",
      bool(run_hook(f'gh issue comment 1544 --body "{CLAIM_BODY}"',
                    with_wrong_number)),
      True)

glab_fires = run_hook(f'glab issue note 1544 --message "{CLAIM_BODY}"', no_read)
check("end-to-end fires for glab issue note too",
      bool(glab_fires), True)
check("end-to-end silent for glab when comments were read",
      run_hook(f'glab issue note 1544 --message "{CLAIM_BODY}"',
               with_glab_comments),
      "")
check("end-to-end silent on a non-claim glab comment even with no prior read",
      run_hook(f'glab issue note 1544 --message "{NON_CLAIM_BODY}"', no_read),
      "")

# --------------------------------------------------------- unreadable body

# `--body-file` naming a path that does not exist on disk: the extractor
# returns None (unreadable), and per the module's stated precedent (mirroring
# flag-unmeasured-timestamp.py's UNREADABLE handling) the hook still warns
# rather than assuming the comment is compliant.
unreadable_fires = run_hook(
    "gh issue comment 1544 --body-file /nonexistent/claim-body.txt", no_read)
check("end-to-end fires on an unreadable --body-file body",
      bool(unreadable_fires), True)
if unreadable_fires:
    try:
        payload = json.loads(unreadable_fires)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        check("unreadable-body warning names the issue number",
              "#1544" in ctx, True)
        check("unreadable-body warning says the body cannot be read",
              "cannot read" in ctx, True)
    except (ValueError, KeyError) as exc:
        failures.append(f"unreadable end-to-end output not well-formed: {exc}")

check("end-to-end silent for an unreadable body once comments were read",
      run_hook("gh issue comment 1544 --body-file /nonexistent/claim-body.txt",
               with_comments),
      "")

# `--body-file -` (stdin) is unreadable by flag, same treatment.
stdin_fires = run_hook("gh issue comment 1544 --body-file -", no_read)
check("end-to-end fires on a stdin (-) body", bool(stdin_fires), True)

# ------------------------------------------------- malformed / non-Bash inputs

proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash", "tool_input": "oops"}),
    capture_output=True, text=True, timeout=10)
check("non-dict tool_input exits 0", proc.returncode, 0)
check("non-dict tool_input prints no traceback",
      "Traceback" in proc.stderr, False)

proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Read", "tool_input": {}}),
    capture_output=True, text=True, timeout=10)
check("non-Bash tool ignored", proc.stdout.strip(), "")

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

for path in (no_read, with_comments, with_json_comments, with_glab_comments,
             with_api_get, with_wrong_number, with_mcp_comments,
             with_mcp_plain_view, prose_comments):
    os.unlink(path)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
