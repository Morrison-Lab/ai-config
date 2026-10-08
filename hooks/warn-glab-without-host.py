#!/usr/bin/env python3
"""PreToolUse guard: `glab` run with no way to know which GitLab host to use.

## The incident

A session ran `glab api ...` from a folder that is not a git checkout. glab
resolves its host from, in order, `--hostname` (api only), a host-qualified
`-R/--repo`, `GITLAB_HOST`, and the `origin` remote of the working directory,
and falls back to `gitlab.com` when none of those names a host. In a
non-checkout directory none did, so glab contacted gitlab.com, got
"Unauthenticated", and the agent told the user their token had expired. The
token was fine; the request had gone to the wrong server
(ai-config#4387).

## What this warns about

A `glab` subcommand that talks to a GitLab project (`api`, `issue`, `mr`,
`ci`, ...) where all of these hold:

  * no `--hostname` / `--hostname=`,
  * no `-R/--repo` carrying a host (`HOST/OWNER/REPO` or a URL),
  * no `GITLAB_HOST` assignment on the command or in an earlier
    `export GITLAB_HOST=` of the same command line,
  * and the working directory (the hook input's `cwd`, moved by any `cd`
    earlier in the same command) is not inside a git repository whose remote
    is a host other than gitlab.com / github.com.

A host set with `glab config set host` or `GL_HOST` also names a host (glab
reads both before falling back), so those silence the warning.

Known limits, accepted: a `GITLAB_HOST=` export made inside a subshell is
treated as set for the rest of the command; a remote on any host other than gitlab.com or
github.com (bitbucket.org, codeberg.org) counts as naming a host, because
glab would try it; a `GITLAB_HOST` in the hook's own process environment
silences the warning, but one exported only in the user's later shell state
cannot be seen.

## Why this warns rather than blocks

Plenty of correct invocations match: a user whose only GitLab is gitlab.com,
a `GITLAB_HOST` exported in the shell profile (the hook cannot see the
user's later shell state), a remote the hook could not read. So it only adds
context, per README's "A hook that misfires is worse than a missing one".

Fails OPEN on any parse trouble.
"""
import json
import os
import re
import subprocess
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (
        env_value, resolve_cd_target, simple_commands_with_scope, strip_env,
    )
except Exception as _exc:  # broken install; fail open and say so
    print(f"warn-glab-without-host: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    simple_commands_with_scope = None

# glab subcommands that act on a GitLab project or the API and so need a host.
# `auth`, `config`, `version`, `help`, `completion`, `alias`, `check-update`
# do not resolve a project host and are left alone.
HOST_SENSITIVE = {
    "api", "issue", "mr", "ci", "pipeline", "release", "repo", "variable",
    "label", "milestone", "snippet", "job", "incident", "schedule",
    "deploy-key", "iteration", "user", "runner", "securefile", "token",
    "cluster", "stack", "ssh-key", "gpg-key",
}

# Flags whose next token is their value, so it is not the subcommand.
VALUE_FLAGS = {"-R", "--repo", "--hostname"}

# Hosts a remote can name that glab would NOT treat as the intended GitLab.
NOT_GITLAB_HOSTS = {"gitlab.com", "www.gitlab.com", "github.com"}

# Approximation: any dotted first path segment reads as a host, so a group
# name that merely contains a dot (`my.grp/sub/repo`) is taken for one.
RX_HOST_REPO = re.compile(r"^(?:[a-z][a-z0-9+.-]*://)?[^/\s]+\.[^/\s]+/[^/\s]+/", re.I)
RX_REMOTE_HOST = re.compile(
    r"^(?:[a-z][a-z0-9+.-]*://)?(?:[^@/\s]+@)?([^:/\s]+)", re.I)


def remote_host(url):
    """Host of a git remote URL (https, ssh://, or scp-style), or None."""
    m = RX_REMOTE_HOST.match(url.strip())
    return m.group(1).lower() if m else None


def cwd_names_host(cwd):
    """True when CWD is inside a git repo with a non-gitlab.com/github.com remote."""
    if not cwd or not os.path.isdir(cwd):
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "remote", "-v"],
            capture_output=True, text=True, timeout=5)
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            host = remote_host(parts[1])
            if host and host not in NOT_GITLAB_HOSTS:
                return True
    return False


def glab_subcommand(rest):
    """First non-flag token after `glab`, skipping value-taking flags."""
    skip = False
    for tok in rest[1:]:
        if skip:
            skip = False
            continue
        if tok in VALUE_FLAGS:
            skip = True
            continue
        if not tok.startswith("-"):
            return tok
    return None


def names_host(rest):
    """True when the glab argv itself carries a --hostname or host-qualified -R."""
    args = rest[1:]
    for i, tok in enumerate(args):
        if tok == "--hostname" and i + 1 < len(args) and not args[i + 1].startswith("-"):
            return True
        if tok.startswith("--hostname=") and tok != "--hostname=":
            return True
        value = None
        if tok in ("-R", "--repo") and i + 1 < len(args):
            value = args[i + 1]
        elif tok.startswith("--repo="):
            value = tok.split("=", 1)[1]
        elif tok.startswith("-R") and len(tok) > 2:
            value = tok[2:]
        if value is not None and RX_HOST_REPO.match(value):
            return True
    return False


def configured_host():
    """Non-gitlab.com host from `glab config get host`, or None (fails open)."""
    try:
        proc = subprocess.run(
            ["glab", "config", "get", "host"],
            capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    host = proc.stdout.strip().lower() if proc.returncode == 0 else ""
    return host if host and host not in NOT_GITLAB_HOSTS else None


def find_offense(command, cwd):
    """The first host-less `glab` simple command in COMMAND, as argv, or None."""
    cmds = simple_commands_with_scope(command)
    if cmds is None:
        return None
    dirs = {}  # subshell scope -> working directory set inside it

    def dir_of(scope):
        while scope:
            if scope in dirs:
                return dirs[scope]
            scope = scope[:-1]
        return cwd

    exported_host = False
    for scope, argv in cmds:
        env, rest = strip_env(argv)
        if argv and argv[0] == "export":
            exported_host = exported_host or any(
                t.startswith("GITLAB_HOST=") and t != "GITLAB_HOST=" for t in argv[1:])
            continue
        if not rest:
            # A bare assignment statement (`GITLAB_HOST=h; glab ...`).
            exported_host = exported_host or any(
                t.startswith("GITLAB_HOST=") and t != "GITLAB_HOST=" for t in argv)
            continue
        prog = os.path.basename(rest[0])
        if prog in ("cd", "pushd", "popd"):
            dirs[scope] = resolve_cd_target(rest, dir_of(scope))
            continue
        if prog != "glab":
            continue
        sub = glab_subcommand(rest)
        if sub not in HOST_SENSITIVE:
            continue
        if names_host(rest) or exported_host:
            continue
        if (env_value(env, "GITLAB_HOST") or env_value(env, "GL_HOST")
                or os.environ.get("GITLAB_HOST") or os.environ.get("GL_HOST")):
            continue
        cur_dir = dir_of(scope)
        if cur_dir is not None and cwd_names_host(cur_dir):
            continue
        if configured_host():
            continue
        return rest
    return None


NOTE = (
    "`{shown}` names no GitLab host, and the working directory "
    "(`{cwd}`) is not inside a git repo whose remote names one. glab will "
    "use its default host (gitlab.com), so an \"Unauthenticated\" or 404 "
    "reply describes gitlab.com, not your server (ai-config#4387).\n\n"
    "Pass the host explicitly: `glab api --hostname <host> ...`, a "
    "host-qualified `-R <host>/<owner>/<repo>`, or a `GITLAB_HOST=<host>` "
    "prefix. Before telling the user a token is expired, verify it against "
    "the intended host (`curl -H \"PRIVATE-TOKEN: $T\" "
    "https://<host>/api/v4/user`).\n\n"
    "If gitlab.com is the intended host, disregard this warning."
)


def _read_payload():
    try:
        payload = json.load(sys.stdin)
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        print(f"warn-glab-without-host: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}


def main() -> int:
    if simple_commands_with_scope is None:
        return 0
    payload = _read_payload()
    if payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
    ):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else None

    try:
        offense = find_offense(command, cwd)
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-glab-without-host: could not parse command ({exc})",
              file=sys.stderr)
        return 0
    if offense is None:
        return 0

    shown = " ".join(offense[:3])
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(shown=shown, cwd=cwd or "unknown"),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"`{shown}` has no GitLab host and this directory has no GitLab "
            "remote; glab will use gitlab.com. Pass --hostname <host>.")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
