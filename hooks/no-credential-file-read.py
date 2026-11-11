#!/usr/bin/env python3
"""PreToolUse guard: refuse printing a credential file into the transcript.

On 2026-10-27 a session ran `cat` on `~/.config/canvas/token` through a `sed`
redaction that matched nothing, and the bare token landed in the transcript
(ai-config#4780). The read is the leak, so this denies rather than warns.

It fires on the Read tool, and on a Bash simple command whose program is a
reader (`cat`, `sed`, `base64`, ...) naming a credential path. A reader inside
`$(...)` is allowed, since its output feeds another program, unless the
enclosing command is `echo` or `printf`. Wrappers (`bash -c`, `xargs`), `cd`
and more stores are not yet covered (ai-config#5443).

Fails open, saying so on stderr. For an approved read, prefix that one
command with ALLOW_CREDENTIAL_READ=1.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

try:
    _LIB = os.path.join(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import is_operator_token, shell_tokens
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-credential-file-read: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); no command will be checked", file=sys.stderr)
    shell_tokens = None

OVERRIDE = "ALLOW_CREDENTIAL_READ=1"

READERS = {
    "cat", "head", "tail", "less", "more", "sed", "awk", "grep", "egrep",
    "fgrep", "rg", "bat", "nl", "xxd", "od", "hexdump", "strings", "base64",
    "tac", "cut", "sort", "uniq", "diff", "jq", "yq", "type", "Get-Content",
}

# Paths relative to the home directory, matched with fnmatch.
HOME_PATTERNS = (
    ".netrc", "_netrc", ".git-credentials", ".pgpass", ".npmrc", ".pypirc",
    ".aws/credentials", ".docker/config.json", ".kube/config",
    ".config/gh/hosts.yml", ".config/canvas/*", ".ssh/id_*",
)
# A ~/.config file named for a secret word between separators, not inside
# a longer word (`api_token.json`, not `tokenize.lua`).
CONFIG_SECRET_NAME = re.compile(
    r"^(?:.*[._-])?(?:token|tokens|secret|secrets|credentials?)(?:[._-].*)?$",
    re.IGNORECASE)
CODE_SUFFIXES = (".py", ".lua", ".js", ".ts", ".sh", ".md", ".vim", ".el")
# Programs that print their arguments, so `echo $(cat token)` still prints.
PRINTERS = {"echo", "printf", "print"}
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)")

LEAD_WORDS = {"sudo", "command", "exec", "nohup", "time", "doas", "env"}


def is_credential_path(raw, cwd):
    """True when `raw` names a credential file under the home directory."""
    if not raw or raw.startswith("-"):
        return False
    path = raw
    for var, repl in (("$HOME", "~"), ("${HOME}", "~"),
                      ("$XDG_CONFIG_HOME", "~/.config"),
                      ("${XDG_CONFIG_HOME}", "~/.config")):
        if path.startswith(var):
            path = repl + path[len(var):]
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    path = os.path.normpath(path)
    home = os.path.expanduser("~")
    if not path.startswith(home + os.sep):
        return False
    rel = path[len(home) + 1:].replace(os.sep, "/")
    if rel.endswith(".pub"):
        return False
    if any(fnmatch.fnmatchcase(rel, pat) for pat in HOME_PATTERNS):
        return True
    name = rel.rsplit("/", 1)[-1]
    return (rel.startswith(".config/") and not name.endswith(CODE_SUFFIXES)
            and bool(CONFIG_SECRET_NAME.match(name)))


def _printed_commands(tokens):
    """Yield each simple command's argv whose output would be printed:
    those outside `$( ... )`, and those inside one under a printer."""
    frames = [{"argv": [], "printed": True}]
    prev = None
    for tok in tokens:
        if not is_operator_token(tok):
            frames[-1]["argv"].append(tok)
            prev = tok
            continue
        for ch in tok:
            top = frames[-1]
            if ch == "(" and prev and prev.endswith("$"):
                outer = _program(top["argv"])[0]
                frames.append({"argv": [], "printed": top["printed"]
                               and outer in PRINTERS})
                continue
            if top["argv"] and top["printed"]:
                yield top["argv"]
            top["argv"] = []
            if ch == "(":
                frames.append({"argv": [], "printed": top["printed"]})
            elif ch == ")" and len(frames) > 1:
                frames.pop()
            prev = ch
        prev = tok
    for frame in frames:
        if frame["argv"] and frame["printed"]:
            yield frame["argv"]


def _is_assignment(token):
    name, sep, _value = token.partition("=")
    return bool(sep) and name.isidentifier()


def _program(argv):
    """(program name, its arguments), skipping assignments and LEAD_WORDS."""
    i = 0
    while i < len(argv) and (_is_assignment(argv[i]) or argv[i] in LEAD_WORDS):
        i += 1
    if i >= len(argv):
        return None, []
    return argv[i].rsplit("/", 1)[-1], argv[i + 1:]


def offending_bash_path(command, cwd):
    """The credential path a reader in `command` would print, or None."""
    if shell_tokens is None:
        return None
    tokens = shell_tokens(command)
    if not tokens:
        return None
    for argv in _printed_commands(tokens):
        name, args = _program(argv)
        if name in PRINTERS:  # a quoted "$(cat token)" stays one token
            for inner in SUBSTITUTION.findall(" ".join(args)):
                hit = offending_bash_path(inner, cwd)
                if hit:
                    return hit
        if name not in READERS or OVERRIDE in argv[:len(argv) - len(args)]:
            continue
        for arg in args:
            if is_credential_path(arg, cwd):
                return arg
    return None


def evaluate(payload):
    """Deny reason for `payload`, or None."""
    tool = payload.get("tool_name")
    inp = payload.get("tool_input")
    if not isinstance(inp, dict):
        return None
    cwd = str(payload.get("cwd") or os.getcwd())
    if tool == "Read":
        path = inp.get("file_path") or ""
        hit = path if is_credential_path(path, cwd) else None
    elif tool in ("Bash", "bash", "run_command", "execute_command", "shell"):
        command = inp.get("command") or inp.get("CommandLine") or ""
        hit = offending_bash_path(command, cwd)
    else:
        return None
    if not hit:
        return None
    return (
        f"Refused: this would print the credential file `{hit}` into the "
        "transcript (ai-config#4780: a Canvas token leaked this way).\n\n"
        "Pass it to the program that needs it, as in `curl -H \"Authorization:"
        " Bearer $(cat <path>)\" ...`, or check it with `test -s <path>`.\n"
        f"If the user approved this exact read, prefix the command with "
        f"`{OVERRIDE}`.")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"no-credential-file-read: unreadable input ({exc})",
              file=sys.stderr)
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        reason = evaluate(payload)
    except Exception as exc:  # fail open on parse trouble, saying so
        print(f"no-credential-file-read: could not check call ({exc})",
              file=sys.stderr)
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
