#!/usr/bin/env python3
"""PreToolUse reminder: relocating toolchain data across drives without ever
asking what the destination drive is made of.

WHAT HAPPENED
-------------
Measured 2026-09-15 on this machine (Windows 11 Pro 26200). A "free space on
`C:`" task ranked directories by SIZE and moved the largest movable ones to
`D:`. `Get-PhysicalDisk` -- run only because the user asked "will it run slower
on D?" -- reported `C:` as a Samsung PM9A1 NVMe SSD and `D:` as a TOSHIBA
DT01ACA100, a 7200rpm spinning platter.

By then `C:\\Users\\Work\\.julia` (7.7 GB) had been moved to `D:\\julia` with
`JULIA_DEPOT_PATH` repointed and the source deleted, `AppData\\Local\\R` (14 GB)
had been copied to `D:\\R`, and the WSL2 `ext4.vhdx` (19.5 GB) was next. All
three are random-small-file workloads -- an R `library()` call opens thousands
of small files, Julia precompilation likewise, a WSL2 ext4 image does constant
small random I/O -- so the size ranking had selected the three worst candidates
on the disk for a medium roughly two orders of magnitude slower at random 4K
reads.

WHY A GUARD RATHER THAN A RULE
------------------------------
Because nothing fails. The copy succeeds, the toolchain still works, and the
cost arrives later as a diffuse "my machine got slow" with no event to attribute
it to. There is no red check, no error, and no moment at which anyone would
re-open a finished cleanup task. `shared/workflow/algorithmatize-checks.md`'s
test applies exactly: the condition is decidable from the transcript, and the
omission is invisible from the inside.

The two halves are both transcript-decidable:

  1. the command's own argv -- a relocation verb at a command position whose
     path arguments span two different drive letters, at least one of which
     names a package library, depot, or VM disk image;
  2. session history -- whether any earlier tool call asked what the physical
     media are (`Get-PhysicalDisk`, `Get-Disk`, `lsblk ... ROTA`, and friends).

WHY IT WARNS, AND WHY IT IS THIS NARROW
---------------------------------------
README's "A hook that misfires is worse than a missing one" is the binding
constraint here, and this rule has an unusually dangerous false positive: **a
backup or an archive copy to an HDD is exactly right.** A guard that fired on
every `robocopy C:\\... D:\\Backup\\...` would be teaching people to ignore it
within a day, on the very commands where the HDD is the correct destination.

So the trigger is narrowed twice, and both narrowings cost real detections:

  * a cross-drive relocation naming NO toolchain path is silent. Documents,
    media, game installs, ISOs, finished datasets -- the whole population for
    which "move it to the big slow drive" is the right answer -- never fire.
  * a cross-drive relocation whose paths name a backup/archive/snapshot
    location is silent even when a toolchain path is involved, because copying
    a package library to `D:\\Backup\\julia` is a backup, not a relocation.

And it only ever ADDS context: no `permissionDecision` key is emitted at all,
so an absent decision defers to the normal permission flow. A false positive
costs one line and a one-second command that is worth running anyway.

DIRECTION IS DELIBERATELY NOT INFERRED
--------------------------------------
The hook does not try to decide which drive is the fast one -- it cannot,
which is the entire point. A move from `D:` to `C:` fires on the same terms as
`C:` to `D:`, and the note asks which of the two named drives is the SSD
rather than asserting an answer. Being wrong about the direction would be
worse than being symmetric, because a confident wrong claim is what this whole
entry exists to prevent.

WHAT IS NOT MATCHED
-------------------
  * A relocator inside a quoted argument, a heredoc body, or a `#` comment.
    The verb must sit at a command position (start of string, or after `;`,
    `&&`, `||`, `|`, a newline, or an opening paren/brace), which is what keeps
    this corpus's own prose about the rule from tripping it -- the failure
    `require-gh-repo-flag.py` is the cautionary example for.
  * A UNC destination (`\\\\server\\share`). A network share is the same hazard
    class and is a known gap, recorded in the test suite's KNOWN_LIMITS rather
    than silently absent.
  * A plain POSIX root (`/home/...`) with no drive letter, which on this
    machine is inside the WSL image rather than on a named volume.
  * `wsl --export`, which writes a `.tar` -- a cold sequential archive, for
    which an HDD is correct. `wsl --import` and `--move`, which place a live
    `ext4.vhdx`, DO match.

Fails OPEN and SILENT on any parse trouble, and treats an unreadable transcript
as discharged.
"""
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Command-position relocation verbs.
#
# `cp`, `mv`, `copy` and `move` are short and common, which is why the position
# anchor below is load-bearing rather than tidiness: `git mv`, `echo "mv ..."`
# and a sentence containing "move" must all miss. PowerShell's aliases are
# included under their own names because a session on this machine writes
# `Copy-Item` and `cp` interchangeably for the same cmdlet.
RELOCATOR = re.compile(
    r"""(?:^|[;&|\n({])\s*
        (?:sudo\s+|env\s+\S+=\S+\s+|timeout\s+\S+\s+)*
        (?P<verb>
            robocopy | xcopy | rsync
          | copy-item | move-item | \bcpi\b | \bmi\b
          | \bcopy\b | \bmove\b | \bcp\b | \bmv\b
        )\b""",
    re.I | re.X,
)

# `wsl --import` and `wsl --manage <d> --move` both place a live ext4 image.
# `--export` writes a tar and is deliberately absent; see the docstring.
WSL_RELOCATOR = re.compile(
    r"(?:^|[;&|\n({])\s*wsl(?:\.exe)?\b[^\n;&|]*?--(?:import|move)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Path tokens carrying a volume.
#
# The negative lookbehind on DRIVE is what keeps a URL out: in `https://x`, the
# character before `s` is a word character, so the scheme never reads as a
# drive letter. A bare `C:` with no separator (`cd C:`) is not a path token.
DRIVE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z]):[\\/][^\s\"';|&,]*")
MOUNT = re.compile(r"/(?:mnt|cygdrive)/([A-Za-z])(?:/[^\s\"';|&,]*)?", re.I)
# Git Bash spells the same drive `/d/GitHub`. A single-letter first segment is
# what distinguishes it from an ordinary POSIX root; `(?<![\w/:])` keeps it
# from matching the tail of `/mnt/d/...`, which MOUNT has already consumed.
GITBASH = re.compile(r"(?<![\w/:.])/([A-Za-z])/[^\s\"';|&,]*")


def paths(command):
    """[(volume, raw_token)] for every path token naming a drive letter.

    MOUNT is consumed first and blanked, so `/mnt/d/x` is read once as drive D
    rather than also as a Git Bash `/d/`-style path underneath it.
    """
    found = []
    rest = command

    def take(rx, text):
        out = []
        holes = []
        for m in rx.finditer(text):
            out.append((m.group(1).upper(), m.group(0)))
            holes.append((m.start(), m.end()))
        for start, end in reversed(holes):
            text = text[:start] + " " * (end - start) + text[end:]
        return out, text

    got, rest = take(MOUNT, rest)
    found += got
    got, rest = take(DRIVE, rest)
    found += got
    got, rest = take(GITBASH, rest)
    found += got
    return found


# ---------------------------------------------------------------------------
# Toolchain paths: package libraries, depots, and VM/container disk images.
#
# Every alternative is segment-anchored, so a file merely NAMED `renv-notes.md`
# does not qualify. Generic `.cache` is deliberately absent: a pip or browser
# cache on a platter is fine, and including it would put this guard back into
# the cry-wolf territory the docstring rules out. What is here is the class the
# incident names -- data a build, a REPL, or an `import` touches per
# invocation.
SEG = r"(?:[\\/]|^)"
END = r"(?:[\\/]|[\"']|\s|$)"
TOOLCHAIN = re.compile(
    SEG + r"""(?:
        \.julia | julia_depot
      | \.cargo | \.rustup
      | \.m2 | \.gradle | \.ivy2 | \.nuget | \.gem | \.rbenv | \.nvm
      | \.bun | \.deno | \.opam | \.cabal | \.stack | \.conan | \.pub-cache
      | \.ccache | \.sccache | \.yarn | \.pnpm-store | pnpm-store
      | node_modules | site-packages | win-library | renv | vcpkg
      | virtualenvs | \.venv | venv
      | miniconda3 | anaconda3 | miniforge3
      | CanonicalGroupLimited | docker-desktop(?:-data)? | DockerDesktopWSL
    )""" + END + r"""
  | """ + SEG + r"""go[\\/]pkg[\\/]mod""" + END + r"""
  | """ + SEG + r"""AppData[\\/](?:Local|Roaming)[\\/]R""" + END + r"""
  | \.(?:vhdx|vhd|avhdx|vmdk|vdi|qcow2)(?=["'\s]|$)
    """,
    re.I | re.X,
)

# An env var being set in the same command names the same class of directory
# even when the path itself is unrecognisable (`D:\\depot`).
TOOLCHAIN_ENV = re.compile(
    r"\b(?:JULIA_DEPOT_PATH|R_LIBS(?:_USER|_SITE)?|GOPATH|GOMODCACHE"
    r"|CARGO_HOME|RUSTUP_HOME|PNPM_HOME|NODE_PATH|CONDA_PKGS_DIRS"
    r"|PIP_CACHE_DIR|npm_config_cache|GRADLE_USER_HOME|MAVEN_OPTS"
    r"|RENV_PATHS_CACHE)\b",
    re.I,
)

# A destination that names a backup, an archive, or a snapshot is the case
# where the slow drive is CORRECT. Matched against the path tokens rather than
# the whole command, so an unrelated sentence containing "archive" elsewhere in
# a chained command does not silence a real relocation.
BACKUP = re.compile(
    r"(?:^|[\\/_. -])(?:backups?|bkp|bak|archives?|archived|snapshots?"
    r"|restore|vault|cold[-_]?storage)(?:[\\/_. -]|$)",
    re.I,
)

# ---------------------------------------------------------------------------
# What discharges the obligation: any earlier (or same-command) tool call that
# asks what the physical media are.
#
# Deliberately generous. For a warn-only guard the expensive direction is
# nagging a session that already knows the answer, not staying quiet for one
# that does not: a hook people route around enforces nothing.
MEDIA_CHECK = re.compile(
    r"""get-physicaldisk
      | get-disk\b
      | mediatype
      | msft_physicaldisk
      | win32_diskdrive
      | wmic\s+diskdrive
      | smartctl
      | nvme\s+list
      | \blsblk\b[^\n;|]*\brota
      | fsutil\s+fsinfo""",
    re.I | re.X,
)

HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?^\s*\2\s*$",
    re.S | re.M,
)
COMMENT = re.compile(r"(?m)(?<![\\$])#[^\n]*$")


def strip_noise(command):
    """Blank heredoc bodies and `#` comments.

    A heredoc writing an issue body that contains `robocopy C:\\a D:\\b` on its
    own line puts the verb at what looks like a command position; a comment
    explaining this very rule does the same.
    """
    out = HEREDOC.sub(lambda m: "\n" * m.group(0).count("\n"), command)
    return COMMENT.sub("", out)


def command_is_media_check(text):
    """True when this command text asks what the physical media are."""
    return bool(isinstance(text, str) and MEDIA_CHECK.search(text))


def find_risky_move(command):
    """(verb, [volumes], toolchain_token) when the command needs the warning.

    None when it does not. Every clause must hold: a relocation verb at a
    command position, path tokens spanning at least two drive letters, at least
    one toolchain path or toolchain env var, and no backup/archive path token.
    """
    if not isinstance(command, str) or not command.strip():
        return None
    text = strip_noise(command)

    hit = RELOCATOR.search(text)
    verb = hit.group("verb").lower() if hit else None
    # `wsl --import` / `--manage --move` names only its DESTINATION, so the
    # source volume is never in the argv and the two-volume test below can
    # never pass. The thing being placed is a live `ext4.vhdx` by definition,
    # which is why this arm needs neither the second volume nor a recognised
    # toolchain path -- the verb itself supplies both facts.
    is_wsl = verb is None and bool(WSL_RELOCATOR.search(text))
    if is_wsl:
        verb = "wsl --import/--move"
    if verb is None:
        return None

    tokens = paths(text)
    volumes = sorted({vol for vol, _ in tokens})
    if not volumes or (len(volumes) < 2 and not is_wsl):
        return None

    if any(BACKUP.search(raw) for _, raw in tokens):
        return None

    toolchain = next((raw for _, raw in tokens if TOOLCHAIN.search(raw)), None)
    if toolchain is None and TOOLCHAIN_ENV.search(text):
        toolchain = tokens[0][1]
    if toolchain is None and is_wsl:
        toolchain = tokens[-1][1]
    if toolchain is None:
        return None

    return verb, volumes, toolchain


def _tool_uses(entry):
    """Yield (name, payload_dict) for each tool_use in a transcript entry."""
    message = entry.get("message")
    content = (message.get("content") if isinstance(message, dict)
               else entry.get("content"))
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                payload = block.get("input")
                yield (block.get("name") or "",
                       payload if isinstance(payload, dict) else {})
    calls = entry.get("tool_calls")
    if isinstance(calls, list):
        for call in calls:
            if not isinstance(call, dict):
                continue
            name = (call.get("name")
                    or (call.get("function") or {}).get("name") or "")
            payload = (call.get("args") or call.get("input")
                       or (call.get("function") or {}).get("arguments") or {})
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {"command": payload}
            yield name, payload if isinstance(payload, dict) else {}


def transcript_has_media_check(transcript_path):
    """True when an earlier tool call asked what the physical media are.

    Returns True (discharged, silent) on any read failure -- fail open.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return True
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                for _, payload in _tool_uses(entry):
                    for key in ("command", "cmd", "CommandLine"):
                        if command_is_media_check(payload.get(key)):
                            return True
    except OSError:
        return True
    return False


NOTE = (
    "Cross-drive relocation of toolchain data, with no media-type check in "
    "this session.\n"
    "`{verb}` moves `{token}` between drives {volumes}, and nothing in this "
    "session has established what those drives are made of.\n"
    "Drives are not interchangeable storage. A package library, depot, "
    "container/VM disk image or compiler cache is a random-small-file "
    "workload: an R `library()` call or a Julia precompile opens thousands of "
    "small files, and a WSL2 `ext4.vhdx` does constant small random I/O. On a "
    "7200rpm platter those run roughly two orders of magnitude slower than on "
    "NVMe, and NOTHING FAILS -- the copy succeeds, the toolchain still works, "
    "and the cost surfaces later as an unattributable slowdown.\n"
    "Run `Get-PhysicalDisk | Format-Table DeviceId, FriendlyName, MediaType, "
    "Size` (or `lsblk -d -o NAME,ROTA`) FIRST and say which of {volumes} is "
    "the SSD. The media type is a precondition of the plan, not a detail: "
    "learning it late means already-done work has to be reverted, including "
    "any source directory already deleted.\n"
    "If the destination is genuinely the right home for this data -- cold, "
    "large, sequentially read, or a backup -- say so and carry on; this only "
    "adds context and blocks nothing."
)


def _read_payload():
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
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
        print(f"warn-cross-drive-toolchain-move: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


SHELL_TOOLS = ("Bash", "bash", "PowerShell", "powershell", "run_command",
               "execute_command", "terminal", "shell")


def main():
    payload, _ = _read_payload()
    if not isinstance(payload, dict) or not payload:
        return 0
    if payload.get("tool_name") not in SHELL_TOOLS:
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = (tool_input.get("command") or tool_input.get("cmd")
               or tool_input.get("CommandLine") or "")

    try:
        hit = find_risky_move(command)
        if hit is None:
            return 0
        # A media check chained into this very command discharges it too.
        if command_is_media_check(command):
            return 0
        if transcript_has_media_check(payload.get("transcript_path") or ""):
            return 0
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-cross-drive-toolchain-move: could not evaluate ({exc})",
              file=sys.stderr)
        return 0

    verb, volumes, token = hit
    drives = " and ".join(f"{v}:" for v in volumes)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                verb=verb, token=token, volumes=drives),
        },
    }
    # Gated per README's Antigravity double-warn rule: the adapter's PreToolUse
    # branch surfaces both channels, so a payload carrying both warns twice.
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Moving `{token}` across {drives} with no media-type check this "
            "session. Run `Get-PhysicalDisk` first -- toolchain data on a "
            "spinning disk is ~100x slower at random reads and nothing fails "
            "to say so."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
