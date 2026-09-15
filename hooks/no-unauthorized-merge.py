#!/usr/bin/env python3
"""PreToolUse guard: mechanistically prohibit PR/MR merge commands and MCP merge tools.

Prohibits commands or MCP tool calls attempting to merge PRs/MRs (e.g. `gh pr merge`,
`glab mr merge`, `gh api .../merge`, `glab api .../merge`, GraphQL `mergePullRequest` /
`enablePullRequestAutoMerge`, or GitHub MCP `mcp__github__merge_pull_request` and
defensive auto-merge tool variants)
unless explicit authorization is present via ALLOW_MERGE=1, --allow-merge, active /mwc,
or standing per-repository grant.

Three authorization paths, narrowest last: the per-command ALLOW_MERGE=1 /
--allow-merge override, an active session `/mwc` grant, and a STANDING
per-repository grant for PRs targeting a repo in STANDING_MERGE_GRANT_REPOS.
"""
from __future__ import annotations

import bisect
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

# A command word begins only at a *command position*. Segments reaching
# MERGE_PATTERNS are already split on `;`, `&&`, `||`, `|` and newlines, so
# within a segment the command positions are: its start, after a background
# `&`, and after a subshell / command-substitution opener (`(`, `` ` ``, `$(`).
#
# Plain whitespace is deliberately NOT one. It used to be, and that is what made
# the guard fire on any prose, grep pattern, or string literal that merely NAMED
# the command -- including its own refusal text, so it blocked writing
# documentation, filing a bug report, or debugging itself (ai-config#1279,
# defect 2). shared/principles/fail-fast.md states the bar this restores:
# "test that mentions, greps, and quotes of the gated command pass".
CMD_POS = r"""(?:^|[;&`(\n]|\$\()\s*"""
# Keywords and wrappers whose OPERAND is itself a command word, so the word
# after one is still at a command position. Dropping bare whitespace from
# CMD_POS also dropped every one of these, because each is separated from its
# operand by a space rather than by punctuation: `! gh pr merge`, `time gh pr
# merge`, `nohup gh pr merge`, `{ gh pr merge; }` and `if true; then gh pr
# merge; fi` are all executable bash that ran the merge while the guard
# returned allow (ai-config#1287 review, reproduced end to end).
#
# This does NOT re-admit bare whitespace, because a keyword only counts when a
# CMD_POS precedes it: prose like `you can gh pr merge later` still has no
# command position before `gh` and stays allowed. Bounded for the same reason
# VAR_PREFIX is -- see its note below.
KEYWORD_PREFIX = r"""(?:(?:!|\{|time|nohup|sudo|then|else|do|if|elif|while|until)\s+){0,4}"""
# Expansions that may expand to nothing and so leave the NEXT word as the
# command: `$FOO gh pr merge` runs the merge when $FOO is empty. Matched only
# after a command position, so a mid-command `echo $FOO gh pr merge` does not.
#
# The repetition is BOUNDED rather than `*`. Unbounded, each of the N command
# positions in a long run of substitutions rescans the rest of the run before
# failing, which is quadratic: measured 610ms on 800 chained backtick pairs
# against 2.8ms for the pre-anchor matcher, on a hook that runs before every
# Bash call. Four consecutive empty-expansion prefixes is already well past
# anything a real command does, and capping makes the work per position
# constant.
VAR_PREFIX = r"""(?:(?:\$\{?[A-Za-z0-9_]+\}?|\$\([^)]*\)|`[^`]*`)\s*){0,4}"""
LEAD = CMD_POS + KEYWORD_PREFIX + VAR_PREFIX
# The permissive counterpart: ANY whitespace is a command position, plus a
# closing `)`. Defined here beside LEAD because three separate places need a
# command-position anchor and each one that rolled its own has since had to be
# fixed. See the note above PERMISSIVE_MERGE_PATTERNS for why the permissive
# form exists at all, and HEREDOC_EXECUTOR for why the masking decision wants
# this one rather than the narrow one.
PERMISSIVE_LEAD = r"""(?:^|[;&`()\n\s]|\$\()\s*""" + KEYWORD_PREFIX + VAR_PREFIX
ENV_WRAP = r"""(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*"""
# Programs that RUN text handed to them, rather than consuming it as data.
#
# One list, three consumers, because getting it wrong in any of them fails open
# in the same way and each door was found separately: a quoted operand
# (`bash -c "<merge>"`), pass 2's quote masking, and a heredoc body fed to a
# shell (`bash <<EOF`). Three rounds of review found one door each. Keeping the
# membership in one place is what makes the residual a single reviewable list
# rather than three lists that drift.
#
# Both masking consumers now share ONE anchor (EXEC_AT_CMD_POS below). The
# third, EXEC_WRAP, is pattern-side and is measured DEAD against the suite --
# see its own note.
EXEC_PROGS = r"env|exec|command|bash|sh|zsh|ksh|dash|eval|trap|watch|su|ssh"

# Lets a matching pattern step over an executor between the command position
# and `gh`, e.g. `bash -c gh pr merge`. The optional non-flag word is `ssh`'s
# hostname.
#
# MEASURED DEAD, and kept deliberately. Since mask_inert_quotes stopped
# blanking an executor's live operand, the permissive pass anchors on the
# whitespace left where the quote was and matches the operand directly, so
# dropping EXEC_WRAP from all nine patterns fails ZERO of the suite's cases --
# including every one it was originally added for. Retained because this is a
# guard: a redundant path costs a few characters of regex, while removing one
# on suite evidence alone fails OPEN if the suite is the thing that is
# incomplete. Its removal is a reviewable simplification, not a bug fix.
#
# Pass 1 itself is NOT dead: removing it fails two cases, both `gh api graphql`
# mutations whose payload the permissive pass has already masked.
EXEC_WRAP = (
    r"""(?:[/\w.-]+/)?(?:""" + EXEC_PROGS + r""")"""
    r"""(?:\s+-[a-zA-Z0-9]+)*(?:\s+[A-Za-z0-9_.@-]+)?(?:\s+-[a-zA-Z0-9]+)*"""
    r"""(?:\s+["'])?\s*"""
)

# A heredoc whose consumer is one of the above is a SCRIPT, not data: `bash
# <<EOF` and `ssh host <<EOF` execute the body line by line. The quoted-delimiter
# form is not an exception -- `<<'EOF'` only suppresses expansion, and bash still
# runs what it reads.
# Built from the SAME LEAD machinery the matching passes use, not a hand-rolled
# anchor. The first version rolled its own and accepted only an env assignment
# before the executor, so `sudo bash <<EOF`, `time bash <<EOF`, `! bash <<EOF`
# and `if true; then bash <<EOF` all walked through -- the keyword-prefix gap
# from round 1, reproduced in a fourth place by the very commit that
# consolidated EXEC_PROGS into one list. Consolidating one duplicated concept
# is no protection against forking a different one in the same edit.
# PERMISSIVE_LEAD, not LEAD. The narrow one still carries a closed enumeration
# of what may precede a command word, so `sudo -u x bash <<EOF`, `timeout 30
# bash <<EOF`, `nice bash <<EOF` and `xargs bash <<EOF` all failed the anchor
# and had their bodies masked as prose. Building it from LEAD fixed the
# keyword forms and left every wrapper-with-an-argument form open, which is the
# same enumeration failing in the same place a round later.
#
# The permissive one is not merely wider, it is the CORRECT direction here.
# This anchor decides whether to MASK, and over-detecting an executor means
# declining to mask -- so the body is scanned rather than skipped. A false
# positive costs a scan; a false negative hides a merge. That asymmetry is the
# reverse of pass 1's, which is why the MASKING side is permissive while the
# MATCHING side keeps the narrow lead.
# One anchor for "an executor is invoked here", shared by both masking
# decisions -- now literally the same compiled object, not two built from a
# common part. Rolling a second one produced round 5's gap and round 6's; the
# leftover DIFFERENCE between them produced round 7's.
#
# The heredoc consumer used to require the executor to come BEFORE the `<<`
# token (`EXEC_AT_CMD_POS + r"[^\n]*?<<"`). A redirection may appear anywhere in
# a simple command, so `<<EOF bash`, `<<'EOF' sh` and `<<EOF ssh host` are all
# ordinary bash that run the body -- and all of them failed a forward-only scan,
# so the body was masked as prose and the merge ran.
#
# What the decision actually needs is CO-OCCURRENCE: this line introduces a
# heredoc (that is why the caller is asking), and an executor is invoked
# somewhere on it. Order was never part of the question, and assuming it was is
# the same shape as enumerating what may precede a command word.
EXEC_AT_CMD_POS = re.compile(
    PERMISSIVE_LEAD + ENV_WRAP + r"(?:[/\w.-]+/)?(?:" + EXEC_PROGS + r")\b"
)
# HEREDOC_EXECUTOR is bound below, once DOT_SOURCE_AT_CMD_POS exists.
# The quote-masking counterpart. A quoted span is inert only when nothing
# before it in the same simple command can run it; `bash -c "<merge>"`,
# `eval "<merge>"` and `ssh host "<merge>"` are the executor's own operand and
# are LIVE. Same asymmetry as the heredoc anchor above: over-detecting means
# declining to mask, which costs a scan, while under-detecting hides a merge.
EXEC_BEFORE_QUOTE = EXEC_AT_CMD_POS
# `source` and `.` run the CONTENTS of what they are handed, so a process
# substitution or a heredoc given to either is a script exactly as
# `bash <(...)` and `bash <<EOF` are.
#
# Deliberately NOT folded into EXEC_PROGS, which has THREE consumers where only
# two want this. EXEC_BEFORE_QUOTE reads an operand as a COMMAND, while
# `source`'s operand is a FILENAME, so adding it there would keep
# `source "gh pr merge"` live for no gain. And `.` cannot take the `\b` that
# consumer appends: `\b` after a non-word character requires a word character
# next, which `. <(` does not have.
#
# Getting that split wrong once already cost a hole. The first version of this
# comment reasoned about the quoted-operand consumer, concluded "not in
# EXEC_PROGS", and never asked what the OTHER consumers needed -- so
# `source /dev/stdin <<'EOF' ... EOF` had its body masked as inert prose while
# bash ran the merge inside it. Enumerating one consumer and stopping is the
# same shape as enumerating what may precede a command word.
#
# The lookahead keeps `./script.sh` from matching, since `.` is followed by
# `/`. It does NOT keep a bare `.` pathspec from matching: PERMISSIVE_LEAD
# makes any whitespace a command position, so the ` . ` in `rsync -a . <(...)`
# matches and that substitution is read as executed. The over-block is
# accepted rather than narrowed -- this anchor decides whether to SCAN, where
# a false positive costs a scan and a false negative hides a merge -- but it
# is stated here because the claim, not the behaviour, was wrong before.
DOT_SOURCE_AT_CMD_POS = re.compile(
    PERMISSIVE_LEAD + ENV_WRAP + r"(?:source|\.)(?=[ \t])"
)
# "This construct's CONTENTS are executed", for a caller that only asks WHETHER
# one is present. `mask_heredocs` is that caller: it decides whether the line's
# consumer RUNS the body, and `source`/`.` do (ai-config#1308 review, finding
# 3) -- `source /dev/stdin <<'EOF'` executes what it reads.
#
# An alternation is sound for `search`, and NOT for `finditer`. A single
# pattern consumes text non-overlappingly, so one branch's match can swallow a
# position the other branch would have reported: over 60,000 random token
# strings its match-end set differed from the true union in 2,027 of them, and
# `')$FOO )`bash` . '` reports only the `.` while dropping the `` `bash` ``.
# For a guard a dropped executor position is the fail-open direction, so the
# scanner that enumerates POSITIONS uses `executes_its_input_ends` below
# instead. Calling this one "the union" was wrong (same review, finding 6).
HEREDOC_EXECUTOR = re.compile(
    "(?:" + EXEC_AT_CMD_POS.pattern + ")|(?:" + DOT_SOURCE_AT_CMD_POS.pattern + ")"
)


def executes_its_input_ends(text: str) -> list:
    """Sorted end offsets where `text` invokes something that RUNS its input.

    Each anchor is run separately and the results merged, because ONE
    alternation cannot report a position another branch consumed: its
    match-end set differed from the merged one in 2,027 of 60,000 random
    strings.

    NOT every such position, which this docstring claimed until round 3
    finding 6. `finditer` is non-overlapping WITHIN each anchor too, so
    `EXEC_AT_CMD_POS` alone still drops an executor consumed by an earlier
    match of itself -- 14 of 20,000 random strings disagree with a
    match-at-every-offset scan. That residue changed 0 of 40,000 fuzzed
    verdicts, and reverting this function to the alternation fails 0 suite
    cases, so it narrows a known fail-open direction rather than fixing a
    reachable defect. Stated here rather than left looking complete.
    """
    return sorted({m.end() for m in EXEC_AT_CMD_POS.finditer(text)}
                  | {m.end() for m in DOT_SOURCE_AT_CMD_POS.finditer(text)})


# Where the current simple command begins. An operand cannot be separated from
# its executor by a command separator, so scanning back only this far keeps
# `bash -c "x"; echo "prose"` from treating the second quote as live.
COMMAND_SEPARATOR = re.compile(r"[;&|\n`()]")
OPT_VAL = r"""(?:="[^"]*"|='[^']*'|=[^\s;&|`()]+|\s+"[^"]*"|\s+'[^']*'|\s+[^\s;&|`()]+|\$\{IFS\}[^\s;&|`()]+)"""
OPT_FLAGS = rf"(?:\s+-[A-Za-z0-9_-]+(?:{OPT_VAL})?)*"
HTTP_METHOD = r"(?:[pP][uU][tT]|[pP][oO][sS][tT]|[pP][aA][tT][cC][hH])"
API_WRITE_FLAG = rf"(?:-X\s*=?\s*{HTTP_METHOD}|--method\s*=?\s*{HTTP_METHOD}|-f\b|-F\b|--field\b|--raw-field\b|--input\b)"

DELIM = r"(?:\s+|\$\{IFS\}|\$IFS\b|\$\([^)]*\)|\$[A-Za-z0-9_]+)+"
GH_PROG = r"(?:[/\w.-]+/)?(?:gh|\$GH|\$\{GH\})\b"
GLAB_PROG = r"(?:[/\w.-]+/)?(?:glab|\$GLAB|\$\{GLAB\})\b"

def _merge_patterns(lead: str) -> list:
    """Build the merge-command patterns against a given command-position LEAD.

    Parameterized so the same nine patterns can run twice: once with the narrow
    LEAD over raw text, and once with PERMISSIVE_LEAD over quote-masked text.
    See the two-pass note on `offending`.
    """
    return [
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + OPT_FLAGS + DELIM + r"pr\b" + OPT_FLAGS + DELIM + r"merge\b", "gh pr merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GLAB_PROG + OPT_FLAGS + DELIM + r"mr\b" + OPT_FLAGS + DELIM + r"merge\b", "glab mr merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*(?:^|[\s/])pulls/[^\n]+/merge\b", "gh api PR merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"[^\n]*\s+api\b[^\n]*(?:^|[\s/])pulls/[^\n]+/merge\b[^\n]*" + API_WRITE_FLAG, "gh api PR merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*(?:^|[\s/])repos/[^\n]+/merges\b", "gh api repository merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"[^\n]*\s+api\b[^\n]*(?:^|[\s/])repos/[^\n]+/merges\b[^\n]*" + API_WRITE_FLAG, "gh api repository merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GH_PROG + r"(?:\s+[^\n]+)?\s+api\b[^\n]*graphql\b[^\n]*(?:mergePullRequest|enablePullRequestAutoMerge|disablePullRequestAutoMerge)", "gh api GraphQL PR merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GLAB_PROG + r"[^\n]*\s+api\b[^\n]*" + API_WRITE_FLAG + r"[^\n]*(?:^|[\s/])merge_requests/[^\n]+/merge\b", "glab api MR merge"),
        (lead + ENV_WRAP + r"(?:" + EXEC_WRAP + r")?" + GLAB_PROG + r"[^\n]*\s+api\b[^\n]*(?:^|[\s/])merge_requests/[^\n]+/merge\b[^\n]*" + API_WRITE_FLAG, "glab api MR merge"),
    ]


MERGE_PATTERNS = _merge_patterns(LEAD)

# Pass 2's command position: ANY whitespace, plus a closing `)`.
#
# Enumerating what may precede a command word cannot be finished. Two rounds of
# review found five constructs and then two more (`case $x in p) <merge>`, and
# `f() { <merge>; }; f`), each a real bypass, each a member of a class with no
# closed definition -- and every miss fails OPEN, which is the direction that
# matters for a guard whose stated purpose is to be unbypassable.
#
# So pass 2 stops enumerating. It treats every position as a command position
# and instead removes the text that cannot execute. That inverts the failure:
# an unforeseen construct is now blocked rather than allowed, and the cost of
# being wrong is an over-block, which ALLOW_MERGE=1 clears.
#
# The measurement that chose this: making the narrow LEAD permissive changed
# exactly seven of 141 cases, and all seven were prose inside quotes. Nothing
# else in the suite depends on the narrowness -- so masking quotes buys back
# every one of them, and keeps defect 2 (ai-config#1279) fixed by construction
# rather than by enumeration.
PERMISSIVE_MERGE_PATTERNS = _merge_patterns(PERMISSIVE_LEAD)

# The leading-whitespace allowance is OUTSIDE the repeated env-assignment group,
# not inside it. Inside, it only ever applied to assignments AFTER the first, so
# a segment whose first token was the override itself failed the `^` anchor the
# moment it carried any leading whitespace -- which every segment after a `&&`,
# `;` or `|` does, because SPLIT leaves the separator's trailing space on the
# next segment. `ALLOW_MERGE=1 <merge>` was accepted while
# `cd /repo && ALLOW_MERGE=1 <merge>` was not (ai-config#1279, defect 4), and the
# refusal message printed the segment `.strip()`ed, removing the very character
# that caused the mismatch. Leading whitespace in a segment is inert in bash, so
# accepting it authorizes nothing a bare `ALLOW_MERGE=1 ...` did not already.
ALLOW_ENV_FLAG = re.compile(
    r"^\s*(?:(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)\s+)*ALLOW_MERGE=(?:\"1\"|'1'|1\b)"
)
SPLIT = re.compile(r"&&|\|\||;|\||\n")


def unquote_words(text: str) -> str:
    """Normalize bash quote-removal on individual command/subcommand word tokens.

    In Bash, quoting part or all of a word token without spaces or subshells
    (e.g. "gh", 'gh', "pr", "merge", g""h, 'glab', "mr", "/usr/bin/gh")
    is identical to the unquoted word. This function strips inert quotes from single-word tokens
    so MERGE_PATTERNS matches regardless of quote placement on command/subcommand names.
    """
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'''(["'])([A-Za-z0-9_./-]+)\1''', r'\2', text)
        text = re.sub(r'''(?<=[A-Za-z0-9_./-])(?:""|'')(?:(?=[A-Za-z0-9_./-])|$)''', '', text)
        text = re.sub(r'''(?:^|(?<=[\s;&|`()]))(?:""|'')(?:(?=[A-Za-z0-9_./-])|$)''', '', text)
    return text


def has_allow_override(segment: str) -> bool:
    """Check if command segment contains an explicit authorization override.

    Matches either:
    1. ALLOW_MERGE=1 env assignment anchored at segment start.
    2. Standalone --allow-merge flag token occurring OUTSIDE of string quotes.
       Tokenizing quote context ensures forged --allow-merge strings inside unmasked flag values
       or bare positional text (e.g. --reviewer "please --allow-merge this") do not bypass authorization.
    """
    if ALLOW_ENV_FLAG.search(segment):
        return True

    for m in re.finditer(r"(?:^|[\s;&|`\n])(--allow-merge)\b", segment):
        idx = m.start(1)
        in_single = False
        in_double = False
        escaped = False
        for i in range(idx):
            c = segment[i]
            if escaped:
                escaped = False
                continue
            if c == "\\" and not in_single:
                escaped = True
                continue
            if c == "'" and not in_double:
                in_single = not in_single
                continue
            if c == '"' and not in_single:
                in_double = not in_double
                continue
        if not in_single and not in_double:
            return True
    return False


def mask_trailing_comments(text: str) -> str:
    """Mask trailing shell comments (# ...) with spaces while respecting quote context.

    In Bash, '#' inside quotes ('...' or "...") is a literal character, not a comment boundary.
    This function tokenizes quote state line-by-line to ensure '#' inside quoted strings is NOT
    mistaken for a shell comment, preventing quote-enclosed '#...' strings from swallowing
    subsequent statement separators or merge commands.
    """
    lines = text.split("\n")
    masked_lines = []
    for line in lines:
        in_single = False
        in_double = False
        escaped = False
        comment_start = -1
        for i, c in enumerate(line):
            if escaped:
                escaped = False
                continue
            if c == "\\" and not in_single:
                escaped = True
                continue
            if c == "'" and not in_double:
                in_single = not in_single
                continue
            if c == '"' and not in_single:
                in_double = not in_double
                continue
            if c == "#" and not in_single and not in_double:
                if i == 0 or line[i - 1] in " \t;&|`()":
                    comment_start = i
                    break
        if comment_start != -1:
            line = line[:comment_start] + " " * (len(line) - comment_start)
        masked_lines.append(line)
    return "\n".join(masked_lines)


def mask_subexpressions(val: str) -> str:
    """Mask literal prose inside payload flags with spaces, while preserving live command substitutions (`...` or $(...)) unmasked."""
    sub_pattern = r"(`[^`]*`|\$\([^)]*\))"
    tokens = re.split(sub_pattern, val)
    result = []
    for i, tok in enumerate(tokens):
        if i % 2 == 1:
            result.append(tok)
        else:
            result.append("".join("\n" if c == "\n" else " " for c in tok))
    return "".join(result)


# Where a shell word ends. Anything not in here is part of the word, so
# `use_case` is one word and not a `case`.
_WORD_BREAK = set(" \t\n;&|()<>\"'`$\\")


def _paren_scan(text: str, quote_aware: bool):
    """`(closes, starts, quotes_balanced)` for one pass over `text`.

    `closes` maps an opener index to its closer; `starts` lists each expandable
    `<(` as `(lt_index, open_index)`.

    SOME `)` CHARACTERS ARE NOT CLOSERS. The three below are the ones this
    scanner models, each found the same way -- by a reviewer executing a merge
    the scanner had read past. They are NOT the whole set: this docstring once
    said "THREE THINGS" and there turned out to be at least five, which is why
    `_body_is_simple` now trusts a matched `)` only for a body containing none
    of `_APPROXIMATED`. Read that function's comment for the ones NOT modelled
    here; do not read this list as exhaustive.

    A `case` PATTERN's `)` opened nothing (round 3). Pairing it with the
    nearest open paren truncated that paren's body, so
    `bash <(case x in x) echo "<merge>";; esac)` recorded `case x in x` and ran
    the merge. The discriminator is the stack DEPTH the `case` was opened at: a
    `)` while the stack has grown no deeper cannot close anything that `case`
    contains. `case` also requires its `in` -- without that, `grep -c case f`
    armed pattern mode and the substitution's own closer was skipped, which
    over-blocked every later quoted merge mention on the line (round 4).

    An EXPANSION's `)` or `}` belongs to the expansion (round 4). `${x//)/}`,
    `$(echo ")")` and a backtick span all make a `)` literal to bash, and the
    quote-aware pass reported BALANCED for each -- so the fail-closed default
    never engaged and the merge ran. `$(`, `${` and backticks are therefore
    tracked as their own nesting contexts rather than left to the quote state.

    A `)` inside QUOTES is not a closer, which is the original quote tracking.
    """
    closes = {}
    starts = []
    stack = []            # (kind, index); kind is proc, paren, subst or brace
    case_depths = []      # stack depth at each `case`, once its `in` is seen
    pending_case = []     # stack depth at each `case` awaiting its `in`
    at_cmd_pos = True     # the word about to be flushed starts a command
    prev_word = ""        # the last complete unquoted word
    word = ""
    in_single = in_double = in_backtick = escaped = ansi_c = False
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if escaped:
            escaped = False
        # `$'...'` is ANSI-C quoting, where a backslash DOES escape -- unlike a
        # plain `'...'`, where it does not.
        #
        # MEASURED DEAD AT VERDICT LEVEL AND KEPT, like `EXEC_WRAP` and the
        # comment masking below: reverting this branch fails 0 suite cases and
        # produces 0 verdict differences across 30,000 random inputs, because
        # `$'` is in `_APPROXIMATED` and short-circuits the region either way.
        # It stays live at SCANNER level (quote balance differs), and it is
        # kept because the whitelist's coverage of `$'` is itself the thing
        # under review. The fail-open below is stated in the PAST tense for
        # that reason (ai-config#1308 review, round 8 finding 6). Reading `$'a\')'` under plain
        # single-quote rules ended the string one quote early, closed the
        # substitution at the `)` that followed, and truncated the body past
        # the merge (ai-config#1308 review, round 4 finding 2).
        elif (quote_aware and c == "$" and i + 1 < n and text[i + 1] == "'"
              and not in_single and not in_double and not in_backtick):
            in_single = ansi_c = True
            i += 2
            continue
        elif quote_aware and c == "\\" and (not in_single or ansi_c):
            escaped = True
        elif quote_aware and c == "'" and not in_double and not in_backtick:
            if in_single:
                ansi_c = False
            in_single = not in_single
        elif quote_aware and c == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif quote_aware and c == "`" and not in_single and not in_double:
            # A backtick span is a command substitution whose parens are its
            # own. Treated as opaque rather than modelled, which is the
            # fail-closed direction for the span that contains it.
            in_backtick = not in_backtick
        elif not in_single and not in_double and not in_backtick:
            # Word tracking runs only outside quotes, so a quoted "esac" in
            # prose closes nothing.
            #
            # A word ends at a shell METACHARACTER, not at any non-letter.
            # Accumulating `c.isalpha()` alone gave the word no LEFT boundary,
            # so `use_case` and `test_case` flushed as the bare word `case`,
            # pushed a spurious depth, and the substitution's own `)` was
            # skipped -- 36 fail-opens in a 660-command fuzz, every one that
            # class (round 3).
            #
            # `$case` is NOT in that list and never was: `$` is a word break
            # here, so it still flushes `case`. It is harmless now only because
            # `in` is also required, and saying otherwise was a false claim in
            # this comment's previous version (round 4).
            if c not in _WORD_BREAK:
                word += c
            else:
                # The `in` must belong to the `case`, which means no command
                # separator between them: `for case in a b` and
                # `grep -c case f; grep -c in f` both armed pattern mode
                # otherwise, ran the body to end of text, and blocked a later
                # prose mention (round 5 finding 9).
                # `for case in a b` and `select case in ...` name a VARIABLE
                # `case`, and its `in` follows immediately with no separator,
                # so the separator test above cannot tell them apart. The
                # preceding word can (round 5 finding 9).
                if word == "case" and prev_word not in ("for", "select"):
                    pending_case.append(len(stack))
                elif word == "in" and pending_case:
                    if pending_case.pop() == len(stack):
                        case_depths.append(len(stack))
                elif word == "esac" and at_cmd_pos:
                    # Guarded on COMMAND POSITION and on DEPTH. With neither,
                    # an ordinary argument word `esac` (`echo esac`,
                    # `grep esac f`) disarmed a live `case` mid-construct and
                    # the next arm's `)` truncated the body the same way
                    # (round 6 finding 2). A real `esac` always follows `;;`
                    # or a newline, so it is always at a command position.
                    if case_depths and case_depths[-1] == len(stack):
                        case_depths.pop()
                    elif pending_case and pending_case[-1] == len(stack):
                        pending_case.pop()
                # A NEWLINE is a command separator everywhere EXCEPT between
                # a `case` and its `in`, where bash permits one:
                #
                #     case b
                #     in b) echo hi;; esac
                #
                # Counting it left a real `case` unarmed, its first arm's `)`
                # popping the `proc` frame, and the truncated body passing
                # `_body_is_simple` -- the THIRD executing fail-open in this
                # model, blocked by rounds 4 and 5 and allowed by 6 and 7. A
                # grammar enumeration of 103,680 valid `case` shapes found
                # 28,350 executing strings, every one carrying a newline in
                # this window and none carrying a plain space (round 7
                # finding 1).
                #
                # The cost is that a newline-separated prose mention
                # (`grep -c case f` then `grep -c in f` on the next line) now
                # arms pattern mode and extends the body. That is the
                # fail-closed direction, and it is narrower than the `;`-
                # separated shape round 5 finding 9 was about, which
                # `del pending_case[:]` below still catches.
                if c in ";&|":
                    # A real separator proves every PENDING `case` was not a
                    # construct: bash allows only whitespace and newlines
                    # between `case WORD` and its `in`, so `: case; ...` is an
                    # argument word, not a keyword.
                    #
                    # Leaving the entry on the stack let a later argument word
                    # `in` pop it and arm a SECOND `case_depths` entry that the
                    # construct's single `esac` never disarmed. The
                    # substitution's own `)` was then consumed as a pattern
                    # terminator, `closes` came back empty, and
                    # `< <(: case; case x in x) : in; echo "<merge>";; esac) bash`
                    # ran a real merge -- the fourth fail-open in this model,
                    # present on every revision of this branch, and one whose
                    # body carries no `_APPROXIMATED` token at all
                    # (ai-config#3649). Both decoys are load-bearing: remove
                    # either `: case;` or `: in;` and it blocks.
                    #
                    # A newline deliberately does NOT clear it, because
                    # `case b` / `in b)` across two lines is legal bash and is
                    # the round-7 fail-open.
                    #
                    # THIS LINE SUBSUMED A WHOLE `separated` FLAG, which used
                    # to gate the `in` above and is now removed. The flag was
                    # set on `;&|` and on a newline with nothing pending; the
                    # first case clears `pending_case` on the very next line,
                    # and the second leaves it empty -- so reaching the `in`
                    # branch at all needs a `case` pushed afterwards, which
                    # is where the flag was reset. It could therefore never be
                    # True where it was read.
                    #
                    # Measured rather than argued alone: reverting the
                    # conjunct failed 0 of 343 cases, reverting its assignment
                    # failed 0, and an instrumented build recorded 0 hits at
                    # the read site across 300,000 random token strings --
                    # against 4,640 reads of that site, which is the negative
                    # control making the 0 a measurement rather than a
                    # detector that never ran.
                    #
                    # A sanity mutant for THAT harness -- dropping the
                    # `separated = False` reset in the `case` push, the only
                    # edit that can make the flag True at the read -- records
                    # 621 hits. An earlier version of this comment said "a
                    # sanity mutant on the same harness failed 2", which
                    # attached a SUITE-failure count to a harness that reports
                    # hits, and named no mutant, so the figure could not be
                    # reproduced by anyone but its author (ai-config#3681,
                    # finding 4). The file
                    # annotates its other measured-dead clauses (`EXEC_WRAP`,
                    # the ANSI-C `$'` branch) rather than leaving them to read
                    # as load-bearing; this one was removed instead, because
                    # unlike those it has a proof and not only a measurement
                    # (ai-config#3635 pre-merge gate).
                    del pending_case[:]
                # A command position is the start of the TEXT, or anything
                # just past a separator or a bare `(`. Flushing a real word
                # consumes it: the NEXT word is an argument.
                #
                # Two things this deliberately is NOT, both checked rather
                # than assumed (round 7 finding 4 corrected the earlier
                # wording, which claimed both):
                #   - not the start of a REGION. The flag is initialized once
                #     per `_paren_scan` pass and never reset at a `<(`, so a
                #     body's first word reads as an argument.
                #   - not the `(` of `$(`, `${` or `<(`. Each of those
                #     branches runs AFTER this block and skips its `(` with
                #     `i += 2; continue`, so only a bare subshell `(` arrives
                #     here.
                # Both divergences leave a `case` armed for longer than
                # strictly necessary, which extends the body -- the
                # fail-closed direction.
                if c in ";&|\n(":
                    at_cmd_pos = True
                elif word:
                    at_cmd_pos = False
                if word:
                    prev_word = word
                word = ""
            if c == "$" and i + 1 < n and text[i + 1] == "(":
                stack.append(("subst", i + 1))
                i += 2
                continue
            if c == "$" and i + 1 < n and text[i + 1] == "{":
                stack.append(("brace", i + 1))
                i += 2
                continue
            if c == "(":
                stack.append(("paren", i))
            elif c == "}":
                if stack and stack[-1][0] == "brace":
                    stack.pop()
            elif c == ")":
                # The case-pattern test comes FIRST. Popping a `subst`
                # unconditionally consumed the pattern terminator of a `case`
                # opened inside `$( )`, after which the substitution's real `)`
                # popped the enclosing region and truncated the body
                # (round 5 finding 2).
                if case_depths and len(stack) <= case_depths[-1]:
                    pass                 # a `case` pattern terminator
                elif stack and stack[-1][0] == "subst":
                    stack.pop()          # closes the command substitution
                elif stack and stack[-1][0] in ("paren", "proc"):
                    closes[stack.pop()[1]] = i
            elif c == "<" and i + 1 < n and text[i + 1] == "(":
                starts.append((i, i + 1))
                stack.append(("proc", i + 1))
                i += 2
                continue
        else:
            word = ""
        i += 1
    return closes, starts, not (in_single or in_double or in_backtick)


def _paren_matches(text: str):
    """`(closes, starts)`, quote-aware, with a quote-blind reading merged in.

    An odd quote leaves every later character reading as quoted, so the
    quote-aware scan silently stops seeing `<(` at all. Masking comments closes
    one source of that; it is not the only one, because `mask_heredocs`
    deliberately leaves an EXECUTING heredoc's body live and an apostrophe
    there arrives unmasked (round 3). Enumerating the sources is the failure
    this file keeps recording, so when the quote state does not balance -- the
    scan calling itself unreliable -- a second, quote-blind pass runs.

    The two readings are MERGED, never substituted. A quote-blind pass finds
    more region STARTS and can find strictly SHORTER bodies, because a `)`
    inside quotes closes a region it should not, which is what the substituted
    version did (round 4). So a start is kept if either pass saw it, and a body
    runs to the FURTHER of the two closers.

    A body whose CLOSER only one pass found runs to the end of the text. That
    is about the closer, not about the region: both passes routinely see the
    same start while only one finds a closer, and the earlier wording here --
    "when only one pass saw the region at all" -- described a narrower
    condition than the code applies (round 5 finding 10). The implemented rule
    is the one stated now.

    Calling it "the more fail-closed of the two" was false when written, and
    is true only because of a later fix. Dropping the closer leaves
    `_proc_subst_regions` with no entry for that opener, and blanking to the
    defaulted end of text erased a TRAILING executor -- so an apostrophe or a
    lone backtick in an executing heredoc body, which is what makes this pass
    run at all, opened an executing bypass rather than closing one
    (ai-config#3635 pre-merge gate). `_depth_view` now reads the region's
    `closed` field and blanks only the `<(` delimiter in that case, which is
    what makes the sentence hold.

    `starts` from the fallback may include a `<(` inside quotes, which bash
    would not expand. That is an over-detection and it is deliberate: the pass
    only runs on input whose quoting this scanner has already failed to read.
    """
    closes, starts, balanced = _paren_scan(text, quote_aware=True)
    if balanced:
        return closes, starts
    blind_closes, blind_starts, _ = _paren_scan(text, quote_aware=False)
    merged = dict(closes)
    for open_idx, close_idx in blind_closes.items():
        merged[open_idx] = max(merged.get(open_idx, close_idx), close_idx)
    seen = {open_idx for _lt, open_idx in starts}
    all_starts = list(starts)
    for lt_idx, open_idx in blind_starts:
        if open_idx not in seen:
            all_starts.append((lt_idx, open_idx))
            seen.add(open_idx)
    all_starts.sort()
    # A region only one pass saw has no closer the other can confirm, so it
    # runs to the end of the text. `_proc_subst_regions` reads a missing key
    # that way already.
    for _lt, open_idx in all_starts:
        if open_idx not in closes or open_idx not in blind_closes:
            merged.pop(open_idx, None)
    return merged, all_starts


# Past this many nested process substitutions, stop analysing and treat the
# body as executed. The analysis costs one linear pass per nesting LEVEL, so an
# unbounded depth is unbounded work on a guard that runs before every Bash
# call; a cap turns that into a constant. Failing CLOSED at the cap is the
# direction this whole file takes -- an over-block clears with ALLOW_MERGE=1,
# and nothing anyone writes by hand nests six deep.
MAX_PROC_SUBST_DEPTH = 6


# Constructs this scanner models APPROXIMATELY. A body containing any of them
# is not one whose closing `)` can be trusted.
#
# WHY A WHITELIST, after five rounds of the other thing. The design rested on
# "a modelling error fails closed", and that held only when the error also
# unbalanced the QUOTE state, because the fail-closed path is keyed on quote
# balance alone. Every fail-open found since has been a `)` misread while
# quotes stayed balanced, so the net never fired: a `)` in a shell comment, a
# `case` pattern inside `$( )` whose terminator pops the substitution first, a
# `$( )` or `${ }` or backtick nested inside DOUBLE QUOTES where bash restarts
# quoting and this scanner does not, and a `)` inside an executing heredoc body
# that `mask_heredocs` deliberately leaves live.
#
# Each was found by a reviewer executing a real merge. `_paren_scan`'s
# docstring ABOVE enumerates the three this scanner models, and says there that
# the list is not exhaustive; there were at least
# five, and this file records the same enumeration failing five separate times
# for command-position anchors. An enumeration of what BREAKS the model cannot
# be finished. An enumeration of what the model provably HANDLES can.
#
# So the matched `)` is trusted only for a body with none of these in it, and
# any other body runs to the end of the text. The cost is an over-block on a
# command that both contains one of these constructs AND carries a merge-shaped
# string later on the same line; the benefit is that the next unmodelled
# construct is a blocked command rather than a silent merge.
_APPROXIMATED = ("#", "`", "$(", "${", "$'", "<<")


def _body_is_simple(text: str, body_start: int, body_end: int) -> bool:
    """True when nothing in this body defeats the paren model.

    Deliberately conservative and deliberately cheap: a substring scan over one
    region, with no attempt to decide whether a given occurrence is really the
    construct it looks like. A `#` inside a word is not a comment, and paying
    an over-block for it is the whole design.

    `case` is the one construct NOT listed, and that exemption is the weakest
    joint in this design. The whitelist's safety argument is "everything not
    on the list is modelled", so exempting a construct is a claim that needs a
    proof rather than an assertion -- and the first version of this paragraph
    asserted it. Round 6 of review then executed two real merges straight
    through the `case` model: a `case` after any separator failed to arm, and
    an argument word `esac` disarmed a live one. Round 6 was therefore a
    REGRESSION against rounds 4 and 5, which both blocked those strings.

    Both holes are closed in `_paren_scan`: the first because the `in` arm is
    now unconditional, the second by its `at_cmd_pos` handling. The six
    regression cases are in the suite.

    `del pending_case[:]` was named here for the first of them and does not do
    that work. Reverting it fails exactly one case and that case is an ALLOW:
    it prevents the round-5-finding-9 over-block and closes no fail-open
    (ai-config#3681, finding 5). Round 6's hole is closed by the ABSENCE of
    the `separated` gate, which is a consequence of removing it rather than of
    any line added. The
    exemption stays because listing `case` extends every body merely MENTIONING
    the word to end of text, re-creating the over-block the `in` requirement
    was added to remove -- `bash <(grep -c case f); echo "<prose>"` blocking a
    prose mention. A `case` nested inside `$( )`, which the model does not
    handle, is covered by `$(` being listed.

    A third one did turn up -- round 7's newline between the case word and its
    `in` -- and a previous version of this paragraph said what to do about it:
    "the honest alternative if a third one turns up is to list `case` and pay
    the over-block." That instruction was WRONG, and it was measured wrong
    rather than argued away.

    Listing `case` (word-bounded, which is the cheaper of the two spellings)
    moves 5 suite cases -- four verdict-level over-blocks and one scanner-level
    span change. The figure 6 stood here briefly and belonged to the PLAIN
    SUBSTRING spelling, which is the one a `_APPROXIMATED` entry gets for free
    and which this sentence does not name: the parenthetical calls
    word-bounded the cheaper of the two, and cheaper means fewer, so the
    sentence contradicted its own number (ai-config#3681, finding 1). Both
    re-derived here:

        word-bounded  `re.search(r"\bcase\b", body)`   338/343   moves 5
        substring     `"case" in body`                  337/343   moves 6

    The four over-blocks are `source <(...)`, a bare argument word `case`, a
    loop variable named `case`, and an `in` in a later simple command; the
    fifth is the span check `a case pattern's `)` is not the closer`, whose
    verdict does not change. The paragraph this replaced drew that
    distinction and the rewrite collapsed it.

    The span for

        < <(case x in x) echo "<merge>";; esac) bash

    goes `[(4, 46)]` to `[(4, 52)]` -- longer, with `len(text) = 52` -- and
    the verdict stays BLOCK.

    THAT IS A CHANGE, and the paragraph it replaces is worth stating because
    the correction runs the reassuring way. It read "8 suite cases ... 3
    fail-opens ... `[(4, 46)]` becomes `[]`", and all three figures were true
    when written. The commit that split `real_end` from the extended
    `close_idx` -- and its follow-up, which stopped blanking past a region
    whose closer was never recorded -- invalidated them without touching this
    paragraph. A measurement quoted beside a mechanism it can no longer
    exercise is how the next reader learns a wrong cost model, which is what
    the sibling suite legislates against: re-measure, never copy forward.

    So the ARGUMENT for the exemption has changed even though the exemption
    has not. It used to be that listing `case` opened fail-opens, which made
    keeping it out mandatory. It is now that listing `case` extends every body
    merely MENTIONING the word to end of text, re-creating the over-block the
    `in` requirement was added to remove -- `bash <(grep -c case f); echo
    "<prose>"` blocking a prose mention. A cost, not a hazard.

    The model still has to hold, because the whitelist's safety argument is
    "everything not on the list is modelled". Four fail-opens have been found
    in it, the last a stale `pending_case` popped by an argument word `in`,
    which `_paren_scan` now discards at a separator.

    The general property -- that extending a body is fail-closed for a leading
    executor and fail-OPEN for a trailing one -- is ai-config#3649, and it is
    NOT a constraint on future entries only. That is how a previous version of
    this paragraph and of #3649 both put it, and it was the more damaging
    error: five of the six entries ALREADY shipped an executing bypass, each
    blocked by four earlier revisions of this branch.

    Blanking to the real closer restores the premise the whitelist rests on
    ONLY where a closer was recorded. Where none was, `real_end` defaults to
    end of text and the split is a no-op -- two more executing bypasses lived
    there, and `_depth_view` now reads the region's `closed` field instead.
    The suite carries one trailing-executor case per whitelist member, and one
    per no-recorded-closer route.

    Finding a mechanism that invalidates a design premise and then scoping it
    to future work reads as diligence -- a rule written, an issue filed --
    while the live instances go unexamined. The check cost one loop over six
    strings.
    """
    body = text[body_start:body_end]
    return not any(token in body for token in _APPROXIMATED)


def _proc_subst_regions(text: str) -> list:
    """`(lt_idx, body_start, close_idx, depth, parent, real_end, closed)` per `<(`.

    Ordered by position, so siblings at one depth are disjoint and a child
    always follows its parent. `parent` indexes back into this same list, or is
    `-1` at the top level.

    A candidate with no matching `)` has its BODY taken to run to the end of
    the text, which is the fail-closed direction for `bash <(...)` and the
    fail-OPEN direction for `< <(...) bash` -- the extended body swallows the
    trailing executor, so the region is never classified as executed and the
    span list comes back empty rather than longer. An earlier version of this
    paragraph called the behaviour fail-closed without qualification, four
    paragraphs after the note that records the asymmetry. The seventh tuple
    field says whether a closer was actually recorded, and `_depth_view` reads
    it so the blanking does not reach past the region.

    The earlier version dropped it, justified as "bash rejects the command
    outright". That is a claim about bash, and the condition is a claim about
    THIS SCANNER -- `bash <(use_case=1; echo "<merge>")` is balanced, bash
    accepts it, bash runs the merge, and a modelling bug here read it as
    unbalanced (ai-config#1308 review, round 3 findings 1 and 3). Dropping made
    every present and future error in the paren model an ALLOW, which is the
    one direction this file never takes. A genuinely unbalanced command is
    rejected by bash before anything runs, so over-blocking one costs nothing.
    """
    closes, candidates = _paren_matches(text)
    regions, stack = [], []
    for lt_idx, open_idx in candidates:
        real_end = closes.get(open_idx, len(text))
        close_idx = real_end
        if not _body_is_simple(text, open_idx + 1, close_idx):
            close_idx = len(text)
        while stack and lt_idx > regions[stack[-1]][2]:
            stack.pop()
        # Both ends are kept, and the difference is load-bearing.
        #
        # `close_idx` is what the SPAN uses: an unmodelled body is assumed to
        # run to end of text, so everything after it is live. `real_end` is
        # what BLANKING uses, and blanking to the extended end was an
        # executing fail-open.
        #
        # `bash <(...)` puts the executor BEFORE the region, where a longer
        # body cannot hide it. `< <(...) bash` puts it AFTER, so blanking to
        # end of text erased the `bash` itself; `executes_its_input_ends`
        # then found no executor, the region was never classified as
        # executed, and the span list came back EMPTY rather than longer.
        # Five of the six `_APPROXIMATED` entries had a `bash -n` clean
        # proof of concept that ran a real merge, each blocked by four
        # earlier revisions of this branch and allowed from the whitelist
        # commit onward (ai-config#3649).
        #
        # The premise the whitelist rests on -- "extending a body is the
        # fail-closed direction" -- is therefore true only once blanking
        # stops at the real closer.
        #
        # `real_end` alone was not enough, and that is this fix's own missed
        # half. `closes.get(open_idx, len(text))` DEFAULTS to end of text, so
        # for a candidate with no recorded closer `real_end` IS the extended
        # end and blanking erased the trailing executor exactly as before.
        # Two routes reach that state with valid bash -- a `case` pattern's
        # `)`, and `_paren_matches` popping the closer on quote imbalance --
        # and each ran a real merge while the hook allowed it, with the
        # leading-executor twin of the same command blocking (ai-config#3635
        # pre-merge gate). `closed` is what lets `_depth_view` tell the two
        # apart.
        regions.append((lt_idx, open_idx + 1, close_idx,
                        len(stack), stack[-1] if stack else -1, real_end,
                        open_idx in closes))
        stack.append(len(regions) - 1)
    return regions


# What a blanked region is filled with, and it is deliberately NOT a space.
#
# EXEC_AT_CMD_POS is quadratic on a long WHITESPACE run -- its command-position
# lead is `[;&`()\n\s]\s*` followed by two bounded repetitions that each end in
# `\s*`/`\s+`, so every position in the run re-tries the same partitions.
# Measured on `main`: `echo x` plus 1200 trailing spaces takes 1502ms inside
# `offending`, and 2400 takes 5886ms. That is pre-existing (ai-config#3640) --
# but filling a view with spaces would hand that regex its worst input once per
# nesting level, so a 400-deep nest cost 1288ms here before this character
# changed.
#
# What makes NUL work is narrow, and an earlier version of this note overstated
# it as "NUL is in no character class this file matches" -- false, since `\S`,
# ENV_WRAP and VAR_PREFIX all match it. What is true is the only part that
# matters: NUL is not in PERMISSIVE_LEAD's `[;&`()\n\s]`, so no command
# position opens inside a filled run and the whitespace partitioning above
# cannot start (ai-config#1308 review, finding 5).
#
# `_FILL` fixes the WHITESPACE shape and not the others. A run of `$(` is still
# quadratic in EXEC_AT_CMD_POS itself, and where a depth view IS built, running
# that scan once per view multiplies it -- bounded by `MAX_PROC_SUBST_DEPTH` at
# 7 rather than by the nesting depth, so a constant factor on a pre-existing
# quadratic rather than a new order. The quadratic itself is ai-config#3640.
#
# An earlier version of this comment quoted "380ms on `main` against 923ms
# here" for 6 KB of `$( ` repetitions. Re-measured on this revision: 385ms,
# against 381ms on `main`. The figure was wrong AND the mechanism could not
# have applied to that input, because `'$( ' * 2000` contains no `<(` at all --
# `_proc_subst_regions` returns 0 regions, `live_proc_subst_spans` returns at
# `if not regions`, and `_depth_view` is never called. A measurement quoted
# beside a mechanism it cannot exercise is how the next reader learns a wrong
# cost model (round 6 finding 7).
_FILL = "\x00"


def _blank(view: list, start: int, stop: int) -> None:
    """Fill `view[start:stop]` with `_FILL`, keeping one space at each end.

    The end spaces replace the `<` and the `)` themselves, so they supply the
    command position PERMISSIVE_LEAD needs on either side of a filled run.

    They are NOT what saves `< <(...) bash`: the space before that `bash` sits
    outside the blanked range and is never touched, and deleting both
    assignments still blocks it and fails no suite case. An earlier version of
    this docstring claimed otherwise (ai-config#1308 review, finding 4). What
    they do change is degenerate input -- a fuzz over 120,000 random token
    strings found 103 verdict differences with them removed -- so they stay,
    with the reason stated as what it is.
    """
    # `stop` may run one past the end: a candidate with no matching `)` fails
    # closed with its body taken to the end of the text, and the caller then
    # asks to blank through `body_end + 1`.
    stop = min(stop, len(view))
    if stop <= start:
        return
    for i in range(start, stop):
        view[i] = _FILL
    view[start] = " "
    view[stop - 1] = " "


def _depth_view(text: str, regions: list, depth: int) -> str:
    """`text` with only the simple commands at nesting `depth` legible.

    Length-preserving, so one set of offsets indexes this and `text` alike.

    Two blankings, and the second is the whole point. Everything outside a
    depth-`depth` body is blanked, so a separator in an enclosing shell cannot
    bound a command in this one. Then every depth-`depth` substitution is
    blanked WHOLE -- its `<(`, its body, and its `)` -- so the enclosing simple
    command reads as one contiguous run.

    Blanking the DELIMITERS is what finding 1 of ai-config#1308's review
    turned on. `(` and `)` are COMMAND_SEPARATORs, so leaving them in place
    cuts the enclosing simple command in two, and an executor written on the
    far side of the substitution lands in a different segment:
    `< <(echo "<merge>") bash` really runs the merge, and a scan that only
    looked BEFORE the `<(` never saw the `bash`. This file already recorded
    that lesson for heredocs -- "A redirection may appear anywhere in a simple
    command ... Order was never part of the question" -- and the first draft of
    this scanner reproduced it anyway.
    """
    if depth == 0:
        view = list(text)
    else:
        view = [_FILL] * len(text)
        for (_lt, body_start, body_end, region_depth, _parent, _real,
                _closed) in regions:
            if region_depth == depth - 1:
                view[body_start:body_end] = list(text[body_start:body_end])
                # The `(` and `)` just outside the body become the command
                # positions its first and last simple commands anchor on.
                if body_start:
                    view[body_start - 1] = " "
                if body_end < len(view):
                    view[body_end] = " "
    for (lt_idx, body_start, _body_end, region_depth, _parent, real_end,
            closed) in regions:
        if region_depth != depth:
            continue
        if closed:
            # `real_end`, never the extended end -- see `_proc_subst_regions`.
            _blank(view, lt_idx, real_end + 1)
        else:
            # No closer was recorded, so `real_end` is the extended end and
            # blanking to it erases whatever follows -- including a trailing
            # executor. Blank the `<(` DELIMITER only: that is what has to go,
            # since `(` is a COMMAND_SEPARATOR and would otherwise cut the
            # enclosing simple command in two. Everything after it stays
            # legible, which is the over-detecting direction and the one this
            # file takes everywhere else.
            _blank(view, lt_idx, body_start)
    return "".join(view)


def live_proc_subst_spans(text: str) -> list:
    """Body spans of `<(...)` process substitutions whose output is EXECUTED.

    `<(...)` runs the body and hands the caller a `/dev/fd/N` path whose
    contents are the body's OUTPUT. When the caller runs what it is given, that
    output is a script -- so `bash <(echo "<merge>")`, `sh <(printf "%s"
    "<merge>")`, `source <(...)` and `. <(...)` all run the merge, while the
    merge text never appears at a command position anywhere in the command
    line.

    `mask_inert_quotes` could not see it. `(` is a COMMAND_SEPARATOR, so
    scanning back from a quote inside the body stops at the `(` and never
    reaches the `bash` in front of it: the quoted merge was masked as prose and
    the guard returned allow (ai-config#1308). Widening the command-position
    anchor does not reach this, and neither does the live-operand rule -- the
    executor is plainly visible and it is the OPERAND that is unreachable.

    The test is CO-OCCURRENCE, not order: does the simple command owning this
    `<(` invoke something that executes its input, anywhere on it? A
    redirection may be written before the command name, so `bash <(...)` and
    `< <(...) bash` are the same command and both run the body's output. See
    `_depth_view`.

    Comments are masked first. A `)` inside a shell comment is literal to bash,
    structural to this scanner, and leaves the quote state BALANCED, so the
    quote-blind merge never runs and the body is truncated -- which is why the
    call belongs here.

    Its history is worth stating precisely, because the obvious summary is now
    wrong. Removing the call WAS a fail-open in round 5's code, where
    `sh <(#)\necho "<merge>")` ran a real merge with it gone (round 5
    finding 1). It is no longer, because `_APPROXIMATED` lists `#`: with the
    masking removed the body reads `#`, `_body_is_simple` returns False, the
    region runs to end of text, and all three variants still BLOCK (verified
    round 6 finding 6). So this call is now redundant with the whitelist for
    the case that motivated it, and is kept because the whitelist's coverage of
    `#` is itself the thing under review -- not because removing it would
    reopen that merge today. Stating the round-5 finding in the present tense
    was the error the round-5 docstring made about round 4, one revision on.

    Returns maximal `(body_start, body_end)` pairs, disjoint and sorted by
    start. Disjoint because a substitution inside an already-live body is
    skipped rather than recorded: its own enclosing command may well not be an
    executor (`bash <(cat <(echo "<merge>"))`), and the outer span already
    covers it.

    `cat <(echo "<merge>")` is deliberately NOT a span, because `cat` does not
    run its input. That is a claim about `cat`, NOT about the command line, and
    two shapes make the difference concrete. `cat <(echo "<merge>") | bash`
    merges, because SPLIT makes the pipe a segment boundary. And
    `echo "<merge>" > >(bash)` merges with no pipe at all, because only `<(` is
    collected here -- an OUTPUT substitution fed by the enclosing command's
    stdout is a script this scanner never looks at.

    Both are allowed on this branch and on `main` alike, and both are
    ai-config#3639. Naming only the pipe was wrong (ai-config#1308 review,
    finding 3): the diff's own `echo x > >(bash -c "<merge>")` BLOCK case
    catches the merge INSIDE the substitution and says nothing about the merge
    FEEDING it, which is the shape that is open.
    """
    text = mask_trailing_comments(text)
    regions = _proc_subst_regions(text)
    if not regions:
        return []

    # `covered` means live OR inside something live, and the OR is the point:
    # skipping a child because its parent runs must mark the CHILD too, or a
    # grandchild reads an unmarked parent, evaluates itself, and records a span
    # already inside a recorded one -- breaking the disjointness
    # `mask_inert_quotes` bisects on.
    #
    # There was a second array, `live`, kept for that contrast. It was written
    # and never read, so it explained a distinction the code did not make
    # (ai-config#1308 review, round 3 finding 5).
    covered = [False] * len(regions)
    spans = []
    by_depth = {}
    for index, region in enumerate(regions):
        by_depth.setdefault(region[3], []).append(index)
    deepest = max(by_depth)
    for depth in range(deepest + 1):
        at_depth = by_depth.get(depth)
        if not at_depth:
            continue
        if depth > MAX_PROC_SUBST_DEPTH:
            # Past the cap, stop asking and assume the body runs.
            #
            # `covered` is set on EVERY region here, not only the ones that
            # record a span. Marking only the recorders left the first region
            # past the cap uncovered -- its parent was covered, so it was
            # skipped without being marked -- and its own child then read an
            # uncovered parent and appended a span INSIDE the recorded
            # ancestor. That breaks the disjointness `mask_inert_quotes`
            # bisects on, and the bisect then lands on the inner span and
            # reports the quote as dead: a nest one level past the cap ran a
            # real merge and was allowed (ai-config#1308 review, finding 1).
            # The loop that did this was written as a separate tail pass, which
            # is how it came to disagree with the main loop about `covered`.
            for index in at_depth:
                parent = regions[index][4]
                if parent < 0 or not covered[parent]:
                    spans.append((regions[index][1], regions[index][2]))
                covered[index] = True
            continue
        view = _depth_view(text, regions, depth)
        separators = list(COMMAND_SEPARATOR.finditer(view))
        sep_ends = [m.end() for m in separators]
        sep_starts = [m.start() for m in separators]
        exec_ends = executes_its_input_ends(view)
        for index in at_depth:
            (lt_idx, body_start, body_end, _depth, parent, _real,
             _closed) = regions[index]
            if parent >= 0 and covered[parent]:
                covered[index] = True
                continue  # already covered by an enclosing executed body
            # bisect_RIGHT: a separator ENDING exactly at `lt_idx` bounds this
            # segment, and bisect_left would return its own index and hand back
            # the separator before it -- reaching into the previous segment for
            # an executor that never introduced this command.
            i = bisect.bisect_right(sep_ends, lt_idx)
            seg_start = sep_ends[i - 1] if i else 0
            j = bisect.bisect_left(sep_starts, body_end)
            seg_end = sep_starts[j] if j < len(sep_starts) else len(view)
            if bisect.bisect_right(exec_ends, seg_end) > bisect.bisect_left(
                    exec_ends, seg_start):
                covered[index] = True
                spans.append((body_start, body_end))
    spans.sort()
    return spans


def mask_inert_quotes(text: str, exec_subject: str | None = None) -> str:
    """Blank quoted spans that bash cannot execute, preserving length.

    `exec_subject` is the text the EXECUTOR scan reads, defaulting to `text`.
    The caller passes the pre-`mask_payloads` string, because `mask_payloads`
    blanks a flag's following word without checking that the flag belongs to a
    `gh`/`glab` invocation -- so `nsenter -t 1 -m bash -c "<merge>"` had its
    `bash` erased before this function ever saw it, and the operand was then
    masked as prose. The executor word was invisible to the check that decides
    whether it is there.

    Both strings are length-preserving, so one set of offsets indexes either.
    Separator offsets still come from `text`: a separator inside a quoted span
    is not a command separator, and reading them off the unmasked subject would
    push a segment boundary PAST a real executor -- under-detecting, which is
    the direction that hides a merge.

    Length-preserving because `offending` derives segment offsets from one
    string and slices another with them; a shorter result would misalign the
    segment reported in the refusal message.

    A single-quoted span is wholly inert. A double-quoted span is inert EXCEPT
    for `$(...)` and backtick substitutions, which bash still expands inside
    double quotes -- those are preserved verbatim, so hiding a merge in one
    still blocks.

    An executor's own quoted operand (`bash -c "<merge>"`, `eval "<merge>"`,
    `ssh host "<merge>"`) is NOT inert -- bash runs it -- so it is kept
    verbatim and only its delimiters are blanked. Blanking the delimiters
    rather than skipping the span is what leaves a whitespace command position
    in front of the operand for the permissive pass to anchor on.

    An earlier version masked every quoted span and relied on the narrow pass
    to catch these on raw text via EXEC_WRAP. That worked only while the
    wrapper before the executor was one of KEYWORD_PREFIX's six literals: any
    flag or unlisted wrapper (`sudo -u x bash -c`, `timeout 5 bash -c`,
    `xargs -0 bash -c`) broke the narrow anchor, the span was masked as prose,
    and the merge ran. The enumeration failing in a third place is what moved
    the decision here, where the safe direction is to mask LESS.
    """
    def blank(s: str) -> str:
        return "".join("\n" if c == "\n" else " " for c in s)

    if exec_subject is None or len(exec_subject) != len(text):
        exec_subject = text
    exec_ends = [m.end() for m in EXEC_AT_CMD_POS.finditer(exec_subject)]
    # Read off the SAME subject the executor scan reads, for the same reason:
    # `mask_payloads` can blank the executor word before this function sees it.
    # Both strings are length-preserving, so these offsets index either.
    proc_spans = live_proc_subst_spans(exec_subject)
    proc_starts = [start for start, _ in proc_spans]

    def live_operand_test(subject: str):
        """A `quote_start -> bool` test over one fixed subject string.

        BOTH the separator offsets and the executor offsets are computed once
        per pass, and each quote then answers by binary search. Scanning for an
        executor per quote is quadratic in the number of quoted spans -- and
        bounding the scan by the nearest separator does not fix it, because a
        long command line with no separators at all leaves every scan starting
        from zero. Measured on 2000 quoted spans: 1787ms rescanning, 305ms
        precomputed, against a hook that runs before every Bash call. Same trap
        VAR_PREFIX's bound was added for, reached by a different route.
        """
        seps = [m.end() for m in COMMAND_SEPARATOR.finditer(subject)]

        def test(quote_start: int) -> bool:
            # A quote anywhere inside an EXECUTED process-substitution body is
            # live, whatever separators sit between it and the `<(`. Bash runs
            # the body's whole output, so `bash <(echo a; echo "<merge>")`
            # merges exactly as `bash <(echo "<merge>")` does -- and the `;`
            # would otherwise reset the command position past the executor.
            k = bisect.bisect_right(proc_starts, quote_start)
            if k and quote_start < proc_spans[k - 1][1]:
                return True
            j = bisect.bisect_right(exec_ends, quote_start)
            if j == 0:
                return False
            i = bisect.bisect_left(seps, quote_start)
            seg_start = seps[i - 1] if i else 0
            return exec_ends[j - 1] >= seg_start

        return test

    live = live_operand_test(text)

    def repl_double(m: "re.Match") -> str:
        inner = m.group(0)[1:-1]
        if live(m.start()):
            return " " + inner + " "
        return " " + mask_subexpressions(inner) + " "

    text = re.sub(r"\"(?:\\.|[^\"\\])*\"", repl_double, text, flags=re.DOTALL)

    live = live_operand_test(text)

    def repl_single(m: "re.Match") -> str:
        if live(m.start()):
            return " " + m.group(0)[1:-1] + " "
        return blank(m.group(0))

    return re.sub(r"'[^']*'", repl_single, text, flags=re.DOTALL)


HEREDOC_START = re.compile(
    r"""<<-?[ \t]*(?:(['"])([A-Za-z_][A-Za-z0-9_]*)\1|([A-Za-z_][A-Za-z0-9_]*))"""
)


def _heredoc_intro(line: str):
    """The first `<<DELIM` on `line` that is a REAL heredoc introducer, or None.

    Quote context decides it, and getting this wrong fails OPEN rather than
    noisily: `echo "see <<EOF for details"` introduces no heredoc, but treating
    it as one masks every following line until a lone `EOF` that never comes --
    hiding any real merge command underneath it. Same for a `grep "<<PATTERN"`.

    `<<<` is a herestring, not a heredoc, and is skipped whole: scanning it
    character by character would otherwise match `<<` at its second `<` and read
    the rest as a delimiter.
    """
    in_single = in_double = escaped = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if escaped:
            escaped = False
        elif c == "\\" and not in_single:
            escaped = True
        elif c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "<" and not in_single and not in_double:
            if line.startswith("<<<", i):
                i += 3
                continue
            m = HEREDOC_START.match(line, i)
            if m:
                return m
        i += 1
    return None


def mask_heredocs(text: str) -> str:
    """Mask heredoc bodies, preserving length and line structure.

    A QUOTED delimiter (`<<'EOF'`, `<<"EOF"`) tells bash to perform no expansion
    at all in the body, so nothing in it can execute: it is inert text and is
    masked in full. An UNQUOTED delimiter (`<<EOF`) does expand, so only the
    literal prose is masked and `$(...)` / backtick substitutions are left live,
    exactly as mask_subexpressions does for payload flags.

    Without this a heredoc carrying prose ABOUT a merge command was matched as
    one -- which is how filing ai-config#1279 was itself blocked, by the guard
    matching its own refusal text quoted inside a `gh issue create` heredoc.

    But "inert text" is a claim about the CONSUMER, not about the heredoc. A
    body fed to a shell (`bash <<EOF`, `ssh host <<EOF`) is a script, and
    masking it hid a real merge from both later passes -- the quoted-delimiter
    form included, since `<<'EOF'` suppresses expansion and bash still runs
    what it reads. Those are left untouched; see HEREDOC_EXECUTOR.
    """
    lines = text.split("\n")
    out = list(lines)
    i = 0
    while i < len(lines):
        m = _heredoc_intro(lines[i])
        if not m:
            i += 1
            continue
        quoted = bool(m.group(2))
        delim = m.group(2) or m.group(3)
        executes = bool(HEREDOC_EXECUTOR.search(lines[i]))
        j = i + 1
        while j < len(lines) and lines[j].strip() != delim:
            if not executes:
                out[j] = " " * len(lines[j]) if quoted else mask_subexpressions(lines[j])
            j += 1
        i = j + 1
    return "\n".join(out)


def mask_payloads(text: str) -> str:
    """Mask string payload flags (--body, -m, etc.) so benign occurrences of gh pr merge inside commit/PR messages do not trigger false positives.

    Leaves command substitutions (`...` or $(...)) inside payload flags unmasked so malicious execution cannot be hidden inside payload flags.
    """
    flag_pattern = (
        r"(?:--body-file\b|--body\b|--title\b|--subject\b|--comment\b|--message\b|"
        r"--commit-title\b|--commit-message\b|--reason\b|--notes\b|--description\b|"
        r"--summary\b|-m\b|-b\b|-d\b|-t\b|-s\b|"
        r"(?:-f|-F|--field|--raw-field|--input)\s+"
        r"(?:body|title|subject|comment|message|commit_title|commit_message|reason|notes|description|text|summary)\b)"
    )
    hspace = r"[ \t]*"

    def repl_double(m):
        return m.group(1) + mask_subexpressions(m.group(2))

    def repl_single(m):
        val = m.group(2)
        return m.group(1) + "".join("\n" if c == "\n" else " " for c in val)

    def repl_unquoted(m):
        return m.group(1) + mask_subexpressions(m.group(2))

    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(\"(?:\\.|[^\"])*\")", repl_double, text, flags=re.DOTALL)
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(\'(?:\\.|[^\'])*\')", repl_single, text, flags=re.DOTALL)
    text = mask_trailing_comments(text)
    text = re.sub(rf"({flag_pattern}{hspace}=?{hspace})(`[^`]*`|\$\([^)]*\)|[^-;\s&|\n][^;\s&|\n]*)", repl_unquoted, text)
    return text


# --- Standing per-repository merge grant ---------------------------------
#
# ai-config#1352: the user granted a STANDING merge permission for PRs
# targeting this repository -- "PRs targeting the ai-config repo should have a
# standing mwc". That is not the session-scoped kind `/mwc` records, so the
# guard has to honour it with no marker file and no per-session enabling step.
#
# The grant is TARGET-scoped, which makes it strictly TIGHTER than the session
# grant it sits beside: `check_mwc_active()`'s marker lives in the CURRENT
# repository's git dir, so an active MWC authorizes `gh pr merge -R other/repo`
# run from an ai-config checkout. This one reads the repo the merge lands in.
#
# Deliberately NOT env-configurable, against the usual
# shared/coding/configurable-parameters.md default. An env-settable allowlist
# would widen a security guard from ambient state that a reader of the command
# cannot see, and `ALLOW_MERGE=1` already covers the one-off case from inside
# the command text. Adding a repository here is a one-line diff, and code
# review is the right gate for an allowlist.
STANDING_MERGE_GRANT_REPOS = frozenset({"morrison-lab/ai-config"})

# Only the GitHub PR-merge forms carry the grant, which is what the user
# granted: "PRs targeting the ai-config repo".
#   - `repos/<owner>/<name>/merges` is a direct BRANCH merge, not a PR merge --
#     it writes to the default branch with no PR, review or required check.
#   - a GraphQL `mergePullRequest` names its target by node id, so no repo is
#     derivable from the command at all.
#   - the two glab forms are GitLab; this repository is on GitHub.
# Each of those three keeps the baseline prohibition.
STANDING_GRANT_LABELS = frozenset({"gh pr merge", "gh api PR merge"})

NWO = r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+"
# `-R x/y`, `-Rx/y`, `-R=x/y`, `--repo x/y`, `--repo=x/y`. Anchored so a longer
# flag ending in `-R` is not read as one.
REPO_FLAG = re.compile(rf"(?:^|[\s;&|`()])(?:-R|--repo)\s*=?\s*({NWO})(?:\b|$)")
# `gh api .../repos/<owner>/<name>/pulls/N/merge`, with or without a leading
# slash. The trailing `/` is required so the two path components cannot run
# past the repo name.
REPO_API_PATH = re.compile(rf"""(?:^|[\s/'"])repos/({NWO})/""")

# Mutation measurements over the 243-case suite, taken 2026-08-09. Reverting a
# clause and counting the cases that then fail is the only thing that tells a
# load-bearing clause from a decorative one, so the numbers live here rather
# than in a commit message that nobody re-reads.
#
#   merge-type subset check ................................  8 cases
#   target ambiguity (`len(targets) != 1`) .................  2
#   allowlist membership ................................... 17
#   payload-masked target subject (mutated at the call site)  3
#   `-R` token anchor ......................................  1
#   the standing-grant call site ........................... 10
#
# Three clauses fail ZERO and are KEPT, per shared/principles/fail-fast.md:
# for a guard, a redundant path costs a few characters while removing one on
# suite evidence alone fails OPEN when the suite is the incomplete thing. Each
# is a reviewable simplification rather than a bug fix.
#
#   - REPO_API_PATH's trailing `/`. `/` is outside NWO's charset, so neither
#     component can over-consume with or without it.
#   - `matched_merge_labels`'s permissive pass. NOT inert: it adds a label the
#     narrow pass misses on 29 of the suite's 233 commands. In none of those 29
#     does the extra label change the outcome, because each is denied on other
#     grounds anyway -- so it is additive but not yet decisive.
#   - `standing_grant_target`'s `not labels` guard, unreachable from the one
#     call site (which only calls after a hit, so a label always re-derives).
#     It matters if anything ever calls this without pre-matching, since an
#     empty set is a subset of every set and would ALLOW.
#
# Those last two cover each other: mutating BOTH together still fails zero.
# A case separating them would need the narrow pass to see only granted labels
# while the permissive pass adds an excluded one, and GH_PROG plus `[^\n]*`
# means any segment opening with a command-position `gh` matches every gh
# pattern narrowly -- so it may not be constructible at all.


def matched_merge_labels(masked_seg: str, inert_seg: str) -> set:
    """EVERY merge interpretation these segments match, not just the first.

    `offending` stops at its first hit, which is all a BLOCK decision needs --
    one match is enough to refuse. An ALLOW decision needs the whole set,
    because the patterns are unanchored `[^\\n]*` scans over the segment and a
    single command line can satisfy several of them at once.
    """
    labels = set()
    for seg, patterns in ((masked_seg, MERGE_PATTERNS), (inert_seg, PERMISSIVE_MERGE_PATTERNS)):
        for pattern, label in patterns:
            if re.search(pattern, seg):
                labels.add(label)
    return labels


def standing_grant_target(masked_seg: str, inert_seg: str) -> bool:
    """True when this segment's merge provably lands in a granted repository.

    TWO ambiguity tests, and they are the same test on two axes: WHAT kind of
    merge this is, and WHICH repository it lands in. Either one coming back
    undetermined denies, per shared/principles/fail-fast.md -- a guard's
    discharge fires on positive evidence, and "I could not tell" is not
    evidence.

    **Merge type.** Every interpretation the segment matches must be a granted
    one. Reading the FIRST matched label instead is a bypass, because
    `_merge_patterns` tries the `pulls/N/merge` forms before the
    `repos/<o>/<n>/merges` ones and both scan the whole segment unanchored: a
    real BRANCH merge carrying a forged `pulls/1/merge` substring in an
    unmasked flag (`-H "X-Note: .../pulls/1/merge"` -- `-H` is not in
    `mask_payloads`'s list) is labelled `gh api PR merge`, and the two forged
    and real `repos/<o>/<n>/` paths then name the SAME granted repo, so the
    target test sees one target and grants a direct push to the default
    branch with no PR, review or required check. Reported and reproduced on
    ai-config#1353.

    That is precisely the reasoning the target test below already rejects,
    one axis over: the first match is not the determination.

    **Target.** Read from the COMMAND TEXT only -- an `-R`/`--repo` flag or a
    REST `repos/<owner>/<name>/` path -- never from the current working
    directory. A cwd fallback would fail OPEN on the commonest shape there is:
    `offending` splits on `&&`, so `cd ../other-repo && gh pr merge 1` reaches
    this function as a bare `gh pr merge 1` while the hook's own cwd is still
    the ai-config checkout, and the merge would be allowed into a repo nobody
    granted anything for. `hooks/require-gh-repo-flag.py` already refuses a
    `gh pr merge` with no -R, so requiring an explicit target costs nothing.

    Zero targets denies, and so do two different ones -- reading the first
    would let `gh api -X PUT repos/other/repo/pulls/1/merge -R
    morrison-lab/ai-config` through on the strength of a repo it does not
    touch.

    Targets come from the PAYLOAD-MASKED segment, so that an `-R` flag or a
    `repos/.../` path forged inside a `--body` or a trailing `#` comment
    cannot supply one.
    """
    labels = matched_merge_labels(masked_seg, inert_seg)
    if not labels or not labels <= STANDING_GRANT_LABELS:
        return False
    targets = {m.group(1).lower() for m in REPO_FLAG.finditer(masked_seg)}
    targets |= {m.group(1).lower() for m in REPO_API_PATH.finditer(masked_seg)}
    if len(targets) != 1:
        return False
    return next(iter(targets)) in STANDING_MERGE_GRANT_REPOS


def sanitize(name: str) -> str:
    """Sanitize session ID matching ai-session.sh: tr -c 'A-Za-z0-9._-' '_'"""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def is_session_alive(sess_file: Path) -> bool:
    try:
        content = sess_file.read_text(encoding="utf-8")
        sess_data = dict(line.split("=", 1) for line in content.splitlines() if "=" in line)
        pid = sess_data.get("pid")
        host = sess_data.get("host")
        local_host = platform.node()
        if pid and pid.isdigit() and int(pid) > 0:
            if not host or host.split(".")[0].lower() == local_host.split(".")[0].lower():
                try:
                    os.kill(int(pid), 0)
                    return True
                except OSError:
                    return False  # PID is dead on local host
        hb = int(sess_data.get("heartbeat") or sess_data.get("started") or 0)
        return (time.time() - hb) < 1800
    except Exception:
        pass
    return False


def get_git_common_dirs() -> list[Path]:
    dirs = []
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        ).strip()
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = (Path.cwd() / common_path).resolve()
        dirs.append(common_path)
    except Exception:
        pass

    repo_dir = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parents[1])
    try:
        common_dir = subprocess.check_output(
            ["git", "-C", repo_dir, "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = (Path(repo_dir) / common_path).resolve()
        if common_path not in dirs:
            dirs.append(common_path)
    except Exception:
        pass

    pwd_git = Path.cwd() / ".git"
    if pwd_git.is_dir() and pwd_git.resolve() not in dirs:
        dirs.append(pwd_git.resolve())

    return dirs


def resolve_session_id(payload: dict | None = None) -> str | None:
    """The id of the session this hook is running under, or None.

    The harness supplies its own session id in the hook payload, alongside
    `transcript_path`; that is the SAME id `/mwc` passes to
    `ai-session.sh enable-mwc --id`, so it is the authoritative one. Reading it
    is what makes a granted MWC visible to the guard at all: the hook process
    inherits neither AI_SESSION_ID nor CLAUDE_SESSION_ID (both measured unset on
    a machine where the grant was live), so the env-only lookup this replaces
    returned None unconditionally and no legitimate grant ever reached the guard
    (ai-config#1279, defect 1).

    Order: the payload's session fields (session_id, sessionId, sessionID,
    conversation_id, conversationId), then transcript filename stem, then
    environment forms.
    """
    if payload:
        for key in ("session_id", "sessionId", "sessionID", "conversation_id", "conversationId"):
            sid = payload.get(key)
            if isinstance(sid, str) and sid.strip():
                return sid.strip()
        tpath = payload.get("transcript_path") or payload.get("transcriptPath")
        if isinstance(tpath, str) and tpath.strip():
            stem = Path(tpath.strip()).stem
            if stem:
                return stem
    return os.environ.get("AI_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")


def check_mwc_active(payload: dict | None = None) -> bool:
    try:
        current_session = resolve_session_id(payload)
        if not current_session:
            return False

        sanitized_session = sanitize(current_session)
        for common_dir in get_git_common_dirs():
            reg_dir = common_dir / "ai-sessions"
            if not reg_dir.exists():
                continue
            mwc_file = reg_dir / f"{sanitized_session}.mwc"
            if mwc_file.exists():
                sess_file = reg_dir / f"{sanitized_session}.session"
                if sess_file.exists() and is_session_alive(sess_file):
                    return True
    except Exception:
        pass
    return False


def offending(command: str, payload: dict | None = None):
    # 1. Normalize bash backslash-newline line continuations (matching bash semantics: remove backslash and newline without inserting a space)
    norm_command = re.sub(r"\\\n", "", command)
    # 2. Mask heredoc bodies BEFORE unquote_words, which would otherwise strip
    #    the quotes off a `<<'EOF'` delimiter and make an inert body look live.
    #    Length-preserving, so later slice offsets stay aligned.
    heredoc_masked = mask_heredocs(norm_command)
    # 3. Normalize single-word token quote removal (e.g. "gh" -> gh, "pr" -> pr, "merge" -> merge, g""h -> gh)
    unquoted_command = unquote_words(heredoc_masked)
    # 4. Mask prose payloads across the entire command BEFORE splitting on separators/newlines
    masked_command = mask_payloads(unquoted_command)

    # 5. Use finditer on masked_command to derive exact character slice offsets for unquoted_command
    matches = list(SPLIT.finditer(masked_command))
    starts = [0] + [m.end() for m in matches]
    ends = [m.start() for m in matches] + [len(masked_command)]

    # 6. Two passes, both length-preserving so the same offsets slice both.
    #    Pass 1 (narrow LEAD, raw text) is what still sees a `gh api graphql`
    #    mutation, whose payload pass 2 has masked. It no longer carries the
    #    executor's quoted operand -- mask_inert_quotes keeps that live now.
    #    Pass 2 (permissive LEAD, quote-masked text) is strictly ADDITIVE: it
    #    stops asking which constructs may precede a command word -- an
    #    enumeration two review rounds showed cannot be finished -- and instead
    #    removes the text that cannot execute. See PERMISSIVE_LEAD.
    inert_command = mask_inert_quotes(masked_command, unquoted_command)

    for start, end in zip(starts, ends):
        orig_seg = unquoted_command[start:end]
        if has_allow_override(orig_seg):
            continue
        hit = None
        for seg, patterns in (
            (masked_command[start:end], MERGE_PATTERNS),
            (inert_command[start:end], PERMISSIVE_MERGE_PATTERNS),
        ):
            for pattern, label in patterns:
                if re.search(pattern, seg):
                    hit = label
                    break
            if hit is not None:
                break
        if hit is None:
            continue
        if check_mwc_active(payload):
            continue  # Allowed via active MWC session grant
        if standing_grant_target(masked_command[start:end], inert_command[start:end]):
            continue  # Allowed via the standing per-repository grant
        # Report every interpretation this segment matches, not just the
        # first: `hit` alone can name the wrong merge type when a segment
        # satisfies several patterns at once (ai-config#1362) -- a real
        # BRANCH merge carrying a forged `pulls/N/merge` substring reads as
        # "gh api PR merge", pointing whoever is debugging the refusal at
        # patterns that explain nothing.
        labels = matched_merge_labels(masked_command[start:end], inert_command[start:end])
        return labels, orig_seg.strip()
    return None


def is_mcp_merge_tool(tool_name: str) -> bool:
    if not tool_name:
        return False
    name = tool_name.lower()
    return bool(re.search(r"(?:^|__)(?:merge_pull_request|(?:enable|disable)_(?:pull_request_|pr_)?auto_merge)$", name))


def check_mcp_merge(payload: dict) -> tuple[str, str] | None:
    tool_input = payload.get("tool_input") or {}
    tool_name = payload.get("tool_name") or "mcp__github__merge_pull_request"

    if tool_input.get("allow_merge") in (1, "1", True) or tool_input.get("ALLOW_MERGE") in (1, "1", True):
        return None

    if check_mwc_active(payload):
        return None

    owner = tool_input.get("owner")
    repo = tool_input.get("repo")
    if isinstance(owner, str) and isinstance(repo, str) and owner.strip() and repo.strip():
        target = f"{owner.strip()}/{repo.strip()}".lower()
        if target in STANDING_MERGE_GRANT_REPOS:
            return None

    pull_num = tool_input.get("pull_number") or tool_input.get("pullNumber") or tool_input.get("number") or ""
    segment = f"{tool_name}(owner='{owner}', repo='{repo}', pull='{pull_num}')"
    return tool_name, segment


def _join_labels(labels) -> str:
    """Render a set of matched merge-type labels as backtick-quoted prose:
    one label alone, two joined by "and", three or more Oxford-commaed."""
    quoted = sorted(f"`{label}`" for label in labels)
    if len(quoted) == 1:
        return quoted[0]
    if len(quoted) == 2:
        return f"{quoted[0]} and {quoted[1]}"
    return ", ".join(quoted[:-1]) + f", and {quoted[-1]}"


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
        print(f"no-unauthorized-merge: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    tool_name = payload.get("tool_name") or ""
    hit = None

    if tool_name in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        inp = payload.get("tool_input") or {}
        command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""
        hit = offending(command, payload)
    elif is_mcp_merge_tool(tool_name):
        hit = check_mcp_merge(payload)
    else:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    if not hit:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    label_or_labels, segment = hit
    # check_mcp_merge (the MCP path) returns a single label string; offending
    # (the Bash path) returns the full set every interpretation matches, per
    # ai-config#1362. Normalize both to a set before rendering.
    labels = (label_or_labels if isinstance(label_or_labels, (set, frozenset))
              else {label_or_labels})
    verb = "is" if len(labels) == 1 else "are"
    reason = (
        f"MECHANISTIC PROHIBITION: {_join_labels(labels)} {verb} strictly "
        "blocked without explicit permission.\n\n"
        f"    Offending call/segment: {segment}\n\n"
        "AI agents are mechanistically forbidden from merging PRs/MRs unless explicitly instructed "
        "by the user, executing under an explicit override (e.g. ALLOW_MERGE=1 or active /mwc), or "
        "merging a PR whose target repo carries a standing grant (see STANDING_MERGE_GRANT_REPOS)."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
