#!/usr/bin/env python3
r"""PreToolUse reminder: warn on recursive search over cloud-sync or network mounts.

WHAT HAPPENED
-------------
Measured on 2026-09-28 on this Windows machine (Morrison-Lab/mlr#10):
A search was run to find book PDFs in `G:\\My Drive\\Texts 2` (a collection of
1700+ book folders). Two recursive searches (`find` and `grep -r`) were run
over `G:\\My Drive\\Texts 2`, each under a 300-400 second `timeout`. Because
Google Drive for desktop streams files on demand rather than caching the full
1700+ folders locally, the recursive traversal faulted in and streamed every
directory touched across the network.

The resulting network and disk thrashing made the machine lag so severely that
the user's Remote Control client displayed "Can't reach your computer", and
the searches timed out before completion. Worse, the timeout-truncated output
was misread as a complete absence of the target texts.

WHY A GUARD RATHER THAN A RULE
------------------------------
The rule was already documented in `memories/course-repos.md` ('List a
cloud-sync mount's top level before searching it'):
  "The fix is not a shorter search. It is a narrower one: list the top-level
   index directory first (this library keeps a `Texts_by_Title` folder for
   exactly this purpose) and descend only into the specific folders a task
   actually needs."

Despite this clear documentation, an agent composed the search using recursive
tools (`find` / `grep -r`) at prompt composition time without consulting the
memory. As established in `shared/workflow/algorithmatize-checks.md`, a
condition decidable from the command string and its arguments at invocation
time belongs in an automated guard.

WHY IT WARNS RATHER THAN BLOCKS
-------------------------------
A deliberate, targeted search or a script intended to run over a local cached
portion of a cloud drive is sometimes necessary, and the boundary between
virtual streaming mounts and local cached folders cannot always be proven from
path strings alone. Therefore, this hook WARNS and NEVER blocks. It adds
structured context (`additionalContext` and `systemMessage`) pointing the agent
to `memories/course-repos.md` without denying the tool call or altering
permissions.

WHAT IT MATCHES
---------------
A Bash or run_command tool invocation executing a recursive search targeting a
known cloud-sync or network mount path:
  1. `find`: without `-maxdepth 0` or `-maxdepth 1` (or depth > 1).
  2. `grep` / `egrep` / `fgrep` / `rgrep`: with `-r`, `-R`, `--recursive`,
     `--dereference-recursive`, or `rgrep`.
  3. `rg`: ripgrep (recursive by default) without `--max-depth 1` or `-d 1` (or depth > 1).
  4. `fd` / `fdfind`: fd (recursive by default) without `-d 1` or `--max-depth 1`.
  5. `ls -R` / `ls --recursive`, `dir /s`.
  6. Shell glob `**` targeting a cloud mount path.
  7. PowerShell `Get-ChildItem -Recurse` / `gci -r`.

Chained commands (e.g. `cd "/g/My Drive/Texts 2" && find . -name "*.pdf"`) are
tracked via `shellcmd.resolve_cd_target` so relative targets (`.`) in cloud
directories are caught.

Command wrappers (`timeout 300`, `time`, `nice`, `nohup`, etc.) are stripped
before evaluation.

WHAT PATHS ARE MATCHED
----------------------
  - Google Drive virtual drive on Windows: `G:`, `G:\...`, `G:/...`
  - MSYS/Git Bash/Cygwin/WSL mounts of G drive: `/g/...`, `//g/...`,
    `/cygdrive/g/...`, `/mnt/g/...`
  - Named cloud directories:
      `My Drive`, `Shared drives`
      `Google Drive`, `GoogleDrive`
      `OneDrive` (e.g. `OneDrive - Personal`)
      `Dropbox`
      `Box`, `Box Sync`
      `iCloud Drive`, `com~apple~CloudDocs`
  - UNC / SMB network shares: `\\server\share\...`, `//server/share/...`

OVERRIDE
--------
Prefix the command or set the environment variable:
  ALLOW_RECURSIVE_CLOUD_SEARCH=1
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib"
    )
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (
        COMMAND_WRAPPERS,
        ENV_ASSIGNMENT,
        SHELL_KEYWORDS,
        native_path,
        resolve_cd_target,
        simple_commands,
    )
except Exception as _exc:
    print(f"warn-recursive-search-cloud-mount: cannot load scripts/lib/shellcmd.py ({_exc}); not evaluating",
          file=sys.stderr)
    simple_commands = None
    resolve_cd_target = None
    native_path = None
    COMMAND_WRAPPERS = set()
    ENV_ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
    SHELL_KEYWORDS = set()

OVERRIDE_VAR = "ALLOW_RECURSIVE_CLOUD_SEARCH"
OVERRIDE_CMD_RE = re.compile(
    rf"\A[ \t]*(?:export[ \t]+)?{OVERRIDE_VAR}=1(?:[ \t]*[;&|]|\Z)"
)

RE_WIN_G_DRIVE = re.compile(r"^[gG]:([/\\].*)?$")
RE_POSIX_G_DRIVE = re.compile(r"^/(?:(?:cygdrive|mnt)/)?[gG](?:[/\\].*)?$")
RE_UNC_SHARE = re.compile(r"^(?:\\\\|//)[^/\\]+[/\\][^/\\]+")
RE_CLOUD_FOLDER = re.compile(
    r"""(?xi)
    (?:^|[/\\])
    (?:
        My\ Drive
      | Shared\ drives
      | Google\ ?Drive(?:-[^/\\]*)?
      | OneDrive(?:\s*-\s*[^/\\]+)?
      | Dropbox(?:\s*\([^/\\]+\))?
      | Box(?:\s*Sync)?
      | iCloud\ Drive
      | com~apple~CloudDocs
    )
    (?:[/\\]|$)
    """
)

FIND_GLOBAL_OPTS_NO_ARG = {"-H", "-L", "-P"}

WARN_MESSAGE = (
    "Recursive search ({search_cmd}) over cloud-sync or network mount ({path}):\n\n"
    "Streaming/network mounts (Google Drive, OneDrive, Dropbox, SMB) fault in and stream "
    "every folder touched, causing heavy system lag and timeouts.\n\n"
    "Per `memories/course-repos.md` ('List a cloud-sync mount's top level before searching it'):\n"
    "  - List the top level first: `find <dir> -maxdepth 1`, `ls <dir>`, or inspect a top-level\n"
    "    index directory (such as `Texts_by_Title`).\n"
    "  - Descend only into the specific folder(s) a task actually needs.\n\n"
    "To bypass this warning for a deliberate recursive search, prefix the command with\n"
    "ALLOW_RECURSIVE_CLOUD_SEARCH=1."
)

SYSTEM_MESSAGE = (
    "Recursive search ({search_cmd}) over cloud-sync or network mount ({path}). "
    "List the top level first (`find ... -maxdepth 1` or `ls`) and descend only into needed folders. "
    "(memories/course-repos.md)"
)


def is_cloud_mount_path(path: str) -> bool:
    """True if path points into a known cloud-sync or network mount."""
    p = path.strip().strip("'\"")
    if not p:
        return False
    if RE_WIN_G_DRIVE.match(p):
        return True
    if RE_POSIX_G_DRIVE.match(p):
        return True
    if RE_UNC_SHARE.match(p):
        return True
    if RE_CLOUD_FOLDER.search(p):
        return True
    return False


def _resolve_path(target: str, cur_dir: str | None) -> str:
    """Resolve a target path against cur_dir."""
    t = target.strip().strip("'\"")
    if not t:
        return cur_dir or ""
    # Check absolute
    is_abs = (
        t.startswith(("/", "\\"))
        or bool(re.match(r"^[A-Za-z]:[/\\]?", t))
        or t.startswith(("//", "\\\\"))
    )
    if is_abs or cur_dir is None:
        return t
    if t == ".":
        return cur_dir
    if native_path:
        cur_dir_nat = native_path(cur_dir)
        t_nat = native_path(t)
        return os.path.normpath(os.path.join(cur_dir_nat, t_nat))
    return os.path.normpath(os.path.join(cur_dir, t))


def _extract_find_paths(argv: list[str]) -> tuple[list[str], bool]:
    """Extract starting paths and recursion status from find argv.

    Returns (paths, is_recursive).
    """
    paths: list[str] = []
    i = 0
    n = len(argv)
    maxdepth: int | None = None

    while i < n:
        tok = argv[i]
        if tok in FIND_GLOBAL_OPTS_NO_ARG:
            i += 1
            continue
        if tok.startswith("-O") and len(tok) > 2 and tok[2:].isdigit():
            i += 1
            continue
        if tok.startswith("-maxdepth"):
            if "=" in tok:
                val = tok.split("=", 1)[1]
                if val.isdigit():
                    maxdepth = int(val)
                i += 1
                continue
            elif i + 1 < n and argv[i + 1].isdigit():
                maxdepth = int(argv[i + 1])
                i += 2
                continue
        # If token starts with '-' or is a predicate/operator, stop collecting paths
        if tok.startswith("-") or tok in ("(", ")", "!"):
            i += 1
            continue
        # Positional starting path
        paths.append(tok)
        i += 1

    is_recursive = (maxdepth is None or maxdepth > 1)
    if not paths:
        paths = ["."]
    return paths, is_recursive


def _is_recursive_grep(argv: list[str]) -> tuple[list[str], bool]:
    """Extract paths and recursion status from grep/egrep/fgrep/rgrep argv."""
    prog = os.path.basename(argv[0]).lower()
    if prog.endswith(".exe"):
        prog = prog[:-4]

    is_rec = (prog == "rgrep")
    paths: list[str] = []
    i = 1
    n = len(argv)

    while i < n:
        tok = argv[i]
        if tok == "--":
            i += 1
            paths.extend(argv[i:])
            break
        if tok in ("--recursive", "--dereference-recursive"):
            is_rec = True
            i += 1
            continue
        if tok.startswith("-") and not tok.startswith("--"):
            # Flag cluster, e.g. -rn, -ri, -r, -R
            if any(c in "rR" for c in tok[1:]):
                is_rec = True
            # Check flags that consume next argument
            if any(c in "efm" for c in tok[1:]) and i + 1 < n and not tok.endswith(("e", "f", "m")):
                i += 2
                continue
            i += 1
            continue
        if tok.startswith("--exclude") or tok.startswith("--include"):
            i += 1
            continue
        # Non-flag token
        paths.append(tok)
        i += 1

    # In grep, the first non-flag argument is the pattern unless -e/-f was used
    # If paths was [pattern, dir1, dir2...], paths[1:] are search locations
    search_paths = paths[1:] if len(paths) > 1 else (paths if paths and is_rec else ["."])
    return search_paths, is_rec


def _is_recursive_rg(argv: list[str]) -> tuple[list[str], bool]:
    """Extract paths and recursion status from rg argv."""
    is_rec = True
    paths: list[str] = []
    i = 1
    n = len(argv)

    while i < n:
        tok = argv[i]
        if tok == "--":
            i += 1
            paths.extend(argv[i:])
            break
        if tok in ("-d", "--max-depth", "--maxdepth"):
            if i + 1 < n and argv[i + 1].isdigit():
                depth = int(argv[i + 1])
                if depth <= 1:
                    is_rec = False
                i += 2
                continue
        if tok.startswith(("--max-depth=", "--maxdepth=", "-d=")):
            val = tok.split("=", 1)[1]
            if val.isdigit() and int(val) <= 1:
                is_rec = False
            i += 1
            continue
        if tok.startswith("-") and not tok.startswith("--"):
            # Check short flag -d1 or -d0
            if tok.startswith("-d") and len(tok) > 2 and tok[2:].isdigit():
                if int(tok[2:]) <= 1:
                    is_rec = False
                i += 1
                continue
            i += 1
            continue
        if tok.startswith("--"):
            i += 1
            continue
        paths.append(tok)
        i += 1

    search_paths = paths[1:] if len(paths) > 1 else ["."]
    return search_paths, is_rec


def _is_recursive_fd(argv: list[str]) -> tuple[list[str], bool]:
    """Extract paths and recursion status from fd/fdfind argv."""
    is_rec = True
    paths: list[str] = []
    i = 1
    n = len(argv)

    while i < n:
        tok = argv[i]
        if tok in ("-d", "--max-depth", "--maxdepth"):
            if i + 1 < n and argv[i + 1].isdigit():
                depth = int(argv[i + 1])
                if depth <= 1:
                    is_rec = False
                i += 2
                continue
        if tok.startswith(("--max-depth=", "--maxdepth=", "-d=")):
            val = tok.split("=", 1)[1]
            if val.isdigit() and int(val) <= 1:
                is_rec = False
            i += 1
            continue
        if tok.startswith("-") and not tok.startswith("--"):
            if tok.startswith("-d") and len(tok) > 2 and tok[2:].isdigit():
                if int(tok[2:]) <= 1:
                    is_rec = False
                i += 1
                continue
            i += 1
            continue
        if tok.startswith("--"):
            i += 1
            continue
        paths.append(tok)
        i += 1

    search_paths = paths[1:] if len(paths) > 1 else (paths if paths else ["."])
    return search_paths, is_rec


def _strip_wrappers(cmd: list[str]) -> list[str]:
    """Strip command wrappers and leading options."""
    c = list(cmd)
    while c and (c[0] in COMMAND_WRAPPERS or c[0] in SHELL_KEYWORDS or c[0].startswith("-")):
        prog = c[0]
        if prog in COMMAND_WRAPPERS or prog in SHELL_KEYWORDS:
            c.pop(0)
            if prog == "timeout":
                # timeout [options] duration command...
                while c and c[0].startswith("-"):
                    opt = c.pop(0)
                    if opt in ("-s", "--signal", "-k", "--kill-after") and c:
                        c.pop(0)
                # Next token is duration (e.g. 300, 400s)
                if c and (c[0].isdigit() or re.match(r"^\d+[smhd]?$", c[0])):
                    c.pop(0)
            elif prog in ("stdbuf", "nice", "ionice"):
                while c and c[0].startswith("-"):
                    c.pop(0)
                    if c and not c[0].startswith("-"):
                        c.pop(0)
            else:
                while c and c[0].startswith("-"):
                    opt = c.pop(0)
                    if opt in ("-u", "-k", "-s") and c:
                        c.pop(0)
        else:
            break
    return c


def check_simple_command(argv: list[str], cur_dir: str | None) -> tuple[str, str] | None:
    """Check one simple command argv.

    Returns (search_cmd, matched_path) if recursive search over cloud mount, else None.
    """
    if not argv:
        return None

    cmd = list(argv)
    # Strip leading env assignments
    while cmd and ENV_ASSIGNMENT.match(cmd[0]):
        if cmd[0] == f"{OVERRIDE_VAR}=1":
            return None
        cmd.pop(0)

    if not cmd:
        return None

    cmd = _strip_wrappers(cmd)
    if not cmd:
        return None

    prog = os.path.basename(cmd[0]).lower()
    if prog.endswith(".exe"):
        prog = prog[:-4]

    # 1. Glob ** check across all tokens
    for tok in cmd:
        if "**" in tok:
            resolved = _resolve_path(tok, cur_dir)
            if is_cloud_mount_path(resolved):
                return "glob **", resolved

    # 2. find
    if prog == "find":
        paths, is_rec = _extract_find_paths(cmd[1:])
        if is_rec:
            for p in paths:
                resolved = _resolve_path(p, cur_dir)
                if is_cloud_mount_path(resolved):
                    return "find", resolved

    # 3. grep / egrep / fgrep / rgrep
    elif prog in ("grep", "egrep", "fgrep", "rgrep"):
        paths, is_rec = _is_recursive_grep(cmd)
        if is_rec:
            for p in paths:
                resolved = _resolve_path(p, cur_dir)
                if is_cloud_mount_path(resolved):
                    return prog, resolved

    # 4. rg
    elif prog == "rg":
        paths, is_rec = _is_recursive_rg(cmd)
        if is_rec:
            for p in paths:
                resolved = _resolve_path(p, cur_dir)
                if is_cloud_mount_path(resolved):
                    return "rg", resolved

    # 5. fd / fdfind
    elif prog in ("fd", "fdfind"):
        paths, is_rec = _is_recursive_fd(cmd)
        if is_rec:
            for p in paths:
                resolved = _resolve_path(p, cur_dir)
                if is_cloud_mount_path(resolved):
                    return prog, resolved

    # 6. ls -R / ls --recursive
    elif prog == "ls":
        is_rec = any(tok in ("-R", "--recursive") or (tok.startswith("-") and not tok.startswith("--") and "R" in tok[1:]) for tok in cmd[1:])
        if is_rec:
            paths = [tok for tok in cmd[1:] if not tok.startswith("-")]
            if not paths:
                paths = ["."]
            for p in paths:
                resolved = _resolve_path(p, cur_dir)
                if is_cloud_mount_path(resolved):
                    return "ls -R", resolved

    # 7. Windows dir /s
    elif prog == "dir":
        is_rec = any(tok.lower() in ("/s", "-s") for tok in cmd[1:])
        if is_rec:
            paths = [tok for tok in cmd[1:] if not tok.startswith(("/", "-"))]
            if not paths:
                paths = ["."]
            for p in paths:
                resolved = _resolve_path(p, cur_dir)
                if is_cloud_mount_path(resolved):
                    return "dir /s", resolved

    # 8. PowerShell Get-ChildItem -Recurse
    elif prog in ("get-childitem", "gci"):
        is_rec = any(tok.lower() in ("-recurse", "-r", "/s") for tok in cmd[1:])
        if is_rec:
            paths = [tok for tok in cmd[1:] if not tok.startswith(("-", "/"))]
            if not paths:
                paths = ["."]
            for p in paths:
                resolved = _resolve_path(p, cur_dir)
                if is_cloud_mount_path(resolved):
                    return f"{prog} -Recurse", resolved

    return None


def evaluate_command(command: str, cwd: str | None = None) -> tuple[str, str] | None:
    """Evaluate a command string.

    Returns (search_cmd, matched_path) if a recursive search targets a cloud mount, else None.
    """
    if os.environ.get(OVERRIDE_VAR) == "1":
        return None
    if OVERRIDE_CMD_RE.match(command):
        return None

    if simple_commands is None:
        return None

    cmds = simple_commands(command)
    if cmds is None:
        return None

    cur_dir = cwd
    for argv in cmds:
        if not argv:
            continue
        prog = argv[0].lower()
        if prog in ("cd", "pushd") and resolve_cd_target:
            cur_dir = resolve_cd_target(argv, cur_dir)
            continue
        hit = check_simple_command(argv, cur_dir)
        if hit is not None:
            return hit

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if not isinstance(payload, dict):
        return 0

    is_dry_run = payload.get("is_dry_run", False)
    command = (
        payload.get("tool_input", {}).get("command")
        or payload.get("command")
        or ""
    )
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    cwd = payload.get("cwd") or payload.get("tool_input", {}).get("directory") or os.getcwd()

    try:
        hit = evaluate_command(command, cwd)
    except Exception as exc:
        print(f"warn-recursive-search-cloud-mount: could not evaluate ({exc})", file=sys.stderr)
        return 0

    if hit is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    search_cmd, path = hit
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": WARN_MESSAGE.format(search_cmd=search_cmd, path=path),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = SYSTEM_MESSAGE.format(search_cmd=search_cmd, path=path)

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
