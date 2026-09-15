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
     own segment's path arguments span two different drive letters, at least
     one of which names a package library, depot, or VM disk image. The
     `wsl --import`/`--move` arm is the deliberate exception: the verb itself
     supplies both facts, so it needs neither a second volume nor a
     recognised toolchain path -- and its SOURCE tar is exempt from the
     backup test too, so an export landing in a backup directory does not
     silence the import beside it (see the comment at that arm);
  2. session history -- whether any earlier tool call asked what the physical
     media are (`Get-PhysicalDisk`, `Get-Disk`, `lsblk ... ROTA`, and friends).

WHY IT WARNS, AND WHY IT IS THIS NARROW
---------------------------------------
README's "A hook that misfires is worse than a missing one" is the binding
constraint here, and this rule has an unusually dangerous false positive: **a
backup or an archive copy to an HDD is exactly right.** A guard that fired on
every `robocopy C:\\... D:\\Backup\\...` would be teaching people to ignore it
within a day, on the very commands where the HDD is the correct destination.

So the trigger is narrowed four ways. The two below cost real detections and
are the ones the cry-wolf argument turns on. The other two are under WHAT IS
NOT MATCHED: a rehearsal flag costs nothing, while segment scoping can lose a
detection, as `_segment_at` and the suite's KNOWN_LIMITS both record:

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
  * A relocator inside a heredoc body or a `#` comment, and inside a quoted
    argument that contains no command separator. Quoting alone does not
    protect: the command-position class is blind to quotes, so
    `echo "step one; robocopy C:\\... D:\\..."` DOES warn, where the same
    string without the `;` does not (case S11 pins only the latter).
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
    `ext4.vhdx`, DO match. `--import` carries a source `.tar` as well as the
    destination, and the note must never name the tar: an archive is the one
    argument in that command an HDD is unambiguously right for.
  * A rehearsal -- `robocopy /L`, `-WhatIf`, `rsync -n`/`--dry-run` -- which
    moves nothing.
  * A path token in a NEIGHBOURING command segment. Tokens are collected from
    the relocator's own segment only, so a size survey chained to an unrelated
    move (`Get-ChildItem C:\\...\\.julia; robocopy C:\\Videos D:\\Media`) neither
    warns nor names a directory the command does not touch.

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
# The lookahead after the letter is load-bearing, not tidiness. Without it the
# optional tail let `/mnt/backup/julia` match as `/mnt/b` -- inventing a drive
# `B:` that does not exist, AND handing `BACKUP` a token in which the word
# `backup` no longer appears, which made the backup exemption structurally
# unreachable for every `/mnt/<word>` path. Same for `/mnt/data`, `/mnt/wsl`,
# `/mnt/archive` (adversarial review of a331d675, finding FP-1).
MOUNT = re.compile(
    r"/(?:mnt|cygdrive)/([A-Za-z])(?=[/\s\"';|&,]|$)(?:/[^\s\"';|&,]*)?", re.I)
# Git Bash spells the same drive `/d/GitHub`. A single-letter first segment is
# what distinguishes it from an ordinary POSIX root; `(?<![\w/:])` keeps it
# from matching the tail of `/mnt/d/...`, which MOUNT has already consumed.
GITBASH = re.compile(r"(?<![\w/:.])/([A-Za-z])/[^\s\"';|&,]*")


def _segment_at(text, index):
    """The command-list segment of `text` containing character `index`.

    Segments are split on `;`, `&`, `|` and a newline. Paren and brace edges
    are deliberately NOT in this class: they were in the first spelling and
    came out, since a paren is not a command-list separator in either shell.
    The command-position anchor is a SUPERSET of this class, not the same one
    -- it also accepts `(` and `{` as the preceding character. This is a
    deliberate approximation: a separator inside a quoted string splits a
    segment it should not, which can only LOSE a detection (fewer tokens in
    view), never invent one.
    """
    start = 0
    for hit in SEGMENT_SPLIT.finditer(text):
        if hit.start() >= index:
            return text[start:hit.start()]
        start = hit.end()
    return text[start:]


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
#
# The long words are matched as SUBSTRINGS rather than as whole segments,
# because real backup directories carry affixes: `D:\MyBackups`, `D:\Backup2`,
# `D:\BackupDrive`, `D:\Archive2026` all warned under a whole-word spelling
# (adversarial review of a331d675, finding FP-3).
#
# Each entry still has to INDEPENDENTLY mean "this is a backup" -- the same
# admission test the sibling hook's irreplaceable list is held to. Round-2
# review applied it here and `vault` and `restore` failed: `restore` is a BUILD
# verb before it is a backup noun (`dotnet restore`, `renv::restore`,
# `D:\nuget-restore-cache`), and `vault` names a product and a notes app
# (finding R-6). Both were removed rather than defended. `archiv` stays, and
# over-exempts `D:\dev\archived-projects` -- recorded in the suite's
# KNOWN_LIMITS rather than left implicit. Only `bak` keeps word boundaries,
# since it is a substring of ordinary words ("baker", "bakery").
BACKUP = re.compile(
    r"backups?|bkp|archiv|snapshot|cold[-_ ]?storage"
    r"|sicherung|sauvegarde|respaldo"
    r"|(?:^|[\\/_. -])bak(?:[\\/_. -]|$)",
    re.I,
)

# A rehearsal is not a relocation. `robocopy /L` lists without copying and
# PowerShell's `-WhatIf` is the same intent, so warning about a command that
# moves nothing is pure noise (finding FP-7).
REHEARSAL = re.compile(r"(?:^|\s)(?:/L|-WhatIf)(?=\s|$)", re.I)

# `-n` is rsync's dry-run flag and cp/mv's NO-CLOBBER flag, and `cp -n` copies.
# Keeping it in REHEARSAL silenced every `cp -n` and `mv -n` relocation
# (finding R-1), so it is matched only against an rsync segment.
RSYNC_DRY_RUN = re.compile(r"(?:^|\s)(?:-n|--dry-run)(?=\s|$)", re.I)

# Cold sequential archives. A `.tar` named in a `wsl --import` is the SOURCE
# the image is unpacked FROM, and an HDD is the right home for one, so it must
# never be the token the note names (finding FN-1).
ARCHIVE_FILE = re.compile(
    r"\.(?:tar|tar\.gz|tgz|tar\.xz|txz|tar\.zst|zip|7z|iso|vhdx?\.gz)"
    r"(?=[\"'\s]|$)", re.I)

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
# A `#` only opens a comment at the start of a word. Anchored on the preceding
# whitespace because the unanchored spelling truncated real arguments --
# `robocopy ... /LOG:C:\l#1.txt D:\julia` lost everything from the `#`,
# including the second drive letter (finding FN-2).
#
# The `(?<![\\$])` the first spelling carried was dropped in round 2: given the
# whitespace anchor, the character before `#` is always start-of-line, a space
# or a tab, so the lookbehind could never fire. Round-2 review proved it dead
# by exhaustive enumeration, and dead code in a matcher reads as a guard that
# is doing something (finding R-8).
COMMENT = re.compile(r"(?m)(?:^|(?<=[ \t]))#[^\n]*$")

# Command-list separators, used to scope path tokens to the relocator's OWN
# segment. Pooling tokens over the whole command string made a survey chained
# to an unrelated move warn about the surveyed directory:
# `Get-ChildItem C:\...\.julia -Recurse | ...; robocopy C:\Videos D:\Media /E`
# named `.julia`, which that command does not move (finding FP-2).
#
# `(`, `)`, `{` and `}` were in this class in the first spelling and are not
# any more: `Copy-Item (Join-Path C:\Users\Work '.julia') -Destination D:\julia`
# is idiomatic PowerShell on this machine, and a paren in the separator class
# amputated the destination so the two-volume test could never pass
# (finding R-4). A paren is not a command-list separator in either shell.
SEGMENT_SPLIT = re.compile(r"[;&|\n]")


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

    None when it does not. For a general relocator every clause must hold: a
    verb at a command position, path tokens spanning at least two drive
    letters, at least one toolchain path or toolchain env var, and no
    backup/archive path token. The `wsl --import`/`--move` arm is exempt from
    the last three, not the middle two: the verb names the operation and the
    subject, so one volume and no recognised toolchain token still warn (W4),
    and its SOURCE tar is excluded from the backup test too, so an export
    landing in `D:\\Backup` does not silence the import beside it (W24).
    A `--move` INTO a backup-named path is still exempt, that token being
    live rather than an archive (S27).
    """
    if not isinstance(command, str) or not command.strip():
        return None
    text = strip_noise(command)

    # EVERY relocation verb in the command is considered, not just the first.
    # Taking `RELOCATOR.search`'s single hit and scoping to its segment meant
    # any harmless earlier relocation blinded the guard --
    # `cp notes.txt notes.bak; robocopy C:\...\.julia D:\julia /E` went silent
    # (round-2 adversarial review of b1694279, finding R-3).
    candidates = [(m.group("verb").lower(), m.start("verb"), False)
                  for m in RELOCATOR.finditer(text)]
    # `wsl --import` / `--manage --move` names its DESTINATION and, for
    # `--import`, a source file. The thing being placed is a live `ext4.vhdx`
    # by definition, so this arm needs neither a second volume nor a
    # recognised toolchain path -- the verb supplies both facts.
    # EXTEND, never fall back. This was an `if not candidates` gate, which
    # recreated R-3 across verb families: any ordinary relocator anywhere in
    # the command suppressed the wsl arm entirely, so appending `; cp a b` to
    # W4 silenced it, and the canonical WSL move -- stage the tar with `cp`,
    # then `wsl --import` -- was silent for exactly the relocation this guard
    # exists for (round-9 review of 418e5821). The two patterns cannot
    # double-report: RELOCATOR's command-position anchor stops `\bmove\b`
    # matching inside `--move` (see M1).
    candidates += [("wsl --import/--move", m.end(), True)
                   for m in WSL_RELOCATOR.finditer(text)]
    if not candidates:
        return None

    for verb, at, is_wsl in candidates:
        # Only the relocator's OWN command segment supplies path tokens or the
        # rehearsal flags. A token in a neighbouring segment belongs to a
        # different command, and naming it is worse than staying silent -- a
        # guard that reports a path the command does not touch teaches people
        # to stop reading it.
        segment = _segment_at(text, at)

        # `-n` means dry-run for rsync and NO-CLOBBER for cp/mv, which do
        # copy. Scoping the flag to the verb costs nothing and was the
        # difference between a rehearsal and a real relocation (finding R-1).
        if REHEARSAL.search(segment):
            continue
        if verb == "rsync" and RSYNC_DRY_RUN.search(segment):
            continue

        tokens = paths(segment)
        volumes = sorted({vol for vol, _ in tokens})
        if not volumes or (len(volumes) < 2 and not is_wsl):
            continue

        # On the wsl arm the SOURCE tar is excluded from the backup test as
        # well as from the named token. A `wsl --export` tar idiomatically
        # lands under a backup or archive directory, and testing it here made
        # the canonical export-then-import recipe silent -- the same shape as
        # the R-3 fallback: an incidental token elsewhere in the command
        # suppressing the arm (round-10 review). `--move`ing an install INTO
        # a backup-named path is still exempt, because that token is live.
        backup_scope = ([raw for _, raw in tokens if not ARCHIVE_FILE.search(raw)]
                        if is_wsl else [raw for _, raw in tokens])
        if any(BACKUP.search(raw) for raw in backup_scope):
            continue

        if is_wsl:
            # `wsl --import <Distro> <InstallLocation> <FileName>` puts the
            # DESTINATION first, so `live[0]` is the live image's location.
            # This arm runs BEFORE the generic TOOLCHAIN scan, because a
            # `--vhd` import's SOURCE is itself a `.vhdx` and the generic scan
            # picked it -- naming the argument an HDD is arguably right for
            # and omitting the one it is not (finding R-5).
            live = [raw for _, raw in tokens if not ARCHIVE_FILE.search(raw)]
            toolchain = live[0] if live else None
        else:
            toolchain = next(
                (raw for _, raw in tokens if TOOLCHAIN.search(raw)), None)
            # The env var may be exported in an EARLIER segment
            # (`$env:X='D:\d'; robocopy ...`), so it is looked for across the
            # whole command even though the path tokens are not.
            if toolchain is None and TOOLCHAIN_ENV.search(text):
                toolchain = tokens[0][1]
        if toolchain is None:
            continue

        return verb, volumes, toolchain

    return None


def _tool_uses(entry):
    """Yield (name, payload_dict) for each tool_use in a transcript entry."""
    # A transcript line can be valid JSON and not an object. Without this
    # guard one such line raised out of the whole scan, `main`'s blanket
    # handler swallowed it, and every later media check went unseen -- a
    # silent wrong answer rather than a loud one (adversarial review of
    # a331d675, finding 4a).
    if not isinstance(entry, dict):
        return
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
    except Exception:
        # Widened from OSError: an unexpected record shape must not decide
        # the obligation either way by raising. Fail open, as documented.
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
    "Run this FIRST and say which of {volumes} is the SSD:\n"
    "  Get-Partition -DriveLetter {letters} | Select-Object DriveLetter, "
    "@{{n='Media';e={{($_ | Get-Disk | Get-PhysicalDisk).MediaType}}}}, "
    "@{{n='Model';e={{($_ | Get-Disk | Get-PhysicalDisk).FriendlyName}}}}\n"
    "  (Linux: lsblk -o NAME,ROTA,MOUNTPOINT)\n"
    "The calculated properties are not decoration. `Get-PhysicalDisk` prints "
    "no drive letter at all, and piping a partition straight into it projects "
    "the letter away -- so the shorter `Get-Partition | Get-Disk | "
    "Get-PhysicalDisk | Format-Table` gives rows you cannot attach to a drive, "
    "in DISK order rather than the order you asked for. Reading that output "
    "positionally is how you get the answer exactly backwards. "
    "The media type is a precondition of the plan, not a detail: "
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
    # The command literal is parameterised on the volumes this command
    # actually touches. The first spelling hardcoded `C,D` while interpolating
    # the real drives in the same sentence, so a move between E: and F: was
    # told to query two volumes it does not touch (finding R-2 of round 2).
    letters = ",".join(volumes)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                verb=verb, token=token, volumes=drives, letters=letters),
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
