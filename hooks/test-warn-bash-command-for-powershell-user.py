#!/usr/bin/env python3
"""Tests for warn-bash-command-for-powershell-user.py.

The negatives are the whole design, and they are CONSTRUCTED rather than
harvested -- which is the honest thing to say about the evidence here.

The corpus under `~/.claude/projects` holds exactly one genuine incident
(re-issued three times in one session). Re-derived 2026-09-15 over 120
transcripts: 1297 assistant text messages, of which 500 are not sidechain and
so readable by a `Stop` hook, 16 of those carrying a fenced block. The shipped
matcher fires 3 times, all on that one directive. An earlier revision of this
docstring published "13 firings for one true positive" as the cost of the
naive `&&` trigger; round-1 adversarial review re-derived it as 4 and showed
the 13 belonged to a much broader trigger measured over messages this hook
cannot read. The corrected figures are in the hook's own docstring.

So the corpus cannot validate the design, and the cases below are what does.
Round-1 review built the false positives the corpus lacks -- a Dockerfile
`RUN` line, a Make recipe, a git alias, a CI step, a session prompted
`user@host:~$`, a URL whose mask ate a closing quote, a heredoc merely named
in a comment -- and every one of them fired against the first implementation.
They are `S16`-`S29`, and they carry more weight than any count.

What does hold up from the original reasoning is the negative result: the
discriminator that suggests itself (suppress when the surrounding prose is
retrospective) marks the true positive and the false ones identically, because
a message can hand over a command AND discuss a failure in the same breath. So
the separation is done on the SHAPE of the block, and `PROMPT` carries almost
all of that load -- `S2`, `S3`, `S21`-`S25`.

`HARNESS NOTE`: the hook fires once per (transcript, reply) via a /tmp
sentinel. The mutation section runs every case many times, so `verdict()`
gives each subprocess a FRESH temp directory. Without it the suite goes RED at
0/18 clauses rather than vacuously green -- every mutation reports NOTHING
FLIPPED, because the sentinel suppresses the second run of each case while the
41 case tests still pass on their unique paths. (Corrected after round-1
review, which measured the failure mode; the earlier note called it a vacuous
pass.) `fires the first time` / `fire-once sentinel suppresses the repeat`
assert the sentinel still works.
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

    # -- cases from round 1 of the adversarial review (8b504813) -----------
    # 2.1: formats whose bodies are bash BY DESIGN and are never pasted into
    # the user's terminal. Every one of these fired before the review.
    "S16": payload("The image builds with:\n\n```dockerfile\n"
                   "RUN apt-get update && apt-get install -y git\n```"),
    "S17": payload("The recipe is:\n\n```makefile\ntest:\n"
                   "\tcd src && pytest -q\n```"),
    "S18": payload("Add the alias:\n\n```gitconfig\n[alias]\n"
                   "  ca = !git add -A && git commit\n```"),
    "S19": payload("The step reads:\n\n```yaml\nrun: npm ci && npm test\n```"),
    # 2.2: URL masking ran first, ate the closing quote of the URL, orphaned
    # the opening one and exposed a `&&` that is inside the SECOND quoted
    # span -- the mask manufacturing the false positive it exists to prevent.
    "S20": payload("Run:\n\n```bash\necho 'https://x.test/a' 'b && c'\n```"),
    # 2.5: the prompts a quoted session actually carries. `user@host:~$` is
    # the DEFAULT Git Bash prompt and so the commonest way a failure is
    # pasted; the first PROMPT spelling knew none of these four.
    "S21": payload("You saw:\n\n```\nuser@host:~$ cd /tmp && ls\n```"),
    "S22": payload("It printed:\n\n```\nroot@box:/# cd /tmp && ls\n```"),
    "S23": payload("From the log:\n\n```\n[user@host ~]$ cd /tmp && ls\n```"),
    "S24": payload("Earlier:\n\n```\nbash-5.1$ cd /tmp && ls\n```"),
    "S25": payload("Your terminal showed:\n\n```\n"
                   "(venv) PS C:\\Work> cd /d/x && git push\n```"),
    # 3.1: the heredoc construct is matched on the RAW body, so a heredoc
    # merely NAMED in a comment or a string fired -- the exact class the
    # comment mask exists to stop.
    "S26": payload("Note:\n\n```bash\n"
                   "git status  # a heredoc looks like <<EOF\n```"),
    "S27": payload("Print it:\n\n```powershell\n"
                   'Write-Output "use <<EOF for a heredoc"\n```'),
    # the tag is normalised before the exclusion test
    "S28": payload("The image builds with:\n\n```DOCKERFILE\n"
                   "RUN apt-get update && apt-get install -y git\n```"),
    # ... and the info string may carry attributes after the language
    "S30": payload('Recipe:\n\n```dockerfile title="build step"\n'
                   "RUN apt-get update && apt-get install -y git\n```"),
    # the MSYS lookbehind: `/c/` inside a relative path is not a drive
    "S29": payload("Copy it:\n\n```bash\ncp src/c/file dst/\n```"),

    # -- must warn, added in the same pass ---------------------------------
    # 3.4: the WSL spelling, which this corpus uses constantly
    "W7": payload("Then:\n\n```bash\ncp /mnt/c/Users/Work/.julia /tmp/x\n```"),
    # 3.4: Git Bash accepts an uppercase drive letter
    "W8": payload("Go there:\n\n```bash\ncd /D/GitHub/x\n```"),
    # 3.5: the harness emits a four-backtick fence when the body itself
    # contains a triple backtick -- the fixed-three pattern missed it
    "W9": payload("Run:\n\n````bash\ncd /d/x && git push\n```\n````"),
    # 3.6: a turn that hands over a command and then makes one more tool call
    # ends with a short record; taking only the LAST one hid the directive
    "W10": payload("Done.", extra_replies=(
        "Run this:\n\n```bash\ncd /d/x && git push\n```",)),
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
    "S16": "a Dockerfile RUN line is bash by design, never pasted",
    "S17": "a Make recipe is bash by design",
    "S18": "a git alias body is bash by design",
    "S19": "a CI `run:` step is bash by design",
    "S20": "the URL mask must not eat a closing quote and expose a `&&`",
    "S21": "`user@host:~$` is the default Git Bash prompt",
    "S22": "`root@box:/#` is a root prompt",
    "S23": "`[user@host ~]$` is a bracketed prompt",
    "S24": "`bash-5.1$` is a version-stamped prompt",
    "S25": "`(venv) PS C:\\Work>` is a prefixed PowerShell prompt",
    "S26": "a heredoc NAMED in a comment is not a heredoc being used",
    "S27": "a heredoc named inside a string is not one either",
    "S28": "the language tag is lowercased before the exclusion test",
    "S30": "an info string's attributes are dropped before the tag test",
    "S29": "`src/c/file` is a relative path, not drive C",
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
    "zero occurrences across the 500 in-scope assistant messages, but running "
    "the matcher over memories/shell.md itself finds four such blocks (the "
    "`pgrep -f` and heredoc sections), so the residual risk is named rather "
    "than assumed absent -- the new section added for THIS hook does not "
    "fire, because it shows its failing command with a prompt and its error",
    "an UNTAGGED Dockerfile/Make/CI/gitconfig body still warns. The tag "
    "exclusion covers only the tagged spelling, and nothing in an untagged "
    "`RUN apt-get update && ...` says it is a build step rather than a "
    "command to paste",
    "a command for a REMOTE host or a container shell warns, and correctly "
    "cannot be distinguished: `cd /var/www/app && systemctl restart app` is "
    "bash the user really should run, just not in the terminal in front of "
    "them. This is the largest false-positive class and there is no signal "
    "for it",
    "MAX_LINES counts NON-BLANK lines, so a release sequence of eight "
    "commands padded with blank lines (18 raw lines) is admitted",
    "the corpus holds ONE genuine incident, so it establishes that the "
    "matcher is quiet on the other 13 in-scope fenced messages and nothing "
    "about the true false-positive rate. The constructed negatives above are "
    "the real evidence",
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
# The whole TURN is checked, not just its last record: a turn that hands over
# a command and then makes one more tool call ends with a short "Done." record,
# and taking only that one hid the directive (round-1 review, finding 3.6).
check("the turn is accumulated, not just its last record",
      hook.last_assistant_text(
          transcript("second", extra_replies=("first",))).split(),
      ["first", "second"])
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
# The sentinel is keyed on the transcript path AS WELL as the reply. Without
# that, two sessions emitting the identical short command share one sentinel
# and the second session's genuine warning is silently swallowed -- the bug
# `remind-ums-after-error.py` documents fixing, cited in the hook's own
# comment and, until round-1 review, tested by nothing.
twin = payload("To make them durable:\n\n```bash\n" + BAD + "\n```")
check("a second session with the identical reply still fires",
      _run(twin), True)
# `seen` de-duplicates (construct, line) pairs so one command repeated in two
# blocks is reported once, not twice. Also untested until round-1 review.
two_blocks = ("```bash\n" + BAD + "\n```\n\ntext\n\n```bash\n" + BAD + "\n```")
check("identical hits in two blocks are reported once",
      len(hook.find_wrong_shell_blocks(two_blocks)),
      len(hook.find_wrong_shell_blocks("```bash\n" + BAD + "\n```")))

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
        [("named in the suite's KNOWN_LIMITS.\nMAX_LINES = 8",
          "named in the suite's KNOWN_LIMITS.\nMAX_LINES = 999")],
        {"S5"},
    ),
    "M3_prompt_marks_a_quotation": (
        "a quoted session shows its prompt -- this is what separates "
        "explaining the mistake from committing it, and dropping it makes "
        "the guard fire on its own post-mortem",
        [("        if PROMPT.search(body):\n            continue",
          "        if False:\n            continue")],
        # every quoted-session form, old and new -- this clause is where the
        # directive/citation split actually lives
        {"S2", "S3", "S21", "S22", "S23", "S24", "S25"},
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
        # S14 plus the four formats whose bodies are bash by design; the
        # other non-shell negatives are protected twice over (S2b by its
        # prompt, S4/S12/S28 by the quote mask or the tag normaliser)
        # S28 and S30 join once their tags are normalised: both are
        # `dockerfile` bodies, differing only in case and in an info-string
        # attribute, so they depend on this exclusion too.
        {"S14", "S16", "S17", "S18", "S19", "S28", "S30"},
    ),
    "M5_quote_and_url_masking": (
        "`&&` inside a quoted argument or a URL is data, not a separator",
        [("    for rx in (QUOTED, URL, COMMENT):", "    for rx in ():")],
        # Removing every mask flips each negative that depends on one: the
        # quoted and URL cases, the comment case (M6 isolates that half), and
        # both heredoc-mentioned-not-used cases, whose position check reads
        # the mask (M12 isolates those).
        {"S6", "S7", "S13", "S20", "S26", "S27"},
    ),
    "M6_comment_masking": (
        "a `#` comment is prose inside a command block, and it is where a "
        "path gets QUOTED rather than run",
        [("    for rx in (QUOTED, URL, COMMENT):", "    for rx in (QUOTED, URL):")],
        # S26's heredoc-in-a-comment rides on the comment mask too: its
        # position check reads the masked copy.
        {"S13", "S26"},
    ),
    "M7_env_prefix_is_uppercase_only": (
        "an env-var prefix is uppercase by convention; accepting any "
        "identifier matched `ok=1 msg=done` and `start=18 end=...` in real "
        "transcript output -- three false positives out of six firings",
        [(r'r"(?:^|[;&|\n])[ \t]*[A-Z_][A-Z0-9_]*=[^\s;&|]*[ \t]+[A-Za-z]"',
          r'r"(?:^|[;&|\n])[ \t]*[A-Za-z_][A-Za-z0-9_]*=[^\s;&|]*[ \t]+[A-Za-z]"')],
        {"S15"},
    ),
    # -- clauses added after round-1 review, which broke fourteen clauses the
    # suite asserted in prose and exercised with nothing.
    "M9_prompt_knows_real_prompts": (
        "`user@host:~$` is the DEFAULT Git Bash prompt and the commonest way "
        "a failing session is pasted; the first spelling knew only a bare "
        "`$ ` at column 0, so the shape gate leaked exactly where it is "
        "load-bearing",
        [(r"      | \S*@\S*[:~][^\n]*[$#][ \t]          # user@host:~$   root@box:/#",
          r"      | (?!x)x                              # disabled")],
        {"S21", "S22"},
    ),
    "M10_prompt_allows_a_venv_prefix": (
        "`(venv) PS C:\\Work>` is any virtualenv or conda PowerShell, and "
        "anchoring `PS` to column 0 missed all of them",
        [(r"      | [^\n>]{0,24}?PS[^>\n]*>             # PS C:\> and (venv) PS C:\>",
          r"      | PS[^>\n]*>                          # PS only")],
        {"S25"},
    ),
    "M11_quoted_is_masked_before_urls": (
        "`URL` is greedy to whitespace, so masking it FIRST eats the closing "
        "quote of a quoted URL, orphans the opening one, and exposes a `&&` "
        "that is inside the next quoted span -- the mask manufacturing the "
        "false positive it exists to prevent",
        [("    for rx in (QUOTED, URL, COMMENT):",
          "    for rx in (URL, QUOTED, COMMENT):")],
        {"S20"},
    ),
    "M12_raw_heredoc_match_is_position_checked": (
        "the heredoc opener is matched on the RAW body so the quote mask "
        "cannot hide its own delimiter -- but the match position must then "
        "be checked against the mask, or a heredoc merely NAMED in a comment "
        "or a string fires",
        [("            hit = next((m for m in rx.finditer(body)\n"
          "                        if masked[m.start():m.end()].strip()), None)",
          "            hit = rx.search(body)")],
        {"S26", "S27"},
    ),
    "M13_tag_is_normalised": (
        "the language tag is lowercased before the exclusion test, so ```JSON "
        "is excluded like ```json",
        [("        tag = tag.strip().lower().split()[0] if tag.strip() else \"\"",
          "        tag = tag.strip().split()[0] if tag.strip() else \"\"")],
        {"S28"},
    ),
    "M18_tag_info_string_is_split": (
        "a fenced info string may carry attributes after the language, and "
        "the exclusion test reads the language alone",
        [("        tag = tag.strip().lower().split()[0] if tag.strip() else \"\"",
          "        tag = tag.strip().lower() if tag.strip() else \"\"")],
        {"S30"},
    ),
    "M14_fence_accepts_more_than_three_ticks": (
        "the harness emits a four-backtick fence whenever the body itself "
        "contains a triple backtick -- exactly when a reply is showing "
        "markdown that contains a command",
        [(r'FENCE = re.compile(r"^[ \t]*(`{3,})([^\n`]*)\n(.*?)^[ \t]*\1[ \t]*$",',
          r'FENCE = re.compile(r"^[ \t]*(`{3})([^\n`]*)\n(.*?)^[ \t]*\1[ \t]*$",')],
        {"W9"},
    ),
    "M15_msys_path_lookbehind": (
        "`/c/` inside a relative path (`src/c/file`) is not a drive letter",
        [(r'r"(?<![\w.])/(?:mnt/[A-Za-z]/|[A-Za-z]/[A-Za-z0-9_.-]"',
          r'r"/(?:mnt/[A-Za-z]/|[A-Za-z]/[A-Za-z0-9_.-]"')],
        {"S29"},
    ),
    "M16_turn_is_accumulated_not_last_message": (
        "a turn that hands over a command and then makes one more tool call "
        "ends with a short record, so taking only the LAST assistant message "
        "made the directive invisible",
        [("    turn = []\n    for entry in _records(transcript_path):",
          "    turn = []\n    for entry in list(_records(transcript_path))[-1:]:")],
        {"W10"},
    ),
    "M17_attachment_list_of_dicts": (
        "the environment brief arrives as `rendered: [{'content': ...}]` in "
        "every real transcript measured, so losing that branch blinds the "
        "shell gate entirely and the hook can never fire",
        [("                elif isinstance(item, dict):\n"
          "                    value = item.get(\"content\")\n"
          "                    if isinstance(value, str):\n"
          "                        yield value",
          "                elif isinstance(item, dict):\n"
          "                    pass")],
        # every positive goes silent: with no shell evidence the gate closes
        {"W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W10"},
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
