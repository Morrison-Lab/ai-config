"""Find raw LaTeX math notation that a shared semantic macro already names.

Shared by `scripts/check-raw-math.py` (the lint) and
`hooks/warn-raw-math-notation.py` (the write-time warning), so the two
agree on what counts as raw notation.

The rule they enforce is in `skills/use-math-macros/SKILL.md`: any LaTeX
math, in any repo or format, uses the shared macros library
(`d-morrison/macros`) wherever a macro names the concept.

Two sources of rules:

- BUILTIN_RULES: operators whose raw spellings vary too much to derive
  (`\\mathbb{E}`, `\\operatorname{E}`, `\\text{Var}`, ...), each mapped to
  the library macro that names it.
- derive_rules(): every zero-argument `\\def\\NAME{\\operatorname{X}}` in a
  macros file, mapped from the raw `\\operatorname{X}` (or `\\mathrm{X}`,
  `\\text{X}`) back to `\\NAME`, so a new library operator is covered
  without editing this file.
"""
from __future__ import annotations

import re
from pathlib import Path

# Raw font or operator wrappers people use to spell an operator by hand.
_WRAPPERS = r"(?:operatorname\*?|mathrm|mathbb|mathsf|mathbf|text|textrm|textup|rm)"

BUILTIN_RULES: dict[str, str] = {
    "E": r"\Ep (bare operator) or \E{...} (subscripted)",
    "P": r"\P (bare operator) or \Pf{...}",
    "Pr": r"\P (bare operator) or \Pf{...}",
    "Var": r"\Var{...}",
    "Cov": r"\Cov{...}",
    "Cor": r"\Cor{...}",
    "Corr": r"\Corr{...}",
    "logit": r"\logit",
    "expit": r"\expit",
}

# A macro *definition* line legitimately spells the raw form.
_DEFINITION = re.compile(
    r"\\(?:def|newcommand|renewcommand|providecommand|DeclareMathOperator)\b")

_DERIVABLE = re.compile(
    r"\\def\\([A-Za-z]+)\{\\operatorname\{([A-Za-z]+)\}\}")


def derive_rules(macros_text: str) -> dict[str, str]:
    """Map each raw operator name to the zero-arg macro that defines it."""
    rules: dict[str, str] = {}
    for name, op in _DERIVABLE.findall(macros_text):
        rules.setdefault(op, "\\" + name)
    return rules


def compile_rules(rules: dict[str, str]) -> re.Pattern[str]:
    names = "|".join(sorted((re.escape(n) for n in rules), key=len, reverse=True))
    return re.compile(
        r"\\" + _WRAPPERS + r"\s*\{\s*(" + names + r")\s*\}"
        r"|\\mathbb\s+(" + names + r")\b")


def find_raw(text: str, rules: dict[str, str] | None = None):
    """Yield (line_number, raw_text, suggested_macro) for each hit."""
    rules = rules or BUILTIN_RULES
    rx = compile_rules(rules)
    for lineno, line in enumerate(text.splitlines(), 1):
        if _DEFINITION.search(line):
            continue
        for m in rx.finditer(line):
            name = m.group(1) or m.group(2)
            yield lineno, m.group(0), rules[name]


def load_rules(macros_file: Path | None) -> dict[str, str]:
    rules = dict(BUILTIN_RULES)
    if macros_file and macros_file.is_file():
        for op, macro in derive_rules(macros_file.read_text(encoding="utf-8")).items():
            rules.setdefault(op, macro)
    return rules


MATH_SUFFIXES = (".qmd", ".rmd", ".tex", ".md", ".r", ".rd", ".rnw", ".ipynb")
