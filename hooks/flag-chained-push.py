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
GIT_PUSH_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?push\b")

# A redirection suffix: plain or doubled `>`, its fd-duplication form
# (`2>&1`, `>&2`), or the bash `&>`/`&>>` shorthand. This is the shape that
# reads as a stray digit or ampersand to a guard scanning the whole command
# text for tokens that look like a commit-ish value.
REDIRECT_RE = re.compile(r"&>{1,2}|\d*>{1,2}&?\d*")


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
    """
    out = list(command)
    pos, n = 0, len(command)
    while True:
        m = HEREDOC_START.search(command, pos)
        if not m:
            break
        line_end = command.find("\n", m.end())
        if line_end == -1:
            break  # no body possible for any heredoc on this line

        tags = [m]
        search_from = m.end()
        while True:
            nxt = HEREDOC_START.search(command, search_from)
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

    Quotes are masked last, so a quote appearing only inside a heredoc body
    never enters the quote scan below.
    """
    command = _mask_heredocs(command)
    command = CONTINUATION_RE.sub(lambda m: " " * len(m.group(0)), command)
    out = []
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        if ch in "'\"":
            quote = ch
            out.append(ch)
            i += 1
            while i < n and command[i] != quote:
                if quote == '"' and command[i] == "\\" and i + 1 < n:
                    out.append("xx")
                    i += 2
                    continue
                out.append("x")
                i += 1
            if i < n:
                out.append(command[i])
                i += 1
        else:
            out.append(ch)
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
        match = GIT_PUSH_RE.search(masked_text)
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
