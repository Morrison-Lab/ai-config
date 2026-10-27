"""Find raw LaTeX math notation that a shared semantic macro already names.

Shared by `scripts/check-raw-math.py` (the lint) and
`hooks/warn-raw-math-notation.py` (the write-time warning).
Both extend BUILTIN_RULES from the macros library itself (`load_rules`),
found for a file by `read_macros_library`: the macros submodule that the
file's git repository declares in `.gitmodules`.

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

A third, fixed class, SYMBOL_RULES, flags notation that is not a concept:
a bare letter symbol (`\\ell`), manual delimiter sizing (`\\big(`, `\\left(`), a raw
transpose (`^\\top`) and a font command used as a symbol (`\\mathbb{R}`,
`\\mathcal{L}`), naming the macros that replace each.
"""
from __future__ import annotations

import os
import posixpath
import re
import subprocess
import time
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

# Symbols that spell a letter rather than name a concept. Each maps to the
# concept macros that replace it; the right one depends on the meaning.
_BS = "\\\\"
SYMBOL_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(_BS + r"ell(?![A-Za-z])"),
     r"\llik (log-likelihood), \obsloss{i} (loss on one observation), "
     r"\lpnorm{p} (the name of an l_p norm) or \lbound (a lower bound); "
     r"a dummy index takes a Latin letter"),
    # Manual delimiter sizing: the macros size themselves.
    (re.compile(_BS + r"(?:big|Big|bigg|Bigg)[lrm]?\s*(?:[()\[\]|]|" + _BS + r"[{}|]|"
                + _BS + r"[lr](?:vert|Vert|brace|floor|ceil|angle)(?![A-Za-z]))"),
     r"\paren{}, \sb{}, \cb{}, \abs{}, \norm{} or \evalAt{}{} (they size themselves)"),
    # Manual \left ... \right pairs: the same sizing, written by hand.
    (re.compile(_BS + r"(?:left|right)(?![A-Za-z])"),
     r"\paren{}, \sb{}, \cb{}, \set{} or \abs{} (they size themselves)"),
    # A raw transpose.
    (re.compile(r"\^\s*(?:\{\s*" + _BS + r"top\s*\}|" + _BS + r"top(?![A-Za-z]))"),
     r"\tp{X}, \pt{...}, \dprod{a}{b} (a dot product) or \stprod{X}"),
    # A font command used to spell a symbol.
    (re.compile(_BS + r"(?:mathbb|mathcal|mathscr|mathfrak)\s*(?:\{[^{}]*\}|[A-Za-z])"),
     r"a concept macro: \reals, \Nat, \Lik, \Ep, ... (search macros.qmd; add one "
     r"named for the concept if none exists)"),
]

# A single letter in bold or sans-serif, or inside \text, is usually a
# matrix, a complexity class, or prose ("E-value"), so single-letter names
# are matched only in the wrappers that spell an operator.
_LETTER_WRAPPERS = r"(?:operatorname\*?|mathrm|mathbb)"
_NAME_WRAPPERS = r"(?:operatorname\*?|mathrm|mathit|text|textrm|textup)"

_DEFINITION = re.compile(
    r"\\(?:def|newcommand|renewcommand|providecommand|DeclareMathOperator)\*?(?![A-Za-z])")

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


# The macros library's repository, as a submodule URL names it.
MACROS_REPOS = ("morrison-lab/macros", "d-morrison/macros")
DEFAULT_BUDGET = 2.0  # seconds, for all the git calls of one lookup
_URL_TAIL = re.compile(r"(?:^|[/:])([^/:]+/[^/:]+?)(?:\.git)?/*$")


def _git_root(start: Path) -> Path | None:
    """Return the nearest directory at or above `start` holding `.git`.

    `.git` may be a directory or, in a submodule or worktree, a file. The
    start need not exist (a Write may create the file and its directory).
    """
    for d in (start, *start.parents):
        if (d / ".git").exists():
            return d
    return None


_SUBMODULE = re.compile(r'\[\s*submodule\s+"([^"]*)"\s*\]')


def _gitmodules_entries(text: str):
    """Yield (name, path, url) for each submodule in a `.gitmodules` text."""
    sections: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            m = _SUBMODULE.match(line)
            sections.append({"name": m.group(1)} if m else {})
        elif "=" in line and sections:
            key, _, value = line.partition("=")
            value = value.strip()
            if value.startswith('"'):
                value = value[1:].partition('"')[0]
            else:  # git drops an unquoted value's trailing comment
                value = re.sub(r"\s+[#;].*$", "", value)
            sections[-1][key.strip().lower()] = value
    for sec in sections:
        if "name" in sec and "path" in sec and "url" in sec:
            yield sec["name"], sec["path"], sec["url"]


def is_macros_url(url: str, base: str | None = None) -> bool:
    """True when a submodule URL names the macros library's repository.

    A relative URL (`../macros.git`) is resolved against `base`, the
    superproject's own remote URL; without one it never matches.
    """
    url = url.strip()
    if url.startswith(("./", "../")):
        m = _URL_TAIL.search(base or "")
        if not m:
            return False
        url = posixpath.normpath(posixpath.join(m.group(1), url))
    m = _URL_TAIL.search(url)
    return bool(m) and m.group(1).lower() in MACROS_REPOS


def _origin_url(root: Path, deadline: float) -> str | None:
    p = subprocess.run(["git", "-C", str(root), "config", "--get", "remote.origin.url"],
                       capture_output=True, text=True, timeout=_left(deadline))
    return p.stdout.strip() if p.returncode == 0 else None


def _left(deadline: float) -> float:
    """Seconds left before `deadline`; raises TimeoutExpired once it passes."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise subprocess.TimeoutExpired("git", 0)
    return left


def _macros_submodules(start, deadline: float):
    """Yield (git_root, name, path) for each macros submodule `start` sees.

    Walks up from `start` (a file or a directory, which need not exist) to
    its git root and reads `.gitmodules` there. Lab repos name the macros
    submodule differently (`latex-macros/`, `macros/`), so its URL, not its
    directory name, identifies it. Raises OSError or UnicodeDecodeError
    when `.gitmodules` exists but cannot be read.
    """
    start = Path(start).absolute()
    root = _git_root(start if start.is_dir() else start.parent)
    if root is None:
        return
    gm = root / ".gitmodules"
    if not gm.is_file():
        return
    origin: list[str | None] = []  # looked up once, and only for a relative URL
    for name, path, url in _gitmodules_entries(gm.read_text(encoding="utf-8")):
        if url.startswith(("./", "../")) and not origin:
            try:
                origin.append(_origin_url(root, deadline))
            except (OSError, subprocess.SubprocessError):
                origin.append(None)
        if is_macros_url(url, origin[0] if origin else None):
            yield root, name, path


def _git_show(git_dir: str, spec: str, deadline: float) -> str | None:
    """The blob at `spec`, or None if absent; a non-UTF-8 blob raises."""
    p = subprocess.run(["git", "--git-dir", git_dir, "show", spec],
                       capture_output=True, timeout=_left(deadline))
    return p.stdout.decode("utf-8") if p.returncode == 0 else None


def read_macros_library(start, budget: float = DEFAULT_BUDGET) -> tuple[str, str] | None:
    """Return (source, text) of the macros library for `start`, or None.

    Reads the checked-out `macros.qmd` when there is one. A worktree often
    leaves the submodule uninitialised, so otherwise the library is read
    from the submodule's clone in the superproject's git directory
    (`modules/<name>`): the commit the superproject pins, or that clone's
    HEAD when the pinned commit was never fetched. Every git call shares one
    `budget` of seconds, so a hung git costs the write-time hook at most
    that; past it the lookup gives up (None). Raises OSError or
    UnicodeDecodeError when the library it finds, checked out or in the
    clone, cannot be read or is not UTF-8.
    """
    deadline = time.monotonic() + budget
    subs = list(_macros_submodules(start, deadline))
    for root, _name, path in subs:
        lib = root / path / LIBRARY_BASENAME
        if lib.is_file():
            return str(lib), lib.read_text(encoding="utf-8")
    for root, name, path in subs:
        try:
            common = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--path-format=absolute",
                 "--git-common-dir"], capture_output=True, text=True,
                timeout=_left(deadline))
            if common.returncode != 0:
                continue
            git_dir = os.path.join(common.stdout.strip(), "modules", name)
            if not os.path.isdir(git_dir):
                continue
            pin = subprocess.run(["git", "-C", str(root), "ls-tree", "HEAD", "--", path],
                                 capture_output=True, text=True, timeout=_left(deadline))
            fields = pin.stdout.split()  # "<mode> commit <sha>\t<path>"
            revs = ([fields[2]] if len(fields) > 2 and fields[1] == "commit" else []) + ["HEAD"]
            for rev in revs:
                text = _git_show(git_dir, f"{rev}:{LIBRARY_BASENAME}", deadline)
                if text is not None:
                    return f"{git_dir} at {rev[:12]}", text
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def derive_rules(macros_text: str) -> dict[str, str]:
    """Map each raw operator name to the zero-arg macro that defines it."""
    rules: dict[str, str] = {}
    for name, op in _DERIVABLE.findall(macros_text):
        rules.setdefault(op, "\\" + name)
    return rules


def load_rules(macros_file: Path | None = None,
               macros_text: str | None = None) -> dict[str, str]:
    """BUILTIN_RULES extended from a macros library, given as a file or its text."""
    rules = dict(BUILTIN_RULES)
    if macros_file is not None:
        macros_text = macros_file.read_text(encoding="utf-8")
    if macros_text is not None:
        for op, macro in derive_rules(macros_text).items():
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


def _definition_end(text: str, start: int, limit: int) -> int | None:
    r"""Return the end of the definition whose command ends at `start`.

    The definition is the macro's name (`\Ep`, or `{\Ep}`), an optional
    argument spec (`[1]`, `#1`), and one brace body. The walk skips escaped
    characters such as `\{` and `%` comments, and stops at a blank line.
    It returns None for anything that does not parse as a definition (a
    prose mention, a truncated body), so that text is scanned, not hidden.
    The walk never passes `limit`, the start of the next definition command,
    so each character is walked at most once across all definitions.
    """
    i = start
    depth = 0
    named = False  # the macro's name has been read
    in_spec = False  # inside [..] at depth 0
    while i < limit:
        c = text[i]
        if c == "\n" and text.startswith("\n", i + 1):
            return None  # a blank line ends the search
        if c == "\\":
            j = i + 1
            while j < limit and text[j].isalpha():
                j += 1
            if depth == 0 and not in_spec:
                if named:  # a second control sequence before any body
                    return None
                named = True
            i = max(j, i + 2)
            continue
        if c == "%":
            nl = text.find("\n", i, limit)
            i = limit if nl < 0 else nl + 1
            continue
        if in_spec:
            in_spec = c != "]"
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                return None
            if depth == 0:
                if named:
                    return i + 1
                named = True  # that group was the name: {\Ep}
        elif depth == 0:
            if c == "[" and named:
                in_spec = True
            elif not (c.isspace() or c.isdigit() or c == "#"):
                return None  # ordinary text: not a definition
        i += 1
    return None


def _mask_definitions(text: str) -> str:
    """Blank each macro definition's span, keeping line breaks.

    Works on the whole text in one pass, so a body that starts on the next
    line (`\\newcommand{\\Ex}{%` then the body) is masked too.
    """
    pieces = []
    pos = 0
    matches = list(_DEFINITION.finditer(text))
    for k, m in enumerate(matches):
        if m.start() < pos:
            continue  # inside a definition already masked
        limit = matches[k + 1].start() if k + 1 < len(matches) else len(text)
        end = _definition_end(text, m.end(), limit)
        if end is None:
            continue
        pieces.append(text[pos:m.start()])
        pieces.append(re.sub(r"[^\n]", " ", text[m.start():end]))
        pos = end
    pieces.append(text[pos:])
    return "".join(pieces)


# A fence line, optionally inside a blockquote or after a list marker.
# Any indent is accepted, so a fence inside a list item opens and closes
# by the same rule; a backtick fence's info string cannot contain a
# backtick.
_FENCE = re.compile(r"^((?: {0,3}>)*) *((?:[-*+]|[0-9]{1,9}[.)]) +)?(`{3,}|~{3,})(.*)$")
_QUOTE = re.compile(r"(?: {0,3}>)*")


def _fence(line: str):
    """Return the fence marker a line opens or closes, or None."""
    m = _FENCE.match(line)
    if not m or (m.group(3)[0] == "`" and "`" in m.group(4)):
        return None
    return m


def _quote_depth(line: str) -> int:
    """Count the blockquote markers (`>`) that prefix a line."""
    return _QUOTE.match(line).group(0).count(">")


def _mask_spans(line: str) -> str:
    """Blank inline code spans, in time linear in the line's length.

    A span opens at a backtick run and closes at the next run of the same
    length. A backslash escapes the first backtick of an opening run, but
    not a closing one, since escapes do not work inside a span. A run with
    no matching closer is left as text, so the math after it is still
    scanned.
    """
    runs = []  # (start, end, escaped)
    i, n = 0, len(line)
    slashes = 0  # backslashes immediately before line[i]
    while i < n:
        if line[i] == "`":
            j = i
            while j < n and line[j] == "`":
                j += 1
            runs.append((i, j, slashes % 2 == 1))
            slashes = 0
            i = j
        else:
            slashes = slashes + 1 if line[i] == "\\" else 0
            i += 1
    later: dict[int, list[int]] = {}  # run length -> later run indexes, reversed
    for k in range(len(runs) - 1, -1, -1):
        later.setdefault(runs[k][1] - runs[k][0], []).append(k)
    out = list(line)
    k = 0
    while k < len(runs):
        start, end, escaped = runs[k]
        start += escaped  # an escaped first backtick is literal text
        stack = later.get(end - start, [])
        while stack and stack[-1] <= k:
            stack.pop()
        if start == end or not stack:
            k += 1
            continue
        close = stack.pop()
        out[start:runs[close][1]] = " " * (runs[close][1] - start)
        k = close + 1
    return "".join(out)


def _mask_code(lines):
    """Blank fenced blocks and inline code spans in Markdown-like text."""
    opener = None  # the open fence's marker, e.g. "````"
    depth = 0  # blockquote depth the fence opened at
    for line in lines:
        m = _fence(line)
        if opener is not None and _quote_depth(line) < depth:
            opener = None  # the blockquote ended, and the fence with it
        if opener is None and m:
            opener = m.group(3)
            depth = m.group(1).count(">")
            yield ""
        elif opener is not None:
            if (m and m.group(1).count(">") == depth and not m.group(2)
                    and m.group(3)[0] == opener[0] and len(m.group(3)) >= len(opener)
                    and not m.group(4).strip()):
                opener = None
            yield ""
        else:
            yield _mask_spans(line)


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
    lines = _mask_definitions("\n".join(lines)).split("\n")
    for lineno, line in enumerate(lines, 1):
        named = []
        for m in rx.finditer(line):
            name = next(g for g in m.groups() if g)
            named.append(m.span())
            yield lineno, m.group(0), rules[name]
        for sym, hint in SYMBOL_RULES:
            for m in sym.finditer(line):
                # An operator already named above (\mathbb{E}) is reported once.
                if any(s < m.end() and m.start() < e for s, e in named):
                    continue
                yield lineno, m.group(0), hint
