#!/usr/bin/env python3
"""PreToolUse guard: warn on a duplicate-key-blind YAML key check.

## The incident (gha#839)

2026-09-07, `Morrison-Lab/gha`. A verification sweep over `examples/*.yml`
asked which caller stubs had a commented `with:` block that would not
"uncomment" into valid YAML. It stripped the comment markers, parsed with
`yaml.safe_load`, and asserted:

    isinstance(job.get('with'), dict) and len(job['with']) >= 1

It reported exactly 1 broken file. That was wrong.

PyYAML's non-strict loader silently keeps the LAST of duplicate mapping
keys. The defect being searched for was a stub that uncomments into a
DUPLICATE `with:` key -- and such a stub still yields a valid one-key
mapping, so it passed the check. The instrument's PASS condition was
satisfiable by the very defect it existed to detect.

Re-run with a duplicate-key-rejecting loader, the true count was 5, not 1.
The wrong count shipped into a public tracking issue and was only caught by
a reviewer who re-derived the population independently. GitHub Actions also
takes the last duplicate silently, so for a consumer the consequence is
silently dropped workflow inputs rather than an error.

## The general principle

When an instrument's pass condition is satisfiable by the defect it exists
to detect, a green result from it is not evidence. See
`shared/workflow/algorithmatize-checks.md`.

## What this checks

A Bash command that ACTUALLY RUNS Python code (a `-c` one-liner, a heredoc
piped to python's stdin, or a heredoc that writes a `.py` file the same
command then executes) where that code:

  1. calls `yaml.safe_load` / `yaml.load` / `yaml.full_load` (non-strict --
     PyYAML's default constructors keep the LAST of duplicate keys); and
  2. later asserts something about the parsed mapping's KEYS or their count
     (`.keys()`, `len(...)`, a membership test such as `'x' in job`, or
     `== set(...)`).

That combination cannot see a duplicate-key defect: PyYAML already
collapsed the duplicate before either analysis had a chance to notice.

Silent when the load is paired with a custom duplicate-rejecting
constructor (`add_constructor` appears anywhere in the same script) --
that IS the fix this hook recommends, and it must not warn on itself.

## Why AST, not text search

This corpus quotes its own detector strings constantly, including in this
very docstring: `yaml.safe_load`, `len(`, `assert` all appear above as
PROSE, not as code. A textual match would fire on a `-c` one-liner that
merely PRINTS a sentence describing this rule ("warns when yaml.safe_load
is followed by len(...) or assert"), because the substrings are present
even though no such call or assertion is ever made.

Parsing the extracted script text with `ast` and walking real `Call`,
`Assert`, and `Compare` nodes avoids that: a string literal containing the
words "yaml.safe_load" is an `ast.Constant`, never a `Call`, so it cannot
satisfy either clause. It also resolves the `in` ambiguity for free -- a
`for k in d:` loop is an `ast.For`, not an `ast.Compare`, so an ordinary
loop over the parsed mapping never counts as "asserting on its keys" while
`if 'with' in job:` (an `ast.Compare` with an `In` op) does.

## What this deliberately does NOT reach

  * A Bash command that only WRITES prose about this rule (a heredoc to a
    `.md`/`.txt` file, a `git commit -m` message, an `echo`) -- there is no
    Python execution to inspect at all, so the guard is silent by
    construction rather than by a text-level exemption.
  * `python3 script.py` where `script.py` was not created by a heredoc
    earlier in the SAME command -- this hook cannot read a file it did not
    just see written, so a pre-existing script is invisible to it. Under-
    detection is the safe direction for a warn-only guard.
  * Code that resolves the mapping through anything other than a literal
    `<name>.safe_load(...)` / `.load(...)` / `.full_load(...)` attribute
    call -- e.g. `yaml.compose` or a hand-rolled parser -- is out of scope.

Fails OPEN and SILENT on any parse trouble (unreadable payload, a `-c`
script that is not valid Python, an unresolvable heredoc), matching every
other advisory hook here.
"""
import ast
import json
import re
import shlex
import sys

# `<`/`>` are included so a redirect target (`cat foo > bar.py`) never
# glues onto the command word as an ordinary argument. `\n` is included so
# an UNQUOTED physical newline -- a command boundary in bash exactly like
# `;` -- separates two simple commands instead of letting the second
# command's word run onto the first one's trailing argument. Without it,
# `['cat', '>', '/tmp/check.py', 'python3', '/tmp/check.py']` (two lines,
# no `;`/`&&` between them) read as ONE simple command starting with
# `cat`, and the `python3 /tmp/check.py` invocation on the second line
# was never reached at all.
_SHELL_OPS = set("();|&<>\n")

_PY_CMD_RE = re.compile(r"^python3?(\.\d+)?$")

_HEREDOC_OPEN_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")

# `> script.py` / `>> script.py`, anywhere after the heredoc opener on the
# same physical line -- the write-then-run shape.
_REDIRECT_PY_RE = re.compile(r">{1,2}\s*(\S+\.py)\b")


def _last_segment(text):
    """The final simple-command segment of TEXT, split on shell separators.

    Deliberately crude relative to `scripts/lib/shellcmd.py`'s `shlex`-based
    splitter: this only needs to answer "what command word does the heredoc
    attach to", not to dequote or handle nested quoting, and the heredoc
    opener itself can never appear inside a quoted argument for this
    purpose (bash treats `<<` as an operator lexically, not as text).
    """
    parts = re.split(r"&&|\|\||[;|&]", text)
    return parts[-1] if parts else text


def _cmd_word(segment):
    """The basename of the first token of SEGMENT, or "" if none."""
    toks = segment.strip().split()
    if not toks:
        return ""
    return toks[0].rsplit("/", 1)[-1]


def _extract_heredocs(text):
    """[(prefix_line, suffix_line, tag, body), ...] for each heredoc in TEXT.

    Line-based rather than a single regex: a heredoc body can contain
    anything (including text that looks like a heredoc opener), so hunting
    for the literal closing tag line by line is both simpler and more
    correct than trying to express the whole construct as one pattern.

    Does not handle two heredocs opened on the same line (`cmd <<A <<B`) --
    rare, and under-detecting it is the safe direction.
    """
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        m = _HEREDOC_OPEN_RE.search(lines[i])
        if not m:
            i += 1
            continue
        tag = m.group(2)
        prefix = lines[i][: m.start()]
        suffix = lines[i][m.end():]
        close_re = re.compile(r"^[ \t]*" + re.escape(tag) + r"\s*$")
        j = i + 1
        body_lines = []
        while j < len(lines) and not close_re.match(lines[j]):
            body_lines.append(lines[j])
            j += 1
        out.append((prefix, suffix, tag, "\n".join(body_lines)))
        i = j + 1
    return out


def _blank_heredocs(text):
    """TEXT with every heredoc body (and its opener/closer) removed.

    Run before splitting the remainder into simple commands, so a heredoc
    body's own content -- which can contain `;`, `&&`, quote characters,
    anything -- cannot be mistaken for shell structure outside the heredoc.
    """
    lines = text.split("\n")
    out_lines = []
    i = 0
    while i < len(lines):
        m = _HEREDOC_OPEN_RE.search(lines[i])
        if not m:
            out_lines.append(lines[i])
            i += 1
            continue
        tag = m.group(2)
        out_lines.append(lines[i][: m.start()] + lines[i][m.end():])
        close_re = re.compile(r"^[ \t]*" + re.escape(tag) + r"\s*$")
        j = i + 1
        while j < len(lines) and not close_re.match(lines[j]):
            j += 1
        i = j + 1
    return "\n".join(out_lines)


def _simple_commands(text):
    """Simple-command argv lists in TEXT (heredoc-free), or [] on parse error.

    A bare newline is a command separator in bash exactly like `;`, but by
    default `shlex` classifies it as ordinary whitespace and swallows it
    silently -- which loses the boundary between two commands on
    consecutive lines with no `;`/`&&` between them, so a `python3 ...`
    invocation sitting on its own line after an unrelated command is never
    reached at all.

    Declaring `\\n` a punctuation character AND removing it from
    `whitespace` (rather than rewriting it to `;` in the raw text first,
    the idiom other hooks in this repo use) makes `shlex` emit it as its
    own token wherever it appears UNQUOTED, while its quote state machine
    still keeps every newline INSIDE a quoted token (a multi-line `-c`
    script argument, say) as literal content. A text-level rewrite cannot
    make that distinction, since it runs before `shlex` has any notion of
    what is quoted -- and this hook's ordering check (a key assertion must
    have a STRICTLY LATER line number than the load call) depends on a
    `-c` argument's internal line numbers staying real.
    """
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars="();<>|&\n")
        lex.whitespace = lex.whitespace.replace("\n", "")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return []
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _dash_c_scripts(text):
    """Script text passed via a bare `python`/`python3` `-c`/`-e` in TEXT."""
    out = []
    for argv in _simple_commands(_blank_heredocs(text)):
        if not argv:
            continue
        i = 0
        while i < len(argv) and re.match(r"^[A-Za-z_]\w*=", argv[i]):
            i += 1
        rest = argv[i:]
        if not rest or not _PY_CMD_RE.match(rest[0].rsplit("/", 1)[-1]):
            continue
        j = 1
        while j < len(rest):
            arg = rest[j]
            if arg == "-c" and j + 1 < len(rest):
                out.append(rest[j + 1])
                j += 2
                continue
            if arg.startswith("-c") and len(arg) > 2:
                out.append(arg[2:])
                j += 1
                continue
            j += 1
    return out


def _runs_file(whole_text, filename):
    """True if WHOLE_TEXT (heredoc-blanked) invokes python on FILENAME."""
    base = filename.rsplit("/", 1)[-1]
    for argv in _simple_commands(_blank_heredocs(whole_text)):
        if not argv:
            continue
        i = 0
        while i < len(argv) and re.match(r"^[A-Za-z_]\w*=", argv[i]):
            i += 1
        rest = argv[i:]
        if not rest or not _PY_CMD_RE.match(rest[0].rsplit("/", 1)[-1]):
            continue
        for a in rest[1:]:
            if a in (filename, base) or a.rsplit("/", 1)[-1] == base:
                return True
    return False


def extract_executed_python(command):
    """All script texts COMMAND actually hands to a Python interpreter.

    Covers three shapes: a `-c`/`-e` inline argument, a heredoc piped
    straight to python's stdin (`python3 <<'PY' ... PY`, with or without a
    leading `-`), and a heredoc that writes a `.py` file the same command
    later executes. A heredoc that merely writes a non-`.py` file, or is
    never executed at all, contributes nothing -- see the module docstring's
    "prose vs. code" distinction.
    """
    scripts = list(_dash_c_scripts(command))

    for prefix, suffix, _tag, body in _extract_heredocs(command):
        redirect = _REDIRECT_PY_RE.search(suffix)
        if redirect:
            if _runs_file(command, redirect.group(1)):
                scripts.append(body)
            continue
        seg = _last_segment(prefix)
        if _PY_CMD_RE.match(_cmd_word(seg)):
            scripts.append(body)

    return scripts


LOAD_FUNCS = {"safe_load", "load", "full_load"}


def _is_yaml_load_call(node):
    """True if NODE is a `<name>.safe_load(...)`/`.load(...)`/`.full_load(...)`
    call, or a bare `safe_load(...)` etc. from `from yaml import safe_load`.
    """
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Attribute) and f.attr in LOAD_FUNCS:
        return True
    if isinstance(f, ast.Name) and f.id in LOAD_FUNCS:
        return True
    return False


def _is_add_constructor_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_constructor"
    )


def _is_key_assertion(node):
    """True if NODE asserts something about a mapping's keys or their count.

    Deliberately narrow on the `in` case: only a membership TEST
    (`ast.Compare` with an `In` op, e.g. `if 'with' in job:`) counts, never
    an `ast.For` (`for k in d:`) -- iterating a dict says nothing about
    whether a specific key is present or how many there are.
    """
    if isinstance(node, ast.Assert):
        return True
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "keys":
            return True
        if isinstance(f, ast.Name) and f.id == "len":
            return True
    if isinstance(node, ast.Compare):
        if any(isinstance(op, ast.In) for op in node.ops):
            return True
        if any(isinstance(op, ast.Eq) for op in node.ops):
            for comparator in node.comparators:
                if (isinstance(comparator, ast.Call)
                        and isinstance(comparator.func, ast.Name)
                        and comparator.func.id == "set"):
                    return True
    return False


def find_blind_verification(script_text):
    """The (load_lineno, assert_lineno) pair if SCRIPT_TEXT is a
    duplicate-key-blind key check; None otherwise (including on a syntax
    error, or when a custom constructor already guards the parse).
    """
    if "yaml" not in script_text:
        return None  # cheap gate before paying for a parse
    try:
        tree = ast.parse(script_text)
    except SyntaxError:
        return None

    nodes = list(ast.walk(tree))

    if any(_is_add_constructor_call(n) for n in nodes):
        return None  # already guarded -- the fix this hook recommends

    # Position is a (lineno, col_offset) PAIR, not a bare line number.
    #
    # Python gives every statement on one physical line the same lineno, so a
    # semicolon-joined one-liner puts the load and the assertion at the same
    # lineno, and a `<=` test on lineno alone discards the assertion entirely.
    # That silently missed the incident's own check restated as the one-liner a
    # shell command naturally reaches for:
    #
    #   python3 -c "import yaml; job = yaml.safe_load(open('f.yml'));
    #               print(isinstance(job.get('with'), dict)
    #                     and len(job['with']) >= 1)"
    #
    # Measured: the load call sits at (1, 17) and the assertion at (1, 44), so
    # comparing the pair orders them correctly. It changes nothing in the
    # multi-line case, where the linenos already differ and the column is never
    # reached.
    load_pos = None
    for n in nodes:
        if _is_yaml_load_call(n):
            pos = (getattr(n, "lineno", 0), getattr(n, "col_offset", 0))
            if load_pos is None or pos < load_pos:
                load_pos = pos
    if load_pos is None:
        return None

    for n in nodes:
        pos = (getattr(n, "lineno", 0), getattr(n, "col_offset", 0))
        if pos <= load_pos:
            continue
        if _is_key_assertion(n):
            return (load_pos[0], pos[0])

    return None


NOTE = (
    "This command parses YAML with a non-strict loader "
    "(`yaml.safe_load`/`load`/`full_load`) and then checks something about "
    "the parsed mapping's keys or their count -- but PyYAML's default "
    "constructors silently keep the LAST of any duplicate mapping key, so "
    "that combination cannot detect a duplicate-key defect: the duplicate "
    "is already gone by the time either check runs.\n\n"
    "gha#839: a sweep asking which caller stubs had a commented `with:` "
    "block that would uncomment into a DUPLICATE key used exactly this "
    "shape (`isinstance(job.get('with'), dict) and len(job['with']) >= 1`) "
    "and reported 1 broken file. The true count, under a duplicate-"
    "rejecting loader, was 5. When an instrument's pass condition is "
    "satisfiable by the defect it exists to detect, a green result from it "
    "is not evidence.\n\n"
    "If duplicate keys are what you are looking for, install a duplicate-"
    "rejecting constructor instead:\n\n"
    "    class Strict(yaml.SafeLoader): pass\n"
    "    def _nodup(loader, node, deep=False):\n"
    "        seen = set()\n"
    "        for k, _ in node.value:\n"
    "            key = loader.construct_object(k, deep=deep)\n"
    "            if key in seen:\n"
    "                raise yaml.YAMLError(f\"duplicate key {key!r}\")\n"
    "            seen.add(key)\n"
    "        return yaml.SafeLoader.construct_mapping(loader, node, deep)\n"
    "    Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, "
    "_nodup)\n\n"
    "If duplicates genuinely are not the concern here, disregard this."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") not in ("Bash", "bash", "run_command",
                                         "execute_command", "terminal",
                                         "shell"):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = (tool_input.get("command") or tool_input.get("CommandLine")
               or tool_input.get("cmd") or tool_input.get("script"))
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        scripts = extract_executed_python(command)
    except Exception:
        return 0

    for script in scripts:
        try:
            hit = find_blind_verification(script)
        except Exception:
            hit = None
        if hit:
            out = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": NOTE,
                },
                "systemMessage": (
                    "yaml.safe_load/load/full_load is non-strict and keeps "
                    "the LAST of duplicate keys, so this key-presence/count "
                    "check cannot detect a duplicate-key defect (gha#839). "
                    "Use a duplicate-rejecting constructor if that is what "
                    "you are checking for."
                ),
            }
            print(json.dumps(out))
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
