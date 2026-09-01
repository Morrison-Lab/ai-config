#!/usr/bin/env python3
"""PreToolUse guard: a staged value edit whose neighbouring comment still
asserts the OLD value.

## The incident

On `ucdavis/bcs#679` (2026-08-20), `data-raw/ab507bs-imp.sbatch` had its
concurrency cap raised:

    -#SBATCH --array=1-25%6
    +#SBATCH --array=1-25%20

Four comment lines sat directly above it, untouched by the same edit:

    # Cap concurrent tasks at 6 (%6): each task needs 32G, so 6 running at once
    # already claims 192G, and capping bounds simultaneous network-FS I/O to the
    # setup/output .rds files -- an unbounded array here previously drained a
    # node with an unkillable process stuck on network I/O.

Only the directive line was edited. The comment was never read. So it still
said 6, its arithmetic (192G) was now wrong by a factor of more than three,
and -- the part that made it a finding rather than a nit -- it recorded a
PRIOR INCIDENT that was the whole reason the cap existed. A reviewer caught
the contradiction and returned "Needs more work".

## Why a hook rather than a rule

The corpus already carries the rule in three scoped forms: `memories/
preferences.md` says to grep both code and comments when renaming a concept,
`skills/simplify` calls a vestigial comment worse than no comment, and
`skills/check-dependency-updates` says a stale comment beside a fresh SHA is
its own bug. None of them fired here, because none is about editing a VALUE,
and all three are read at a moment other than the one where the edit happens.

The condition, by contrast, is decidable from the diff alone, with no
semantics: a literal disappears from a changed line, and an unchanged comment
line nearby still contains it. Per `shared/workflow/algorithmatize-checks.md`
that belongs in an instrument rather than in anyone's care.

## Why this warns rather than blocks

A comment that quotes a historical value is legitimate and common -- a
changelog line, a "was 6 until 2026-08" note, a docstring citing a prior
default, or this very file's docstring, which quotes `%6` while the value it
describes is `%20`. The hook cannot tell those from a stale assertion, so it
only ever ADDS context (`additionalContext` plus a `systemMessage`), never a
`permissionDecision`. Per README's "A hook that misfires is worse than a
missing one", a blocking form here would refuse a large class of correct
commits and get switched off.

## The match condition

  M1  the tool is `Bash` and the command contains a `git commit` invocation
      (after skipping env assignments and lead words), excluding forms that
      commit nothing new: `--amend --no-edit` is still included, since it
      re-commits the same tree
  M2  the diff examined is `git diff --cached -U{WINDOW}`, or `git diff HEAD
      -U{WINDOW}` when the commit carries `-a`/`--all`, so what is checked is
      exactly what the commit will record
  M3  within one hunk, OLD literals are those appearing on removed (`-`)
      lines and on NO added (`+`) line of that hunk -- a value that went away
  M4  a literal is narrow by construction: a number, a short or long flag, or
      the contents of a quoted string at least {MIN_QUOTED} characters long.
      Bare words, identifiers, and unquoted paths are NOT literals, because
      matching those floods the report
  M5  the comment lines searched are CONTEXT lines only (unchanged by this
      diff) whose first non-space run is a comment marker for that file's
      extension, within {WINDOW} displayed hunk lines of the changed line
  M6  a match is an OLD literal found in such a comment on a word boundary,
      and not as part of a longer number or identifier

Fails OPEN on any parse trouble, on `git diff` failing or timing out, and
outside a git repository -- consistent with every other guard here.

## CLI mode

Called with arguments, this reads a unified diff instead of hook JSON, so the
same detector can run as a pre-push or CI check:

    git diff -U10 origin/main...HEAD | python3 flag-stale-adjacent-comment.py -
    python3 flag-stale-adjacent-comment.py path/to/saved.diff

It exits 0 when it finds nothing and 1 when it finds something, so a caller
that WANTS a gate can have one while the hook stays advisory.
"""
import json
import os
import re
import shlex
import subprocess
import sys

WINDOW = 10
MIN_QUOTED = 3
MAX_REPORTED = 12

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {"then", "do", "else", "!", "time", "sudo", "command", "exec",
              "nohup", "env"}
_SHELL_OPS = set("();|&")
RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

# M4: the three literal classes. Deliberately narrow -- see the docstring.
RX_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
RX_FLAG = re.compile(r"(?<![\w-])--?[A-Za-z][\w-]*")
RX_QUOTED = re.compile(r"'([^'\n]*)'|\"([^\"\n]*)\"")

# M5: comment markers by file extension. The default set omits `--`, which
# would read a context line beginning `--array=...` as a comment.
_HASH = ("#",)
_SLASH = ("//", "/*", "*")
COMMENT_MARKERS = {
    ".py": _HASH, ".sh": _HASH, ".bash": _HASH, ".zsh": _HASH,
    ".sbatch": _HASH, ".slurm": _HASH,
    ".r": _HASH,
    # .Rmd/.qmd are Markdown-derived: outside an R code chunk `#` starts a
    # HEADING, not a comment, so mapping them to _HASH reproduces exactly
    # the false positive `.md` is special-cased to avoid. Use the HTML
    # comment marker, which is the only comment form valid in their prose.
    ".rmd": ("<!--",), ".qmd": ("<!--",),
    ".yml": _HASH, ".yaml": _HASH, ".toml": _HASH, ".cfg": _HASH,
    ".ini": _HASH, ".conf": _HASH, ".pl": _HASH, ".rb": _HASH,
    ".mk": _HASH, ".dockerfile": _HASH, ".gitignore": _HASH,
    ".c": _SLASH, ".h": _SLASH, ".cc": _SLASH, ".cpp": _SLASH, ".hpp": _SLASH,
    ".js": _SLASH, ".jsx": _SLASH, ".ts": _SLASH, ".tsx": _SLASH,
    ".java": _SLASH, ".go": _SLASH, ".rs": _SLASH, ".css": _SLASH,
    ".scss": _SLASH, ".swift": _SLASH, ".kt": _SLASH,
    ".sql": ("--", "/*", "*"), ".lua": ("--",), ".hs": ("--",),
    ".tex": ("%",), ".m": ("%",),
    ".md": ("<!--",), ".html": ("<!--",), ".xml": ("<!--",),
    ".lisp": (";",), ".el": (";",), ".clj": (";",),
}
DEFAULT_MARKERS = _HASH
BASENAME_MARKERS = {"makefile": _HASH, "dockerfile": _HASH, "justfile": _HASH}


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error.

    Same construction as `flag-add-a-outside-pathspec.py`'s namesake.
    """
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = cmd.replace("\n", ";")
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
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


def commit_invocation(command):
    """M1: (argv, stages_tracked) for the first `git commit` in `command`.

    `stages_tracked` is True when `-a`/`--all` is present, which decides
    which diff M2 examines. Returns None when there is no `git commit`.
    """
    cmds = _simple_commands(command)
    if cmds is None:
        return None
    for argv in cmds:
        i = 0
        while i < len(argv) and (ASSIGNMENT.match(argv[i])
                                 or argv[i] in LEAD_WORDS):
            i += 1
        rest = argv[i:]
        if len(rest) < 2 or rest[0] != "git" or rest[1] != "commit":
            continue
        flags = [a for a in rest[2:] if a.startswith("-")]
        stages_tracked = any(
            f in ("-a", "--all") or (re.fullmatch(r"-[a-zA-Z]+", f) and "a" in f[1:])
            for f in flags
        )
        return rest, stages_tracked
    return None


def markers_for(path):
    """M5: the comment markers that apply to `path`."""
    base = os.path.basename(path).lower()
    if base in BASENAME_MARKERS:
        return BASENAME_MARKERS[base]
    ext = os.path.splitext(base)[1]
    return COMMENT_MARKERS.get(ext, DEFAULT_MARKERS)


def is_comment(line, markers):
    """True when `line`'s first non-space run is one of `markers`."""
    stripped = line.lstrip()
    if not stripped:
        return False
    return any(stripped.startswith(m) for m in markers)


def literals(line):
    """M4: the narrow literal tokens on one line of source."""
    found = set()
    for m in RX_QUOTED.finditer(line):
        val = m.group(1) if m.group(1) is not None else m.group(2)
        if val is not None and len(val) >= MIN_QUOTED:
            found.add(val)
    found.update(RX_NUMBER.findall(line))
    found.update(RX_FLAG.findall(line))
    return found


def _boundary_match(literal, text):
    """M6: `literal` occurs in `text` on a word boundary.

    A number must not be part of a longer number (so `6` does not match
    `1962`), and a flag must not be a prefix of a longer flag.
    """
    esc = re.escape(literal)
    if RX_NUMBER.fullmatch(literal):
        pattern = r"(?<![\w.])" + esc + r"(?![\w.])"
    elif literal.startswith("-"):
        pattern = r"(?<![\w-])" + esc + r"(?![\w-])"
    else:
        pattern = r"(?<!\w)" + esc + r"(?!\w)"
    return re.search(pattern, text) is not None


class Hunk:
    def __init__(self, path):
        self.path = path
        self.lines = []          # (kind, text) with kind in "+-= "

    def add(self, kind, text):
        self.lines.append((kind, text))


def parse_diff(diff_text):
    """Unified diff -> list of Hunk, keyed to the POST-image path."""
    hunks = []
    path = None
    cur = None
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            path, cur = None, None
            continue
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            if target == "/dev/null":
                path = None
            else:
                path = target[2:] if target.startswith("b/") else target
            cur = None
            continue
        if raw.startswith("@@"):
            cur = Hunk(path) if path else None
            if cur is not None:
                hunks.append(cur)
            continue
        if cur is None or not raw:
            continue
        kind, text = raw[0], raw[1:]
        if kind in ("+", "-", " "):
            cur.add(kind, text)
    return [h for h in hunks if h.path]


def findings_for_hunk(hunk):
    """Every (path, literal, changed_line, comment_line) in one hunk."""
    markers = markers_for(hunk.path)

    removed_lits, added_lits = set(), set()
    for kind, text in hunk.lines:
        if kind == "-":
            removed_lits |= literals(text)
        elif kind == "+":
            added_lits |= literals(text)
    old_lits = removed_lits - added_lits          # M3
    if not old_lits:
        return []

    changed_idx = [i for i, (k, _) in enumerate(hunk.lines) if k in ("+", "-")]
    comment_idx = [i for i, (k, t) in enumerate(hunk.lines)
                   if k == " " and is_comment(t, markers)]
    if not comment_idx:
        return []

    out, seen = [], set()
    for ci in comment_idx:
        comment = hunk.lines[ci][1]
        near = [i for i in changed_idx if abs(i - ci) <= WINDOW]   # M5
        if not near:
            continue
        for lit in sorted(old_lits):
            if not _boundary_match(lit, comment):                  # M6
                continue
            # attribute the finding to the nearest changed line carrying it
            source = None
            for i in sorted(near, key=lambda i: abs(i - ci)):
                if hunk.lines[i][0] == "-" and lit in literals(hunk.lines[i][1]):
                    source = hunk.lines[i][1]
                    break
            if source is None:
                continue
            key = (hunk.path, lit, comment.strip())
            if key in seen:
                continue
            seen.add(key)
            out.append((hunk.path, lit, source.strip(), comment.strip()))
    return out


def findings(diff_text):
    out = []
    for hunk in parse_diff(diff_text):
        out.extend(findings_for_hunk(hunk))
    return out


def _git_diff(stages_tracked):
    args = ["git", "diff", f"-U{WINDOW}"]
    args.append("HEAD" if stages_tracked else "--cached")
    try:
        # errors="replace" is load-bearing, not tidiness. This is the first
        # guard in the family to pipe raw file CONTENT through text=True
        # (the siblings read only git-quote-escaped `git status` paths), so
        # a staged non-UTF-8 byte would raise UnicodeDecodeError -- a
        # ValueError, which the except below does not catch -- and crash the
        # hook, breaking the fail-open guarantee the docstring promises.
        out = subprocess.run(args, capture_output=True, text=True,
                             timeout=10, errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


NOTE = (
    "This commit changes {count} literal value(s) while leaving a nearby "
    "comment that still asserts the OLD value:\n\n{items}\n\n"
    "On `ucdavis/bcs#679` an `--array=1-25%6` cap was raised to `%20` and the "
    "four comment lines above it kept saying 6 -- so the comment's arithmetic "
    "was wrong AND it still recorded the prior incident that had motivated the "
    "cap. A reviewer returned \"Needs more work\".\n\n"
    "Read each comment above and either update it or confirm it is quoting the "
    "value historically on purpose (a changelog line, a \"was N until ...\" "
    "note), which is a real and common false positive for this check."
)


def _format(items):
    shown = items[:MAX_REPORTED]
    blocks = []
    for path, lit, source, comment in shown:
        blocks.append(
            f"  {path}\n"
            f"    changed away from `{lit}`:  {source}\n"
            f"    comment still says `{lit}`: {comment}"
        )
    text = "\n".join(blocks)
    if len(items) > len(shown):
        text += f"\n  ... and {len(items) - len(shown)} more"
    return text


def run_cli(argv):
    """Read a unified diff from a file or stdin; exit 1 on any finding."""
    target = argv[0]
    try:
        if target == "-":
            # Same reason as the two reads above: a diff can carry non-UTF-8
            # bytes, and strict decoding turns that into a traceback rather
            # than a verdict. Reconfigure rather than re-wrap, since stdin is
            # already an open text stream by the time we get it.
            sys.stdin.reconfigure(errors="replace")
            diff_text = sys.stdin.read()
        else:
            diff_text = open(target, errors="replace").read()
    except OSError as exc:
        print(f"flag-stale-adjacent-comment: cannot read {target} ({exc})",
              file=sys.stderr)
        return 2
    items = findings(diff_text)
    if not items:
        print("flag-stale-adjacent-comment: no stale adjacent comments found")
        return 0
    print(NOTE.format(count=len(items), items=_format(items)))
    return 1


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
        if is_dry_run:
            print(f"flag-stale-adjacent-comment: unreadable hook input ({exc})",
                  file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    if len(sys.argv) > 1 and not any(a in ("--dry-run", "--simulate") for a in sys.argv[1:]):
        return run_cli(sys.argv[1:])

    payload, is_dry_run = _read_payload()
    if not payload and not is_dry_run:
        try:
            payload = json.load(sys.stdin)
        except Exception as exc:  # fail open, but say so
            print(f"flag-stale-adjacent-comment: unreadable hook input ({exc})",
                  file=sys.stderr)
            return 0

    if not payload:
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0
    inp = payload.get("tool_input") or {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        hit = commit_invocation(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-stale-adjacent-comment: could not parse command ({exc})",
              file=sys.stderr)
        return 0
    if hit is None:
        return 0
    _argv, stages_tracked = hit

    diff_text = _git_diff(stages_tracked)
    if not diff_text:
        return 0  # nothing staged, not a repo, or git unreachable -- fail open

    try:
        items = findings(diff_text)
    except Exception as exc:
        print(f"flag-stale-adjacent-comment: could not parse diff ({exc})",
              file=sys.stderr)
        return 0
    if not items:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(count=len(items),
                                             items=_format(items)),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"{len(items)} nearby comment(s) still assert a value this commit "
            "changed."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
