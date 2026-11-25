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
  - `cat`, `echo` or `printf` overwriting a file with `>`, or `tee FILE` fed
    by a heredoc, echo or printf (use Write). `/dev/...` targets pass.

Passes: a pipeline with any other program in it (`git log | head`), output
redirected into a file from a reader, an append (`>>`, `tee -a`), which Write
cannot do, a search whose exit status is used (`-q`, `-s`, output to
/dev/null, or `&&`/`||` after it), operands or redirect targets holding `$`
or a backtick, commands under `if`/`do`/`then`/... and any `case` statement,
`sudo`, quoted mentions and heredoc bodies, and `ls`/`wc`, which have no
exact tool. `ALLOW_BASH_OVER_TOOL=1` written as a prefix of the command
itself (not an `export`) covers a real need, such as one edit across many
files or a byte count, and the reply says why. Fails open on a parse error
or a missing `scripts/lib/shellcmd.py`.
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
REDIRECT_TOKEN = re.compile(r"^(?=.*[<>])[<>&|]{1,3}-?$")
QUIET_FLAGS = {"-q", "--quiet", "-s", "--silent", "--no-messages"}

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
            if tok in ("<<", "<<-"):
                # The tokenizer drops a heredoc's delimiter word with its body,
                # so nothing follows `<<` to consume (`cat <<EOF > f`).
                redirects.append((tok, ""))
                i += 1
                continue
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


def _overwrites_literal(redirects):
    """True when a redirect overwrites (not appends to) a literally named file.

    Write replaces a whole file, so an append (`>>`) has no exact tool, and a
    `$`-expanded target names a file the tool call cannot spell.
    """
    writes = [(op, t) for op, t in redirects
              if ">" in op and not op.endswith("&") and not t.startswith("/dev/")]
    return bool(writes) and all(">>" not in op and not _dynamic([t]) for op, t in writes)


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


def _pipeline_kind(stages, status_used=False):
    """The tool kind a pipeline should have used, or None.

    `status_used` is True when `&&` or `||` follows the pipeline, so its exit
    status steers the shell; no tool returns one, so a search there passes.
    """
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
        if _dynamic(words) or not _overwrites_literal(redirects):
            return None
        if prog != "cat" or not words or _stdin_is_data(redirects):
            return "write"
        return None
    if prog in ("cat", "echo", "printf", "tee") and parsed[-1][0] == "tee":
        tee_args = parsed[-1][1]
        tee_files = [w for w in tee_args if not w.startswith("-")]
        appends = any(w in ("-a", "--append") for w in tee_args)
        fed = prog in ("echo", "printf") or _stdin_is_data(redirects)
        if fed and tee_files and not appends and len(parsed) <= 2 \
                and not any(f.startswith("/dev/") for f in tee_files) \
                and not _dynamic(tee_files) and not _dynamic(words):
            return "write"
    literal = [w for w in words if not (prog == "sed" and SED_PRINT_RANGE.match(w))]
    if _dynamic(literal) or _dynamic([t for _op, t in redirects]):
        return None
    kind = _reader_kind(prog, words, redirects)
    if kind is None:
        return None
    to_null = any(">" in op and t == "/dev/null" for op, t in redirects)
    if kind == "search" and (status_used or to_null or QUIET_FLAGS & set(words)):
        return None
    for later, later_words, later_redirects, _e in parsed[1:]:
        if later not in FILTERS or _writes_file(later_redirects):
            return None
        if later == "cat" and later_words:
            return None
    return kind


def pipelines(command):
    """Each top-level pipeline as `(stages, status_used)`; None on a parse error.

    `stages` is a list of argv lists, and `status_used` is True when `&&` or
    `||` follows the pipeline. A pipeline that opens inside `$(...)` is
    dropped: its output feeds another command, which no tool call replaces.
    A command holding a `case` statement is skipped whole, since its `)`
    pattern ends look like subshell closes to the tokenizer.
    """
    toks = shell_tokens(command)
    if toks is None or "case" in toks:
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
                out.append((stages, tok.lstrip(")").startswith(("&&", "||"))))
            stages = []
            skip = "(" in tok and prev.endswith("$")
            prev = tok
            continue
        cur.append(tok)
        prev = tok
    if cur:
        stages.append(cur)
    if stages and not skip:
        out.append((stages, False))
    return out


def offending(command):
    """The tool kind for the first pipeline a dedicated tool covers, or None."""
    for stages, status_used in pipelines(command) or []:
        kind = _pipeline_kind(stages, status_used)
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
        f"checks, renders, running scripts. Only if the tool cannot do this, start the command "
        f"itself with `{OVERRIDE}=1 ` and say why."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
