#!/usr/bin/env python3
"""Flag test-fixture git init/clone calls that do not pin a branch name.

String regions are located with `tokenize` rather than a line scanner.
A line scanner toggles docstring state on any lone triple quote, so the bare
closing quote of a multi-line constant *enters* the skipped region instead of
leaving it, and every call site until the next lone triple quote goes
unexamined (ai-config#2986).
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


def multiline_string_lines(source):
    """Return the 1-based line numbers covered by a string spanning >1 line.

    Docstrings and multi-line fixture constants both land here, so their
    contents are treated as documentation rather than as call sites.
    A single-line string is left alone: an ordinary call is written on one
    line and its arguments are strings.
    """
    covered = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in STRING_TOKEN_TYPES:
            continue
        first, last = token.start[0], token.end[0]
        if last > first:
            covered.update(range(first, last + 1))
    return covered


def main(argv):
    failures = 0
    call_sites_examined = 0

    for file_path in collect_files(argv):
        source = file_path.read_text(encoding="utf-8")
        try:
            skip_lines = multiline_string_lines(source)
        except (tokenize.TokenError, SyntaxError) as err:
            print(f"{file_path}: ERROR: could not tokenize: {err}")
            failures += 1
            continue

        for i, line in enumerate(source.splitlines(), start=1):
            if i in skip_lines:
                continue

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
    if call_sites_examined == 0:
        print("ERROR: No call sites examined. Negative-control failure.")
        return 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
