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

Fails open on any parse trouble.
"""
from __future__ import annotations

import json
import os
import re
import sys

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

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


def _mask(command: str) -> str:
    """`command` with heredoc bodies and quoted-string interiors replaced by
    `x`, same length, so an operator inside either cannot split a segment and
    a `git push` mentioned inside either cannot match.

    Heredocs are masked first, on the raw command, so a quote appearing only
    inside a heredoc body never enters the quote scan below.
    """
    command = RX_HEREDOC.sub(lambda m: "x" * len(m.group(0)), command)
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
    """`(preceding op or None, segment text, following op or None)` triples.

    Operators are found in the MASKED command (so one inside a quote or a
    heredoc body cannot split anything), and segment text is sliced from the
    ORIGINAL command at the same offsets, since masking preserves length. A
    literal newline is folded to `;` for the purpose named here -- a script
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
        segments.append((preceding, command[s:e], following))
    return segments


def evaluate(command: str) -> str | None:
    """Warning text for the first chained/suffixed `git push` found, else
    `None`."""
    for preceding, text, following in _segments(command):
        masked_text = _mask(text)
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
