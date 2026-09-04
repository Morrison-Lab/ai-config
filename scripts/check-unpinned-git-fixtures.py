#!/usr/bin/env python3
"""Flag test-fixture git init/clone calls that do not pin a branch name.

String regions are located with `tokenize` rather than a line scanner.
A line scanner toggles docstring state on any lone triple quote, so the bare
closing quote of a multi-line constant *enters* the skipped region instead of
leaving it, and every call site until the next lone triple quote goes
unexamined (ai-config#2986).

Masking is done character-by-character within a multi-line string token's own
span, not by discarding its first and last source lines wholesale: a call
that shares a line with the string's opening or closing quote sits outside
the token's column range on that line, and treating the whole line as
covered would hide it too (ai-config#2986).
"""
import io
import re
import sys
import tokenize
from pathlib import Path

DEFAULT_TARGETS = (("hooks", "test-*.py"), ("scripts", "test_*.py"))

GIT_CMD_RE = re.compile(r'(?:git|_git)[\s"\'`,()[\]a-zA-Z0-9_]*\b(?:init|clone)\b')
BRANCH_FLAG_RE = re.compile(r'-b\b|--initial-branch\b|--branch\b|init\.defaultBranch')

STRING_TOKEN_TYPES = {tokenize.STRING} | {
    getattr(tokenize, name)
    for name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
    if hasattr(tokenize, name)
}


def collect_files(argv):
    """Resolve the files to scan: the given paths, or the default test globs."""
    if not argv:
        files = []
        for directory, pattern in DEFAULT_TARGETS:
            files.extend(sorted(Path(directory).rglob(pattern)))
        return files

    files = []
    for arg in argv:
        path = Path(arg)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
        else:
            files.append(path)
    return files


def _mask_span(line, start_col, end_col):
    """Replace line[start_col:end_col] with spaces, leaving any line ending alone."""
    ending = ""
    body = line
    while body and body[-1] in "\r\n":
        ending = body[-1] + ending
        body = body[:-1]

    body_len = len(body)
    end_col = min(end_col, body_len)
    if start_col >= body_len:
        return line

    return body[:start_col] + " " * (end_col - start_col) + body[end_col:] + ending


def mask_multiline_strings(source):
    """Return a copy of source with each multi-line string token's contents masked.

    Docstrings and multi-line fixture constants both land here, so their
    contents are treated as documentation rather than as call sites. Only
    the characters within a token's own span are replaced with spaces (line
    endings are kept, so line numbers do not shift) -- a call sharing a line
    with the string's opening or closing quote sits outside that span and is
    left intact for the caller to examine. A single-line string is left
    alone: an ordinary call is written on one line and its arguments are
    strings.
    """
    lines = source.splitlines(keepends=True)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in STRING_TOKEN_TYPES:
            continue
        start_row, start_col = token.start
        end_row, end_col = token.end
        if end_row == start_row:
            continue

        first_idx, last_idx = start_row - 1, end_row - 1
        lines[first_idx] = _mask_span(lines[first_idx], start_col, len(lines[first_idx]))
        for idx in range(first_idx + 1, last_idx):
            lines[idx] = _mask_span(lines[idx], 0, len(lines[idx]))
        lines[last_idx] = _mask_span(lines[last_idx], 0, end_col)
    return "".join(lines)


def main(argv):
    failures = 0
    call_sites_examined = 0

    for file_path in collect_files(argv):
        source = file_path.read_text(encoding="utf-8")
        try:
            masked_source = mask_multiline_strings(source)
        except (tokenize.TokenError, SyntaxError) as err:
            print(f"{file_path}: ERROR: could not tokenize: {err}")
            failures += 1
            continue

        for i, line in enumerate(masked_source.splitlines(), start=1):
            line_str = line.strip()
            if line_str.startswith("#"):
                continue

            if not GIT_CMD_RE.search(line_str):
                continue

            call_sites_examined += 1
            if "# unpinned ok" in line_str:
                continue
            if BRANCH_FLAG_RE.search(line_str):
                continue

            print(f"{file_path}:{i}: Unpinned git fixture command: {line_str}")
            failures += 1

    print(f"Examined {call_sites_examined} git init/clone call sites.")
    if call_sites_examined == 0 and not argv:
        print("ERROR: No call sites examined. Negative-control failure.")
        return 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
