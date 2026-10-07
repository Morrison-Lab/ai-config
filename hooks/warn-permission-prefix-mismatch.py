#!/usr/bin/env python3
"""PreToolUse warn-only guard: a git global option defeats an allow-rule prefix.

Claude Code matches a `Bash(<prefix>:*)` allow rule against the literal start
of the command. `ALLOW_UNREVIEWED_PUSH=1 git -C /repo push` does not start
with `ALLOW_UNREVIEWED_PUSH=1 git push`, so the rule the user already has does
not cover it, the auto-mode classifier denies the override, and the agent asks
the user for a rule that exists (measured 2026-10-07, Morrison-Lab/mlr;
memories/claude-code-hooks.md, "A permission allow-rule matches the command's
literal prefix").

Trigger: the command starts with one or more `VAR=val` assignments, then
`git`, then at least one global option (`-C <path>`, `-c k=v`, `--git-dir`,
`--work-tree`, `--no-pager`, ...) before the subcommand.
The env-assignment requirement is a deliberate narrowing (the override-push
shape that was measured); plain `git -C /r push` is left alone.
Check: no allow rule in the user/project settings matches the command as
written, but one would match it with the global options removed.
Output: additionalContext (plus systemMessage outside Antigravity) suggesting
the cwd form. Never blocks. Fails open on any trouble.

Test hook: WARN_PREFIX_SETTINGS_FILES (os.pathsep-separated) replaces the
default settings-file search.
"""
import glob
import json
import os
import re
import shlex
import sys

_ASSIGN = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
_SEPARATORS = {"&&", "||", ";", "|", "&", "(", ")", ";;"}
# global options taking a separate value argument
_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
               "--exec-path", "--super-prefix", "--config-env"}
_FLAG_OPTS = {"--no-pager", "-P", "-p", "--paginate", "--bare",
              "--no-replace-objects", "--literal-pathspecs",
              "--no-optional-locks", "--no-lazy-fetch"}
_RULE = re.compile(r"\ABash\((.*):\*\)\Z", re.DOTALL)

NOTE = (
    "Permission-rule prefix mismatch (likely cause, not proven): `{orig}` carries a git global option "
    "before the subcommand, so it does not start with `{stripped}`, which "
    "the allow rule `Bash({rule}:*)` in {src} matches. Claude Code matches "
    "allow rules against the literal command prefix, so this command may "
    "prompt or be classifier-denied although the rule exists. Run it from "
    "the repo's cwd as `{stripped} ...` (no `-C`, no `cd` chain) instead of "
    "asking the user to add a rule."
)


def split_command(command):
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    toks = []
    for tok in lex:
        if tok in _SEPARATORS:
            break
        toks.append(tok)
    return toks


def parse(toks):
    """Return (assignments, option_tokens, rest) or None if not the shape."""
    i = 0
    while i < len(toks) and _ASSIGN.match(toks[i]):
        i += 1
    if i == 0 or i >= len(toks) or toks[i] != "git":
        return None
    assigns, j = toks[:i], i + 1
    start = j
    while j < len(toks) and toks[j].startswith("-"):
        t = toks[j]
        if t in _VALUE_OPTS:
            j += 2
        elif t in _FLAG_OPTS or re.match(
                r"\A(--git-dir|--work-tree|--namespace|--exec-path|"
                r"--config-env)=|\A-[Cc].", t):
            j += 1
        else:
            return None  # unknown option: do not guess
    if j == start or j >= len(toks):
        return None
    return assigns, toks[start:j], toks[j:]


def settings_files():
    override = os.environ.get("WARN_PREFIX_SETTINGS_FILES")
    if override is not None:
        return [p for p in override.split(os.pathsep) if p]
    home = os.path.expanduser("~/.claude")
    files = [os.path.join(home, "settings.json"),
             os.path.join(home, "settings.local.json")]
    files += sorted(glob.glob(os.path.join(os.getcwd(), ".claude",
                                           "settings*.json")))
    return files


def allow_prefixes():
    out = []
    for path in settings_files():
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            allow = data.get("permissions", {}).get("allow", [])
        except Exception:
            continue
        for rule in allow if isinstance(allow, list) else []:
            m = _RULE.match(rule) if isinstance(rule, str) else None
            if m:
                out.append((m.group(1), path))
    return out


def matches(prefix, toks):
    ptoks = prefix.split()
    return bool(ptoks) and toks[:len(ptoks)] == ptoks


def find_mismatch(command):
    parsed = parse(split_command(command))
    if not parsed:
        return None
    assigns, opts, rest = parsed
    full = assigns + ["git"] + opts + rest
    stripped = assigns + ["git"] + rest
    rules = allow_prefixes()
    if any(matches(p, full) for p, _ in rules):
        return None
    for prefix, src in rules:
        if matches(prefix, stripped):
            return {"orig": shlex.join(full[:len(assigns) + 1 + len(opts)]),
                    "stripped": prefix, "rule": prefix, "src": src}
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") not in ("Bash", "bash"):
            return 0
        command = (payload.get("tool_input") or {}).get("command")
        if not isinstance(command, str):
            return 0
        hit = find_mismatch(command)
    except Exception as exc:  # fail open
        print(f"warn-permission-prefix-mismatch: skipped ({exc})",
              file=sys.stderr)
        return 0
    if not hit:
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "additionalContext": NOTE.format(**hit)}}
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Allow rule `Bash({hit['rule']}:*)` will not match this command "
            "because of the git global option; run it from the repo's cwd "
            "without `-C`.")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
