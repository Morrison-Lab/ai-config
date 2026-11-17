#!/usr/bin/env python3
"""PreToolUse DENY: creating a GitHub repository without applying its ruleset.

## The failure this exists for

On 2026-11-17 a session created `Morrison-Lab/answer-space` with a plain
`gh repo create` on a Remote Control host and left it with no branch
ruleset, so `main` took direct pushes, force pushes and deletion. Ezra asked
why. The rule that a new repository gets a ruleset is in
`shared/workflow/repo-templates.md` ("Set a branch ruleset that follows the
template's example", ai-config#4671), as prose only, and the session never
read that file while creating the repository. It had happened before: 32
course repositories created from `qwt` on 2026-11-12 also shipped with no
ruleset (ai-config#5610).

ai-config#5610 proposed a stateful pair (PostToolUse records the new repo,
PreToolUse blocks later work on it) that only covered `--template` creates.
This hook is the stateless form, and it covers every create: the create
itself is refused unless the SAME Bash command also applies the ruleset.
Writing the two steps as one chain is cheap, and a stateless check cannot
lose track of a pending repository between turns or sessions.

## The condition

A Bash command that runs `gh repo create` (at command position, found with
`scripts/lib/shellcmd.py`, so an echoed, grepped or heredoc-quoted create is
inert) is DENIED unless one of its simple commands also:

* runs `apply-all.sh --apply` naming the new repository (bare name or
  `owner/name`), the org-wide applier in `examples/branch-rulesets/`; or
* runs `apply-rulesets.sh`, the per-repository applier every template
  carries in `.github/scripts/`; or
* writes a ruleset with `gh api` to `repos/<owner>/<name>/rulesets` using a
  write method (`-X POST`, `--method POST`, or an `--input` body).

`gh repo create --help` is not a create and passes.

`mcp__github__create_repository` is DENIED outright. A cloud session's proxy
refuses ruleset writes (403), so a repository created through it would be
left unprotected by construction; create it from a host with repo admin
(Remote Control) as a `gh repo create ... && apply-all.sh --apply ...` chain.

## Why there is no escape variable

The discharge costs one `&& ...` on the same line. An escape variable would
become the reflex answer to the deny, which is the outcome the hook exists to
prevent (`feedback-fix-wrong-gate-never-override`). A repository that truly
should have no ruleset is a decision for Ezra, made by applying and then
deleting the ruleset by hand.

## Limits

* A repository created in the GitHub web UI, by another tool, or by the
  `@claude` agent is not seen. The periodic `apply-all.sh` dry run proposed in
  ai-config#5610 is the backstop for those.
* The hook does not check that the applier SUCCEEDED. Chain with `&&` so a
  failed apply fails the command visibly.
* Fails OPEN on an unreadable payload or a broken `shellcmd` import (one
  stderr line), like the other Bash-parsing hooks here.
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
    from shellcmd import simple_commands, strip_env, shell_c_expansions
except Exception as _exc:  # broken install: degrade, never block every call
    print(f"require-ruleset-on-repo-create: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); no gate will run", file=sys.stderr)
    simple_commands = strip_env = shell_c_expansions = None

SHELL_TOOLS = frozenset({"Bash", "bash", "PowerShell", "run_command",
                         "execute_command", "terminal", "shell"})
MCP_CREATE = "mcp__github__create_repository"
SHELLS = frozenset({"bash", "sh", "zsh", "dash"})
# gh repo create flags that take a value, so their value is not the repo name.
VALUE_FLAGS = frozenset({
    "-d", "--description", "-h", "--homepage", "-g", "--gitignore",
    "-l", "--license", "-p", "--template", "-r", "--remote", "-s", "--source",
    "-t", "--team",
})
RX_RULESETS = re.compile(r"repos/([^/\s]+)/([^/\s]+)/rulesets/?$")

DENY_BASH = (
    "BLOCKED: `gh repo create{name}` with no branch ruleset applied in the same "
    "command.\n\n"
    "Every new repository gets a ruleset at creation "
    "(shared/workflow/repo-templates.md; Morrison-Lab/answer-space shipped "
    "without one on 2026-11-17, and 32 qwt course repos on 2026-11-12, "
    "ai-config#5610).\n\n"
    "Chain the applier onto the create, from a host with repo admin (a cloud "
    "session gets 403 on ruleset writes):\n"
    "  gh repo create {full} ... && "
    "<ai-config>/examples/branch-rulesets/apply-all.sh --apply {short}\n"
    "or, for a repo made from a template, run the template's own "
    "`.github/scripts/apply-rulesets.sh` in the same chain. Then verify with "
    "`gh api repos/{full}/rulesets` (non-empty)."
)
DENY_MCP = (
    "BLOCKED: `mcp__github__create_repository` cannot give the new repository a "
    "branch ruleset: the cloud proxy refuses ruleset writes (403), so the "
    "repository would ship with an unprotected default branch "
    "(Morrison-Lab/answer-space, 2026-11-17; ai-config#5610).\n\n"
    "Create it from a host with repo admin (a Remote Control session) as one "
    "chain:\n"
    "  gh repo create <owner>/<name> ... && "
    "<ai-config>/examples/branch-rulesets/apply-all.sh --apply <name>\n"
    "using the matching template (shared/workflow/repo-templates.md)."
)


def _program(argv):
    """Basename of the program a simple command runs, looking through a shell."""
    _env, rest = strip_env(argv)
    if not rest:
        return None, []
    prog = os.path.basename(rest[0])
    if prog in SHELLS:
        ops = [t for t in rest[1:] if not t.startswith("-")]
        if ops:
            return os.path.basename(ops[0]), ops[1:] + [t for t in rest[1:] if t.startswith("-")]
        return prog, rest[1:]
    return prog, rest[1:]


def _create_target(args):
    """For `gh` argv after the program: the repo name if this is `repo create`."""
    if len(args) < 2 or args[0] != "repo" or args[1] != "create":
        return None
    rest = args[2:]
    if "--help" in rest:
        return None
    skip = False
    for tok in rest:
        if skip:
            skip = False
            continue
        if tok.startswith("-"):
            if tok in VALUE_FLAGS:
                skip = True
            continue
        return tok
    return ""


def _applies(prog, args, short, full):
    if prog == "apply-rulesets.sh":
        return True
    if prog == "apply-all.sh":
        if "--apply" not in args:
            return False
        names = {a.split("=", 1)[0] for a in args if not a.startswith("-")}
        return bool(short) and (short in names or full in names)
    if prog == "gh" and args[:1] == ["api"]:
        write = ("--input" in args or any(a.startswith("--input=") for a in args)
                 or any(args[i] in ("-X", "--method") and i + 1 < len(args)
                        and args[i + 1].upper() in ("POST", "PUT")
                        for i in range(len(args)))
                 or any(a.upper() in ("--METHOD=POST", "--METHOD=PUT") for a in args))
        if not write:
            return False
        for a in args:
            m = RX_RULESETS.search(a)
            if m and short and m.group(2) == short:
                return True
    return False


def check_bash(command):
    """Return a deny reason, or None."""
    if simple_commands is None or "repo" not in command or "create" not in command:
        return None
    # A create wrapped in `bash -c '...'` is one opaque token to shlex, so
    # every command line reachable through a shell's -c is parsed too
    # (review on ai-config#5764). The discharge may sit in any of them.
    parsed = []
    for line in shell_c_expansions(command):
        cmds = simple_commands(line)
        if cmds:
            parsed.extend(_program(argv) for argv in cmds)
    for prog, args in parsed:
        if prog != "gh":
            continue
        target = _create_target(args)
        if target is None:
            continue
        full = target
        short = target.split("/")[-1] if target else ""
        if any(_applies(p, a, short, full) for p, a in parsed):
            continue
        return DENY_BASH.format(name=f" {target}" if target else "",
                                full=full or "<owner>/<name>",
                                short=short or "<name>")
    return None


def decide(payload):
    tool = payload.get("tool_name", "")
    if tool == MCP_CREATE:
        return DENY_MCP
    if tool in SHELL_TOOLS:
        cmd = (payload.get("tool_input") or {}).get("command", "")
        if isinstance(cmd, str):
            return check_bash(cmd)
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"require-ruleset-on-repo-create: unreadable payload ({exc})",
              file=sys.stderr)
        return 0
    reason = decide(payload)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
