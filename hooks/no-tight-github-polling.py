#!/usr/bin/env python3
"""PreToolUse (Bash, Monitor, mcp__github__.*): deny polling that drains the GitHub budget.

ai-config#5970: the account's shared 5,000-request hourly GitHub budget hit 0
twice on 2026-11-19, pausing every merge, from CI watchers polling every few
seconds in parallel threads. Guidance (monitor-pushed-heads.md, #5045) was read
past, so this DENIES (#4741), below the floor `AI_CONFIG_GH_POLL_FLOOR` (120 s):
`gh pr checks --watch` / `gh run watch` (defaults 10 s, 3 s), `watch` on a
GitHub call, and `while`/`until` or sleeping `for` loops calling GitHub. A `for`
over at most five literal words (a retry) or with no sleep (a batch) passes, as
does a non-literal `sleep`. `ALLOW_GITHUB_POLL=1` overrides one command and
`AI_CONFIG_NO_GITHUB_POLL_GUARD=1` disables it. Fails open, reporting on stderr.

It also denies a GitHub read identical to one this session made less than
`AI_CONFIG_GH_REPEAT_COOLDOWN` (120 s) ago: the same MCP read tool with the
same arguments, or the same `gh` read command. Check-run annotation reads (the
annotations endpoint, `batch-read-annotations.py`, `summarize-pr-annotations.sh`)
get `AI_CONFIG_GH_ANNOTATION_COOLDOWN` (1800 s), since a completed run's
annotations never change; the runner saw them re-read several times per head.
Any GitHub write, or `git push`, clears the log, so a read after a write
passes. `ALLOW_REPEAT_GITHUB_READ=1` overrides a Bash read; an MCP read has no
prefix and passes once the cooldown has run.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import time

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
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
REPEAT_OVERRIDE = "ALLOW_REPEAT_GITHUB_READ=1"
# (subcommand, verbs) that only read; `api` is judged by its method, `search` always reads.
GH_READ_VERBS = {"pr": {"view", "list", "checks", "diff", "status"}, "run": {"view", "list"},
                 "issue": {"view", "list", "status"}, "workflow": {"view", "list"},
                 "release": {"view", "list"}, "repo": {"view", "list"}, "label": {"list"},
                 "cache": {"list"}}
ANNOTATION_SCRIPTS = re.compile(r"(?:^|/)(?:batch-read-annotations\.py|"
                                r"summarize-pr-annotations\.sh)$")
ANNOTATION_PATH = re.compile(r"check-runs/\d+/annotations(?:$|[/?])")
MCP_PREFIX = "mcp__github__"
MCP_READ = re.compile(r"\A(?:get_|list_|search_)|\A(?:pull_request_read|issue_read|"
                      r"actions_get|actions_list)\Z")
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


def _api_read_path(args):
    """The path of a `gh api` call that reads (GET), else None."""
    method, path, field, it = None, "", False, iter(args)
    for arg in it:
        if arg in ("-X", "--method"):
            method = next(it, "").upper()
        elif arg.startswith("--method="):
            method = arg.split("=", 1)[1].upper()
        elif arg in ("-f", "--raw-field", "-F", "--field", "--input"):
            field = True  # gh sends a POST when fields are given with no method
            next(it, None)
        elif arg in ("-H", "--header", "-q", "--jq", "-t", "--template", "--hostname",
                     "--cache", "-p", "--preview"):
            next(it, None)
        elif not arg.startswith("-") and not path:
            path = arg
    return path if (method or ("POST" if field else "GET")) == "GET" else None


def classify(rest):
    """For one peeled argv: ("read", key, annotation) or ("write",), else None."""
    prog = os.path.basename(rest[0]) if rest else ""
    key = " ".join(rest)
    if prog == "git":
        return ("write",) if rest[1:2] == ["push"] else None
    if prog != "gh":
        if any(ANNOTATION_SCRIPTS.search(tok) for tok in rest[:2]):
            return ("read", key, True)
        return None
    sub, args = _gh_parts(rest)
    if sub == "api":
        path = _api_read_path(args)
        return ("write",) if path is None else ("read", key, bool(ANNOTATION_PATH.search(path)))
    if sub == "search" or (args[:1] and args[0] in GH_READ_VERBS.get(sub, ())):
        return ("read", key, False)
    if sub in GH_API_SUBS and not (sub == "run" and args[:1] == ["watch"]):
        return ("write",)
    return None


def bash_reads(command, depth=0):
    """`(reads, wrote)` for a Bash command; reads are `(key, annotation)` pairs."""
    reads, wrote = [], False
    for argv in simple_commands(command) or []:
        env, rest = _peel(argv)
        if not rest:
            continue
        if os.path.basename(rest[0]) in SHELLS and "-c" in rest[1:-1] and depth < 3:
            inner, inner_wrote = bash_reads(rest[rest.index("-c", 1) + 1], depth + 1)
            reads, wrote = reads + inner, wrote or inner_wrote
            continue
        cls = classify(rest)
        if cls and cls[0] == "write":
            wrote = True
        elif cls and REPEAT_OVERRIDE not in env:
            reads.append(cls[1:])
    return reads, wrote


def repeat_violation(session, reads, wrote, now):
    """A sentence naming a too-soon identical read, else None; updates the session's log."""
    cooldown = float(os.environ.get("AI_CONFIG_GH_REPEAT_COOLDOWN", "120"))
    ann_cooldown = float(os.environ.get("AI_CONFIG_GH_ANNOTATION_COOLDOWN", "1800"))
    digest = hashlib.sha256(session.encode()).hexdigest()[:16]
    path = os.path.join(tempfile.gettempdir(), f".claude-github-reads-{digest}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            log = json.load(fh)
    except (FileNotFoundError, ValueError):  # no log yet, or a torn one: start fresh
        log = {}
    horizon = max(cooldown, ann_cooldown)
    log = {} if wrote or not isinstance(log, dict) else {
        k: t for k, t in log.items() if isinstance(t, (int, float)) and now - t < horizon}
    for key, annotation in reads:
        limit = ann_cooldown if annotation else cooldown
        if key in log and now - log[key] < limit:
            kind = "check-run annotation read" if annotation else "GitHub read"
            return (f"this identical {kind} ran {now - log[key]:.0f} s ago in this session "
                    f"(cooldown {limit:g} s): `{key[:200]}`")
    log.update({key: now for key, _annotation in reads})
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(log, fh)
    os.replace(tmp, path)
    return None


def _repeat(payload):
    """The repeat-read deny sentence for this tool call, else None."""
    tool, inp = payload.get("tool_name") or "", payload.get("tool_input") or {}
    session = str(payload.get("session_id") or "no-session")
    if tool == "Bash" and isinstance(inp.get("command"), str):
        reads, wrote = bash_reads(inp["command"])
    elif tool.startswith(MCP_PREFIX) and MCP_READ.search(tool[len(MCP_PREFIX):]):
        reads, wrote = [(f"{tool} {json.dumps(inp, sort_keys=True)}", "annotation" in tool)], False
    elif tool.startswith(MCP_PREFIX):
        reads, wrote = [], True
    else:
        return None
    if not reads and not wrote:
        return None
    return repeat_violation(session, reads, wrote, time.time())


def _deny_repeat(why):
    reason = (
        f"[hook: {NAME}] Denied: {why}. Every session on the account shares one 5,000-request "
        "hourly GitHub budget, and repeated reads helped empty it twice on 2026-11-19 "
        "(ai-config#5970). Reuse the earlier result; a completed run's annotations do not "
        "change, so read them once per head. To wait for CI, subscribe to the PR or schedule "
        "a wake instead of re-reading; `gh api rate_limit` (free) shows the budget left. If "
        f"the data must be fresh now, a Bash read can take the prefix `{REPEAT_OVERRIDE}`; "
        "say why. Any GitHub write or `git push` clears the log.")
    out = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
           "permissionDecisionReason": reason}
    print(json.dumps({"hookSpecificOutput": out}))


def main() -> int:
    if simple_commands is None or os.environ.get("AI_CONFIG_NO_GITHUB_POLL_GUARD") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
        floor = float(os.environ.get("AI_CONFIG_GH_POLL_FLOOR", "120"))
        command = (payload.get("tool_input") or {}).get("command")
        why = (payload.get("tool_name") in ("Bash", "Monitor") and isinstance(command, str)
               and poll_violation(command, floor))
        repeat = None if why else _repeat(payload)
    except Exception as exc:  # fail open, but say so
        print(f"{NAME}: {type(exc).__name__}: {exc}; not gating", file=sys.stderr)
        return 0
    if repeat:
        _deny_repeat(repeat)
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
