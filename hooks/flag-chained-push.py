#!/usr/bin/env python3
"""PreToolUse guard: a `git push` chained with other commands, or suffixed by
a pipe or redirection.

## The incident

Lacaedemon/sparta, 2026-09-05: a single session hit this shape three times in
one sitting. Each time the command looked like an ordinary compound line --

    git add -A && git commit -m "..." && git push

    git push origin HEAD 2>&1 | tee push.log

-- and each time the whole Bash call was refused. `hooks/no-clobbering-push.py`
and the plugin's own push policy (`no-push-without-self-review.py`) both parse
the ENTIRE command text looking for a `git push`, not just the isolated push
segment a human would read out. A trailing `2>&1` hands the parser a bare `2`
sitting where a commit-ish token would sit in other shapes these guards
recognize, and a chained prefix (`git add -A && ...`) reads as part of the
same invocation the guard is reasoning about. The two guards named above are
not the only ones this can confuse -- any PreToolUse guard that scans
`tool_input.command` as one string rather than as parsed simple commands is
exposed the same way.

The result is a refusal that names only the push. Because a PreToolUse deny
rejects the WHOLE Bash call, NOTHING in the chain ran -- not the `git add`,
not the `git commit` -- but the refusal reads as if it were only about the
push, and the natural next move is to assume the prefix succeeded and retry
just the tail. `shared/workflow/check-before-pushing.md`'s
`no-commit-chained-to-push.py` sibling already names this exact
misattribution for a chained commit; this hook covers the two shapes that
sibling does not: a push chained after ANY command (not only a commit) via
`&&`/`;`/`||`, and a push suffixed by a pipe or a redirection.

## Why this warns rather than blocks

Neither shape is wrong on its own. `git fetch && git push` is an entirely
ordinary sequence, and `git push 2>&1 | tee push.log` is a reasonable way to
keep a push's output. What is actually risky is narrower than either shape by
itself: a refused push discards a chain's prefix silently, and a suffix that
looks like `2>&1` can be misread by a sibling guard's text scan. Neither of
those is something this hook can verify -- it has no way to know whether the
command will in fact be refused, or whether the author already knows to
re-check state after a refusal. So, per README's "A hook that misfires is
worse than a missing one", it only ever adds context: run the push alone, and
if a chain WAS refused, verify what actually happened rather than assuming the
prefix ran.

## The match condition

The command is split into simple commands on the top-level shell operators
`&&`, `||`, `;`, `|`, and newline (folded to `;`), after quoted-string
interiors and heredoc bodies are neutralized so an operator character inside
either cannot split anything and a `git push` mentioned inside either cannot
match. This hook does not track subshells, `case` statements, or brace
groups the way `no-clobbering-push.py` does -- it warns rather than blocks, so
an occasional miss on a deeply nested shape costs nothing a refusal would not
already have caught on its own, and the scope stays proportionate to what the
hook actually verifies (a lexical shape, not shell semantics).

A segment fires when it contains a `git push` (`git push ...` or
`git -C <dir> push ...`) and either:

  (a) the operator immediately BEFORE the segment is `&&`, `||`, or `;`
      (chained after another command), or
  (b) the operator immediately AFTER the segment is `|` (piped onward), or
  (c) the segment carries a redirection token after the `push` match --
      `>`, `>>`, `&>`, `&>>`, or an fd-duplication form like `2>&1` --
      which is the shape that reads as a stray digit to a whole-string parser.

A bare `&` (backgrounding) is deliberately NOT one of the split operators.
`cmd1 & git push` carries the same "the prefix may not have run" risk as the
`;`/`&&`/`||` shapes above, but backgrounding a command ahead of a push is
rare enough in practice that adding it was left for a later pass rather than
chased here; a miss on that shape costs nothing a refusal would not already
surface on its own, the same argument this hook already makes for subshells
and `case` statements.

Fails open on any parse trouble.
"""
from __future__ import annotations

import json
import os
import re
import sys

HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")

# A backslash immediately followed by a newline is a line CONTINUATION, not a
# command separator -- `git \` + newline + `push origin HEAD` is one logical
# `git push`. Left unhandled, the newline both split the command into two
# segments (so `git` and `push` never shared one) and broke `GIT_PUSH_RE`'s
# `\s+` match (the literal backslash between "git " and the newline is not
# whitespace) -- a silent miss on the exact incident shape this hook exists
# to catch, measured on the shape `git add -A && git commit -m "x" && git \`
# / `  push origin HEAD` (2026-09-05 review).
CONTINUATION_RE = re.compile(r"\\\r?\n")

# Top-level shell operators this hook splits on. `||` and `&&` are listed
# before the single-character alternatives so the regex engine consumes both
# characters of a compound operator rather than stopping at the first.
OPS = re.compile(r"\|\||&&|[;|\n]")

# `git push`, or `git -C <dir> push`. Deliberately narrower than
# `no-clobbering-push.py`'s full option scan: this hook only needs to find
# the segment to classify, not resolve its destination, so a rarer spelling
# (`git --git-dir=... push`, several stacked global options) is left unmatched
# rather than chased -- a miss there costs nothing a refusal would not already
# surface on its own.
#
# ANCHORED at the segment's own leading command (via `LEAD_RE` in
# `evaluate`), not searched for anywhere in the segment. A segment is
# already one simple command by construction of `_segments`, so "git push"
# appearing later in it is necessarily an ARGUMENT to that command, not a
# second one -- `find . -exec git push {} \;` passes the two words "git"
# and "push" to `find` as `-exec` arguments, and a `.search()` over the
# whole segment could not tell that from a genuine invocation (Copilot
# review finding on this hook's own PR, 2026-09-05).
GIT_PUSH_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?push\b")

# Skipped before `GIT_PUSH_RE` is anchored: leading whitespace, any number
# of env assignments (`VAR=val `), and a handful of wrapper commands that
# still leave "git push" as the command actually run. Each wrapper may take
# its OWN flags or arguments first (`sudo -H`, `nice -n5`, `timeout 30`,
# `env -i VAR=1`), so a wrapper is followed by any run of tokens that is not
# itself "git" -- an anchored `.match()` that stopped right after the bare
# wrapper word regressed `sudo -H git push` (a real, common shape) to a
# false negative, since `lead_end` landed on `-H` and `GIT_PUSH_RE` was
# required to start exactly there (measured 2026-09-05 review). Deliberately
# smaller than `no-clobbering-push.py`'s `LEAD_WORDS` -- this hook only
# needs enough to avoid a false negative on common cases, not a full
# simple-command grammar.
LEAD_RE = re.compile(
    r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:(?:sudo|exec|env|command|time|nohup|nice|timeout)\s+"
    r"(?:(?!git\b)\S+\s+)*)*"
)

# A redirection suffix: plain or doubled `>`, its fd-duplication form
# (`2>&1`, `>&2`), or the bash `&>`/`&>>` shorthand. This is the shape that
# reads as a stray digit or ampersand to a guard scanning the whole command
# text for tokens that look like a commit-ish value.
REDIRECT_RE = re.compile(r"&>{1,2}|\d*>{1,2}&?\d*")


def _quote_spans(command: str):
    """Yield `(start, end, closed)` for every single- or double-quoted span in
    `command` -- `start`/`end` exclusive and quote characters included,
    `closed` False when the string ends before a matching quote is found.

    The ONE place quoting is understood, shared by `_quoted_ranges` (which
    only needs the ranges, to keep heredoc detection out of them) and
    `_mask_quotes` (which needs to know whether a span actually closed, to
    mask only its interior).

    A quote character preceded by an escaping backslash OUTSIDE any quote is
    a literal character, not an opener -- real shell syntax escapes the very
    next character that way. Both this scanner's predecessor loops tested
    `ch in "'\\\""` with no such check, so `echo \\" && git push` read the
    escaped `"` as opening a genuinely unterminated quoted span and masked
    everything after it to the end of the string, silently swallowing the
    real chained `git push` (measured 2026-09-05 review, fourth pass) -- the
    same over-consuming failure the heredoc fixes above already went
    through, arriving from the opposite direction (a real escape mistaken
    for punctuation, rather than fabricated punctuation mistaken for real).

    Escaping INSIDE a double-quoted span still applies only there: a
    double-quoted backslash escapes the next character (so a quote character
    it precedes does not close the string); a single-quoted one does not.
    """
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        if ch == "\\" and i + 1 < n:
            i += 2  # an escaped literal outside any quote; never an opener
            continue
        if ch in "'\"":
            quote = ch
            start = i
            i += 1
            while i < n and command[i] != quote:
                if quote == '"' and command[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                i += 1
            closed = i < n
            end = i + 1 if closed else i
            yield start, end, closed
            i = end
        else:
            i += 1


def _quoted_ranges(command: str) -> list[tuple[int, int]]:
    """`(start, end)` ranges (exclusive, quote characters included) covering
    every single- or double-quoted span in `command`.

    Used to keep `_mask_heredocs` from treating a literal `<<` inside an
    ordinary quoted string as a real heredoc introducer -- a commit message
    quoting a diff marker or a shift-left operator (`git commit -m "see <<
    3 retries"`) is not a heredoc, and `_mask_heredocs` used to run before
    any quote awareness existed, so it found the fabricated tag, found no
    real terminator for it, and masked everything to the end of the string
    -- silently swallowing a real chained `git push` after it (measured
    2026-09-05 review, third pass).
    """
    return [(start, end) for start, end, _closed in _quote_spans(command)]


def _next_heredoc_start(command: str, pos: int, quoted: list[tuple[int, int]]):
    """The next `HEREDOC_START` match at or after `pos` whose `<<` does NOT
    fall inside one of `quoted`'s ranges, or `None`."""
    while True:
        m = HEREDOC_START.search(command, pos)
        if not m:
            return None
        if any(s <= m.start() < e for s, e in quoted):
            pos = m.end()
            continue
        return m


def _mask_heredocs(command: str) -> str:
    """`command` with each heredoc BODY (and its terminator line) replaced by
    `x`, same length. The introducing line -- `<<TAG`, and everything on that
    same physical line before and after it -- is left untouched, because that
    text can carry a real chained command: `cat <<'EOF' && git push` chains a
    genuine `git push` on the very line that opens the heredoc, and the body
    itself does not begin until the NEXT line.

    A single regex spanning tag-to-terminator (the earlier approach) cannot
    tell those two apart: `.*?` between the tag and the terminator matches
    lazily across the whole span, so it swallows the same-line trailing text
    along with the real body -- masking away exactly the `&& git push` this
    hook exists to catch (measured 2026-09-05 review). Scanning line-by-line
    is what keeps the same-line text visible while still masking the body.

    A `<<-` heredoc's terminator line may be indented; a plain `<<` heredoc's
    may not (POSIX). An unterminated heredoc is masked to the end of the
    string, matching this hook's general fail-toward-silence posture for
    malformed input -- nothing downstream should trust content that never
    reaches a real terminator.

    Several heredocs can be introduced on ONE line (`cmd <<A <<B`), and the
    shell delivers their bodies in order immediately after that line, before
    the command runs at all. Advancing `pos` to the first tag's own
    terminator and resuming the outer search from there missed every later
    tag on the same intro line -- their `<<TAG` tokens sit BEFORE that
    position, so a forward-only search past the first body's terminator
    never finds them, and their bodies are never masked (measured
    2026-09-05 review, second pass). All tags sharing one intro line are
    therefore collected up front, and their bodies are masked in order
    before the outer loop resumes.

    Every search below goes through `_next_heredoc_start`, which skips a
    `<<` that falls inside an ordinary quoted string -- `HEREDOC_START` has
    no quoting awareness of its own, so a commit message like
    `git commit -m "see << 3 retries"` was read as a genuine (and
    unterminated) heredoc, and masking ran to the end of the string,
    swallowing a real chained `git push` after it (measured 2026-09-05
    review, third pass).
    """
    quoted = _quoted_ranges(command)
    out = list(command)
    pos, n = 0, len(command)
    while True:
        m = _next_heredoc_start(command, pos, quoted)
        if not m:
            break
        line_end = command.find("\n", m.end())
        if line_end == -1:
            break  # no body possible for any heredoc on this line

        tags = [m]
        search_from = m.end()
        while True:
            nxt = _next_heredoc_start(command, search_from, quoted)
            if nxt is None or nxt.start() >= line_end:
                break
            tags.append(nxt)
            search_from = nxt.end()

        body_start = line_end + 1
        for tag_match in tags:
            tag = tag_match.group(2)
            strip_indent = tag_match.group(0).startswith("<<-")
            pattern = r"^[ \t]*" if strip_indent else r"^"
            terminator = re.compile(pattern + re.escape(tag) + r"$", re.M)
            term_match = terminator.search(command, body_start)
            mask_end = term_match.end() if term_match else n
            for i in range(body_start, mask_end):
                out[i] = "x"
            if term_match is None:
                body_start = n
                break
            body_start = (mask_end + 1 if mask_end < n
                          and command[mask_end] == "\n" else mask_end)
        pos = body_start
    return "".join(out)


def _mask(command: str) -> str:
    """`command` with heredoc bodies masked, line continuations joined, and
    quoted-string interiors replaced by `x` -- all same length, so an
    operator inside any of those cannot split a segment and a `git push`
    mentioned inside any of those cannot match.

    Heredocs are masked FIRST, on the pristine command, so `_mask_heredocs`'s
    terminator search sees the heredoc's REAL newlines. Continuation-joining
    a QUOTED heredoc tag's body is wrong -- unlike an unquoted tag, a quoted
    one (`<<'EOF'`) suppresses parameter/command expansion but NOT the
    literal content, so a body line ending in a genuine trailing backslash
    keeps its own newline. Joining first erased that newline, the
    terminator's `^TAG$` no longer matched at any line start, the heredoc
    read as unterminated, and masking ran to the end of the string --
    swallowing a real chained command after it (measured 2026-09-05 review,
    second pass). Masking heredocs before joining keeps every heredoc's
    terminator search anchored to real line boundaries; a continuation
    outside any heredoc is untouched by heredoc-masking and is still joined
    correctly on the next line, and one INSIDE a masked body is moot -- that
    span is already all `x` by the time continuation-joining runs.

    Quotes are masked next, via the same `_quote_spans` scanner
    `_quoted_ranges` uses, so a quote appearing only inside a heredoc body
    never enters the quote scan and an escaped quote outside any real
    quoting is never mistaken for one (see `_quote_spans`'s docstring).

    A backslash-escaped OPERATOR character (`;`, `&`, `|`, `>`) is masked
    last, and only outside quotes -- by this point everything inside a
    quote is already `x`, so this pass needs no quote-awareness of its own.
    `find . -exec rm {} \\;` escapes that `;` precisely so the SHELL leaves
    it alone (it is `find`'s own argument terminator, not a command
    separator); with no masking here, the raw `;` still split the command
    for `OPS`, and a `git push` sitting inside such a `find -exec` clause
    could then be misattributed as chained after a genuine operator sitting
    nearby (Copilot review finding on this hook's own PR, 2026-09-05).
    """
    command = _mask_heredocs(command)
    command = CONTINUATION_RE.sub(lambda m: " " * len(m.group(0)), command)
    command = _mask_quotes(command)
    return _mask_escaped_ops(command)


def _mask_quotes(command: str) -> str:
    """`command` with every quoted span's INTERIOR replaced by `x`, same
    length -- the quote characters themselves, and an escaped quote outside
    any real quoting, are left untouched.
    """
    out = list(command)
    for start, end, closed in _quote_spans(command):
        interior_end = end - 1 if closed else end
        for i in range(start + 1, interior_end):
            out[i] = "x"
    return "".join(out)


# The operator characters `OPS`/`REDIRECT_RE` care about, other than the
# newline (already handled by `CONTINUATION_RE` before this runs).
ESCAPABLE_OPS = set(";&|>")


def _mask_escaped_ops(command: str) -> str:
    """`command` with a backslash immediately followed by one of
    `ESCAPABLE_OPS` replaced by `xx`, same length.

    Runs LAST, after quote masking, so a `\\;` that happened to sit inside a
    quoted string is already `x` by the time this scans -- no quote
    awareness is needed here. A backslash escaping an ORDINARY character
    (`\\p`, a POSIX no-op) is left untouched: masking every escaped
    character rather than only the operator-relevant ones would erase a
    `git push` written as `\\push`, trading one false negative for another;
    the operator characters are the only ones `OPS`/`REDIRECT_RE` can
    misread.
    """
    out = list(command)
    i, n = 0, len(command)
    while i < n - 1:
        if command[i] == "\\" and command[i + 1] in ESCAPABLE_OPS:
            out[i] = "x"
            out[i + 1] = "x"
            i += 2
            continue
        i += 1
    return "".join(out)


def _segments(command: str):
    """`(preceding op or None, segment text, masked segment text, following op
    or None)` quadruples.

    Operators are found in the MASKED command (so one inside a quote or a
    heredoc body cannot split anything), and both the segment text (sliced
    from the ORIGINAL command) and its masked counterpart (sliced from the
    single command-level mask) are returned at the same offsets, since
    masking preserves length.

    The masked text is sliced from the ONE mask computed here, rather than
    recomputed per segment, deliberately: a heredoc's own body is masked as a
    span, but the NEWLINE ending its `<<TAG` introducer line is not part of
    that span (real text can follow the tag on that same line -- see
    `_mask_heredocs`), so `OPS` still splits on it and the body becomes its
    own segment. Re-masking that segment IN ISOLATION would find no `<<TAG`
    inside it and see only ordinary text, letting a `git push` sitting inside
    a heredoc body match once the body was carved out into its own segment
    (measured 2026-09-05 review, on `cat <<'EOF'` immediately followed by a
    body line containing `git push`). Slicing from the single whole-command
    mask instead means that body is already `x`-filled at the point it
    becomes a segment, wherever the split happened to land.

    A literal newline is folded to `;` for the purpose named here -- a script
    written one command per line chains its commands exactly the way `;`
    does.
    """
    masked = _mask(command)
    matches = [(m.start(), m.end(), ";" if m.group(0) == "\n" else m.group(0))
               for m in OPS.finditer(masked)]
    starts = [0] + [e for _, e, _ in matches]
    ends = [s for s, _, _ in matches] + [len(command)]
    segments = []
    for idx, (s, e) in enumerate(zip(starts, ends)):
        preceding = matches[idx - 1][2] if idx > 0 else None
        following = matches[idx][2] if idx < len(matches) else None
        segments.append((preceding, command[s:e], masked[s:e], following))
    return segments


def evaluate(command: str) -> str | None:
    """Warning text for the first chained/suffixed `git push` found, else
    `None`."""
    for preceding, text, masked_text, following in _segments(command):
        lead_end = LEAD_RE.match(masked_text).end()
        match = GIT_PUSH_RE.match(masked_text, lead_end)
        if not match:
            continue

        chained_before = preceding in ("&&", "||", ";")
        piped_after = following == "|"
        redirected = bool(REDIRECT_RE.search(masked_text[match.end():]))
        if not (chained_before or piped_after or redirected):
            continue

        segment = text.strip()
        reasons = []
        if chained_before:
            reasons.append(
                f"chained after another command with `{preceding}`"
            )
        if piped_after:
            reasons.append("piped onward with `|`")
        if redirected:
            reasons.append(
                "carries a redirection suffix (`>`, `>>`, or an fd form like "
                "`2>&1`)"
            )

        return (
            "This `git push` is " + " and ".join(reasons) + ":\n\n"
            f"    {segment}\n\n"
            "`hooks/no-clobbering-push.py` and the plugin's own "
            "`no-push-without-self-review.py` push policy both parse the "
            "WHOLE command text looking for a push, not just this segment in "
            "isolation. A trailing `2>&1` hands either parser a bare `2` "
            "sitting where a commit-ish token would sit in other shapes they "
            "recognize, and a chained prefix reads as part of the same "
            "invocation being reasoned about -- so a chain can be refused for "
            "a reason that has nothing to do with the commands before the "
            "push.\n\n"
            "A PreToolUse deny rejects the WHOLE Bash call. If this chain "
            "gets refused, nothing in it ran -- not the commands before the "
            "push either -- so do not assume the prefix succeeded and retry "
            "only the tail: re-check state (`git status`, `git log`) before "
            "deciding what actually happened.\n\n"
            "Run the push alone, in its own Bash call, with nothing chained "
            "before it and no pipe or redirect suffix after it -- "
            "`shared/workflow/check-before-pushing.md`."
        )
    return None


def _read_payload() -> dict:
    try:
        payload = json.load(sys.stdin)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def main() -> int:
    payload = _read_payload()
    if payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
    ):
        return 0
    inp = payload.get("tool_input") or {}
    command = (
        inp.get("command") or inp.get("CommandLine") or inp.get("cmd")
        or inp.get("script")
    )
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        warning = evaluate(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-chained-push: could not evaluate command ({exc})",
              file=sys.stderr)
        return 0
    if not warning:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": warning,
        },
    }
    # The `PreToolUse` branch of Antigravity's adapter prints
    # `additionalContext` itself AND separately prints every collected
    # `systemMessage`, so a payload carrying both surfaces the warning twice
    # there -- see README's "warn-only hook" census.
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            "This `git push` is chained with another command, or suffixed "
            "by a pipe/redirect -- run it alone in its own call."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
