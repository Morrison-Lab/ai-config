#!/usr/bin/env python3
"""
Reformat Markdown prose to use semantic line breaks.

Semantic line breaks = each sentence on its own source line, plus a clause
split at the gate's own flagged boundaries -- currently a sufficiently long
line broken at a mid-line semicolon. Never break a phrase mid-way at a
column boundary.

This is NARROWER by design than the house style documented in
`shared/writing/semantic-line-breaks.md` ("one clause per line"), which also
breaks at comma and conjunction boundaries this tool does not detect.
Prose hand-broken at those wider boundaries gets REJOINED into one line when
run through this tool in whole-file mode (`--all`), since it first joins a
paragraph's lines and then only re-splits at the sentence/semicolon boundaries
above (ai-config#1416, #2586).
The tool deliberately stays narrower by design: natural language clause
detection at comma and coordinating-conjunction boundaries requires a full
syntactic parser; heuristic regex splits on those boundaries yield massive
false-positive rates (>50% on commas per check-new-line-breaks measurements)
and diverge from CI.
Don't run `--all` over already-compliant prose expecting it to be a no-op;
use diff-scoping (the default for `--write`) which preserves hand-broken clause
formatting on untouched sentences in modified paragraphs (ai-config#1599).

Sentence and clause predicates come from the same
`check-new-line-breaks.py` CI pins in `.github/workflows/validate.yml`
(see `scripts/lib/nlb_gate.py`). This script is a reformatter, not a
second implementation of the gate.

Preserves: YAML frontmatter, fenced code blocks (including nested fences),
tables, headings, horizontal rules, HTML comments, @-import directives, and
list items inside blockquotes.
Reformats: prose paragraphs, bullet continuation text, and blockquote prose.

Writing is opt-in, and its scope is opt-in separately. A run that names a
path previews the reformat and writes nothing; `--write` applies it, scoped
by default to paragraphs containing lines the branch changed against a base ref;
`--all` widens that scope to the whole file. See `main()` for the rationale.
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path


def _load_nlb_gate():
    """Import `scripts/lib/nlb_gate.py` without requiring `scripts.lib`."""
    path = Path(__file__).resolve().parent / "lib" / "nlb_gate.py"
    spec = importlib.util.spec_from_file_location("nlb_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_nlb_gate = _load_nlb_gate()


def split_sentences(text: str) -> list[str]:
    """Split text at sentence boundaries using CI's checker."""
    return _nlb_gate.load_nlb_checker().split_sentences(text)


# Paragraph / bullet helpers

_BULLET_RE = re.compile(r'^(\s*)([-*+]|\d+\.)\s+(.*)', re.DOTALL)
_HEADING_RE = re.compile(r'^\s*#{1,6}[\s#]')
_TABLE_RE = re.compile(r'^\s*\|')
_HR_RE = re.compile(r'^\s*[-*_]{3,}\s*$')
# Setext H1 underline (`===`). Scoped to `=` only, not `-`: a `-`-underline
# is CommonMark's Setext H2 form too, but `-` already means horizontal rule
# and bullet marker in this file, and no file in this corpus uses Setext
# headings at all (ai-config#1416) -- so only the unambiguous `=` form is
# handled here, leaving the `-` case for whoever needs it.
# Also scoped to SINGLE-LINE heading text: the detection below only checks
# the line immediately before the underline, not a multi-line paragraph
# ending in one (CommonMark allows the heading text itself to span several
# lines). A multi-line Setext heading still gets swallowed and collapsed --
# the same bug this fix addresses, just for a shape neither this corpus nor
# the reported bug's repro exercises (PR #2587 review round 1).
_SETEXT_H1_RE = re.compile(r'^\s{0,3}=+\s*$')
_FENCE_RE = re.compile(r'^\s*(`{3,}|~{3,})')
_BQ_RE = re.compile(r'^\s*>')
_BLANK_RE = re.compile(r'^\s*$')
# GitHub alert marker (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`,
# `[!CAUTION]`): GitHub only renders the alert when this sits alone on the
# blockquote's first line, so it must never be joined with adjacent prose.
_BQ_ALERT_RE = re.compile(r'^\[![A-Z]+\]\s*$')
_HTML_COMMENT_RE = re.compile(r'^\s*<!--')
_AT_DIRECTIVE_RE = re.compile(r'^\s*@[\w./-]+\.md\s*$')


def _is_new_block(line: str) -> bool:
    """True if line starts a new structural block (not a prose continuation)."""
    return bool(
        _BLANK_RE.match(line) or
        _HEADING_RE.match(line) or
        _FENCE_RE.match(line) or
        _TABLE_RE.match(line) or
        _HR_RE.match(line) or
        _BQ_RE.match(line) or
        _BULLET_RE.match(line) or
        _HTML_COMMENT_RE.match(line) or
        _AT_DIRECTIVE_RE.match(line)
    )


# Blockquote prose flusher

def _emit_prose_sentences(
    orig_lines: list[str],
    orig_start_idx: int,
    indent_str: str,
    changed: set[int] | None,
    output: list[str],
    raw_lines: list[str] | None = None,
    first_prefix: str | None = None,
) -> None:
    """Emit prose sentences with sentence-granular scope preservation.

    If changed is None (whole-file mode), all sentences are reformatted to
    semantic line breaks.
    If changed is a set of 1-based line numbers, sentences whose original lines
    were completely untouched by `changed` (and not sharing a line with a
    touched sentence) are emitted verbatim, preserving their exact multi-line
    breaks. Sentences touched by changed lines are reformatted to semantic line
    breaks.
    """
    if raw_lines is None:
        raw_lines = orig_lines

    line_spans: list[tuple[int, int, int]] = []  # (line_index, start_pos, end_pos)
    para_text_parts: list[str] = []
    pos = 0
    for offset, line in enumerate(orig_lines):
        s = re.sub(r'\s+', ' ', line.strip())
        if not s:
            line_spans.append((orig_start_idx + offset, pos, pos))
            continue
        if para_text_parts:
            pos += 1
        start_pos = pos
        end_pos = start_pos + len(s)
        line_spans.append((orig_start_idx + offset, start_pos, end_pos))
        para_text_parts.append(s)
        pos = end_pos

    para_text = ' '.join(para_text_parts)
    if not para_text:
        output.extend(raw_lines)
        return

    sentences = split_sentences(para_text)
    if not sentences:
        output.extend(raw_lines)
        return

    def emit_clean(s: str, prefix: str) -> None:
        pieces = _nlb_gate.emit_gate_clean(s)
        for j, piece in enumerate(pieces):
            line_prefix = prefix if j == 0 else indent_str
            output.append(line_prefix + piece)

    if changed is None:
        for k, s in enumerate(sentences):
            prefix = first_prefix if (k == 0 and first_prefix is not None) else indent_str
            emit_clean(s, prefix)
        return

    curr_pos = 0
    for k, s in enumerate(sentences):
        prefix = first_prefix if (k == 0 and first_prefix is not None) else indent_str
        s_idx = para_text.find(s, curr_pos)
        if s_idx == -1:
            # split_sentences returned a piece that is not a substring of
            # para_text. Still emit through the gate so a scoped run cannot
            # write a line classify_line would flag.
            emit_clean(s, prefix)
            continue
        s_start = s_idx
        s_end = s_idx + len(s)
        curr_pos = s_end

        overlapping = [
            line_idx for line_idx, l_start, l_end in line_spans
            if (l_start < s_end and l_end > s_start) or (l_start == l_end and s_start <= l_start <= s_end)
        ]

        touched = any((line_idx + 1) in changed for line_idx in overlapping)
        is_isolated = False
        if overlapping:
            first_line = overlapping[0]
            last_line = overlapping[-1]
            first_span = next(span for span in line_spans if span[0] == first_line)
            last_span = next(span for span in line_spans if span[0] == last_line)
            if s_start <= first_span[1] and s_end >= last_span[2]:
                is_isolated = True

        if not touched and is_isolated:
            for line_idx in overlapping:
                output.append(raw_lines[line_idx - orig_start_idx])
        else:
            emit_clean(s, prefix)


def _flush_bq_prose(
    bq_lines: list[str],
    output: list[str],
    bq_start_idx: int = 0,
    changed: set[int] | None = None,
) -> None:
    """Sentence-split accumulated blockquote prose lines and append to output."""
    if not bq_lines:
        return
    bq_prefix = re.match(r'^(\s*>\s*)', bq_lines[0]).group(1)
    inner_lines = [re.sub(r'^\s*>\s*', '', bl) for bl in bq_lines]
    _emit_prose_sentences(
        inner_lines, bq_start_idx, bq_prefix, changed, output, raw_lines=bq_lines
    )


# Diff scoping

class ScopeError(RuntimeError):
    """Raised when the changed-line scope cannot be determined."""


_HUNK_RE = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')


def parse_changed_lines(diff_text: str) -> set[int]:
    """
    Return the 1-based line numbers present in the post-image of a unified
    diff, read from its hunk headers.

    A hunk header `@@ -a,b +c,d @@` means d lines starting at c. A pure
    deletion has d == 0 and contributes no post-image lines; the line it
    was deleted from is still worth reformatting, so attribute the deletion
    to the line it now abuts.
    """
    changed: set[int] = set()
    for line in diff_text.split('\n'):
        m = _HUNK_RE.match(line)
        if not m:
            continue
        start = int(m.group(1))
        count = 1 if m.group(2) is None else int(m.group(2))
        if count == 0:
            changed.add(max(start, 1))
        else:
            changed.update(range(start, start + count))
    return changed


def changed_lines_for(path: Path, base: str) -> set[int]:
    """
    Line numbers in `path` that differ from `base`, via `git diff`.

    Raises ScopeError rather than falling back to whole-file scope: a
    scope we could not determine must fail loudly, since the silent
    fallback is exactly the whole-file rewrite this guard exists to
    prevent.

    Every git call is anchored with `-C` on the file's own directory, so
    the scope depends on where the file is rather than on the caller's
    working directory.

    The pathspec passed to git is therefore the BARE FILENAME, not the path
    as given. Passing a relative path such as `docs/foo.md` while running
    under `-C docs` makes git resolve it as `docs/docs/foo.md`, which
    matches nothing -- and an empty match is indistinguishable from an
    unmodified file, so it would fall through to the untracked branch below
    and silently widen to whole-file scope. That silent widening is the
    exact rewrite this guard exists to prevent.
    """
    anchor = str(path.parent)
    name = path.name

    def git(*args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ['git', '-C', anchor, *args], capture_output=True, text=True,
                encoding='utf-8', errors='replace',
            )
        except OSError as e:
            raise ScopeError(f'could not run git: {e}') from e

    proc = git('diff', '--unified=0', f'{base}...HEAD', '--', name)
    if proc.returncode != 0:
        raise ScopeError(
            f'`git -C {anchor} diff {base}...HEAD -- {name}` failed '
            f'(exit {proc.returncode}): {proc.stderr.strip() or "no stderr"}'
        )

    changed = parse_changed_lines(proc.stdout)

    # A file git does not know about has no diff against the base, which is
    # indistinguishable from an unmodified one by the hunk headers alone.
    # Treat an untracked file as wholly new rather than as wholly unchanged.
    if not changed:
        tracked = git('ls-files', '--error-unmatch', name)
        if tracked.returncode != 0:
            return set(range(1, len(path.read_text(encoding='utf-8').split('\n')) + 1))

    # Uncommitted edits are invisible to a `base...HEAD` range, so fold in
    # the working tree's own diff against HEAD.
    worktree = git('diff', '--unified=0', 'HEAD', '--', name)
    if worktree.returncode == 0:
        changed |= parse_changed_lines(worktree.stdout)

    return changed


def _in_scope(start: int, end: int, changed: set[int] | None) -> bool:
    """True if the block spanning 0-based lines [start, end) should be reformatted."""
    if changed is None:
        return True
    return any((n + 1) in changed for n in range(start, end))


# File processor

def process_file(path: Path, changed: set[int] | None = None) -> bool:
    """
    Process a single Markdown file in-place.
    Returns True if the file was modified, False if unchanged.

    `changed` is the set of 1-based line numbers in scope; None means the
    whole file.
    """
    original = path.read_text(encoding='utf-8')
    result = reformat(original, changed)
    if result != original:
        path.write_text(result, encoding='utf-8')
        return True
    return False


def reformat(original: str, changed: set[int] | None = None) -> str:
    """
    Return `original` with prose reformatted to semantic line breaks.

    Pure: takes text, returns text. Blocks outside `changed` are emitted
    verbatim, so a scoped run leaves untouched regions byte-identical.
    """
    lines = original.split('\n')
    output: list[str] = []

    in_frontmatter = False
    frontmatter_done = False
    in_code_block = False
    fence_char_count = 0
    fence_open_char = None
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # YAML frontmatter
        if not frontmatter_done and not in_frontmatter and i == 0 and stripped == '---':
            in_frontmatter = True
            output.append(line)
            i += 1
            continue

        if in_frontmatter:
            output.append(line)
            if i > 0 and stripped == '---':
                in_frontmatter = False
                frontmatter_done = True
            i += 1
            continue

        # Fenced code blocks --- track opening fence length and character so
        # inner fences of a different character, or fewer characters, are
        # treated as content rather than closers (CommonMark §4.5).
        fence_m = _FENCE_RE.match(stripped)
        if fence_m:
            fence_str = fence_m.group(1)
            fence_len = len(fence_str)
            fence_char = fence_str[0]
            if not in_code_block:
                in_code_block = True
                fence_char_count = fence_len
                fence_open_char = fence_char
            elif fence_char == fence_open_char and fence_len >= fence_char_count:
                in_code_block = False
                fence_char_count = 0
                fence_open_char = None
            # else: a shorter fence, or one using a different character,
            # inside a code block --- emit it verbatim as content.
            else:
                output.append(line)
                i += 1
                continue
            output.append(line)
            i += 1
            continue

        if in_code_block:
            output.append(line)
            i += 1
            continue

        # HTML comments --- may span multiple lines; track open/close so
        # interior prose isn't reflowed.
        if _HTML_COMMENT_RE.match(line):
            output.append(line)
            j = i + 1
            if '-->' not in line:
                while j < len(lines) and '-->' not in lines[j]:
                    output.append(lines[j])
                    j += 1
                if j < len(lines):
                    output.append(lines[j])
                    j += 1
            i = j
            continue

        # Pass-through: blank, heading, table row, horizontal rule,
        # and @-import directives.
        if (not stripped or
                _HEADING_RE.match(line) or
                _TABLE_RE.match(line) or
                _HR_RE.match(stripped) or
                _AT_DIRECTIVE_RE.match(line)):
            output.append(line)
            i += 1
            continue

        # Blockquotes --- process line by line
        if _BQ_RE.match(line):
            # Process the blockquote line-by-line, tracking fence state so
            # code blocks nested inside blockquotes are emitted verbatim.
            j = i
            block_out: list[str] = []
            bq_prose: list[str] = []   # accumulated prose lines to sentence-split
            bq_prose_start = i
            in_bq_code = False

            while j < len(lines) and _BQ_RE.match(lines[j]):
                bq_line = lines[j]
                inner = re.sub(r'^\s*>\s?', '', bq_line)
                if _FENCE_RE.match(inner):
                    # Flush any buffered prose before toggling code state.
                    _flush_bq_prose(bq_prose, block_out, bq_prose_start, changed)
                    bq_prose = []
                    in_bq_code = not in_bq_code
                    block_out.append(bq_line)
                elif in_bq_code:
                    block_out.append(bq_line)
                elif _BULLET_RE.match(inner) or _BLANK_RE.match(inner) or _BQ_ALERT_RE.match(inner):
                    # List items, blank separator lines, and GitHub alert
                    # markers inside blockquotes: flush any preceding prose
                    # and pass through verbatim. An alert marker must stay
                    # alone on its line (never joined with the prose before
                    # or after it), so it gets the same hard-break treatment
                    # as a bullet or blank line.
                    _flush_bq_prose(bq_prose, block_out, bq_prose_start, changed)
                    bq_prose = []
                    block_out.append(bq_line)
                else:
                    if not bq_prose:
                        bq_prose_start = j
                    bq_prose.append(bq_line)
                j += 1

            # Flush any trailing prose.
            _flush_bq_prose(bq_prose, block_out, bq_prose_start, changed)
            output.extend(block_out if _in_scope(i, j, changed) else lines[i:j])
            i = j
            continue

        # Bullet points
        bullet_m = _BULLET_RE.match(line)
        if bullet_m:
            pre = bullet_m.group(1)    # leading spaces
            mark = bullet_m.group(2)   # -, *, +, or 1.
            first_text = bullet_m.group(3)

            marker_str = pre + mark + ' '
            cont_indent = ' ' * len(marker_str)

            # Collect continuation lines: indented >= marker width,
            # and not a new bullet at the same or lower indent.
            j = i + 1
            all_text = first_text.strip()
            while j < len(lines):
                nl = lines[j]
                ns = nl.strip()
                if not ns:
                    break
                # Stop at a fenced code block --- emit the rest verbatim.
                if _FENCE_RE.match(nl):
                    break
                nl_lead = len(nl) - len(nl.lstrip())
                # Stop at a new top-level bullet (same or lower indent) or
                # any other block element.
                if nl_lead < len(marker_str) or _BULLET_RE.match(nl):
                    break
                # It's a continuation line (indented more than marker).
                all_text += ' ' + ns
                j += 1

            if not _in_scope(i, j, changed):
                output.extend(lines[i:j])
                i = j
                continue

            inner_lines = [first_text] + [re.sub(r'^\s*', '', lines[k]) for k in range(i + 1, j)]
            _emit_prose_sentences(
                inner_lines, i, cont_indent, changed, output,
                raw_lines=lines[i:j], first_prefix=marker_str,
            )
            i = j
            continue

        # Setext H1 heading (`Heading\n===\n`): the underline line never
        # matches _is_new_block on its own, so without this check it gets
        # swept into the following prose-paragraph accumulation and joined
        # onto the heading text -- destroying the heading (ai-config#1416).
        if i + 1 < len(lines) and _SETEXT_H1_RE.match(lines[i + 1]):
            output.append(line)
            output.append(lines[i + 1])
            i += 2
            continue

        # Prose paragraphs
        # Leading indent of the paragraph's first line.
        para_lead = len(line) - len(line.lstrip())
        indent_str = ' ' * para_lead

        j = i + 1
        while j < len(lines):
            nl = lines[j]
            if _is_new_block(nl):
                break
            j += 1

        if not _in_scope(i, j, changed):
            output.extend(lines[i:j])
            i = j
            continue

        _emit_prose_sentences(lines[i:j], i, indent_str, changed, output)
        i = j

    result = '\n'.join(output)
    if not result.endswith('\n'):
        result += '\n'
    return result


# Entry point

def _diff_preview(path: Path, before: str, after: str) -> list[str]:
    """A unified diff of one file's reformat, for preview output."""
    return list(difflib.unified_diff(
        before.split('\n'), after.split('\n'),
        fromfile=f'{path} (current)', tofile=f'{path} (reformatted)',
        lineterm='',
    ))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Reformat Markdown prose to semantic line breaks.',
        epilog=(
            'Writing is opt-in and its scope is opt-in separately. Naming a '
            'path previews the reformat and writes nothing. --write applies '
            'it, scoped to paragraphs containing lines this branch changed '
            'against --base. --all widens that to the whole file.'
        ),
    )
    parser.add_argument('paths', nargs='+', type=Path, help='Markdown files')
    parser.add_argument(
        '--write', action='store_true',
        help='apply the reformat (default: preview only, write nothing)',
    )
    parser.add_argument(
        '--all', action='store_true',
        help='widen scope from changed-line paragraphs to the whole file',
    )
    parser.add_argument(
        '--base', default='origin/main',
        help='base ref the changed-line scope is computed against '
             '(default: origin/main)',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    changed_files = 0
    unchanged = 0
    errors = 0

    for path in args.paths:
        try:
            before = path.read_text(encoding='utf-8')

            # Whole-file scope is opt-in. Failing to determine the changed-line
            # scope is a loud error rather than a silent widening to the whole
            # file, since that silent widening is the rewrite this guard exists
            # to prevent.
            scope = None if args.all else changed_lines_for(path, args.base)
            after = reformat(before, scope)

            if after == before:
                unchanged += 1
                continue

            changed_files += 1
            if args.write:
                path.write_text(after, encoding='utf-8')
                print(f'  written: {path}')
            else:
                for line in _diff_preview(path, before, after):
                    print(line)
        except ScopeError as e:
            errors += 1
            print(f'  ERROR:   {path}: {e}', file=sys.stderr)
            print(
                '           Refusing to widen to whole-file scope. '
                'Pass --all to reformat the entire file deliberately.',
                file=sys.stderr,
            )
        except Exception as e:
            errors += 1
            print(f'  ERROR:   {path}: {e}', file=sys.stderr)

    scope_label = 'whole file' if args.all else f'paragraphs with lines changed vs {args.base}'
    verb = 'written' if args.write else 'would change'
    print(
        f'\nDone ({scope_label}): {changed_files} {verb}, '
        f'{unchanged} unchanged, {errors} errors'
    )
    if not args.write and changed_files:
        print('Preview only -- nothing was written. Re-run with --write to apply.')

    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
