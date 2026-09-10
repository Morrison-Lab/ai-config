"""Test the flag-unread-commit-citation guard.

The positive case is the 2026-09-09 measurement (ai-config#3471, verbatim in
shape): a case entry citing two commits with a narrative reconstructed from
`git log --oneline` alone, with neither patch actually opened.

The negative cases decide whether the guard survives: a citation discharged
by `git show`/`git diff`/`git cat-file`/`git log -p`/`gh api .../commits/<sha>`
/`gh api .../pulls/N/commits`/`mcp__github__get_commit`, a citation inside a
fenced or indented-log-output block, a `Reviewed-Commit:`/`HEAD=` trailer, a
short hex token with no cue, and a read that happened in a PREVIOUS turn
(which must still fire -- the window is the current turn only).

Run: python3 hooks/test-flag-unread-commit-citation.py hooks/flag-unread-commit-citation.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

MARKER = "_Posted by Claude Code (AI agent) --- not written by a human._"

# Two real-shaped SHAs from the measurement, cited with the backtick cue
# real case entries use.
CITED_BOTH = (
    "`2d37c48` added `pkg::fn()` support and `08f5a73` narrowed it after a "
    "hand-traced case."
)
CITED_ONE = "Fixed by `2d37c48a1b2c3d4e5f6789012345678901234ab` per the diff."


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def edit(path, text):
    return {"tool_name": "Edit", "tool_input": {"file_path": path, "new_string": text}}


def mcp_commit(tool, **kw):
    return {"tool_name": tool, "tool_input": kw}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def tool_use(name, command=None, **extra):
    inp = dict(extra)
    if command is not None:
        inp["command"] = command
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t1", "name": name, "input": inp}]}}


PROMPT = {"type": "user", "message": {"content": "record what these commits did"}}
NEXT_TURN = {"type": "user", "content": "and the memory entry?"}

ONELINE = tool_use("Bash", command="git log --oneline -20")
SHOW_BOTH = [
    tool_use("Bash", command="git show 2d37c48"),
    tool_use("Bash", command="git show 08f5a73"),
]
SHOW_ONE = tool_use("Bash", command="git show 2d37c48")
DIFF_ONE = tool_use("Bash", command="git diff 2d37c48^..2d37c48")
CATFILE_ONE = tool_use("Bash", command="git cat-file -p 2d37c48")
LOG_PATCH_ONE = tool_use("Bash", command="git log -p -1 2d37c48")
LOG_BARE_ONE = tool_use("Bash", command="git log 2d37c48")  # no -p: must not discharge
GH_API_COMMIT_ONE = tool_use(
    "Bash", command="gh api repos/Morrison-Lab/ai-config/commits/2d37c48")
GH_API_PR_COMMITS = tool_use(
    "Bash", command="gh api repos/Morrison-Lab/ai-config/pulls/3471/commits")
MCP_GET_COMMIT = tool_use(
    "mcp__github__get_commit", owner="Morrison-Lab", repo="ai-config", sha="2d37c48")
MCP_LIST_COMMITS = tool_use(
    "mcp__github__list_commits", owner="Morrison-Lab", repo="ai-config", pullNumber=3471)

CASES = [
    # --- the measurement, and its shape --------------------------------------
    ([PROMPT, say("Looking at the log."), ONELINE],
     bash(f'gh issue comment 96 --body "{CITED_BOTH}\n\n{MARKER}"'), True,
     "#3471: both SHAs cited after only `git log --oneline` warns"),
    ([PROMPT, ONELINE],
     edit("memory/rampp-cases.md", CITED_BOTH), True,
     "#3471: the same shape via a memory-file Edit warns"),

    # --- git log --oneline never discharges -----------------------------------
    ([PROMPT, ONELINE],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), True,
     "git log --oneline listing the SHA is not a read"),
    ([PROMPT, LOG_BARE_ONE],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), True,
     "git log <sha> with no -p flag is not a read"),

    # --- real reads discharge --------------------------------------------------
    ([PROMPT] + SHOW_BOTH,
     bash(f'gh issue comment 96 --body "{CITED_BOTH}\n\n{MARKER}"'), False,
     "git show on both cited SHAs discharges"),
    ([PROMPT, SHOW_ONE],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), False,
     "git show on the one cited SHA discharges (prefix match)"),
    ([PROMPT, DIFF_ONE],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), False,
     "git diff naming the SHA discharges"),
    ([PROMPT, CATFILE_ONE],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), False,
     "git cat-file naming the SHA discharges"),
    ([PROMPT, LOG_PATCH_ONE],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), False,
     "git log -p naming the SHA discharges"),
    ([PROMPT, GH_API_COMMIT_ONE],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), False,
     "gh api repos/.../commits/<sha> discharges"),
    ([PROMPT, GH_API_PR_COMMITS],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), False,
     "gh api repos/.../pulls/N/commits broadly discharges"),
    ([PROMPT, MCP_GET_COMMIT],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), False,
     "mcp__github__get_commit naming the SHA discharges"),
    ([PROMPT, MCP_LIST_COMMITS],
     bash(f'gh pr comment 155 --body "{CITED_ONE}"'), False,
     "mcp__github__list_commits broadly discharges"),

    # --- window is the CURRENT turn only ---------------------------------------
    ([PROMPT] + SHOW_BOTH + [NEXT_TURN],
     bash(f'gh issue comment 96 --body "{CITED_BOTH}\n\n{MARKER}"'), True,
     "a read in a PREVIOUS turn does not discharge a citation in this turn"),

    # --- fenced / indented evidence is not a claim ------------------------------
    ([PROMPT, ONELINE],
     edit("memory/rampp-cases.md",
          "```\n2d37c48 added pkg::fn() support\n08f5a73 narrowed it\n```"), False,
     "SHAs inside a fenced code block are quoted evidence, not a claim"),
    ([PROMPT, ONELINE],
     edit("memory/rampp-cases.md",
          "The excerpt:\n\n    2d37c48 added pkg::fn() support\n    08f5a73 narrowed it\n"), False,
     "SHAs inside an indented git-log-shaped block are quoted evidence"),

    # --- reporting rather than asserting -----------------------------------------
    ([PROMPT, ONELINE],
     bash('gh pr comment 155 --body "Reviewed commit: 2d37c48a1b2c3d4e5f6"'), False,
     "a Reviewed-Commit: trailer reports position, not a claim"),
    ([PROMPT, ONELINE],
     bash('gh pr comment 155 --body "HEAD=2d37c48a1b2c3d4e5f6 after the reset."'), False,
     "a HEAD= assignment reports position, not a claim"),

    # --- short hex token needs a cue ---------------------------------------------
    ([PROMPT, ONELINE],
     bash('gh pr comment 155 --body "the counter hit deadbee times today."'), False,
     "a bare 7-char hex-looking word with no cue is silent"),
    ([PROMPT, ONELINE],
     bash('gh pr comment 155 --body "commit deadbee fixed the race."'), True,
     "a 7-char token preceded by the word commit has a cue and fires"),

    # --- pure-digit runs are not SHA candidates -----------------------------------
    ([PROMPT, ONELINE],
     bash('gh pr comment 155 --body "processed 1234567 rows in the batch."'), False,
     "a pure-digit 7+ run has no hex letter and is not a SHA candidate"),
    ([PROMPT, ONELINE],
     bash('gh pr comment 155 --body "reviewed 12345678 lines across the diff."'), False,
     "an 8+ digit pure-numeric run needs no cue but still has no hex letter, "
     "so it is not a SHA candidate either"),

    # --- out of scope -------------------------------------------------------------
    ([PROMPT, ONELINE],
     {"tool_name": "Write", "tool_input": {
         "file_path": "/tmp/scratch/notes.md", "content": CITED_BOTH}}, False,
     "a write under /tmp/ is scratch, not a durable artifact"),
    ([PROMPT, ONELINE],
     {"tool_name": "Bash", "tool_input": {"command": "echo hello"}}, False,
     "a non-posting Bash command is out of scope"),
]


def write_transcript(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return path


def run(events, payload, extra_args=()):
    tpath = write_transcript(events) if events else ""
    tmpdir = tempfile.mkdtemp()
    try:
        full = dict(payload, transcript_path=tpath, cwd=os.getcwd())
        env = dict(os.environ, TMPDIR=tmpdir)
        env.pop("ANTIGRAVITY_AGENT", None)
        r = subprocess.run(
            [sys.executable, HOOK, *extra_args], input=json.dumps(full),
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"hook exited {r.returncode}: {r.stderr}"
        assert "permissionDecision" not in r.stdout, "guard must never block"
        if not r.stdout.strip():
            return {}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if tpath:
            os.unlink(tpath)


def fired(out):
    if not out:
        return False
    hso = out.get("hookSpecificOutput") or {}
    return bool(hso.get("additionalContext")) or bool(out.get("systemMessage"))


def check_dry_run():
    out = run([PROMPT, ONELINE],
              bash(f'gh issue comment 96 --body "{CITED_BOTH}"'), ("--dry-run",))
    again = run([PROMPT, ONELINE],
               bash(f'gh issue comment 96 --body "{CITED_BOTH}"'), ("--dry-run",))
    ok = fired(out) and fired(again)
    quiet = run([PROMPT], bash("git status"), ("--dry-run",))
    ok = ok and quiet == {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    print(f"{'ok  ' if ok else 'FAIL'}  --dry-run warns without a sentinel, and "
          f"reports an empty PreToolUse payload when silent")
    return 0 if ok else 1


def check_sentinel():
    tpath = write_transcript([PROMPT, ONELINE])
    tmpdir = tempfile.mkdtemp()
    try:
        full = dict(bash(f'gh issue comment 96 --body "{CITED_BOTH}"'),
                    transcript_path=tpath, cwd=os.getcwd())
        env = dict(os.environ, TMPDIR=tmpdir)
        env.pop("ANTIGRAVITY_AGENT", None)
        first = subprocess.run([sys.executable, HOOK], input=json.dumps(full),
                               capture_output=True, text=True, env=env).stdout
        second = subprocess.run([sys.executable, HOOK], input=json.dumps(full),
                                capture_output=True, text=True, env=env).stdout
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.unlink(tpath)
    ok = "systemMessage" in first and not second.strip()
    print(f"{'ok  ' if ok else 'FAIL'}  warns once per distinct (transcript, body, sha)")
    return 0 if ok else 1


def check_malformed_stdin():
    r = subprocess.run([sys.executable, HOOK], input="not json",
                       capture_output=True, text=True)
    ok = r.returncode == 0 and not r.stdout.strip()
    print(f"{'ok  ' if ok else 'FAIL'}  malformed stdin fails open and silent")
    return 0 if ok else 1


def check_output_shape():
    out = run([PROMPT, ONELINE], bash(f'gh issue comment 96 --body "{CITED_BOTH}"'))
    hso = out.get("hookSpecificOutput") or {}
    ok = (hso.get("hookEventName") == "PreToolUse"
          and "permissionDecision" not in out
          and "2d37c48" in (hso.get("additionalContext") or "")
          and "systemMessage" in out)
    print(f"{'ok  ' if ok else 'FAIL'}  fire shape: PreToolUse additionalContext "
          f"names the SHA, no permissionDecision, systemMessage present")
    return 0 if ok else 1


def main():
    failures = 0
    failures += check_output_shape()
    failures += check_dry_run()
    failures += check_sentinel()
    failures += check_malformed_stdin()
    case_failures = 0
    for events, payload, want, label in CASES:
        got = fired(run(events, payload))
        ok = got == want
        if not ok:
            case_failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  fire={got!s:5} want={want!s:5}  {label}")
    failures += case_failures
    print(f"\n{len(CASES) - case_failures}/{len(CASES)} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
