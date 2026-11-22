#!/usr/bin/env python3
"""PreToolUse (Bash): read, search and write files with the dedicated tools.

ai-config#6065 (Ezra, 2026-11-21: "can you use tools instead of bash"). A
Bash call can stop on an approval prompt, which Ezra answers from his phone;
Read, Grep, Glob, Edit and Write never do. DENIES, in every session:

  - a pipeline whose first stage reads or searches files and whose every
    later stage only filters text: `cat FILE` (no flags), `head`/`tail FILE`
    (no -f, -F, -c), `grep`/`egrep`/`fgrep`/`rg`, `sed -n 'N,Mp' FILE`, and a
    `find` using only -name, -iname, -path, -ipath, -type f and -print;
    later stages may be head, tail, grep, egrep, fgrep, rg or cat;
  - `sed -i`/`--in-place` and `perl -i`, at any stage (use Edit);
  - `cat`, `echo` or `printf` redirected into a file, or `tee FILE` fed by a
    heredoc, echo or printf (use Write). `/dev/...` targets pass.

Passes: a pipeline with any other program in it (`git log | head`), output
redirected into a file from a reader, operands holding `$` or a backtick,
commands under `if`/`do`/`then`/... (shell control flow), `sudo`, quoted
mentions and heredoc bodies, and `ls`/`wc`, which have no exact tool.
`ALLOW_BASH_OVER_TOOL=1` before the command covers a real need (a bulk edit
over many files, a byte count) and the reply says why. Fails open on a parse
error or a missing `scripts/lib/shellcmd.py`.
"""
import json
import os
import re
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from shellcmd import is_operator_token, shell_tokens, strip_env
except ImportError as exc:
    print(f"prefer-dedicated-tools-over-bash: cannot load scripts/lib/shellcmd.py ({exc}); "
          "not gating", file=sys.stderr)
    shell_tokens = None

OVERRIDE = "ALLOW_BASH_OVER_TOOL"
SEARCHERS = {"grep", "egrep", "fgrep", "rg"}
FILTERS = SEARCHERS | {"head", "tail", "cat"}
CONTROL_WORDS = {"if", "then", "else", "elif", "do", "while", "until", "for", "case",
                 "{", "!", "time", "function"}
FIND_VALUE_PREDICATES = {"-name", "-iname", "-path", "-ipath"}
HEAD_VALUE_FLAGS = {"-n", "--lines"}
SED_PRINT_RANGE = re.compile(r"^(?:\d{1,9}|\$)(?:,(?:\d{1,9}|\$))?p$")
REDIRECT_TOKEN = re.compile(r"^[<>&]{1,3}-?$")

TOOLS = {
    "read": "the Read tool (offset and limit select lines)",
    "search": "the Grep tool (output_mode, -n, -C, glob, head_limit)",
    "glob": "the Glob tool",
    "edit": "the Edit tool (replace_all for a repeated string)",
    "write": "the Write tool",
}


def _split_args(args):
    """`(operands, redirects)`: plain words, and `(operator, target)` pairs."""
    operands, redirects, i = [], [], 0
    while i < len(args):
        tok = args[i]
        if REDIRECT_TOKEN.match(tok):
            if operands and operands[-1].isdigit():
                operands.pop()  # `2>`: the digit is a file descriptor
            target = args[i + 1] if i + 1 < len(args) else ""
            redirects.append((tok, target))
            i += 2
            continue
        operands.append(tok)
        i += 1
    return operands, redirects


def _writes_file(redirects):
    """True when a redirect writes into a file other than a /dev path or an fd."""
    for op, target in redirects:
        if ">" in op and not op.endswith("&") and not target.startswith("/dev/"):
            return True
    return False


def _stdin_is_data(redirects):
    """True when stdin is a heredoc or here-string, not a file."""
    return any(op.startswith("<<") for op, _ in redirects)


def _dynamic(words):
    return any("$" in w or "`" in w for w in words)


def _sed_in_place(words):
    for w in words:
        if w == "--in-place" or w.startswith("--in-place="):
            return True
        if w.startswith("-") and not w.startswith("--"):
            for ch in w[1:]:
                if ch == "i":
                    return True
                if ch in "efl":
                    break
    return False


def _perl_in_place(words):
    for w in words:
        if w.startswith("-") and not w.startswith("--"):
            for ch in w[1:]:
                if ch == "i":
                    return True
                if ch not in "pnawsTtUWXc":
                    break
    return False


def _sed_reads(words):
    """True for `sed -n 'N,Mp' FILE...`."""
    quiet, script, files = False, None, []
    it = iter(words)
    for w in it:
        if w in ("-n", "--quiet", "--silent"):
            quiet = True
        elif w in ("-e", "--expression"):
            if script is not None:
                return False
            script = next(it, "")
        elif w.startswith("-"):
            return False
        elif script is None:
            script = w
        else:
            files.append(w)
    return quiet and bool(files) and bool(script) and bool(SED_PRINT_RANGE.match(script))


def _find_globs(words):
    """True for a `find` that only matches names, which Glob covers."""
    it = iter(words)
    seen_predicate = False
    for w in it:
        if w in FIND_VALUE_PREDICATES:
            if next(it, None) is None:
                return False
            seen_predicate = True
        elif w == "-type":
            if next(it, None) != "f":
                return False
        elif w == "-print":
            continue
        elif w.startswith("-") or w in ("!", "(", ")"):
            return False
        elif seen_predicate:
            return False
    return seen_predicate


def _reader_kind(prog, words, redirects):
    """The tool kind for a first-stage file reader, or None."""
    if _writes_file(redirects) or _stdin_is_data(redirects):
        return None
    if prog == "cat":
        if any(w.startswith("-") for w in words):
            return None
        return "read" if words or any(op == "<" for op, _ in redirects) else None
    if prog in ("head", "tail"):
        files, it = [], iter(words)
        for w in it:
            if w in HEAD_VALUE_FLAGS:
                next(it, None)
            elif w.startswith("-c") or w.startswith("--bytes") or w in ("-f", "-F") \
                    or w.startswith("--follow"):
                return None
            elif not w.startswith("-"):
                files.append(w)
        return "read" if files or any(op == "<" for op, _ in redirects) else None
    if prog in SEARCHERS:
        return "glob" if prog == "rg" and "--files" in words else "search"
    if prog == "sed" and _sed_reads(words):
        return "read"
    if prog == "find" and _find_globs(words):
        return "glob"
    return None


def _stage(argv):
    """`(prog, words, redirects, env)` for one pipeline stage, or None to pass."""
    env, rest = strip_env(argv)
    if not rest or len(argv) - len(rest) > len(env):
        return None  # empty, or behind a wrapper such as sudo
    if rest[0] in CONTROL_WORDS:
        return None
    words, redirects = _split_args(rest[1:])
    return os.path.basename(rest[0]), words, redirects, env


def _pipeline_kind(stages):
    """The tool kind a pipeline should have used, or None."""
    parsed = [_stage(argv) for argv in stages]
    if any(p is None for p in parsed):
        return None
    if any(e.startswith(OVERRIDE + "=") for p in parsed for e in p[3]):
        return None
    for prog, words, redirects, _env in parsed:
        if prog == "sed" and _sed_in_place(words) and not _dynamic(words):
            return "edit"
        if prog == "perl" and _perl_in_place(words) and not _dynamic(words):
            return "edit"
    prog, words, redirects, _env = parsed[0]
    if prog in ("cat", "echo", "printf") and len(parsed) == 1 and _writes_file(redirects):
        if _dynamic(words):
            return None
        if prog != "cat" or not words or _stdin_is_data(redirects):
            return "write"
        return None
    if prog in ("cat", "echo", "printf", "tee") and parsed[-1][0] == "tee":
        tee_files = [w for w in parsed[-1][1] if not w.startswith("-")]
        fed = prog in ("echo", "printf") or _stdin_is_data(redirects)
        if fed and tee_files and not any(f.startswith("/dev/") for f in tee_files) \
                and len(parsed) <= 2 and not _dynamic(tee_files):
            return "write"
    if _dynamic(words):
        return None
    kind = _reader_kind(prog, words, redirects)
    if kind is None:
        return None
    for later, _w, later_redirects, _e in parsed[1:]:
        if later not in FILTERS or _writes_file(later_redirects):
            return None
    return kind


def pipelines(command):
    """Each top-level pipeline as a list of argv stages; None on a parse error.

    A pipeline that opens inside `$(...)` is dropped: its output feeds another
    command, which no tool call replaces.
    """
    toks = shell_tokens(command)
    if toks is None:
        return None
    out, stages, cur, skip, prev = [], [], [], False, ""
    for tok in toks:
        if is_operator_token(tok):
            if cur:
                stages.append(cur)
                cur = []
            if tok in ("|", "|&"):
                prev = tok
                continue
            if stages and not skip:
                out.append(stages)
            stages = []
            skip = "(" in tok and prev.endswith("$")
            prev = tok
            continue
        cur.append(tok)
        prev = tok
    if cur:
        stages.append(cur)
    if stages and not skip:
        out.append(stages)
    return out


def offending(command):
    """The tool kind for the first pipeline a dedicated tool covers, or None."""
    for stages in pipelines(command) or []:
        kind = _pipeline_kind(stages)
        if kind:
            return kind, " | ".join(" ".join(s) for s in stages)
    return None


def main() -> int:
    if shell_tokens is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    inp = payload.get("tool_input")
    command = inp.get("command") if isinstance(inp, dict) else None
    if not isinstance(command, str):
        return 0
    try:
        hit = offending(command)
    except Exception as exc:
        print(f"prefer-dedicated-tools-over-bash: {type(exc).__name__}: {exc}; not gating",
              file=sys.stderr)
        return 0
    if not hit:
        return 0
    kind, what = hit
    if len(what) > 120:
        what = what[:117] + "..."
    reason = (
        f"[hook: prefer-dedicated-tools-over-bash] `{what}` is file work that {TOOLS[kind]} "
        "does without an approval prompt (Ezra, 2026-11-21: \"can you use tools instead of "
        "bash\"; ai-config#6065). Use the tool. Keep Bash for what no tool does: git, "
        f"checks, renders, running scripts. Only if the tool cannot do this, prefix `{OVERRIDE}=1` "
        "and say why."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
