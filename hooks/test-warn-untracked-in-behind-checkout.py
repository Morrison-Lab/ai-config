#!/usr/bin/env python3
"""Test the warn-untracked-in-behind-checkout PostToolUse guard.

Case W1 is the 2026-10-07 incident output, shaped like the real one: a
`git status -sb` whose header said `[behind 23]` and which listed
`?? books/mcs.pdf` and `?? books/mml-book.pdf` (ai-config#4360).

The second half is a MUTATION harness: each clause is reverted on its own and
the cases expected to flip are compared with what actually flipped, so a
clause no case exercises is reported rather than silently trusted.

Run:  python3 hooks/test-warn-untracked-in-behind-checkout.py \\
          hooks/warn-untracked-in-behind-checkout.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1])
with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()

SB_BEHIND = (
    "## main...origin/main [behind 23]\n"
    "?? books/mcs.pdf\n"
    "?? books/mml-book.pdf\n"
)
LONG_BEHIND = (
    "On branch main\n"
    "Your branch is behind 'origin/main' by 23 commits, and can be "
    "fast-forwarded.\n"
    '  (use "git pull" to update your local branch)\n'
    "\n"
    "Untracked files:\n"
    '  (use "git add <file>..." to include in what will be committed)\n'
    "\tbooks/mcs.pdf\n"
    "\tbooks/mml-book.pdf\n"
    "\n"
    "nothing added to commit but untracked files present "
    '(use "git add" to track)\n'
)
LONG_DIVERGED = (
    "On branch main\n"
    "Your branch and 'origin/main' have diverged,\n"
    "and have 2 and 23 different commits each, respectively.\n"
    "\n"
    "Untracked files:\n"
    "\tbooks/mcs.pdf\n"
    "\n"
)
SB_BEHIND_ONE = "## main...origin/main [behind 1]\n?? a.txt\n"
SB_AHEAD_BEHIND = "## main...origin/main [ahead 2, behind 5]\n?? a.txt\n"
SB_UP_TO_DATE = "## main...origin/main\n?? books/mcs.pdf\n"
SB_BEHIND_CLEAN = "## main...origin/main [behind 23]\n M README.md\n"
SB_AHEAD_ONLY = "## main...origin/main [ahead 3]\n?? books/mcs.pdf\n"
LONG_UP_TO_DATE = (
    "On branch main\nYour branch is up to date with 'origin/main'.\n\n"
    "Untracked files:\n\tbooks/mcs.pdf\n\n"
)
LONG_BEHIND_CLEAN = (
    "On branch main\nYour branch is behind 'origin/main' by 4 commits, and "
    "can be fast-forwarded.\n\nnothing to commit, working tree clean\n"
)
LONG_AHEAD_ONLY = (
    "On branch main\nYour branch is ahead of 'origin/main' by 3 commits.\n\n"
    "Untracked files:\n\tbooks/mcs.pdf\n\n"
)
IGNORED_ONLY = "## main...origin/main [behind 23]\n!! build/\n"
V2_BEHIND = (
    "# branch.oid abc\n# branch.head main\n# branch.upstream origin/main\n"
    "# branch.ab +0 -3\n? books/mcs.pdf\n"
)
V2_AHEAD_ONLY = (
    "# branch.oid abc\n# branch.head main\n# branch.upstream origin/main\n"
    "# branch.ab +2 -0\n? books/mcs.pdf\n"
)
SB_MANY = "## main...origin/main [behind 4]\n" + "".join(
    f"?? f{i}.txt\n" for i in range(13))
LONG_BEHIND_TWO_SECTIONS = (
    "On branch main\nYour branch is behind 'origin/main' by 2 commits, and "
    "can be fast-forwarded.\n\nChanges not staged for commit:\n"
    "\tmodified:   README.md\n\nUntracked files:\n"
    '  (use "git add <file>..." to include in what will be committed)\n'
    "\tnew.pdf\n\n"
)
SB_NONASCII = '## main...origin/main [behind 3]\n?? "caf\\303\\251.txt"\n'
SB_SPACE = '## main...origin/main [behind 3]\n?? "my file.pdf"\n'
NON_GIT_OUTPUT = SB_BEHIND  # status-shaped text a non-git command might print


def payload(command, stdout, tool="Bash", response=None):
    return {
        "tool_name": tool,
        "tool_input": {"command": command},
        "tool_response": response if response is not None
        else {"stdout": stdout, "stderr": "", "interrupted": False},
    }


# id -> (payload, expected-to-warn, description)
CASES = {
    "W1": (payload("git status -sb", SB_BEHIND), True,
           "incident: -sb form, behind 23, untracked books"),
    "W2": (payload("git status", LONG_BEHIND), True,
           "long form: 'Your branch is behind' plus Untracked files"),
    "W3": (payload("git -C /repo status --porcelain -b", SB_BEHIND), True,
           "git -C <dir> status -- global option before the subcommand"),
    "W4": (payload("git status -sb", SB_AHEAD_BEHIND), True,
           "[ahead 2, behind 5] counts as behind"),
    "W5": (payload("git status", LONG_DIVERGED), True,
           "diverged long form reports the behind half"),
    "W6": (payload("git status -sb", SB_BEHIND_ONE), True,
           "singular '1 commit' wording"),
    "S1": (payload("git status -sb", SB_UP_TO_DATE), False,
           "up to date with untracked files"),
    "S2": (payload("git status -sb", SB_BEHIND_CLEAN), False,
           "behind, no untracked files"),
    "S3": (payload("git status -sb", SB_AHEAD_ONLY), False,
           "ahead only, with untracked files"),
    "S4": (payload("git status", LONG_UP_TO_DATE), False,
           "long form up to date with untracked files"),
    "S5": (payload("git status", LONG_BEHIND_CLEAN), False,
           "long form behind, nothing untracked"),
    "S6": (payload("git status", LONG_AHEAD_ONLY), False,
           "long form ahead only"),
    "S7": (payload("cat notes.txt", NON_GIT_OUTPUT), False,
           "non-git command whose output contains the signals"),
    "S8": (payload("echo 'we are behind schedule'", "we are behind schedule\n"),
           False, "non-git command containing the word 'behind'"),
    "S9": (payload("git status -sb", IGNORED_ONLY), False,
           "behind with only ignored (!!) entries"),
    "S10": (payload("git status -sb", SB_BEHIND, tool="Read"), False,
            "non-Bash tool"),
    "S11": (payload("git status -sb", "", response="garbage"), False,
            "tool_response that is not a dict: fail open"),
    "W7": (payload("git status --porcelain=v2 -b", V2_BEHIND), True,
           "porcelain v2: branch.ab with behind > 0 and a '? path' entry"),
    "W8": (payload("git status -sb", SB_MANY), True,
           "more than MAX_PATHS untracked paths are truncated, not dropped"),
    "W9": (payload("git status", LONG_BEHIND_TWO_SECTIONS), True,
           "long form: untracked section after a blank line is still read"),
    "W10": (payload('git -C "my dir" status -sb', SB_BEHIND), True,
            "quoted -C value containing a space"),
    "W11": (payload("git status -sb", SB_NONASCII), True,
            "C-escaped non-ASCII name is decoded in the pathspec"),
    "W12": (payload("git status -sb", SB_SPACE), True,
            "double-quoted name with a space is unquoted then shell-quoted"),
    "S14": (payload("git status --porcelain=v2 -b", V2_AHEAD_ONLY), False,
            "porcelain v2: behind count 0"),
    "S15": (payload("git log --grep status", SB_BEHIND), False,
            "'status' is an argument of another git subcommand"),
    "S16": (payload("git diff status.txt", SB_BEHIND), False,
            "'status' is a filename of another git subcommand"),
    "S13": ({"tool_name": "Bash", "tool_input": "git status -sb",
             "tool_response": {"stdout": SB_BEHIND}}, False,
            "tool_input of the wrong type raises inside the hook: fail open"),
    "S12": (payload("git log --oneline", SB_BEHIND), False,
            "git command that is not status"),
}


def run(hook, stdin_text):
    proc = subprocess.run([sys.executable, hook], input=stdin_text,
                          capture_output=True, text=True, timeout=30)
    return proc


def warned(hook, case_payload):
    proc = run(hook, json.dumps(case_payload))
    if proc.returncode != 0:
        return "CRASH"
    if not proc.stdout.strip():
        return False
    ctx = json.loads(proc.stdout)["hookSpecificOutput"]
    assert ctx["hookEventName"] == "PostToolUse"
    return bool(ctx["additionalContext"])


# Cases whose verdict also depends on the message text: id -> needle.
NEEDLES = {
    "W11": "-- 'café.txt'",
    "W12": "-- 'my file.pdf'",
}


def case_warned(hook, case_id, case_payload):
    got = warned(hook, case_payload)
    if got is True and case_id in NEEDLES:
        ctx = json.loads(run(hook, json.dumps(case_payload)).stdout)
        return NEEDLES[case_id] in ctx["hookSpecificOutput"]["additionalContext"]
    return got


wrong = 0
print("cases:")
for case_id, (pl, expected, desc) in CASES.items():
    got = case_warned(HOOK, case_id, pl)
    ok = got == expected
    wrong += not ok
    print(f"  {'ok  ' if ok else 'WRONG'} {case_id:<4} {desc}")

# --- message content (incident case) ---------------------------------------
proc = run(HOOK, json.dumps(CASES["W1"][0]))
msg = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
for needle in ("23 commits behind origin/main", "books/mcs.pdf",
               "books/mml-book.pdf", "git fetch",
               "git ls-tree -r --name-only origin/main -- ",
               "git cat-file -e origin/main:<path>"):
    ok = needle in msg
    wrong += not ok
    print(f"  {'ok  ' if ok else 'WRONG'} message names: {needle}")
proc = run(HOOK, json.dumps(CASES["W6"][0]))
msg1 = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
ok = "1 commit behind" in msg1
wrong += not ok
print(f"  {'ok  ' if ok else 'WRONG'} singular wording: 1 commit behind")

def message_for(command, stdout):
    out = run(HOOK, json.dumps(payload(command, stdout))).stdout
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


for label, msg_text, needle in (
    ("truncation names the remainder",
     message_for("git status -sb", SB_MANY), "(and 3 more)"),
    ("truncation drops the 11th path",
     message_for("git status -sb", SB_MANY), "f10.txt"),
    ("upstream-less header falls back to origin/<branch>",
     message_for("git status -sb", "## main [behind 3]\n?? a.txt\n"),
     "behind origin/<branch>"),
    ("quoted name is unquoted then shell-quoted",
     message_for("git status -sb",
                 '## main...origin/main [behind 3]\n?? "my file.pdf"\n'),
     "-- 'my file.pdf'"),
    ("v2 upstream is used as the ref",
     message_for("git status --porcelain=v2 -b", V2_BEHIND),
     "origin/main"),
    ("freshness limit is stated",
     message_for("git status -sb", SB_BEHIND),
     "only as fresh as the last fetch"),
):
    present = needle in msg_text
    if label == "truncation drops the 11th path":
        present = not present
    wrong += not present
    print(f"  {'ok  ' if present else 'WRONG'} message: {label}")

# --- fail-open on malformed input --------------------------------------------
for label, text in (("empty stdin", ""), ("non-JSON stdin", "not json"),
                    ("JSON list", "[]")):
    proc = run(HOOK, text)
    ok = proc.returncode == 0 and not proc.stdout.strip()
    wrong += not ok
    print(f"  {'ok  ' if ok else 'WRONG'} fail open: {label}")

print(f"\n{wrong} wrong")

# ------------------------------------------------------------ mutation harness

MUTATIONS = {
    "M1_short_behind": (
        "`-sb` header `[behind N]` is recognised",
        [('    m = RX_SHORT_BEHIND.search(text)\n    if m:\n'
          '        return int(m.group("n")), m.group("up")',
          "    pass")],
        {"W1", "W3", "W4", "W6", "W8", "W10", "W11", "W12"},
    ),
    "M2_long_behind": (
        "long-form 'Your branch is behind' is recognised",
        [("    for rx in (RX_LONG_BEHIND, RX_LONG_DIVERGED):",
          "    for rx in (RX_LONG_DIVERGED,):")],
        {"W2", "W9"},
    ),
    "M3_diverged": (
        "long-form diverged output reports its behind half",
        [("    for rx in (RX_LONG_BEHIND, RX_LONG_DIVERGED):",
          "    for rx in (RX_LONG_BEHIND,):")],
        {"W5"},
    ),
    "M4_require_untracked": (
        "behind alone does not warn: untracked files are required",
        [("        if not paths:\n            return 0\n", "")],
        {"S2", "S5", "S9"},
    ),
    "M5_require_behind": (
        "untracked alone does not warn: a behind signal is required",
        [("        if info is None:\n            return 0\n", "        if info is None:\n            info = (0, None)\n")],
        {"S1", "S3", "S4", "S6", "S14"},
    ),
    "M6_git_status_gate": (
        "the command must be a `git ... status`",
        [("        if not RX_GIT_STATUS.search(command):\n            return 0\n",
          "")],
        {"S7", "S12", "S15", "S16"},
    ),
    "M7_bash_gate": (
        "only the Bash tool is inspected",
        [('        if payload.get("tool_name") != "Bash":\n            return 0\n',
          "")],
        {"S10"},
    ),
    "M8_long_untracked": (
        "long-form 'Untracked files:' section is parsed",
        [("    head = RX_LONG_UNTRACKED_HEAD.search(text)\n    if head:",
          "    head = None\n    if head:")],
        {"W2", "W5", "W9"},
    ),
    "M10_v2_behind": (
        "porcelain v2 branch.ab is read",
        [("    m = RX_V2_AB.search(text)\n    if m and int(m.group(\"n\")) > 0:",
          "    m = None\n    if m and int(m.group(\"n\")) > 0:")],
        {"W7"},
    ),
    "M11_v2_zero": (
        "porcelain v2 with zero behind does not warn",
        [("    if m and int(m.group(\"n\")) > 0:", "    if m:")],
        {"S14"},
    ),
    "M12_subcommand_only": (
        "`status` must be the git subcommand, not any later word",
        [('    r"|--[A-Za-z][\\w-]*(?:=\\S+)?|-[A-BD-Za-bd-z]))*\\s+status\\b"',
          '    r"|--[A-Za-z][\\w-]*(?:=\\S+)?|-[A-BD-Za-bd-z]|\\S+))*\\s+status\\b"')],
        {"S15", "S16"},
    ),
    "M13_quoted_option_value": (
        "a quoted `-C` value is one token",
        [('(?:\\"[^\\"]*\\"|\'[^\']*\'|\\S+)"', '(?:\\S+)"')],
        {"W10"},
    ),
    "M14_unquote_path": (
        "git's C-style path quoting is undone before the pathspec is built",
        [('    if not (len(path) > 1 and path[0] == path[-1] == \'"\'):\n'
          '        return path',
          '    return path')],
        {"W11", "W12"},
    ),
    "M9_fail_open": (
        "any exception exits 0 silently",
        [("    except Exception:  # fail open: a warning hook must never break a tool call\n        return 0",
          "    except ZeroDivisionError:\n        return 0")],
        {"S13"},
    ),
}

print("\nmutation tests (revert one clause, see which cases flip):")
mutation_wrong = 0
with tempfile.TemporaryDirectory() as tmp:
    for clause, (statement, edits, expected_flips) in MUTATIONS.items():
        mutated = SOURCE
        for find, replace in edits:
            if mutated.count(find) != 1:
                sys.exit(f"FATAL: clause {clause}'s anchor is not present "
                         f"exactly once in {HOOK} (found "
                         f"{mutated.count(find)}). The mutation harness is "
                         f"measuring nothing; re-derive the anchor.\n---\n"
                         f"{find}\n---")
            mutated = mutated.replace(find, replace)
        path = os.path.join(tmp, f"mutant-{clause}.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(mutated)
        flipped = {cid for cid, (pl, expected, _d) in CASES.items()
                   if case_warned(path, cid, pl) != expected}
        ok = flipped == expected_flips
        mutation_wrong += not ok
        if not flipped and expected_flips:
            note = "NOTHING FLIPPED -- this clause is untested"
        elif ok:
            note = "flipped " + ", ".join(sorted(flipped))
        else:
            note = f"flipped {sorted(flipped)}, expected {sorted(expected_flips)}"
        print(f"  {'ok  ' if ok else 'WRONG'} {clause:<22} {statement}\n"
              f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under reversion")
sys.exit(1 if (wrong or mutation_wrong) else 0)
