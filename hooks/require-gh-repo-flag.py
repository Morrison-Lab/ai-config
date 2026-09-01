#!/usr/bin/env python3
"""PreToolUse guard: refuse mutating, repo-scoped `gh` commands that omit -R.

Without an explicit -R/--repo, `gh` takes its target from the current working
directory. That is fine for reads and dangerous for writes: on 2026-07-29 a
`gh secret set CLAUDE_CODE_OAUTH_TOKEN` meant for Morrison-Lab/wai ran while cwd
was the ucdavis/bcs checkout and overwrote bcs's token instead. Nothing in the
command named the wrong repo, so nothing looked wrong.

Scope is deliberately narrow -- destructive or expensive operations only. Reads
(`gh pr view`, `gh run list`) and high-frequency low-harm writes (`gh pr
comment`, `gh issue comment`) are NOT gated: a comment on the wrong repo is
visible and trivially deleted, and gating them would train the guard into
noise, which is worse than not having it.

Fails OPEN. A guard that breaks every Bash call when python or jq misbehaves
costs more than the failure it prevents; it reports the problem on stderr
instead of blocking.
"""
import json
import re
import sys

# Anchored at the start of a shell segment, after optional leading whitespace
# and VAR=value assignments -- so `gh secret set` only matches where `gh` is
# actually the command being run. Without the anchor the guard fires on any
# command whose *text* merely contains the pattern: a heredoc documenting the
# command, an `echo`, or a JSON payload piped to a script. That is a false
# positive with real cost, since a blocked turn is more disruptive than a
# missed one here (the miss is caught by the -R habit; the false positive
# teaches you to distrust the guard).
# The value slot accepts a quoted string as well as a bare token: `\S*` alone
# stops at the first space, so `VAR="two words" gh secret set` would fail to
# match the prefix and the whole segment would be treated as not-a-gh-command.
# That direction is a false NEGATIVE -- the guard would wave the command
# through -- which is worse here than the false positive the anchor was added
# to fix.
# Keywords and wrappers whose operand is itself a command word at command position.
KEYWORD_PREFIX = r"""(?:(?:!|\{|time|nohup|sudo|then|else|do|if|elif|while|until)\s+)*"""
ENV_WRAP = r"""(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S*)\s+)*"""
LEAD = r"""^\s*""" + KEYWORD_PREFIX + ENV_WRAP + r"""gh\s+"""

GATED = [
    (LEAD + r"secret\s+(set|delete|remove)\b", "gh secret set/delete"),
    (LEAD + r"variable\s+(set|delete|remove)\b", "gh variable set/delete"),
    (LEAD + r"pr\s+(merge|close|reopen)\b", "gh pr merge/close/reopen"),
    (LEAD + r"issue\s+(close|reopen|delete|transfer)\b", "gh issue close/reopen/delete"),
    (LEAD + r"release\s+(create|delete|edit|upload)\b", "gh release create/delete/edit"),
    (LEAD + r"workflow\s+(run|enable|disable)\b", "gh workflow run/enable/disable"),
    (LEAD + r"run\s+(rerun|cancel|delete)\b", "gh run rerun/cancel/delete"),
    (LEAD + r"repo\s+(delete|archive|rename)\b", "gh repo delete/archive/rename"),
    (LEAD + r"label\s+(create|delete|edit)\b", "gh label create/delete/edit"),
    (LEAD + r"ruleset\s+\w+", "gh ruleset (write)"),
]

# `gh api` with {owner}/{repo} placeholders resolves them from cwd, so it has
# the same implicit-target hazard even though the path looks explicit.
API_PLACEHOLDER = re.compile(LEAD + r"api\b[^\n]*\{(owner|repo)\}")

# `gh secret set`/`delete` have three mutually exclusive target selectors --
# -R/--repo, -o/--org, -u/--user; `gh variable set`/`delete` only have two,
# -R/--repo and -o/--org (no -u/--user). Discharging only on -R left every
# org/user-scoped write gated with no way to satisfy the guard short of an
# inert -R that names nothing gh actually uses for that command
# (ai-config#2367). -o/--org and -u/--user are equally explicit targets, so
# accepting them preserves the guard's actual invariant ("the target is
# named, not inherited from cwd") rather than a proxy for it. Note -u/--user
# on `secret set`/`delete` is a bare boolean flag (targets the currently
# authenticated account) -- it takes no value, unlike -R/-o.
HAS_REPO_FLAG = re.compile(
    r"(^|\s)(-R\b|--repo(=|\s)|-o\b|--org(=|\s)|-u\b|--user\b)"
)

# Match heredoc openers: `<<`, `<<-`, `<<~` followed by quoted, backslash-escaped,
# or bare word delimiter.
HEREDOC_OPEN = re.compile(
    r"""(?<!<)[0-9]*<<([-~]?)[ \t]*(?:'([^']+)'|"([^"]+)"|\\([^\s;|&<>()]+)|([A-Za-z_][A-Za-z0-9_\-]*))"""
)


def strip_heredocs(command: str) -> str:
    """Omit heredoc body lines and closing delimiters from a multi-line shell command."""
    lines = command.splitlines(keepends=True)
    out_lines: list[str] = []
    active_delimiter: str | None = None
    strip_tabs = False

    for line in lines:
        if active_delimiter is not None:
            check_line = line.lstrip("\t") if strip_tabs else line
            if check_line.rstrip("\r\n") == active_delimiter:
                active_delimiter = None
            continue

        out_lines.append(line)
        matches = list(HEREDOC_OPEN.finditer(line))
        if matches:
            last_match = matches[-1]
            strip_tabs = bool(last_match.group(1))
            delim = next(g for g in last_match.groups()[1:] if g is not None)
            active_delimiter = delim

    return "".join(out_lines)


def split_command(command: str) -> list[str]:
    """Split a shell command into executable segments, respecting quotes and subshells."""
    segments = []
    current = []
    stack = ["ROOT"]
    escaped = False
    i = 0
    n = len(command)

    while i < n:
        c = command[i]

        if escaped:
            current.append(c)
            escaped = False
            i += 1
            continue

        top = stack[-1]

        if top == "SINGLE_QUOTE":
            if c == "'":
                stack.pop()
            current.append(c)
            i += 1
            continue

        if c == "\\" and top != "SINGLE_QUOTE":
            escaped = True
            current.append(c)
            i += 1
            continue

        if top == "DOUBLE_QUOTE":
            if c == '"':
                stack.pop()
                current.append(c)
                i += 1
                continue
            if c == "$" and i + 1 < n and command[i + 1] == "(":
                seg = "".join(current).strip()
                if seg:
                    segments.append(seg)
                current = []
                stack.append("COMMAND_SUBST")
                i += 2
                continue
            if c == "`":
                seg = "".join(current).strip()
                if seg:
                    segments.append(seg)
                current = []
                stack.append("BACKTICK")
                i += 1
                continue
            current.append(c)
            i += 1
            continue

        # top is ROOT, PAREN, COMMAND_SUBST, or BACKTICK
        if c == "'":
            stack.append("SINGLE_QUOTE")
            current.append(c)
            i += 1
            continue

        if c == '"':
            stack.append("DOUBLE_QUOTE")
            current.append(c)
            i += 1
            continue

        if c == "$" and i + 1 < n and command[i + 1] == "(":
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
            stack.append("COMMAND_SUBST")
            i += 2
            continue

        if c == "`":
            if top == "BACKTICK":
                seg = "".join(current).strip()
                if seg:
                    segments.append(seg)
                current = []
                stack.pop()
                i += 1
                continue
            else:
                seg = "".join(current).strip()
                if seg:
                    segments.append(seg)
                current = []
                stack.append("BACKTICK")
                i += 1
                continue

        if c == "(":
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
            stack.append("PAREN")
            i += 1
            continue

        if c == ")":
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
            if top in ("PAREN", "COMMAND_SUBST"):
                stack.pop()
            i += 1
            continue

        # 2-char operators: &&, ||, |&, ;;
        if i + 1 < n and command[i:i + 2] in ("&&", "||", "|&", ";;"):
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
            i += 2
            continue

        # 1-char operators / delimiters: ;, |, \n
        if c in (";", "|", "\n"):
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
            i += 1
            continue

        # Standalone & (background operator, not part of &>, >&, or 2>&1)
        if c == "&":
            prev_char = command[i - 1] if i > 0 else ""
            next_char = command[i + 1] if i + 1 < n else ""
            if prev_char == ">" or next_char == ">":
                current.append(c)
                i += 1
                continue
            seg = "".join(current).strip()
            if seg:
                segments.append(seg)
            current = []
            i += 1
            continue

        current.append(c)
        i += 1

    seg = "".join(current).strip()
    if seg:
        if stack[-1] in ("SINGLE_QUOTE", "DOUBLE_QUOTE"):
            for fallback_seg in re.split(r"(?:&&|\|\||[;&|\n])", seg):
                s = fallback_seg.strip().strip("'\"")
                if s:
                    segments.append(s)
        else:
            segments.append(seg)

    return segments


def mask_arithmetic(command: str) -> str:
    """Mask $(( ... )) and (( ... )) arithmetic expansions with balanced parentheses."""
    out = []
    i = 0
    n = len(command)
    in_sq = False
    in_dq = False
    escaped = False

    while i < n:
        ch = command[i]

        if escaped:
            escaped = False
            out.append(ch)
            i += 1
            continue

        if ch == "\\":
            escaped = True
            out.append(ch)
            i += 1
            continue

        if ch == "'" and not in_dq:
            in_sq = not in_sq
            out.append(ch)
            i += 1
            continue
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
            out.append(ch)
            i += 1
            continue

        if not in_sq and not in_dq:
            if command.startswith("$((", i) or command.startswith("((", i):
                is_subst = command.startswith("$((", i)
                start = i
                i += 3 if is_subst else 2
                depth = 2
                sub_sq = False
                sub_dq = False
                sub_escaped = False
                while i < n and depth > 0:
                    c = command[i]
                    if sub_escaped:
                        sub_escaped = False
                        i += 1
                        continue
                    if c == "\\":
                        sub_escaped = True
                        i += 1
                        continue
                    if c == "'" and not sub_dq:
                        sub_sq = not sub_sq
                    elif c == '"' and not sub_sq:
                        sub_dq = not sub_dq
                    elif not sub_sq and not sub_dq:
                        if c == "(":
                            depth += 1
                        elif c == ")":
                            depth -= 1
                    i += 1
                if depth == 0:
                    span = command[start:i]
                    out.append("\n" * span.count("\n"))
                    continue
                else:
                    out.append(command[start])
                    i = start + 1
                    continue

        out.append(command[i])
        i += 1

    return "".join(out)


def strip_heredocs(command: str) -> str:
    """Drop heredoc body lines and delimiters so interior text is not scanned as commands."""
    # Mask arithmetic expansions across the whole command before parsing openers,
    # preserving line breaks so line counts stay synchronized.
    command_for_openers = mask_arithmetic(command)
    lines_orig = command.split("\n")
    lines_masked = command_for_openers.split("\n")

    out = []
    pending_heredocs = []  # list of (delim: str, is_tab_strip: bool)
    current_heredoc_buffer = []

    for orig_line, masked_line in zip(lines_orig, lines_masked):
        if pending_heredocs:
            delim, is_tab_strip = pending_heredocs[0]
            clean_line = orig_line.rstrip("\r")
            if is_tab_strip:
                # <<- strips leading tabs (and spaces for robustness)
                matched = (clean_line.lstrip("\t ") == delim)
            else:
                matched = (clean_line == delim)
            if matched:
                pending_heredocs.pop(0)
                current_heredoc_buffer.clear()
            else:
                current_heredoc_buffer.append(orig_line)
            continue

        out.append(orig_line)
        if not orig_line.strip().startswith("#"):
            for m in HEREDOC_OPEN.finditer(masked_line):
                rest = masked_line[m.end():]
                if re.match(r"^\s*\)\)", rest):
                    continue
                strip_flag = m.group(1)
                delim = m.group(2) or m.group(3) or m.group(4) or m.group(5)
                if delim:
                    pending_heredocs.append((delim, bool(strip_flag)))

    # If any heredocs were left unclosed at EOF, keep their buffered lines (fail-safe)
    if pending_heredocs:
        out.extend(current_heredoc_buffer)

    return "\n".join(out)


def offending(command: str):
    command_scannable = strip_heredocs(command)
    for segment in split_command(command_scannable):
        if "gh" not in segment:
            continue
        if HAS_REPO_FLAG.search(segment):
            continue
        for pattern, label in GATED:
            if re.search(pattern, segment):
                return label, segment.strip()
        if API_PLACEHOLDER.search(segment):
            return "gh api with {owner}/{repo} placeholders", segment.strip()
    return None


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
        print(f"require-gh-repo-flag: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        return 0

    inp = payload.get("tool_input") or {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""
    hit = offending(command)
    if not hit:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    label, segment = hit
    reason = (
        f"Blocked: `{label}` without an explicit target.\n\n"
        f"    {segment}\n\n"
        "`gh` would take the target repo from the current working directory, "
        "which is how a secret meant for one repo got written to another on "
        "2026-07-29. Re-issue the command with the target named explicitly, "
        "whichever selector actually applies:\n\n"
        f"    -R <owner>/<repo>   (repository)\n"
        f"    -o <org>            (organization)\n"
        f"    -u                  (your own user account -- no value; "
        f"`gh secret` only, not `gh variable`)\n\n"
        "If you genuinely mean 'whatever repo the cwd points at', run `git "
        "remote -v` first and then pass that repo by name anyway."
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
