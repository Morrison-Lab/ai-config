#!/usr/bin/env python3
"""PreToolUse guard: a file write spells a math operator in raw LaTeX.

The user's standing rule (2026-10-02): any LaTeX math, in any project, repo
or format, uses the shared semantic macros (`d-morrison/macros`) wherever a
macro names the concept, and a new macro is added when none does. It was
broken in a manuscript whose first equation wrote an expectation by hand
instead of using the library's expectation macro. The rule is broken at
composition time, inside a Write or Edit, where it is not being consulted,
so a rule in prose alone does not reach it.

Scans the text being written to a `.qmd`, `.Rmd`, `.tex`, `.md`, `.R`,
`.Rd`, `.Rnw` or `.ipynb` file with the patterns in
`scripts/lib/raw_math.py` (shared with the `scripts/check-raw-math.py`
lint, which can also extend them from the macros library; this hook uses
the built-in rules only), and names each raw operator and the macro to use.

WARNS, never blocks: a raw spelling can be deliberate (a macro definition,
prose quoting the raw form, a document that cannot load the library), and
this hook cannot tell those apart. Fails open on any parse trouble.
Tracked as ai-config#4221.
"""
import json
import os
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from raw_math import MATH_SUFFIXES, find_raw, is_library, is_markdown
except Exception as _exc:  # broken install; fail open and say so
    print(f"warn-raw-math-notation: cannot load scripts/lib/raw_math.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    find_raw = None

MAX_LISTED = 5


def _content(tool_input):
    text = tool_input.get("content") or tool_input.get("new_string") or ""
    if not text:
        text = tool_input.get("new_source") or ""
    return text


def main() -> int:
    if find_raw is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") not in ("Write", "Edit", "NotebookEdit"):
        return 0
    ti = payload.get("tool_input") or {}
    target = str(ti.get("file_path") or ti.get("notebook_path") or "")
    if not target.lower().endswith(MATH_SUFFIXES):
        return 0
    if is_library(target):
        return 0  # the library itself defines the raw forms
    hits = list(find_raw(_content(ti), markdown=is_markdown(target)))
    if not hits:
        return 0
    listed = "\n".join(f"    line {n} of the new text: {raw} -> use {macro}"
                       for n, raw, macro in hits[:MAX_LISTED])
    more = f"\n    ...and {len(hits) - MAX_LISTED} more" if len(hits) > MAX_LISTED else ""
    msg = (
        f"This writes raw LaTeX math notation to `{os.path.basename(target)}` "
        f"where a shared semantic macro exists:\n\n{listed}{more}\n\n"
        "Standing rule (user, 2026-10-02): any LaTeX math, in any repo or "
        "format, uses the shared macros library (d-morrison/macros) wherever a "
        "macro names the concept, and adds a new semantic macro when none "
        "does. See skills/use-math-macros/SKILL.md; "
        "`python3 scripts/check-raw-math.py <path>` lints a whole file or tree. "
        "If the raw form is deliberate (quoting it, or a document that cannot "
        "load the library), carry on -- this is a reminder, not a refusal."
    )
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "additionalContext": msg}}
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = msg.splitlines()[0]
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
