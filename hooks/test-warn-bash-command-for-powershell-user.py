#!/usr/bin/env python3
"""Tests for warn-bash-command-for-powershell-user.py.

The negatives are the whole design. The naive version of this trigger -- "a
fenced block containing `&&` while the user runs PowerShell" -- fires 13 times
over the 118 transcripts under `~/.claude/projects`, of which ONE is a real
directive and twelve are explanations, reviews and corpus edits that merely
quote shell syntax. Worse, the discriminator that suggests itself (suppress
when the surrounding prose is retrospective) marks all thirteen identically,
the true positive included, because a message can hand over a command AND
discuss a failure in the same breath.

So the separation is done on the SHAPE of the block rather than the prose
around it, and `S2`/`S3`/`S5` are the cases that carry it: a quotation shows
its prompt, or its output, or runs long. Each negative names the shape it
protects.

`HARNESS NOTE`: the hook fires once per (transcript, reply) via a /tmp
sentinel. The mutation section runs every case many times, so `verdict()`
gives each subprocess a FRESH temp directory -- without that, every case after
the first run would be silently suppressed and the whole suite would go
vacuously green, which is the failure `shared/workflow/fixtures-are-not-evidence.md`
names. `test_fires_once_per_session` asserts the sentinel still works.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "warn-bash-command-for-powershell-user.py")
SOURCE = open(HOOK, encoding="utf-8").read()

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures = []
TMP = tempfile.mkdtemp(prefix="psfence-hook-")

BRIEF_PS = (
    "<system-reminder>\n# Environment\nYou have been invoked in the following "
    "environment:\n - Primary working directory: C:\\Users\\Work\n"
    " - Platform: win32\n - Shell: PowerShell (primary); Bash tool also "
    "available for POSIX scripts\n</system-reminder>"
)
BRIEF_BASH = (
    "<system-reminder>\n# Environment\n - Platform: linux\n"
    " - Shell: Bash\n</system-reminder>"
)

_n = [0]


def transcript(reply, brief=BRIEF_PS, extra_replies=()):
    """Write a one-session transcript and return its path."""
    _n[0] += 1
    path = os.path.join(TMP, f"t{_n[0]}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        if brief is not None:
            fh.write(json.dumps({
                "type": "attachment",
                "rendered": [{"content": brief}],
            }) + "\n")
        for earlier in extra_replies:
            fh.write(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": earlier}]},
            }) + "\n")
        fh.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": reply}]},
        }) + "\n")
    return path


def payload(reply, brief=BRIEF_PS, extra_replies=()):
    return {"transcript_path": transcript(reply, brief, extra_replies)}


BAD = ("cd /d/GitHub/ai-config/.claude/worktrees/ums-media-type-guard && "
       "ALLOW_UNREVIEWED_PUSH=1 git push -u origin ums/cross-drive")
GOOD = ("Set-Location D:\\GitHub\\ai-config; "
        "$env:ALLOW_UNREVIEWED_PUSH='1'; git push -u origin ums/cross-drive")

CASES = {
    # -- must warn ---------------------------------------------------------
    # The measured incident, verbatim: three incompatibilities in one line,
    # handed over for a PowerShell terminal.
    "W1": payload("To make them durable:\n\n```bash\n" + BAD + "\n```"),
    # the env prefix alone, with no `cd` to lead it -- the `cd` is incidental
    "W2": payload("Then run:\n\n```bash\nALLOW_UNREVIEWED_PUSH=1 git push\n```"),
    "W3": payload("Check it:\n\n```bash\ngit status 2>/dev/null\n```"),
    # a block TAGGED powershell that contains `&&` is the bug, not an
    # exception -- the tag is never an inclusion test
    "W4": payload("Run:\n\n```powershell\ncd D:\\x && git push\n```"),
    "W5": payload("Write it:\n\n```bash\ncat <<'EOF' > notes.md\nhi\nEOF\n```"),
    "W6": payload("Try:\n\n```bash\ngit push || echo failed\n```"),

    # -- must stay silent --------------------------------------------------
    # the corrected form of W1, which also appears in the real corpus
    "S1": payload("Run this instead:\n\n```powershell\n" + GOOD + "\n```"),
    # a QUOTED failing session: the prompt and the error are what mark it as
    # a citation rather than a directive. This is the case that would sink
    # the hook if it fired -- explaining the mistake must not trip the guard
    # that polices it (the ai-config#2997 pattern).
    "S2": payload("You hit this:\n\n```\n$ " + BAD + "\n"
                  "The token '&&' is not a valid statement separator\n```"),
    # the same, tagged console
    "S2b": payload("What happened:\n\n```console\n$ cd /d/x && git push\n"
                   "bash: parse error\n```"),
    # a PowerShell prompt marks a quoted session just as well
    "S3": payload("Output:\n\n```\nPS C:\\Users\\Work> cd /d/x && git push\n"
                  "error\n```"),
    # a settings snippet that NAMES the command inside a JSON string
    "S4": payload('Add this to settings.local.json:\n\n```json\n{\n'
                  '  "allow": ["Bash(ALLOW_UNREVIEWED_PUSH=1 git push)"]\n}\n```'),
    # a long listing is a script being shown, not a command to paste
    "S5": payload("The script reads:\n\n```bash\n"
                  + "\n".join(f"echo step{i} && true" for i in range(12))
                  + "\n```"),
    # `&&` inside a quoted argument is data
    "S6": payload('Run:\n\n```bash\ngit commit -m "handles a && b"\n```'),
    # ... and inside a URL
    "S7": payload("Fetch:\n\n```\ncurl 'https://x.test/?a=1&&b=2'\n```"),
    # no fenced block at all: inline code is not a block handed over
    "S8": payload("Just run `cd /d/x && git push` from Git Bash yourself."),
    # a perfectly good PowerShell command
    "S9": payload("Run:\n\n```powershell\nGet-PhysicalDisk | Format-Table\n```"),
    # THE gate: no evidence the user's shell is PowerShell. Same text as W1.
    "S10": payload("To make them durable:\n\n```bash\n" + BAD + "\n```",
                   brief=None),
    # ... and positive evidence that it is NOT
    "S11": payload("To make them durable:\n\n```bash\n" + BAD + "\n```",
                   brief=BRIEF_BASH),
    # a python block that happens to contain an MSYS path
    "S12": payload("The regex is:\n\n```python\nP = re.compile('/c/Users')\n```"),
    # a path QUOTED in a comment inside a command block
    "S13": payload("Note:\n\n```bash\ngit status  # under Git Bash pwd -P "
                   "answers /c/Users/Work\n```"),
    # a markdown block quoting the bad command while documenting it
    "S14": payload("The memory entry reads:\n\n```markdown\nDon't write "
                   + BAD + "\n```"),
    # test output that looks like an env prefix but is not one
    "S15": payload("It printed:\n\n```\nok=1 msg=done\n```"),
}

EXPECTED = {cid: cid.startswith("W") for cid in CASES}

WHY = {
    "S1": "the corrected PowerShell form must never warn",
    "S2": "a quoted failing session -- explaining the mistake must not fire",
    "S2b": "the same citation, tagged console",
    "S3": "a PowerShell prompt marks a quoted session",
    "S4": "a JSON settings snippet is not a command to paste",
    "S5": "a long listing is a script being shown",
    "S6": "`&&` inside a quoted argument is data",
    "S7": "`&&` inside a URL is data",
    "S8": "inline code is not a fenced block handed over",
    "S9": "valid PowerShell",
    "S10": "no evidence the user's shell is PowerShell",
    "S11": "positive evidence that it is bash",
    "S12": "a python block is not a shell command",
    "S13": "the path is quoted in a comment, not run",
    "S14": "a markdown block documenting the rule",
    "S15": "`ok=1 msg=done` is output, not an env prefix",
}

KNOWN_LIMITS = {
    "backtick command substitution is NOT a construct. Measured over the same "
    "corpus it added two firings, both false (an option description and a "
    "JSON stdout dump), and contributed nothing to the true positive",
    "a tilde-fenced block (~~~) is not matched at all; the harness emits "
    "backtick fences",
    "a directive longer than MAX_LINES lines is missed, which is the price of "
    "excluding script listings -- 8 is one line below where the first false "
    "positive appears in the corpus",
    "a session whose transcript carries no environment brief is never warned, "
    "because an unknown shell must not produce a warning about the wrong one",
    "a block the user is told to run in Git Bash DELIBERATELY still warns; "
    "no signal separates it from one aimed at PowerShell, and the message "
    "says so rather than the hook guessing",
    "a reply that QUOTES a short corpus bash example would warn. Measured "
    "zero occurrences across 1252 real assistant messages, but running the "
    "matcher over memories/shell.md itself finds four such blocks (the "
    "`pgrep -f` and heredoc sections), so the residual risk is named rather "
    "than assumed absent -- the new section added for THIS hook does not "
    "fire, because it shows its failing command with a prompt and its error",
}


def verdict(script, case_payload):
    """True when running `script` on this payload emits the warning.

    Each run gets a FRESH temp directory, so the fire-once sentinel cannot
    silence a later run of the same case. See the HARNESS NOTE above.
    """
    env = dict(os.environ)
    fresh = tempfile.mkdtemp(prefix="psfence-run-")
    for var in ("TMPDIR", "TEMP", "TMP"):
        env[var] = fresh
    out = subprocess.run(
        [sys.executable, script], input=json.dumps(case_payload),
        capture_output=True, text=True, timeout=60, env=env)
    return "systemMessage" in (out.stdout or "")


print("case tests (full payload through the hook):")
wrong = 0
for cid in sorted(CASES):
    got = verdict(HOOK, CASES[cid])
    if got != EXPECTED[cid]:
        wrong += 1
        failures.append(f"{cid}: got warn={got}, want warn={EXPECTED[cid]} "
                        f"({WHY.get(cid, 'must warn')})")
print(f"  {len(CASES) - wrong}/{len(CASES)} cases behaved as declared")


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# Unit-level assertions.
check("shell gate reads the environment brief",
      hook.user_shell_is_powershell(transcript("x")), True)
check("shell gate is negative without a brief",
      hook.user_shell_is_powershell(transcript("x", brief=None)), False)
check("shell gate is negative for bash",
      hook.user_shell_is_powershell(transcript("x", brief=BRIEF_BASH)), False)
check("a missing transcript is not evidence",
      hook.user_shell_is_powershell(os.path.join(TMP, "nope.jsonl")), False)
# The LAST reply is the one being checked, not an earlier clean one.
check("the last assistant message wins",
      hook.last_assistant_text(
          transcript("second", extra_replies=("first",))).strip(), "second")
# The diagnostic must name the real construct and the real line.
hits = hook.find_wrong_shell_blocks("```bash\n" + BAD + "\n```")
check("names the construct", hits[0][0], "`&&`")
check("names the offending line", BAD.split(" &&")[0] in hits[0][2], True)
check("a block with a prompt is not runnable",
      hook.runnable_blocks("```\n$ ls\n```"), [])
check("a python-tagged block is not runnable",
      hook.runnable_blocks("```python\nx = 1\n```"), [])

# The sentinel still works within one session: a SHARED temp dir means the
# second identical run is silent. This is the assertion that keeps the
# fresh-dir trick in `verdict()` from hiding a broken sentinel.
shared = tempfile.mkdtemp(prefix="psfence-shared-")
env = dict(os.environ)
for var in ("TMPDIR", "TEMP", "TMP"):
    env[var] = shared


def _run(p):
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(p),
                         capture_output=True, text=True, timeout=60, env=env)
    return "systemMessage" in (out.stdout or "")


once = CASES["W1"]
check("fires the first time", _run(once), True)
check("fire-once sentinel suppresses the repeat", _run(once), False)

# ---------------------------------------------------------------------------
MUTATIONS = {
    "M1_user_shell_gate": (
        "the warning is about PowerShell, so it needs positive evidence the "
        "user's shell IS PowerShell -- an unknown shell must stay silent",
        [("        if not user_shell_is_powershell(path):\n            return 0",
          "        if False:\n            return 0")],
        {"S10", "S11"},
    ),
    "M2_max_lines_bound": (
        "a long block is a script being shown, not a command to paste; 8 is "
        "one line below where the corpus's first false positive appears",
        # anchored with its comment: the bare assignment also appears in the
        # module docstring, where the measurement is recorded
        [("# The measured ceiling: one line below where the first false "
          "positive appears.\nMAX_LINES = 8",
          "# The measured ceiling: one line below where the first false "
          "positive appears.\nMAX_LINES = 999")],
        {"S5"},
    ),
    "M3_prompt_marks_a_quotation": (
        "a quoted session shows its prompt -- this is what separates "
        "explaining the mistake from committing it, and dropping it makes "
        "the guard fire on its own post-mortem",
        [("        if PROMPT.search(body):\n            continue",
          "        if False:\n            continue")],
        {"S2", "S3"},
    ),
    "M4_non_shell_tags_excluded": (
        "a json/python/markdown block is not a shell command, and the tag is "
        "used ONLY to exclude -- never to include",
        [("        if tag in NON_SHELL_TAGS:\n            continue",
          "        if False:\n            continue")],
        # Only S14 depends on the tag exclusion ALONE. The other three
        # non-shell negatives turn out to be protected twice over, which is
        # worth stating rather than assuming: S2b also carries a `$ ` prompt,
        # and S4's and S12's offending text both sit inside string literals
        # that the quote mask blanks. Defence in depth is fine; believing all
        # four rested on this clause would have been wrong.
        {"S14"},
    ),
    "M5_quote_and_url_masking": (
        "`&&` inside a quoted argument or a URL is data, not a separator",
        [("    for rx in (URL, QUOTED, COMMENT):", "    for rx in ():")],
        # S13's comment masking rides on the same loop, so it flips too; M6
        # isolates that half by removing only COMMENT.
        {"S6", "S7", "S13"},
    ),
    "M6_comment_masking": (
        "a `#` comment is prose inside a command block, and it is where a "
        "path gets QUOTED rather than run",
        [("    for rx in (URL, QUOTED, COMMENT):", "    for rx in (URL, QUOTED):")],
        {"S13"},
    ),
    "M7_env_prefix_is_uppercase_only": (
        "an env-var prefix is uppercase by convention; accepting any "
        "identifier matched `ok=1 msg=done` and `start=18 end=...` in real "
        "transcript output -- three false positives out of six firings",
        [(r'r"(?:^|[;&|\n])[ \t]*[A-Z_][A-Z0-9_]*=[^\s;&|]*[ \t]+[A-Za-z]"',
          r'r"(?:^|[;&|\n])[ \t]*[A-Za-z_][A-Za-z0-9_]*=[^\s;&|]*[ \t]+[A-Za-z]"')],
        {"S15"},
    ),
    "M8_tag_is_not_an_inclusion_test": (
        "the harness tells you to tag runnable blocks ```bash for the Run "
        "button, so requiring that tag would invert the check -- a block "
        "tagged powershell that contains `&&` is the bug itself",
        [("        lines = [ln for ln in body.splitlines() if ln.strip()]",
          "        if tag != 'bash':\n            continue\n"
          "        lines = [ln for ln in body.splitlines() if ln.strip()]")],
        {"W4"},
    ),
}

print("\nmutation tests (break one clause, see which cases flip):")
mutation_wrong = 0
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, replace in edits:
        count = mutated.count(find)
        if count != 1:
            sys.exit(f"FATAL: clause {clause}'s anchor is not present exactly "
                     f"once in {HOOK} (found {count}). The mutation harness is "
                     f"measuring nothing; re-derive the anchor.\n---\n{find}\n"
                     "---")
        mutated = mutated.replace(find, replace)

    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        flipped = {cid for cid in CASES
                   if verdict(path, CASES[cid]) != EXPECTED[cid]}
    finally:
        os.unlink(path)

    ok = flipped == expected_flips
    mutation_wrong += not ok
    if not flipped and expected_flips:
        note = "NOTHING FLIPPED -- this clause is untested"
    elif ok:
        note = "flipped " + ", ".join(sorted(flipped))
    else:
        note = f"flipped {sorted(flipped)}, expected {sorted(expected_flips)}"
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<34} {statement}\n"
          f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under mutation")
print(f"{len(KNOWN_LIMITS)} known limits recorded (see KNOWN_LIMITS)")

if failures or mutation_wrong:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
