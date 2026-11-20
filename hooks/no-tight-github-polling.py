#!/usr/bin/env python3
"""PreToolUse (Bash, Monitor): deny polling that drains the GitHub budget.

ai-config#5970: CI watchers polling every few seconds emptied the shared hourly
GitHub budget twice on 2026-11-19. Denies (#4741), below `AI_CONFIG_GH_POLL_FLOOR`
(120 s): `gh pr checks --watch`, `gh run watch`, `watch` on a GitHub call, and
`while`/`until` or sleeping `for` loops calling GitHub. A retry `for` over at most
five literal words, a `for` with no sleep, and a non-literal `sleep` pass.
`ALLOW_GITHUB_POLL=1` overrides; `AI_CONFIG_NO_GITHUB_POLL_GUARD=1` disables.
Writer and reviewer layers: shared/workflow/monitor-pushed-heads.md and
.claude/agents/adversarial-reviewer.md. Fails open, reporting on stderr.
"""
import json
import os
import re
import sys

_LIB = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "scripts", "lib")
sys.path.insert(0, _LIB)
try:
    from shellcmd import simple_commands
except ImportError as exc:
    print(f"no-tight-github-polling: cannot load scripts/lib/shellcmd.py ({exc}); "
          "not gating", file=sys.stderr)
    simple_commands = None

NAME = "no-tight-github-polling"
POLL_OVERRIDE = "ALLOW_GITHUB_POLL=1"
SHELLS = {"bash", "sh", "zsh", "dash"}
LOOPS = {"while", "until", "for"}
KEYWORDS = {"!", "{", "}", "if", "then", "elif", "else", "fi", "do", "done", "time"}
WRAPPERS = {"env", "command", "nohup", "exec", "builtin", "sudo", "timeout", "nice", "doas"}
ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
WRAPPER_ARG = re.compile(r"\A(?:-.*|[\d.]+[smhd]?)\Z")
GH_VALUE_FLAGS = {"-R", "--repo", "--hostname"}
# gh subcommands that call the API (not `auth`, `config`, `alias`, `extension`).
GH_API_SUBS = {"api", "pr", "run", "issue", "workflow", "release", "repo", "search",
               "cache", "status", "label", "secret", "variable", "ruleset", "gist"}
GH_API_HOST = re.compile(r"(?:https?://)?api\.github\.com(?:/|$)", re.I)
GH_SCRIPTS = re.compile(r"(?:^|/)(?:check-pr-fully-clean\.py|batch-read-annotations\.py|"
                        r"summarize-pr-annotations\.sh)$")
SLEEP_ARG = re.compile(r"\A(\d+(?:\.\d+)?)([smhd]?)\Z")
UNIT = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


def _peel(argv):
    """`(assignments, argv from the program on)`, keywords and wrappers dropped."""
    rest, env = list(argv), []
    while rest:
        tok = rest[0]
        if ASSIGNMENT.match(tok):
            env.append(tok)
        elif os.path.basename(tok) in WRAPPERS:
            rest = rest[1:]
            while rest and (WRAPPER_ARG.match(rest[0]) or ASSIGNMENT.match(rest[0])):
                rest = rest[1:]  # `timeout 60`, `sudo -u me`
            continue
        elif tok not in KEYWORDS:
            break
        rest = rest[1:]
    return env, rest


def _gh_parts(rest):
    """`(subcommand, args after it)` for a `gh` argv, skipping global flags."""
    args = rest[1:]
    while args and args[0].startswith("-"):
        args = args[2:] if args[0] in GH_VALUE_FLAGS else args[1:]
    return (args[0], args[1:]) if args else (None, [])


def _flag_value(args, names, default):
    """The value of `--flag N`, `--flag=N` or `-fN` for any of `names`, else default."""
    for i, arg in enumerate(args):
        for name in names:
            joined = name + ("=" if name.startswith("--") else "")
            if arg == name and i + 1 < len(args):
                text = args[i + 1]
            elif arg.startswith(joined) and len(arg) > len(joined):
                text = arg[len(joined):]
            else:
                continue
            return float(text) if re.fullmatch(r"\d+(?:\.\d+)?", text) else default
    return default


def _watch_target(rest):
    """For `watch [opts] cmd...`: `(interval, inner argv)`."""
    args, i = rest[1:], 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-n", "--interval") else 1
    return _flag_value(args[:i], ["--interval", "-n"], 2.0), args[i:]


def is_github_call(rest):
    """Whether one peeled argv calls the GitHub API."""
    if not rest:
        return False
    prog = os.path.basename(rest[0])
    if prog == "gh":
        return _gh_parts(rest)[0] in GH_API_SUBS
    if prog in ("curl", "wget"):
        return any(GH_API_HOST.match(a) for a in rest[1:])
    if prog == "watch":
        return is_github_call(_peel(_watch_target(rest)[1])[1])
    return any(GH_SCRIPTS.search(tok) for tok in rest[:2])


def _sleep_seconds(rest):
    """Seconds a `sleep` argv waits; None when not a literal."""
    matches = [SLEEP_ARG.match(arg) for arg in rest[1:]]
    if not all(matches):
        return None
    return sum(float(m.group(1)) * UNIT[m.group(2)] for m in matches)


def _watcher(rest, floor):
    """A sentence for a `gh ... watch` or `watch` faster than `floor`, else None."""
    prog, (sub, args) = os.path.basename(rest[0]), _gh_parts(rest)
    if prog == "gh" and sub == "pr" and args[:1] == ["checks"] and "--watch" in args:
        what, iv = "gh pr checks --watch", _flag_value(args, ["--interval", "-i"], 10.0)
    elif prog == "gh" and sub == "run" and args[:1] == ["watch"]:
        what, iv = "gh run watch", _flag_value(args, ["--interval", "-i"], 3.0)
    elif prog == "watch" and is_github_call(rest):
        what, iv = "watch", _watch_target(rest)[0]
    else:
        return None
    return f"`{what}` polls GitHub every {iv:g} s" if iv < floor else None


def poll_violation(command, floor, depth=0):
    """A sentence naming the too-fast GitHub poll in `command`, or None."""
    loop, for_words, slept, unknown, calls = None, None, 0.0, False, False
    for argv in simple_commands(command) or []:
        env, rest = _peel(argv)
        if POLL_OVERRIDE in env:
            return None
        if argv[0] in LOOPS:
            if loop is None:
                loop = argv[0]
                words = argv[3:] if loop == "for" and argv[2:3] == ["in"] else None
                if words is not None and not any("$" in w or "`" in w for w in words):
                    for_words = len(words)
            # The condition of `until gh run view ...` runs on every pass.
            rest = [] if argv[0] == "for" else _peel(argv[1:])[1]
        if not rest:
            continue
        prog = os.path.basename(rest[0])
        if prog in SHELLS and "-c" in rest[1:-1] and depth < 3:
            inner = poll_violation(rest[rest.index("-c", 1) + 1], floor, depth + 1)
            if inner:
                return inner
            continue
        why = _watcher(rest, floor)
        if why:
            return why
        if prog == "sleep":
            secs = _sleep_seconds(rest)
            unknown = unknown or secs is None
            slept += secs or 0.0
        elif loop and is_github_call(rest):
            calls = True
    if not (loop and calls) or unknown:
        return None
    if loop == "for" and (slept == 0 or (for_words is not None and for_words <= 5)):
        return None  # a batch over items, or a short retry
    if slept < floor:
        return f"a `{loop}` loop calls GitHub with {slept:g} s of sleep per pass"
    return None


def main() -> int:
    if simple_commands is None or os.environ.get("AI_CONFIG_NO_GITHUB_POLL_GUARD") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
        floor = float(os.environ.get("AI_CONFIG_GH_POLL_FLOOR", "120"))
        command = (payload.get("tool_input") or {}).get("command")
        why = (payload.get("tool_name") in ("Bash", "Monitor") and isinstance(command, str)
               and poll_violation(command, floor))
    except Exception as exc:  # fail open, but say so
        print(f"{NAME}: {type(exc).__name__}: {exc}; not gating", file=sys.stderr)
        return 0
    if not why:
        return 0
    reason = (
        f"[hook: {NAME}] Denied: {why}, faster than the {floor:g} s floor. Every session on "
        "the account shares one 5,000-request hourly GitHub budget, and tight CI watchers in "
        "parallel threads emptied it twice on 2026-11-19, pausing every merge "
        "(ai-config#5970). Instead, subscribe to the PR's activity or schedule one wake for "
        f"when CI should be done, or poll no faster than every {floor:g} s (for example "
        f"`gh pr checks N --watch --interval {floor:g}`), and check `gh api rate_limit` "
        "(free) first. See shared/workflow/monitor-pushed-heads.md. If a tight poll is truly "
        f"needed, prefix `{POLL_OVERRIDE}` and say why.")
    out = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
           "permissionDecisionReason": reason}
    print(json.dumps({"hookSpecificOutput": out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
