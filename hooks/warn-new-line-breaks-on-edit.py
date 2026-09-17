#!/usr/bin/env python3
"""PreToolUse guard: warn before a `Write`/`Edit` composes an NLB violation.

## The incident

`warn-new-line-breaks-on-push.py` catches a semantic-line-break (SemBr)
violation right before `git push`, which is well before CI but still after
the prose was composed and committed. Working `Morrison-Lab/qbt`
(2026-09-14/15, `.github/rulesets/README.md`), a PR's "check /
check-new-line-breaks" job caught 6 added lines packing more than one
sentence -- the SemBr rule was loaded (this corpus's own
`shared/writing/semantic-line-breaks.md` says so explicitly), and it still
broke at composition time. The very commit written to fix that failure
introduced fresh violations of the same rule in the same file, in the act of
narrating the fix -- see `shared/writing/examples-are-scanned.md` for the
general shape of a passage about a rule tripping the rule it describes.

This hook closes the earlier gap: it evaluates the exact text a `Write` or
`Edit` is about to place on disk, before the call executes and before there
is anything to push or commit.

## Relationship to `warn-new-line-breaks-on-push.py`

Deliberately reuses that hook's target-repo checker resolution
(`_git_root` and `_find_checker`, which between them consult that hook's
own `CHECKER_CANDIDATES`) via the hyphenated-sibling import pattern used
elsewhere in this directory, so the two hooks can never disagree about
which checker script governs a given repo.

That also means this hook inherits the push-time hook's own limitation: it
only fires when the TARGET repo vendors a local copy of the checker
(`scripts/vendor/gha-check-new-line-breaks.py` or
`scripts/check-new-line-breaks.py`). A repo that consumes
`Morrison-Lab/gha`'s `check-new-line-breaks` reusable workflow directly
(`uses: Morrison-Lab/gha/.github/workflows/check-new-line-breaks.yml@v2`,
which is what `Morrison-Lab/qbt` calls, from a job named `check`, with no
`scripts/` directory at all) without vendoring a local copy of the script
gets NO local warning from either hook -- the incident above happened in
exactly such a repo, so this new hook would not have caught it either.
Extending checker resolution to fall back to this repo's own bundled vendor
copy for a repo with none of its own is tracked as ai-config#3747 rather
than folded in here, to keep this hook's own behavior identical to its
push-time sibling's and equally easy to reason about.

## Why this warns rather than blocks

Same fail-open, warn-only convention as `warn-new-line-breaks-on-push.py`:
`additionalContext` plus `systemMessage`, no `permissionDecision`. Composing
prose that still needs a semantic-break pass is not itself wrong -- it is
one keystroke from being fixed -- so nothing here should stop the edit.

## The match condition

  M1  the tool is `Write`, `Edit`, or a harness equivalent, targeting a
      `.md`/`.markdown` path outside a never-authored directory
      (`node_modules`, `.git`)
  M2  the target directory is inside a git repository
  M3  the repository vendors the new-line-breaks checker script
      (`scripts/vendor/gha-check-new-line-breaks.py` or
      `scripts/check-new-line-breaks.py`)
  M4  the file as the edit would leave it (the `Write`'s full `content`,
      or the target file with the `Edit`'s `new_string` spliced in over
      its `old_string`) contains, WITHIN the lines the edit itself
      occupies, at least one prose line classified as a violation by that
      checker's own `classify_line`

Fails OPEN on any parse trouble, non-git directory, missing checker,
checker import error, or an `Edit` whose `old_string` cannot be located in
the target file on disk (so no splice is possible).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys


HERE = os.path.dirname(os.path.realpath(__file__))


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    Same pattern used throughout this directory (see
    `flag-unmeasured-timestamp.py`'s own `_sibling`). Fails open.
    """
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_PUSH_HOOK = _sibling(
    "warn-new-line-breaks-on-push.py", "_sib_nlb_on_edit_push_hook"
)

_git_root = getattr(_PUSH_HOOK, "_git_root", None)
_find_checker = getattr(_PUSH_HOOK, "_find_checker", None)

# Narrowed to the checker's own default scope (`NLB_GLOBS` defaults to
# `*.md`), not the wider prose-extension set some other hooks in this
# directory use -- a composition-time false positive on a `.qmd`/`.rst`
# file the checker itself was never configured to examine would warn about
# a rule that is not actually being enforced there.
RX_MD_PATH = re.compile(r"\.(?:md|markdown)$", re.I)
# Never-authored directories. `tmp`/`scratchpad` are deliberately NOT here:
# subagent worktrees in this harness are full checkouts living under a
# session scratchpad, so excluding those segments by name silenced the hook
# on a large share of the prose this corpus composes, while
# `warn-new-line-breaks-on-push.py` warned on the very same content at push
# time. A scratch path outside any checker-vendoring repo is still silent,
# because M2/M3 below reject it.
RX_EXCLUDED_PATH = re.compile(
    r"(?:^|[/\\])(?:node_modules|\.git)(?:[/\\]|$)", re.I
)

WRITE_TOOL_NAMES = (
    "Write", "Edit", "write_to_file", "replace_file_content", "apply_diff",
)


def _target_path(tool_input: dict) -> str:
    return (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("TargetFile")
        or tool_input.get("target_file")
        or tool_input.get("filePath")
        or ""
    )


def _extract_write_content(tool_input: dict) -> str:
    content = (
        tool_input.get("content")
        or tool_input.get("new_string")
        or tool_input.get("text")
        or tool_input.get("replacement")
        or tool_input.get("CodeContent")
        or tool_input.get("ReplacementContent")
        or ""
    )
    return content


def _in_scope_path(path: str) -> bool:
    return (
        bool(path)
        and not RX_EXCLUDED_PATH.search(path)
        and bool(RX_MD_PATH.search(path))
    )


def splice_edit(tool_input: dict, target: str, content: str):
    """Return (whole_text, lo, hi) -- the file as the edit would leave it.

    `checker.prose_line_numbers` is a WHOLE-FILE state machine: it tracks
    frontmatter, fenced code and HTML comments from line 1. Handing it an
    `Edit`'s `new_string` in isolation therefore misreads any fragment
    whose block context lives outside it -- a fragment opening with a
    fence flips `in_code` on and every later line is skipped, a fragment
    opening with `---` reads as frontmatter, and a fragment that actually
    sits inside an existing fence is classified as prose. So splice the
    replacement into the file on disk and classify that, reporting only
    the lines the edit itself occupies (`lo`..`hi`, 1-based, file-relative).

    A `Write` (or any whole-file replacement) needs no splice: its content
    IS the file. Returns None when the edit cannot be located on disk, so
    the caller stays silent rather than classifying a fragment blind.
    """
    old = tool_input.get("old_string") or tool_input.get("TargetContent")
    if not isinstance(old, str) or not old:
        return content, 1, content.count("\n") + 1
    try:
        with open(target, encoding="utf-8") as handle:
            existing = handle.read()
    except Exception:
        return None
    index = existing.find(old)
    if index < 0:
        return None
    lo = existing.count("\n", 0, index) + 1
    spliced = existing[:index] + content + existing[index + len(old):]
    return spliced, lo, lo + content.count("\n")


def find_violations_in_text(
    checker, text: str, lo: int = 1, hi: int | None = None
) -> list[dict[str, str | int]]:
    """Classify prose lines `lo`..`hi` of `text` with `checker`'s own rules.

    Line numbers are relative to `text`, which `splice_edit` makes the
    whole file rather than the edit fragment, so they address the file the
    edit is about to produce.
    """
    lines = text.split("\n")
    if hi is None:
        hi = len(lines)
    prose = checker.prose_line_numbers(text)
    clause_breaks = getattr(checker, "_DEFAULT_CLAUSE_BREAKS", True)
    clause_min_length = getattr(checker, "_DEFAULT_CLAUSE_MIN_LENGTH", 80)
    violations = []
    for line_no in sorted(prose):
        if line_no < max(1, lo) or line_no > min(len(lines), hi):
            continue
        raw = lines[line_no - 1]
        content = checker.line_content(raw)
        kind = checker.classify_line(content, clause_breaks, clause_min_length)
        if kind is None:
            continue
        preview = content if len(content) <= 80 else content[:77] + "..."
        violations.append({"line": line_no, "kind": kind, "preview": preview})
    return violations


def _load_checker(checker_path: str):
    try:
        spec = importlib.util.spec_from_file_location(
            "_nlb_on_edit_checker", checker_path
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def format_warning(
    violations: list[dict[str, str | int]],
    target_path: str,
    git_root: str = "",
) -> tuple[str, str]:
    shown = violations[:20]
    lines = [
        f"  * line {v['line']}: {v['kind']} -- \"{v['preview']}\"" for v in shown
    ]
    if len(violations) > len(shown):
        lines.append(f"  * ... and {len(violations) - len(shown)} more")
    table = "\n".join(lines)
    basename = os.path.basename(target_path)
    # The hook fires in any repo that vendors the checker, and
    # `scripts/semantic-line-breaks.py` is an `ai-config` script -- so name
    # it only where it exists, exactly as the push-time sibling does.
    sembr_script = os.path.join(git_root, "scripts", "semantic-line-breaks.py")
    if git_root and os.path.isfile(sembr_script):
        remedy = (
            " (`scripts/semantic-line-breaks.py --write` fixes it after the "
            "fact, but it is cheaper to compose it broken-up the first time)"
        )
    else:
        remedy = " -- it is cheaper to compose it broken-up the first time"
    note = (
        f"This edit to `{basename}` packs more than one sentence/clause onto "
        f"{len(violations)} added line(s), which this repo's semantic line "
        f"break check will flag:\n\n{table}\n\n"
        "Break each flagged line into one sentence/clause per line before "
        f"the edit lands{remedy}."
    )
    summary = (
        f"This `{basename}` edit packs {len(violations)} line(s) with more "
        "than one sentence -- this repo enforces semantic line breaks."
    )
    return note, summary


def evaluate(tool_name: str, tool_input: dict) -> tuple[str, str] | None:
    if _git_root is None or _find_checker is None:
        return None
    if tool_name not in WRITE_TOOL_NAMES:
        return None
    target = _target_path(tool_input)
    if not _in_scope_path(target):
        return None
    content = _extract_write_content(tool_input)
    if not isinstance(content, str) or not content.strip():
        return None

    target_dir = os.path.dirname(os.path.abspath(target)) or os.getcwd()
    git_root = _git_root(target_dir)
    if not git_root:
        return None
    checker_path = _find_checker(git_root)
    if not checker_path:
        return None
    checker = _load_checker(checker_path)
    if checker is None:
        return None

    spliced = splice_edit(tool_input, target, content)
    if spliced is None:
        return None
    text, lo, hi = spliced

    try:
        violations = find_violations_in_text(checker, text, lo, hi)
    except Exception:
        return None
    if not violations:
        return None
    return format_warning(violations, target, git_root)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"warn-new-line-breaks-on-edit: unreadable hook input ({exc})", file=sys.stderr)
        return 0

    if not isinstance(payload, dict):
        return 0
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        return 0

    try:
        verdict = evaluate(tool_name, tool_input)
    except Exception as exc:
        print(f"warn-new-line-breaks-on-edit: evaluation failed ({exc})", file=sys.stderr)
        return 0

    if verdict is None:
        return 0

    note, summary = verdict
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = summary
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
