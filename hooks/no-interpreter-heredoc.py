#!/usr/bin/env python3
"""PreToolUse guard: a heredoc carries script text to an interpreter.

## The gap this closes

CLAUDE.md's "Tool transport collapses doubled backslashes" says the default is
not to carry content in a heredoc at all: write the script with the Write tool
to a scratchpad file and run it by path.
`hooks/warn-heredoc-doubled-backslash.py` backs that with a WARNING, and only
for a doubled backslash. A warning did not change behaviour: measured
2026-10-05 in a Morrison-Lab/psw session, the agent fed `python - <<'EOF'`
heredocs about 15 times despite the rule and the warnings, and one of them
silently turned `\\frac` in a LaTeX formula into a form feed plus `rac`. It
was caught only by reading the written file back (ai-config#4298).

## What it REFUSES

A command where a heredoc body is the SCRIPT an interpreter reads from stdin
(`python`, `python3`, `py`, `node`, `Rscript`, `perl`, `ruby`, and `bash`/`sh`
and kin) AND the body contains a backslash or a backtick. Those are the two
characters that transport and shell layers rewrite, and the remedy -- the
Write tool, then run the path -- is always available and costs one call, so a
refusal is always satisfiable (the same test `no-clobbering-push.py` applies
to its bare `--force` refusal).

It stays silent on everything else, and in particular on a heredoc fed to a
non-interpreter (`cat <<EOF > file`, `git commit -F - <<EOF`): that case
keeps the warn-only behaviour of `warn-heredoc-doubled-backslash.py`, which
this hook leaves in place and which also still fires on an interpreter
heredoc (the deny wins).

## What counts as "fed to an interpreter"

The OPENER LINE (the line the `<<DELIM` sits on) is tokenized, and split into
simple commands on `&& || ; | ( )`. A command counts when its program is an
interpreter and the interpreter reads its SCRIPT from stdin: the argument `-`
is present, or there is no positional argument once redirections
(`> out`, `2>&1`) are set aside. So `python3 - <<EOF`, `python3 <<EOF > out`,
`cat <<EOF | python3 -`, and `bash -s <<EOF` count, while
`python3 script.py <<EOF` and `python3 -c "..." <<EOF` do not -- a script
path or inline code is itself a positional argument, and there the heredoc
is data, not code.

Known gaps, accepted rather than hidden:

  * `cat > x.py <<EOF ... EOF` followed by `python x.py` in the same command
    writes a script through a heredoc without feeding an interpreter on the
    opener line. Only the doubled-backslash warning covers it.
  * An interpreter option that takes a value (`python -W ignore <<EOF`) makes
    the value read as a positional script argument, so the heredoc is judged
    data and passes.
  * The opener is found with `scripts/lib/shellcmd.py`'s quote-blind
    `RX_HEREDOC_OPEN`, so a `<<` inside a quoted string on a line that also
    runs an interpreter is read as a heredoc opener (a false deny costs one
    retry with the override, per README's "a hook that misfires is worse than
    a missing one" -- the interpreter-on-the-line requirement is what keeps
    this rare). The denial can then name the wrong delimiter
    (`python3 -c "print(1<<2)" - <<EOF` names `2`).
  * Launchers and interpreters outside the lists in this file (`deno run -`,
    `docker run -i img python -`, a `{ ... }` group's own options) pass, as
    does a here-string (`python3 - <<< "..."`), which is not a heredoc body.

## Override

`ALLOW_INTERPRETER_HEREDOC=1`, as a real leading env assignment on a command
of the opener line that runs the interpreter
(`ALLOW_INTERPRETER_HEREDOC=1 python3 - <<'EOF'`), or in
the hook's own environment. A mention of the string elsewhere in the command
does not count, so a command that merely documents the override cannot
disarm the guard. It exists for a case this guard did not foresee, and using
it means saying why.

Fails OPEN on any parse trouble, same as every guard here.
"""
import importlib.util
import json
import os
import re
import shlex
import sys

OVERRIDE = "ALLOW_INTERPRETER_HEREDOC"

_HERE = os.path.dirname(os.path.realpath(__file__))
_LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")


def _load_heredoc_parser():
    """Import the body parser from the sibling warn hook rather than copy it.

    That module's `_heredoc_bodies` already handles quoted/unquoted and `<<-`
    delimiters, several heredocs on one opener line, and here-strings, and
    itself reuses `scripts/lib/shellcmd.py`'s `RX_HEREDOC_OPEN`.
    """
    path = os.path.join(_HERE, "warn-heredoc-doubled-backslash.py")
    spec = importlib.util.spec_from_file_location("_warn_heredoc", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import RX_HEREDOC_OPEN
    _PARSER = _load_heredoc_parser()
except Exception as _exc:  # broken install; fail open and say so
    print(f"no-interpreter-heredoc: cannot load the heredoc parser "
          f"({_exc}); not evaluating", file=sys.stderr)
    RX_HEREDOC_OPEN = None
    _PARSER = None

_INTERPRETER = re.compile(
    r"^(python[0-9.]*|pypy[0-9.]*|py|node|nodejs|r|rscript|perl|ruby|php"
    r"|pwsh|bash|sh|zsh|dash|ksh)$")
_REDIRECT_ONLY = re.compile(r"^[0-9]*[<>]+&?$")
_REDIRECT_WITH_TARGET = re.compile(r"^[0-9]*[<>]+&?[^<>]+$")
_WRAPPERS = {"sudo", "env", "command", "exec", "time", "nohup", "nice",
             "timeout", "uv", "poetry", "pipx", "run", "{", "!"}
# options of a wrapper that take a VALUE as the next token (`sudo -u bob`)
_WRAPPER_VALUE_OPTS = {"-u", "-g", "-C", "-U", "-h", "-p", "-r", "-t"}
_DURATION = re.compile(r"^[0-9.]+[smhd]?$")
_INFO_FLAGS = {"--version", "-V", "-h", "--help", "-version"}
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SHELL_OPS = set("();|&")


def _segments(opener_line):
    """Simple commands on OPENER_LINE as argv lists, heredoc openers removed."""
    text = RX_HEREDOC_OPEN.sub(" ", opener_line)
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    segments, current = [], []
    try:
        for token in lexer:
            if token and all(ch in _SHELL_OPS for ch in token):
                if current:
                    segments.append(current)
                current = []
            else:
                current.append(token)
    except ValueError:
        # Unbalanced quote (the opener regex is quote-blind, so a stray
        # apostrophe earlier on the line lands here). Failing open would let
        # the command through, so fall back to a quote-stripped split.
        plain = text.replace("'", " ").replace('"', " ")
        return [seg.split() for seg in re.split(r"[;&|()]+", plain)
                if seg.split()]
    if current:
        segments.append(current)
    return segments


def _program(argv):
    """(program, args, override_present) with env assignments and wrappers
    skipped."""
    i, override, in_wrapper = 0, False, False
    while i < len(argv):
        token = argv[i]
        if _ENV_ASSIGN.match(token):
            override = override or token == f"{OVERRIDE}=1"
        elif os.path.basename(token) in _WRAPPERS:
            in_wrapper = True
        elif in_wrapper and token.startswith("-"):
            if token in _WRAPPER_VALUE_OPTS:
                i += 1
        elif in_wrapper and _DURATION.match(token):
            pass
        else:
            break
        i += 1
    if i >= len(argv):
        return None, [], override
    name = os.path.basename(argv[i]).lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name, argv[i + 1:], override


def _positionals(args):
    """ARGS minus options and redirections (`> f`, `2>&1`, `>>f`)."""
    out, i = [], 0
    while i < len(args):
        arg = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else ""
        if _REDIRECT_ONLY.match(arg):
            i += 2  # the operator and its target
        elif arg.isdigit() and _REDIRECT_ONLY.match(nxt):
            i += 3  # `2 > f`: the fd, the operator, and its target
        elif _REDIRECT_WITH_TARGET.match(arg):
            i += 1
        else:
            if arg == "-" or not arg.startswith("-"):
                out.append(arg)
            i += 1
    return out


def _reads_script_from_stdin(args):
    if any(a in _INFO_FLAGS for a in args):
        return False  # `python3 --version <<EOF` runs no script at all
    positionals = _positionals(args)
    if not positionals:
        return True
    # the stdin marker only counts as the SCRIPT when it comes first;
    # `python3 a.py -` passes `-` to a.py as data
    return positionals[0] == "-" or positionals[0] == "/dev/stdin"


def interpreter_feed(opener_line):
    """(interpreter_name, override_present) when a command on OPENER_LINE
    reads its script from stdin, else None."""
    for argv in _segments(opener_line):
        name, args, override = _program(argv)
        if (name and _INTERPRETER.match(name)
                and _reads_script_from_stdin(args)):
            # the override counts only on the interpreter's OWN command, not
            # on an unrelated one earlier on the line
            return name, override
    return None


def find_offense(command):
    """(interpreter, delimiter, trigger_char_name) for the first heredoc that
    feeds an interpreter and carries a backslash or backtick, else None.
    The third item is "backslash" or "backtick"."""
    if _PARSER is None:
        return None
    for delim, body, opener_line in _PARSER._heredoc_bodies(command):
        char = ("backslash" if chr(92) in body
                else "backtick" if "`" in body else None)
        if char is None:
            continue
        feed = interpreter_feed(opener_line)
        if feed is None:
            continue
        interpreter, override = feed
        if override or os.environ.get(OVERRIDE) == "1":
            continue
        return interpreter, delim, char
    return None


REASON = (
    "Refused: a heredoc (delimiter `{delim}`) feeds a script containing a "
    "{char} to `{interpreter}`.\n\n"
    "A backslash or backtick inside a heredoc body is rewritten between what "
    "you type and what the interpreter receives: on this transport a doubled "
    "backslash can arrive as a single one, and a quoted delimiter does not "
    "prevent it. It fails silently -- `\\frac` became a form feed plus `rac` "
    "with no error (ai-config#4298, #1923, #2014).\n\n"
    "Instead: write the script with the Write tool to a uniquely named "
    "scratchpad file, then run it by path (`python3 <path>`). The Write tool "
    "passes bytes unchanged. Read the output back if it wrote a file.\n\n"
    "Escape hatch for a case this guard did not foresee, with the reason "
    "stated: prefix the command with `{override}=1` "
    "(`{override}=1 {interpreter} - <<'EOF'`). See "
    "shared/coding/heredoc-backslash-collapse.md."
)


def _read_payload():
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"no-interpreter-heredoc: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    quiet = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
    ):
        if is_dry_run:
            print(json.dumps(quiet))
        return 0
    tool_input = payload.get("tool_input")
    command = None
    if isinstance(tool_input, dict):
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps(quiet))
        return 0

    try:
        offense = find_offense(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"no-interpreter-heredoc: could not parse command ({exc})",
              file=sys.stderr)
        return 0

    if offense is None:
        if is_dry_run:
            print(json.dumps(quiet))
        return 0

    interpreter, delim, char = offense
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON.format(
            delim=delim, interpreter=interpreter, override=OVERRIDE,
            char=char),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
