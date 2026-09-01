#!/usr/bin/env python3
"""PreToolUse guard: refuse a hand-rolled review-verdict parse.

`scripts/check-pr-fully-clean.py` is this corpus's verdict authority, and
[`shared/workflow/ardi.md`](../shared/workflow/ardi.md) already mandates it for
the single-PR loop. Nothing mandated it for a multi-PR **sweep**, which is
exactly where a hand-rolled parser goes in --- so
[`deterministic-tools`](../shared/principles/deterministic-tools.md)'s
constraint ("use the instrument that exists") got violated in the presence of
the instrument.

WHY A PHRASE SEARCH CANNOT WORK
-------------------------------
A verdict comment routinely QUOTES other verdicts. Citing the previous round,
pasting a repro block, discussing what a phrase should classify as --- all of
that lands verdict vocabulary in the body before the comment reaches its own
`### Verdict` section. So the FIRST match is usually somebody else's verdict.

Measured 2026-08-08 (ai-config#1297, recorded in
[`fully-clean.md`](../shared/workflow/fully-clean.md)), one sweep, two PRs, and
it misread in OPPOSITE directions:

  #1278  first match `Ready for merge` at offset 2980, inside a fenced python
         block quoting `classify_verdict("Ready for merge\\nonce CI passes.")`
         real verdict at 5421: **Needs more work**          -> false-CLEAN
  #1257  first match `Needs more work` at offset 775, inside a parenthetical
         citing the PRIOR round
         real verdict at 2401: **Ready for merge**          -> false-BLOCKED

The bidirectionality is what makes it unfixable by tuning: it cannot be
corrected with an offset or a "the reviewer errs pessimistic" assumption. The
false-clean direction is the expensive one --- it produced a MERGE
RECOMMENDATION on a PR whose verdict was blocking.

WHY PreToolUse RATHER THAN Stop
-------------------------------
Deliberate, and the alternative was really considered.

A `Stop` guard would have to key on the resulting CLAIM, and the claim-shaped
matcher is far too broad: legitimately reporting "the review says needs more
work", after reading a body carefully, is a correct thing to say and must not
be blocked. Narrowing that matcher enough to be safe narrows it into silence.

The parse itself is the decidable event, and it is decidable at the moment the
command is about to run --- before the wrong reading enters context at all. By
`Stop` time the false-clean verdict has already shaped the recap, and may
already have been acted on.

The block is also trivially satisfiable, which is what keeps a `deny` honest
(README, "A hook that misfires is worse than a missing one"): the remedy is one
documented command, and a genuinely-needed hand parse clears it with a one-token
env prefix.

THE CHECK
---------
All five must hold:

  1. a VERDICT phrase appears in the command
  2. that phrase sits in a MATCHING position --- an argument to jq
     test/capture/match/..., to grep/rg, to awk/sed, or to a python `re.` call.
     Merely echoing or printing the phrase is not a parse.
     2a. AND it is not inside a `select(...)`, which is candidate selection
         rather than verdict extraction. This is what lets `fully-clean.md`'s
         own documented query through; see `phrase_in_matcher_position`.
  3. the data is REVIEW-DERIVED --- the same command names a review-comment
     source (`issues/N/comments`, `pulls/N/comments`, `--json comments`, ...)
     or reads a saved body file.
  4. NO `check-pr-fully-clean.py` invocation earlier in the transcript FOR THAT
     PR (see the discharge note below)
  5. NO `ALLOW_HANDROLLED_VERDICT_PARSE=1` env-assignment prefix

Clause 3 is what keeps the negatives silent, and it carries most of the
precision: a `grep` of this repo's own docs for `Ready for merge` has 1 and 2
and fails 3, as does a grep of this file.

THE DISCHARGE IS PER-PR, ON PURPOSE
-----------------------------------
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)'s "A
reminder guard's discharge condition is a second matcher" names the trap: an
over-broad discharge makes a guard go silent, and silence reads as compliance.
Discharging on ANY `check-pr-fully-clean.py` call anywhere in the session would
do exactly that --- one call early in a sweep would license hand-rolling every
remaining PR in it, which is the incident's own shape.

So the PR numbers in the offending command must all have been passed to
`check-pr-fully-clean.py`. Where the command names no PR number the guard falls
back to "any invocation discharges": still armed (a session with zero
invocations still fires), lenient only about WHICH PR. That leniency is
deliberate at the ambiguous edge, because this is a `deny` --- a guard that
blocks work it cannot attribute is a guard that gets switched off.

MEASURED ON A REAL CORPUS
-------------------------
Authored cases inherit the blind spot of whoever already understands the rule,
so the matcher was also run over **7837 real Bash commands** harvested from
live transcripts (`~/.claude/projects/*/*.jsonl`), whose wording nobody here
chose.

    clauses 1-3 fire on 123 / 7837  (1.57%)   before the select() exemption
    clauses 1-3 fire on  53 / 7837  (0.68%)   after

That corpus is what found the `select()` over-block: the 70 commands it
removed are dominated by this corpus's OWN documented candidate-selection
query, which no authored case had thought to include. The surviving 53 are
overwhelmingly the target class -- `grep -iE "ready for merge|findings"` over
a fetched review body, and `capture()` on a verdict comment.

Re-run it after widening anything here, in both directions: an over-block on a
legitimate read is the more urgent finding, since it is the direction that
gets a guard switched off.

KNOWN GAPS
----------
Both recorded rather than papered over, and both are deliberate choices to err
toward allowing, because this is a `deny` and an over-block is the direction
that gets a guard switched off.

1. **An arbitrarily-named saved body.** `gh api ... > /tmp/x.json`, then
   `jq ... /tmp/x.json`, fails clause 3 in the second command. Widening clause
   3 to any file at all would fire on every `jq` in the session.

2. **An OUTCOME phrase inside `select()`.** The exemption above treats
   everything inside a `select(...)` as candidate selection, so
   `select(.body | contains("Needs more work"))` is allowed. That is right when
   the selected bodies are printed for reading, and wrong if the selection
   itself is being read as the verdict -- counting how many bodies matched is
   the first-match fallacy wearing a filter.

   A sharper rule is available and was deliberately not taken: exempt a phrase
   in `select()` only when it is a MARKER (`**Claude finished`, `### Verdict`)
   rather than an OUTCOME (`Ready for merge`, ...), which is what separates the
   corpus's endorsed query -- it selects on the marker -- from selecting on the
   verdict. It was left out because the guard cannot see what the output is
   used for, so the split would block legitimate filtering to catch a misuse
   that only exists downstream. Worth revisiting if the gap is ever observed
   causing harm.

Fails OPEN on any parse trouble. A guard that breaks Bash when a regex
misbehaves costs more than the mistake it prevents.
"""
import json
import re
import sys

# Verdict vocabulary. Sourced from the phrases the incident's own `capture()`
# alternation used, plus the two structural markers `fully-clean.md` names as
# the correct anchors -- a search for THOSE is the same hand-rolled parse.
VERDICT_PHRASE = re.compile(
    r"Ready for merge|Needs more work|Needs minor changes|Needs one fix|"
    r"Needs work|Partial review|###\s*Verdict|\*\*Claude finished",
    re.I,
)

# Tools that MATCH text, as opposed to printing it. The phrase has to sit in an
# argument to one of these for the command to be a parse at all.
MATCHER_TOKEN = re.compile(
    r"\bjq\b|--jq\b|\bgrep\b|\begrep\b|\brg\b|\bag\b|\bawk\b|\bsed\b|"
    r"\bre\.(?:search|match|fullmatch|findall|finditer|compile|split|sub)\b|"
    r"\b(?:test|capture|scan|splits|startswith|endswith)\s*\(",
    re.I,
)
# How far after a matcher token the phrase may sit and still count as its
# argument. Generous, because clause 3 carries the precision -- a wide window
# here costs a false positive only when the command ALSO reads review comments.
MATCH_WINDOW = 400

# Clause 3: the command's data is review-derived. Two alternatives, and no
# more -- a `gh pr view N --json comments` form was dropped as redundant, since
# the `--json` alternative already decides it.
REVIEW_SOURCE = re.compile(
    # REST: repos/O/R/issues/N/comments, .../pulls/N/reviews, and the
    # repo-wide forms that omit the number.
    r"(?:issues|pulls)/(?:\d+/)?(?:comments|reviews)"
    # gh pr view --json comments, --json state,reviews
    r"|--json\s+[\w,]*(?:comments|reviews)",
    re.I,
)
# A body previously saved to a data file.
#
# Matched on the NAME, and only for data-ish extensions. Both restrictions are
# load-bearing. Matching any file whose name contains "verdict" would fire on
# this hook's own source and on its test -- the README's cautionary example
# exactly. And an earlier draft also matched any `/tmp/*.json` at all, which was
# both untested and inconsistent with KNOWN GAPS item 1 above: it is the same claim
# as "an arbitrarily-named saved body is not caught", made twice in opposite
# directions. Dropped in favour of the stated gap.
SAVED_BODY = re.compile(
    r"\S*(?:review|comment|verdict|body)\S*\.(?:json|jsonl|txt)\b",
    re.I,
)

# PR numbers this command is parsing.
PR_IN_COMMAND = [
    re.compile(r"issues/(\d+)/comments", re.I),
    re.compile(r"pulls/(\d+)/(?:comments|reviews)", re.I),
    re.compile(r"gh\s+pr\s+(?:view|diff|checks)\s+(\d+)", re.I),
]

# An INVOCATION of the instrument, and the PR it was run against.
#
# The leading interpreter (or `./`) is load-bearing rather than decoration: a
# bare `check-pr-fully-clean\.py` also matches `cat scripts/check-pr-fully-
# clean.py` and `grep -n foo scripts/check-pr-fully-clean.py`, so READING the
# script would discharge the guard. The `view_file` skip below cannot catch
# those, because they arrive as Bash.
#
# An earlier draft guarded this with a `(?<!test_)(?<!test-)` lookbehind
# instead, to keep a run of the script's own test suite from discharging it.
# That clause was measured DEAD: the suite is `scripts/test_check_pr_fully_
# clean.py`, whose name carries underscores, so the hyphenated string never
# appears in it and the lookbehind could not fire. Removed rather than shipped
# untested (ai-config#1304, "measured-dead guard components").
#
# A flag may carry a SEPARATE value token (`-R OWNER/REPO 445`), not only an
# `=`-joined one. Without the optional value the flag run stops at `-R`, the
# `\s+(\d+)` never reaches `445`, and the PR goes unrecorded.
# `check-pr-fully-clean.py` grew exactly such a flag in ai-config#1391, so this
# is that change's own consequence rather than a hypothetical.
#
# The direction that failure runs in is the SAFE one, and stating it precisely
# matters because this comment exists to guide the next widening. An
# unrecorded PR leaves `checked` empty, so a suspicious command that DOES name
# that PR makes `targets <= checked` false and the guard BLOCKS -- a
# false-positive over-block of work that was properly instrumented. It does
# NOT reach the lenient `elif ran: return 0` fallback, which fires only when
# the suspicious command itself names no PR (`targets` empty) and so does not
# depend on what `checked_prs` captured.
#
# Worth fixing anyway: this is a `deny`, and the docstring above says a guard
# that blocks work it cannot attribute is a guard that gets switched off.
#
# Measured, rather than reasoned: with the optional value removed, the same
# transcript (`... -R Morrison-Lab/gha 1278`) plus a parse targeting #1278
# goes allow -> BLOCK. The mutation case in the test file records the same
# transition as its before/after pair.
#
# The value token is optional and the engine backtracks, so a valueless flag is
# unaffected: in `--verbose 445` the optional value declines to eat `445` and
# the PR still matches. Measured on both forms.
CHECKER_CALL = re.compile(
    r"(?:python3?\s+|\./)\S*check-pr-fully-clean\.py"
    r"((?:\s+-{1,2}\S+(?:\s+[^-\s]\S*)?)*\s+(\d+))?",
    re.I,
)

# The explicit override. A real leading env assignment, not a mention.
OVERRIDE = re.compile(
    r"(?:^|[|;&]\s*|\(\s*)(?:\w+=\S*\s+)*ALLOW_HANDROLLED_VERDICT_PARSE=1\b")


def select_spans(cmd):
    """Character spans of every `select( ... )`, by paren balance.

    A phrase inside one is CANDIDATE SELECTION, not verdict extraction -- see
    `phrase_in_matcher_position`.
    """
    spans = []
    for m in re.finditer(r"\bselect\s*\(", cmd):
        depth, i = 0, m.end() - 1
        while i < len(cmd):
            if cmd[i] == "(":
                depth += 1
            elif cmd[i] == ")":
                depth -= 1
                if depth == 0:
                    spans.append((m.start(), i))
                    break
            i += 1
        else:
            spans.append((m.start(), len(cmd)))  # unbalanced: treat as open
    return spans


def phrase_in_matcher_position(cmd):
    """Clause 1 AND 2: a verdict phrase in a matcher's argument, EXTRACTING.

    A phrase inside a `select(...)` is exempt, and that exemption is the
    difference between the incident and the corpus's own endorsed query. Both
    match a verdict phrase against review comments; only one of them reads a
    verdict off it.

        # fully-clean.md's OWN documented idiom -- selection, then print the
        # whole body for a careful read. Must pass.
        jq -s '[.[][] | select(.body | test("\\*\\*Claude finished|### Verdict"))]
               | last | .body'

        # the incident -- selection, then EXTRACT a verdict from the body.
        ... select(.body|test("\\*\\*Claude finished")) ... | .body
            | capture("(?<v>Ready for merge|Needs more work)").v
                     ^^^^ outside any select(): this is the parse

Blocking the first would be a serious over-block: it is the query this
    corpus tells you to run, it is how a careful read starts, and the brief
    for this guard names "a legitimate careful read" as a must-pass. Measured
    on 7837 real Bash commands from live transcripts, the select() exemption
    is what separates 123 raw hits from the far smaller set that actually
    extract a verdict.
    """
    spans = select_spans(cmd)
    for m in MATCHER_TOKEN.finditer(cmd):
        start = m.end()
        window = cmd[start:start + MATCH_WINDOW]
        for hit in VERDICT_PHRASE.finditer(window):
            pos = start + hit.start()
            if any(a <= pos <= b for a, b in spans):
                continue  # candidate selection, not extraction
            return hit.group(0)
    return None


def is_review_derived(cmd):
    """Clause 3."""
    return bool(REVIEW_SOURCE.search(cmd) or SAVED_BODY.search(cmd))


def prs_in(cmd):
    found = set()
    for rx in PR_IN_COMMAND:
        found.update(rx.findall(cmd))
    return found


def checked_prs(path):
    """Scan the transcript for check-pr-fully-clean.py calls.

    Returns (ran_at_all_successfully, set_of_valid_pr_numbers).
    A call that failed with an environment/usage error (e.g., exit 2 because `gh`
    is missing or invalid arguments) does NOT discharge the guard, either for a
    specific PR or for an untargeted parse.
    """
    if not path:
        return False, set()

    pending = {}  # tool_use_id -> pr_number
    valid_prs = set()
    successful_calls = set()

    with open(path, errors="ignore") as fh:
        for idx, line in enumerate(fh):
            try:
                msg = json.loads(line)
            except Exception:
                continue
            blocks = (msg.get("message") or {}).get("content")
            if blocks is None:
                blocks = msg.get("content") or []
            if isinstance(blocks, dict):
                blocks = [blocks]
            elif isinstance(blocks, str):
                blocks = [{"type": "text", "text": blocks}]
            elif not isinstance(blocks, list):
                blocks = []
            else:
                blocks = list(blocks)

            if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                for tc in msg["tool_calls"]:
                    if isinstance(tc, dict):
                        tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                        targs = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                        if isinstance(targs, str):
                            try:
                                targs = json.loads(targs)
                            except Exception:
                                targs = {"command": targs}
                        tid = tc.get("id") or str(id(tc))
                        blocks.append({
                            "type": "tool_use",
                            "id": tid,
                            "name": tname,
                            "input": targs if isinstance(targs, dict) else {},
                        })

            for b in blocks:
                if not isinstance(b, dict):
                    continue
                b_type = b.get("type")
                if b_type == "tool_use":
                    name = (b.get("name") or "").lower()
                    # Reading the script is not running it. A `Grep` whose PATTERN
                    # is the invocation is the case that needs this: the pattern
                    # carries an interpreter, so it satisfies CHECKER_CALL exactly
                    # as a real run would.
                    if name in ("read", "grep", "glob",
                                "view_file", "read_file", "grep_search", "list_dir"):
                        continue
                    blob = json.dumps(b.get("input") or {})
                    for m in CHECKER_CALL.finditer(blob):
                        pr_target = m.group(2)
                        use_id = b.get("id") or f"call_{idx}"
                        pending[use_id] = pr_target
                        if pr_target:
                            valid_prs.add(pr_target)
                        successful_calls.add(use_id)
                elif b_type == "tool_result":
                    use_id = b.get("tool_use_id")
                    if not use_id or use_id not in pending:
                        continue
                    output_text = str(b.get("content") or b.get("output") or "")
                    is_failure = (
                        "is not installed or not on PATH" in output_text or
                        "This script requires the GitHub CLI" in output_text or
                        "usage: check-pr-fully-clean.py" in output_text or
                        "Cannot resolve the repository" in output_text or
                        "is not in OWNER/REPO form" in output_text or
                        "Traceback (most recent call last)" in output_text or
                        "Command failed (" in output_text or
                        (output_text and "Checking ARDI / fully-clean status for" not in output_text)
                    )
                    if is_failure:
                        failed_pr = pending.pop(use_id)
                        if failed_pr and failed_pr not in pending.values():
                            valid_prs.discard(failed_pr)
                        successful_calls.discard(use_id)

    ran = len(successful_calls) > 0
    return ran, valid_prs


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"no-handrolled-verdict-parse: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    try:
        if (payload.get("tool_name") or "") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
            return 0
        inp = payload.get("tool_input") or {}
        cmd = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""
        if not cmd:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        # 5: explicit override.
        if OVERRIDE.search(cmd):
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0
        # 1 + 2: a verdict phrase in a matching position.
        phrase = phrase_in_matcher_position(cmd)
        if not phrase:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0
        # 3: the data is review-derived.
        if not is_review_derived(cmd):
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0
        # 4: the instrument has not already answered for this PR.
        ran, checked = checked_prs(payload.get("transcript_path") or "")
        targets = prs_in(cmd)
        if targets:
            if targets <= checked:
                return 0
        elif ran:
            return 0
    except Exception:
        return 0  # fail open

    # The emit is inside its own try for the same reason the decision is: the
    # docstring promises this fails OPEN on any trouble, and a crash while
    # BUILDING the refusal would otherwise exit non-zero with a traceback --
    # failing open in the docstring and not in the code.
    try:
        emit(phrase, targets, checked)
    except Exception:
        return 0
    return 0


def emit(phrase, targets, checked):
    unchecked = sorted(targets - checked) if targets else []
    which = f" for PR #{', #'.join(unchecked)}" if unchecked else ""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"This command matches the verdict phrase \"{phrase.strip()}\" "
                "against a PR's review comments. That is a hand-rolled verdict "
                f"parse, and `check-pr-fully-clean.py` has not been run{which}.\n\n"
                "A verdict comment routinely QUOTES other verdicts -- the "
                "previous round's, a repro block, a discussion of what a phrase "
                "should classify as -- all before its own `### Verdict` section. "
                "So a phrase search finds somebody else's verdict, and it "
                "misreads in BOTH directions.\n\n"
                "Measured 2026-08-08, one sweep (ai-config#1297):\n"
                "  #1278  matched `Ready for merge` inside a quoted python "
                "block; real verdict **Needs more work**   -> false-CLEAN\n"
                "  #1257  matched `Needs more work` inside a parenthetical "
                "citing the prior round; real verdict **Ready for merge**   "
                "-> false-BLOCKED\n\n"
                "The false-clean direction produced a merge recommendation on a "
                "PR whose verdict was blocking.\n\n"
                "Call the instrument instead:\n\n"
                "    python3 scripts/check-pr-fully-clean.py <PR>\n\n"
                "If you genuinely must parse by hand, `fully-clean.md` says to "
                "anchor on the LAST `### Verdict` heading -- the last, not the "
                "first -- after selecting candidate comments on the "
                "`**Claude finished` body marker. Then prefix this command with "
                "`ALLOW_HANDROLLED_VERDICT_PARSE=1` (a real env assignment, not "
                "a mention) to say the choice was deliberate."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
