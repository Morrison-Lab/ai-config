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
HEREDOC_EXECUTOR = EXEC_AT_CMD_POS
# The quote-masking counterpart. A quoted span is inert only when nothing
# before it in the same simple command can run it; `bash -c "<merge>"`,
# `eval "<merge>"` and `ssh host "<merge>"` are the executor's own operand and
# are LIVE. Same asymmetry as the heredoc anchor above: over-detecting means
# declining to mask, which costs a scan, while under-detecting hides a merge.
EXEC_BEFORE_QUOTE = EXEC_AT_CMD_POS
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
