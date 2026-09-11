#!/usr/bin/env python3
"""PreToolUse reminder: stderr is suppressed on a command whose output is read.

## The bug

A command whose stderr goes to `/dev/null` and whose stdout is then consumed
-- piped into a parser, captured with a command substitution, or redirected to
a file the same session reads back -- converts a diagnosable failure into an
empty or malformed result that is indistinguishable from a legitimately empty
one.

Measured 2026-09-02 (ai-config#2998), mirroring a repo to a GitLab remote:

    glab api "projects/.../pipelines/$p/jobs" > "$SP/j.json" 2>/dev/null

The file came back empty, the parse failed, and the emptiness was diagnosed as
a sandbox/redirect problem. The command was restructured to pipe rather than
redirect, and that conclusion was reported. It was wrong. The answer was in the
stderr that had been discarded -- `dial tcp: lookup ...: no such host`, a
dropped VPN -- and the redirect was never involved.

## Why a guard rather than another prose site

`shared/principles/fail-fast.md` already names the family: a bare `except:`, a
`tryCatch` returning NULL, a shell `|| true`. Reading that at load time does not
reach the moment this breaks, because `2>/dev/null` is typed as NOISE REDUCTION
-- `gh` and `glab` print progress and warnings that clutter a parse -- so at
composition time it reads as tidiness rather than as a decision to discard
failures.

It is also self-obscuring in a specific way. The empty result invites a
plausible alternative explanation, and every explanation available is about the
parts of the command still visible: the redirect, the pipe, the quoting. The
diagnosis never lands on the missing stderr, because there is nothing there to
look at.

## Why it warns rather than blocks

`2>/dev/null` is legitimate on a probe whose exit status is the whole point
(`command -v x 2>/dev/null`), and legitimate whenever stdout is discarded too
(`cmd >/dev/null 2>&1 && echo OK`). This guard already stays silent on both of
those, but it cannot tell noise reduction from error hiding in the cases that
remain, and it should not try -- it only has to make the tradeoff visible at the
moment it is made. So it emits `hookSpecificOutput.additionalContext` (with a
matching `systemMessage` outside Antigravity, whose adapter surfaces the two
separately and would otherwise double-print) and never a `permissionDecision`,
whose absence defers to the normal permission flow.

## What it anchors on

Redirection structure, not vocabulary. This corpus quotes shell snippets
constantly -- including inside the fragments describing this bug -- so
single-quoted spans, double-quoted spans, `#` comments and heredoc bodies are
blanked before anything is matched, leaving command-substitution interiors
intact because a capture is one of the consumption shapes this exists to catch.

Per pipeline STAGE, not per command: `cmd | jq . 2>/dev/null` suppresses `jq`'s
stderr while `jq`'s own stdout goes to the terminal, so nothing is parsed blind
and no warning is due.

Fails OPEN on any parse trouble, same as every guard here.

Sibling: `warn-status-read-after-pipe.py` covers the same family -- a shell
construct that destroys a failure signal -- for a different construct.

## Known approximations

The redirect model here is a set of regexes, not a bash parser, and it is
approximate on purpose. Six review rounds each found one more gap, and the
shape of that recurrence is the point: bash's redirect grammar has a case
space this approach cannot exhaust, so a new gap is expected rather than a
defect in the design.

What that costs is bounded. The hook warns, never blocks, fails open on any
parse trouble, and its message tells the reader to re-run without the
suppression before trusting an empty result -- so a spurious warning is an
ignorable nag and a missed one leaves the reader exactly where they were.

Known gaps, not exhaustive:

- A `case` nested inside a command substitution does not fire. Under-warn.
- `exec` redirects apply to the rest of the shell rather than to one command,
  and are not modelled at all.
- `/dev/stdout`, `/dev/stderr` and `/proc/self/fd/N` are treated as ordinary
  file targets rather than as the streams they name.
- A redirect target that is a variable or a substitution is recognised as a
  target, but its VALUE is not, so a variable holding `/dev/null` reads as a
  real file. Over-warn.
- `exec` aside, every gap found so far has been in which redirect SHAPES are
  recognised rather than in the stage model, and each was found by an
  adversarial reader rather than by a user hitting it.

When a new gap is reported, fix the general shape rather than the literal
command: the `>|` operator reached this file twice, once as a file target and
once as a discard, because the first fix closed the instance and not the class.
"""
import json
import os
import re
import sys

# The heredoc OPENER is `scripts/lib/shellcmd.py`'s own `RX_HEREDOC_OPEN`,
# imported rather than restated. Its delimiter class is an ordinary shell word
# rather than a `\w+` run, so `END-MSG` and `EOF.1` are recognized, and its
# `(?<!<)` lookbehind tells a heredoc from a here-string, whose second `<`
# would otherwise open a body that swallows the rest of the command. Group 3
# is the delimiter. `hooks/warn-heredoc-doubled-backslash.py` imports it the
# same way, with the same fail-open-and-say-so convention on a broken install.
try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import RX_HEREDOC_OPEN
except Exception as _exc:  # broken install; fail open and say so
    print(f"warn-stderr-suppressed-then-parsed: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); not evaluating",
          file=sys.stderr)
    RX_HEREDOC_OPEN = None

MAXLEN = 90

# --- redirection shapes -------------------------------------------------
#
# Each pattern runs against ONE pipeline stage of already-masked text, so a
# `>` inside a quoted string or a heredoc body cannot reach them.

# Both streams to /dev/null: `&>/dev/null`, `&>>/dev/null`, `>&/dev/null`.
# This is stderr suppression AND stdout discard at once, so it is matched by
# both predicates below and the discard wins -- nothing is parsed blind.
RX_MERGE_NULL = re.compile(r"(?:&>>?|>&)\s*/dev/null(?![^\s;|&<>()])")

# stderr alone to /dev/null. The lookbehind keeps `12>/dev/null` (fd 12) from
# being read as the `2>` form.
RX_STDERR_NULL = re.compile(r"(?<![0-9<>&])2>>?\s*/dev/null(?![^\s;|&<>()])")

# stderr closed outright.
RX_STDERR_CLOSED = re.compile(r"(?<![0-9<>&])2>&-")

# stderr reclaimed by a LATER redirect. The shell applies redirects left to
# right, so `cmd 2>/dev/null 2>err.log` captures stderr to the file and
# suppresses nothing -- warning there is the over-warning this hook rules out.
# `2>&-` is excluded from the file form since closing is itself a suppression.
RX_STDERR_TO_FILE = re.compile(
    r"(?<![0-9<>&])2>>?\s*(?!/dev/null(?![^\s;|&<>()]))(?![&-])\S")
RX_STDERR_MERGED = re.compile(r"(?<![0-9<>&])2>&[0-9]+")

# `&>file` / `>&file` with a NON-null target. Both streams go to the file, so
# this is a stdout file target and an stderr reclaim at once. Only the
# /dev/null spelling was recognised before, which let a later `&>file.log`
# fail to reclaim an earlier `2>/dev/null` and produced a false positive.
RX_MERGE_FILE = re.compile(
    r"(?<![0-9<>&])(?:&>>?|>&)\s*(?!/dev/null(?![^\s;|&<>()]))"
    r"(?![&-])(?![0-9]+-?(?![^\s;|&<>()]))([^\s;|&<>()]+)")

# Every stdout redirect operator, including `>|`, which overrides noclobber and
# is ONE token. Defined once: the previous round added it to the file-target
# pattern only, so the discard pattern still missed it and a fully discarded
# stage read as piped.
_OUT_OP = r"(?:>>?\||>>?)"

# stdout to /dev/null, with or without its explicit `1` fd. The lookbehind
# excludes `2>` (preceded by a digit) and `&>` (preceded by `&`), each of
# which its own pattern above already owns.
RX_STDOUT_NULL = re.compile(
    r"(?<![0-9<>&])1?" + _OUT_OP + r"\s*/dev/null(?![^\s;|&<>()])")

# stdout to a FILE -- anything that is not /dev/null and not an `&fd`
# duplication. `>&2` and `2>&1` are excluded by the `(?!&)`, so sending stdout
# to stderr is not mistaken for a file the session reads back.
RX_STDOUT_FILE = re.compile(
    r"(?<![0-9<>&])1?" + _OUT_OP + r"\s*(?!/dev/null(?![^\s;|&<>()]))"
    r"(?!&)([^\s;|&<>()]+)")


# What a blanked-out substitution leaves behind in the OUTER region. A space
# erases the token entirely, and a bare `> $(mktemp)` then left nothing after
# the operator for the redirect patterns to match, so it scanned clean while
# a quoted or prefixed target of the same shape fired. This stands in for the
# word without carrying any of its text; the reported filename is recovered
# from the original command, so the mark is never shown.
SUBSTITUTION_MARK = "\x01"


def _blank(out, start, end, fill=" "):
    """Fill `out[start:end]`, keeping newlines so line structure holds."""
    for index in range(start, min(end, len(out))):
        if out[index] != "\n":
            out[index] = fill


def _mask_heredocs(command):
    """Blank every heredoc BODY with spaces, preserving length and newlines.

    Length preservation is what lets the report slice the ORIGINAL command by
    an index derived from the masked copy.

    The terminator must be the whole line modulo horizontal whitespace, so
    `EOF # comment` is not mistaken for it. Tolerating any leading spaces or
    tabs there is the same approximation
    `warn-heredoc-doubled-backslash.py` documents: bash
    allows no indent for `<<` and tabs only for `<<-`, so a body line that
    merely looks like an indented delimiter can end the mask early. Ending it
    early only un-blanks text, which can add a false positive here rather than
    hide a real one, and a warn-only guard is the right place for that
    direction of error.
    """
    if RX_HEREDOC_OPEN is None:
        return command
    out = list(command)
    pos = 0
    while True:
        match = RX_HEREDOC_OPEN.search(command, pos)
        if match is None:
            return "".join(out)
        line_end = command.find("\n", match.end())
        if line_end == -1:
            return "".join(out)
        term = re.compile(
            r"^[ \t]*" + re.escape(match.group(3)) + r"[ \t]*(?=\n|\Z)", re.M)
        hit = term.search(command, line_end + 1)
        body_end = len(command) if hit is None else hit.start()
        _blank(out, line_end + 1, body_end)
        if hit is None:
            return "".join(out)
        pos = hit.end()


def _close_substitution(out, spans, stack, index):
    """Record the substitution `stack` is holding as closing at `index`."""
    start, saved, _kind = stack.pop()
    spans.append((start, index))
    _blank(out, index, index + 1)
    return saved


def _enclosing_quote(stack):
    """Return the quote state a closing quoted span should return to.

    A backtick substitution is its own quote state, so a `"` span opened and
    closed inside one must restore it rather than fall to None -- otherwise the
    substitution's own closing backtick reads as opening a second one.
    """
    if stack and stack[-1][2] == "`":
        return "`"
    return None


def _mask(command):
    """Return (masked_text, substitution_spans).

    Blanks single-quoted spans, double-quoted spans, `#` comments and heredoc
    bodies, and returns the interior span of every `$(...)` and backtick
    command substitution -- INCLUDING ones written inside double quotes, since
    `"$(cmd 2>/dev/null)"` is exactly the capture shape this guard exists for.

    Every replacement is one space per character, so an index into the result
    addresses the same character in the original.
    """
    text = _mask_heredocs(command)
    out = list(text)
    spans = []
    stack = []          # (interior_start, saved_quote) per open substitution
    quote = None        # None, "'", '"', '`' or '#' (a comment run)
    index, size = 0, len(text)
    while index < size:
        char = text[index]
        if quote == "'":
            if char == "'":
                quote = _enclosing_quote(stack)
            else:
                _blank(out, index, index + 1)
            index += 1
            continue
        if quote == "#":
            if char == "\n":
                quote = None
            else:
                _blank(out, index, index + 1)
            index += 1
            continue
        # A backslash escapes inside a backtick substitution as it does at top
        # level and inside double quotes; only single quotes take it literally.
        if char == "\\" and index + 1 < size and quote in (None, '"', "`"):
            index += 2
            continue
        if char == "$" and index + 1 < size and text[index + 1] == "(":
            stack.append((index + 2, quote, "("))
            _blank(out, index, index + 2)
            quote = None
            index += 2
            continue
        if char == "`":
            if quote == "`" and stack:
                quote = _close_substitution(out, spans, stack, index)
            else:
                stack.append((index + 1, quote, "`"))
                _blank(out, index, index + 1)
                quote = "`"
            index += 1
            continue
        if char == ")" and quote is None and stack:
            quote = _close_substitution(out, spans, stack, index)
            index += 1
            continue
        if quote == '"':
            if char == '"':
                quote = _enclosing_quote(stack)
            else:
                _blank(out, index, index + 1)
            index += 1
            continue
        if char == "'":
            quote = "'"
        elif char == '"':
            quote = '"'
        elif char == "#" and (index == 0 or text[index - 1] in " \t\n;&|("):
            quote = "#"
            _blank(out, index, index + 1)
        index += 1
    for start, _saved, _kind in stack:      # unterminated substitution: take the rest
        spans.append((start, size))
    return "".join(out), spans


def _regions(masked, spans):
    """[(start, region_text, captured), ...] -- one region per shell context.

    The whole command is one region with every substitution interior blanked
    out, so segmentation cannot run across a substitution boundary; each
    substitution interior is a further region, marked `captured` because its
    last stage's stdout goes to the caller rather than to a terminal.
    """
    contexts = [(0, len(masked), False)]
    contexts.extend((start, end, True) for start, end in spans)
    out = []
    for start, end, captured in contexts:
        local = list(masked[start:end])
        for inner_start, inner_end in spans:
            inside = inner_start >= start and inner_end <= end
            if inside and (inner_start, inner_end) != (start, end):
                _blank(local, inner_start - start, inner_end - start,
                       fill=SUBSTITUTION_MARK)
        out.append((start, "".join(local), captured))
    return out


# Separators that end a simple command. A single `|` is deliberately absent: a
# pipe is what makes the stage before it a consumed one, so it has to stay
# inside the segment and is split out separately. The `&` alternative excludes
# `2>&1` and `>&-` by lookbehind, and `&&` plus the `&>` / `&>>` shorthand by
# lookahead. Without the `>` in that lookahead the shorthand splits its own
# command in two, so its suppression never shares a stage with the redirect
# that consumes stdout, and nothing ever fires.
RX_SEGMENT = re.compile(r"&&|\|\||;|\n|(?<![>&])&(?![&>])")
RX_PIPE = re.compile(r"(?<![\|>])\|(?!\|)")



def _depth_delta(token, is_kw):
    if not is_kw:
        return 0, 0
    if token in ("(", "{", "if", "while", "for", "until", "select", "case"):
        return 0, 1
    if token in (")", "}", "fi", "done", "esac"):
        return -1, -1
    return 0, 0


def _get_depths(text):
    rx = re.compile(r"&&|\|\||;;|<<|>>|<|>|[;|&()\n]|\w+|[^\s\w;|&()<>\n]+")
    depth = 0
    in_cmd = True
    depths = [0] * len(text)
    case_depth = 0
    unmatched_parens = 0

    for match in rx.finditer(text):
        token = match.group()
        is_kw = in_cmd or token in ("(", ")")

        is_pattern_terminator = False
        if is_kw:
            if token == "case":
                case_depth += 1
            elif token == "esac":
                case_depth -= 1
            elif token == "(":
                unmatched_parens += 1
            elif token == ")":
                if unmatched_parens > 0:
                    unmatched_parens -= 1
                elif case_depth > 0:
                    is_pattern_terminator = True

        pre, post = _depth_delta(token, is_kw)
        if is_pattern_terminator:
            pre, post = 0, 0

        token_depth = max(0, depth + pre)
        depth = max(0, depth + post)

        for i in range(match.start(), match.end()):
            depths[i] = token_depth

        if is_kw and token in ("do", "then", "else", "elif", "!", "time", "(", ")", "{", "}", "if", "while", "for", "until", "select", "case", "fi", "done", "esac"):
            in_cmd = True
        # `;;` ends a case clause, so the next token starts a command and can
        # be the `esac` that closes the group. Omitting it left an `esac` on
        # the same line unrecognised, and the depth it should have closed
        # stayed raised for the rest of the string, so no later stage was
        # split off or examined (CI review of b41c1f39).
        elif token in (";", ";;", "&", "|", "&&", "||", "\n"):
            in_cmd = True
        else:
            in_cmd = False
    return depths


def _handle_quoted_char(char, quote, index, text):
    if char == quote:
        return None, index + 1
    if char == "\\" and index + 1 < len(text):
        return quote, index + 2
    return quote, index + 1


def _extract_token(text, start):
    index = start
    quote = None
    paren_depth = 0
    while index < len(text):
        char = text[index]
        if quote:
            quote, index = _handle_quoted_char(char, quote, index, text)
            continue
        if char in "\"'`":
            quote = char
            index += 1
            continue
        if char == "$" and index + 1 < len(text) and text[index+1] == "(":
            paren_depth += 1
            index += 2
            continue
        if char == "(":
            paren_depth += 1
            index += 1
            continue
        if char == ")":
            if paren_depth == 0:
                break
            paren_depth -= 1
            index += 1
            continue
        if paren_depth == 0 and char in " \t\n;&|<>":
            break
        if char == "\\":
            index += 1
        index += 1
    return text[start:index]


def _split(text, separator):
    """[(offset, piece), ...] -- `text` split on `separator`, offsets kept."""
    depths = _get_depths(text)
    out, pos = [], 0
    for match in separator.finditer(text):
        if depths[match.start()] == 0:
            out.append((pos, text[pos:match.start()]))
            pos = match.end()
    out.append((pos, text[pos:]))
    return out


def _last_match(stage, patterns):
    """Position of the last match of any of `patterns`, or None."""
    starts = [m.start() for p in patterns for m in p.finditer(stage)]
    if not starts:
        return None
    return max(starts)


def _stderr_suppressed(stage):
    """True when this stage's stderr ends up discarded.

    Positional, for the same reason `_stdout_discarded` is: a suppression that
    a later redirect reclaims never takes effect, so firing on it would warn
    about a command whose stderr is captured or merged.
    """
    suppressed = _last_match(
        stage, (RX_MERGE_NULL, RX_STDERR_NULL, RX_STDERR_CLOSED))
    if suppressed is None:
        return False
    reclaimed = _last_match(
        stage, (RX_STDERR_TO_FILE, RX_STDERR_MERGED, RX_MERGE_FILE))
    return reclaimed is None or suppressed > reclaimed


def _last_stdout_file(stage):
    """The stdout-to-file redirect that actually takes effect, or None.

    The shell applies redirects left to right, so the LAST file target is the
    one written. Reporting the first names a file the command truncates and
    leaves empty, sending a reader to the wrong place.
    """
    matches = [m for p in (RX_STDOUT_FILE, RX_MERGE_FILE) for m in p.finditer(stage)]
    if not matches:
        return None
    return max(matches, key=lambda m: m.start())


def _stdout_discarded(stage, to_file):
    """True when this stage's own stdout goes nowhere a reader could see.

    A later stdout-to-file redirect supersedes an earlier discard, since the
    shell applies redirects in order. An earlier file redirect superseded by a
    later discard is the reverse case and still discards.
    """
    discards = [
        match
        for pattern in (RX_MERGE_NULL, RX_STDOUT_NULL)
        for match in pattern.finditer(stage)
    ]
    if not discards:
        return False
    if to_file is None:
        return True
    return max(match.start() for match in discards) > to_file.start()


def _consumption(stage, is_last, captured, original_stage):
    """Why this stage's stdout is READ, or None if it is not.

    Order matters: a stage that also discards its own stdout is parsing
    nothing, so the discard is checked before any consumption shape.

    Order matters within the stage too. The shell applies redirects left to
    right, so a discard is only final when nothing after it reclaims stdout:
    `cmd &>/dev/null > out.json` leaves stderr at /dev/null and stdout in the
    file, which is the shape this hook exists to name.
    """
    to_file = _last_stdout_file(stage)
    if _stdout_discarded(stage, to_file):
        return None
    if to_file is not None:
        match = re.match(r"(?:1?>>?)\s*", original_stage[to_file.start():])
        if match:
            target = _extract_token(original_stage, to_file.start() + match.end())
            if target:
                return "redirected to `{}`".format(target)
        return "redirected to `{}`".format(to_file.group(1))
    if not is_last:
        return "piped into the next command"
    if captured:
        return "captured by a command substitution"
    return None


def find_offenses(command):
    """[(stage_text, reason), ...] for every pipeline stage in `command` that
    suppresses stderr while its own stdout is consumed.
    KNOWN LIMIT: a `case` nested inside a command substitution does not fire.
    A pattern terminator's `)` cannot be told apart there from the
    substitution's own closing parenthesis, so the group is not
    recognised. It under-warns, which is the tolerated direction for an
    advisory hook, and a test pins it.
    """
    masked, spans = _mask(command)
    out = []
    for base, text, captured in _regions(masked, spans):
        for seg_offset, segment in _split(text, RX_SEGMENT):
            stages = _split(segment, RX_PIPE)
            for position, (stage_offset, stage) in enumerate(stages):
                if not _stderr_suppressed(stage):
                    continue
                start = base + seg_offset + stage_offset
                original_stage = command[start:start + len(stage)]
                reason = _consumption(
                    stage, position == len(stages) - 1, captured, original_stage)
                if reason is None:
                    continue
                out.append((original_stage.strip(), reason))
    return out


def truncate(text):
    text = " ".join(text.split())
    return text if len(text) <= MAXLEN else text[:MAXLEN - 3] + "..."


NOTE = """\
stderr is suppressed on a command whose output is then consumed.

    stage:     {stage}
    output is: {reason}

With stderr discarded, an empty or malformed result is indistinguishable from a
legitimately empty one, and the channel carrying the reason is gone. Every
explanation still available is about the parts of the command you can see --
the redirect, the pipe, the quoting -- so a wrong diagnosis there looks just as
plausible as a right one. Measured on ai-config#2998: an empty file was
diagnosed as a redirect problem and the command restructured, when the
suppressed stderr said the host was unresolvable.

Before diagnosing an unexpected result here, re-run without the suppression:

    cmd > out.json                 # keep stderr on the terminal
    cmd 2> err.txt > out.json      # keep it, separately, for a parse

`shared/principles/fail-fast.md` names this family -- a bare `except:`, a
`tryCatch` returning NULL, a shell `|| true`, and `2>/dev/null` on a command
whose output is read.

If the suppression here is deliberate noise reduction, and you will re-run
without it the moment the result surprises you, carry on. This is a reminder,
not a refusal.
"""


def _read_payload():
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"warn-stderr-suppressed-then-parsed: unreadable hook input "
              f"({exc})", file=sys.stderr)
        return {}, is_dry_run


def _quiet(is_dry_run):
    """Emit the empty PreToolUse envelope under --dry-run; otherwise nothing."""
    if is_dry_run:
        print(json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
    return 0


def _command_of(payload):
    """The command string this payload carries, or None."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or tool_input.get("cmd")
        or tool_input.get("script")
    )
    if not isinstance(command, str) or not command.strip():
        return None
    return command


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    if payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
    ):
        return _quiet(is_dry_run)
    command = _command_of(payload)
    if command is None:
        return _quiet(is_dry_run)

    try:
        offenses = find_offenses(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-stderr-suppressed-then-parsed: could not parse command "
              f"({exc})", file=sys.stderr)
        return 0
    if not offenses:
        return _quiet(is_dry_run)

    stage, reason = offenses[0]
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                stage=truncate(stage), reason=reason),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"stderr is suppressed on a command whose output is {reason}; "
            "an empty result will not be distinguishable from a failure. "
            "Re-run without the suppression before diagnosing one."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
