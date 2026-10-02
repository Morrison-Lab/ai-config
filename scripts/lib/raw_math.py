"""Find raw LaTeX math notation that a shared semantic macro already names.

Shared by `scripts/check-raw-math.py` (the lint) and
`hooks/warn-raw-math-notation.py` (the write-time warning).
Both use BUILTIN_RULES; the lint can also extend them from the macros
library itself (`load_rules`), which the hook does not, since a write-time
hook has no reliable way to find the library a document will load.

The rule they enforce is in `skills/use-math-macros/SKILL.md`: any LaTeX
math, in any repo or format, uses the shared macros library
(`d-morrison/macros`) wherever a macro names the concept (ai-config#4221).

Two sources of rules:

- BUILTIN_RULES: operators whose raw spellings vary too much to derive
  (`\\mathbb{E}`, `\\operatorname{Var}`, `\\text{logit}`, `{\\rm E}`, ...),
  each mapped to the library macro that names it.
- derive_rules(): every zero-argument `\\def\\NAME{\\operatorname{X}}` in a
  macros file, mapped from the raw `\\operatorname{X}` (or `\\mathrm{X}`,
  `\\text{X}`) back to `\\NAME`, so a new library operator is covered
  without editing this file.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

BUILTIN_RULES: dict[str, str] = {
    "E": r"\Ep (bare operator) or \E{...} (subscripted)",
    "P": r"\P (bare operator) or \Pf{...}",
    "Var": r"\Var{...}",
    "Cov": r"\Cov{...}",
    "Cor": r"\Cor{...}",
    "Corr": r"\Corr{...}",
    "logit": r"\logit",
    "expit": r"\expit",
}

# A single letter in bold or sans-serif, or inside \text, is usually a
# matrix, a complexity class, or prose ("E-value"), so single-letter names
# are matched only in the wrappers that spell an operator.
_LETTER_WRAPPERS = r"(?:operatorname\*?|mathrm|mathbb)"
_NAME_WRAPPERS = r"(?:operatorname\*?|mathrm|mathit|text|textrm|textup)"

_DEFINITION = re.compile(
    r"\\(?:def|newcommand|renewcommand|providecommand|DeclareMathOperator)\*?\b")

_DERIVABLE = re.compile(
    r"\\def\\([A-Za-z]+)\{\\operatorname\{([A-Za-z]+)\}\}")

MATH_SUFFIXES = (".qmd", ".rmd", ".tex", ".md", ".r", ".rd", ".rnw", ".ipynb")
_MARKDOWN_SUFFIXES = (".qmd", ".rmd", ".md", ".ipynb")
LIBRARY_BASENAME = "macros.qmd"


def is_library(path) -> bool:
    """True for the macros library itself, which defines the raw forms."""
    return os.path.basename(str(path)) == LIBRARY_BASENAME


def is_markdown(path) -> bool:
    return str(path).lower().endswith(_MARKDOWN_SUFFIXES)


def derive_rules(macros_text: str) -> dict[str, str]:
    """Map each raw operator name to the zero-arg macro that defines it."""
    rules: dict[str, str] = {}
    for name, op in _DERIVABLE.findall(macros_text):
        rules.setdefault(op, "\\" + name)
    return rules


def load_rules(macros_file: Path | None) -> dict[str, str]:
    rules = dict(BUILTIN_RULES)
    if macros_file is not None:
        for op, macro in derive_rules(macros_file.read_text(encoding="utf-8")).items():
            rules.setdefault(op, macro)
    return rules


def compile_rules(rules: dict[str, str]) -> re.Pattern[str]:
    def alt(names):
        return "|".join(sorted((re.escape(n) for n in names), key=len, reverse=True))
    letters = alt(n for n in rules if len(n) == 1)
    words = alt(n for n in rules if len(n) > 1)
    parts = []
    if letters:
        parts.append(r"\\" + _LETTER_WRAPPERS + r"\s*\{\s*(" + letters + r")\s*\}")
        parts.append(r"\\mathbb\s+(" + letters + r")\b")
    if words:
        parts.append(r"\\" + _NAME_WRAPPERS + r"\s*\{\s*(" + words + r")\s*\}")
    # {\rm E}, \mathop{\rm Var}: the old font switch, any name.
    parts.append(r"\\rm\s+(" + alt(rules) + r")\b")
    return re.compile("|".join(parts))


def _mask_definitions(line: str) -> str:
    """Blank each macro definition's span, keeping the rest of the line."""
    out = line
    for m in reversed(list(_DEFINITION.finditer(line))):
        i = m.end()
        depth = 0
        bodies = 0
        # Walk the name, any [n] argument count, and the brace body.
        while i < len(line):
            c = line[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    bodies += 1
                    nxt = line[i + 1:].lstrip()
                    if not nxt.startswith(("{", "[")) or bodies >= 2:
                        i += 1
                        break
            i += 1
        out = out[:m.start()] + " " * (i - m.start()) + out[i:]
    return out


_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)")


def _mask_code(lines):
    """Blank fenced blocks and inline code spans in Markdown-like text."""
    in_fence = False
    for line in lines:
        if _FENCE.match(line):
            in_fence = not in_fence
            yield ""
            continue
        yield "" if in_fence else _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def find_raw(text: str, rules: dict[str, str] | None = None, markdown: bool = False):
    """Yield (line_number, raw_text, suggested_macro) for each hit.

    markdown=True skips fenced code blocks and inline code spans, so prose
    can quote a raw form.
    """
    rules = rules or BUILTIN_RULES
    rx = compile_rules(rules)
    lines = text.splitlines()
    if markdown:
        lines = list(_mask_code(lines))
    for lineno, line in enumerate(lines, 1):
        for m in rx.finditer(_mask_definitions(line)):
            name = next(g for g in m.groups() if g)
            yield lineno, m.group(0), rules[name]
