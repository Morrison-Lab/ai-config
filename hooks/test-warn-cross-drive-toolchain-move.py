#!/usr/bin/env python3
"""Tests for warn-cross-drive-toolchain-move.py.

The NEGATIVES carry most of the weight here, and they are not incidental: the
guard's whole defensibility rests on staying silent for the cross-drive copies
where the slow drive is the CORRECT destination. A backup to `D:\\Backup`, a
Steam library move, a documents archive -- each is a cross-drive bulk copy, each
is right, and a guard that warned on them would be routed around within a day
(README, "A hook that misfires is worse than a missing one").

So every negative names the shape it protects rather than merely asserting
False, and the mutation section at the end breaks each load-bearing clause on
purpose and asserts which cases flip. A suite that passes against a
deliberately broken matcher is not testing the matcher.

KNOWN_LIMITS records the detections this design deliberately gives up, so a
later reader can tell a gap from an accident.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "warn-cross-drive-toolchain-move.py")
SOURCE = open(HOOK, encoding="utf-8").read()

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# A transcript in which an earlier tool call DID ask what the media are, and
# one in which nothing did. `transcript_has_media_check` fails open, so the
# "nothing did" file must still exist -- a missing path reads as discharged.
TMP = tempfile.mkdtemp(prefix="xdrive-hook-")


def _write(name, commands):
    path = os.path.join(TMP, name)
    with open(path, "w", encoding="utf-8") as fh:
        for command in commands:
            fh.write(json.dumps({
                "type": "assistant",
                "message": {"content": [
                    {"type": "tool_use", "name": "Bash",
                     "input": {"command": command}},
                ]},
            }) + "\n")
    return path


CHECKED = _write("checked.jsonl", [
    "git status --short",
    "Get-PhysicalDisk | Format-Table DeviceId, FriendlyName, MediaType, Size",
])
UNCHECKED = _write("unchecked.jsonl", [
    "git status --short",
    "Get-ChildItem C:\\Users\\Work -Directory | Measure-Object Length -Sum",
])

# ---------------------------------------------------------------------------
# Cases. `W*` must warn, `S*` must stay silent. Each is a full PreToolUse
# payload, so the suite exercises the tool gate and the transcript discharge
# rather than only the string matcher.
J = r"C:\Users\Work\.julia"


def bash(command, transcript=UNCHECKED, tool="Bash"):
    return {"tool_name": tool, "transcript_path": transcript,
            "tool_input": {"command": command}}


CASES = {
    # -- must warn ---------------------------------------------------------
    "W1": bash(rf"robocopy {J} D:\julia /E /MOVE"),
    "W2": bash(r"Copy-Item C:\Users\Work\AppData\Local\R "
               r"-Destination D:\R -Recurse", tool="PowerShell"),
    "W3": bash(r'Move-Item "C:\Users\Work\.cargo" "D:\cargo"'),
    "W4": bash(r"wsl --manage Ubuntu --move D:\WSL\Ubuntu"),
    "W5": bash(r"cp -r /c/Users/Work/.m2 /d/m2"),
    "W6": bash(r"mv /mnt/c/Users/Work/.gradle /mnt/d/gradle"),
    "W7": bash(r"Move-Item D:\images\ext4.vhdx C:\vm\ext4.vhdx"),
    "W8": bash(r"Copy-Item C:\a\node_modules D:\b -Recurse"),
    # NEITHER path is recognisable as a depot; only the env var says what
    # this is. The first spelling used `.julia` as the source, which TOOLCHAIN
    # matched directly, so TOOLCHAIN_ENV was never reached and the whole
    # 14-name regex was untested (adversarial review of a331d675, finding 3a).
    "W9": bash(r"$env:JULIA_DEPOT_PATH='D:\depot'; "
               r"robocopy C:\Users\Work\stuff D:\depot /E", tool="PowerShell"),
    # xcopy and rsync are the same verb class
    "W10": bash(r"xcopy C:\Users\Work\.nuget D:\nuget /E /I"),

    # -- must stay silent --------------------------------------------------
    # the whole population for which the slow drive is the RIGHT answer
    "S1": bash(r"robocopy C:\Users\Work\Documents D:\Backup\Documents /MIR"),
    "S2": bash(r'robocopy "C:\Games\Steam" "D:\Steam" /E'),
    "S3": bash(r"Move-Item C:\Users\Work\Videos D:\Media\Videos"),
    # a backup OF a toolchain directory: the HDD is still correct
    "S4": bash(rf"robocopy {J} D:\Backups\julia /E"),
    "S5": bash(rf"robocopy {J} D:\cold-storage\julia /E"),
    # same drive on both sides -- not a media decision at all
    "S6": bash(rf"Copy-Item {J} C:\scratch\julia -Recurse"),
    # the session already asked; nagging a session that knows is the
    # expensive direction for a warn-only guard
    "S7": bash(rf"robocopy {J} D:\julia /E /MOVE", transcript=CHECKED),
    # ... including when the check is chained into this very command
    "S8": bash(r"Get-PhysicalDisk | Format-Table MediaType; "
               rf"robocopy {J} D:\julia /E", tool="PowerShell"),
    # not a relocation verb
    "S9": bash(rf"Get-ChildItem {J} -Recurse | Measure-Object Length -Sum"),
    # `git mv` is not a filesystem relocation of a depot
    "S10": bash(r"git mv scripts/a.py scripts/b.py"),
    # the verb inside a quoted argument is prose, not a command
    "S11": bash(rf'echo "robocopy {J} D:\julia"'),
    # a heredoc BODY documenting the very command this guard is about
    "S12": bash("cat <<'EOF' > notes.md\n"
                rf"robocopy {J} D:\julia /E" "\nEOF"),
    # `wsl --export` writes a tar: a cold sequential archive, HDD-correct
    "S13": bash(r"wsl --export Ubuntu D:\images\ubuntu.tar"),
    # a URL is not a drive letter
    "S14": bash(r"curl -fsSL https://example.com/x.tar && cp x.tar /tmp/"),
    # cross-drive, but nothing toolchain-shaped is named
    "S15": bash(r"robocopy C:\Users\Work\Pictures D:\Pictures /E"),
    # a non-shell tool must never be evaluated at all
    "S16": {"tool_name": "Edit", "transcript_path": UNCHECKED,
            "tool_input": {"command": rf"robocopy {J} D:\julia /E"}},

    # -- cases added from the adversarial review of a331d675 ---------------
    # FP-2: a size survey chained to an unrelated media move. Pooling tokens
    # over the whole command warned, and named `.julia` -- a directory this
    # command does not move.
    "S17": bash(rf"Get-ChildItem {J} -Recurse | Measure-Object Length -Sum; "
                r"robocopy C:\Users\Work\Videos D:\Media\Videos /E"),
    # FP-1: `/mnt/backup` truncated to `/mnt/b`, inventing drive B: and
    # putting the word `backup` out of the exemption's reach.
    "S18": bash(r"rsync -a /mnt/c/Users/work/.julia/ /mnt/backup/julia/"),
    # FP-3: real backup directories carry affixes.
    "S19": bash(rf"robocopy {J} D:\MyBackups\julia /E"),
    # FP-7: `/L` lists and copies nothing.
    "S20": bash(rf"robocopy {J} D:\julia /L"),
    # a `#` comment carrying a separator, which would otherwise put the verb
    # at a command position -- the half of `strip_noise` no case reached
    # before (finding 3b).
    "S21": bash(rf"ls {J}  # ; robocopy {J} D:\julia /E"),
    # FN-1: `wsl --import` carries BOTH the destination and a source tar. It
    # must warn, and the unit assertion below pins WHICH path it names.
    "W11": bash(r"wsl --import Ubuntu D:\WSL\Ubuntu "
                r"C:\downloads\ubuntu-22.04.tar"),
    # FN-2: the `#` strip truncated a real argument, losing the second drive.
    "W12": bash(rf"robocopy {J} /LOG:C:\l#1.txt D:\julia /E"),
    # `--export` without a `.tar` suffix: still a cold archive, still silent.
    # This is what makes the `--export` exclusion independently testable now
    # that the archive filter also protects the suffixed spelling.
    "S22": bash(r"wsl --export Ubuntu D:\exports\ubuntu"),
    # `--import` into the current directory: the only volume-bearing token is
    # the source tar, and an HDD is right for that, so there is nothing to
    # warn about.
    "S23": bash(r"wsl --import Ubuntu . C:\downloads\ubuntu-22.04.tar"),
}

EXPECTED = {cid: cid.startswith("W") for cid in CASES}

WHY = {
    "S1": "an ordinary backup -- the HDD is the correct destination",
    "S2": "a game library: large, cold, sequentially read",
    "S3": "a media library, same class as S2",
    "S4": "a BACKUP of a depot is still a backup",
    "S5": "'cold-storage' is the same exemption as 'backup'",
    "S6": "one drive on both sides: no media decision exists",
    "S7": "the session already ran Get-PhysicalDisk",
    "S8": "the media check is chained into this very command",
    "S9": "measuring a directory is not relocating it",
    "S10": "`git mv` renames tracked files, not a depot",
    "S11": "the verb is inside a quoted argument",
    "S12": "the verb is inside a heredoc body",
    "S13": "`wsl --export` writes a cold tar archive",
    "S14": "an https scheme is not a drive letter",
    "S15": "cross-drive but names nothing toolchain-shaped",
    "S16": "not a shell tool",
    "S17": "the tokens belong to a neighbouring command, not this one",
    "S18": "`/mnt/backup` is a backup, not drive B:",
    "S19": "`MyBackups` is a backup directory like any other",
    "S20": "`/L` lists and copies nothing",
    "S21": "the separator sits inside a `#` comment",
    "S22": "`wsl --export` writes a cold archive whatever it is named",
    "S23": "the only drive-bearing token is the source tar",
}

# Detections this design deliberately gives up. Each is a gap, not an
# accident; recording them here is what keeps a later reader from reading
# silence as coverage.
KNOWN_LIMITS = {
    "a UNC destination (\\\\server\\share) carries no drive letter, so a "
    "relocation onto a network share -- the same hazard class, worse -- is "
    "never seen",
    "a plain POSIX source (/home/work/.cargo) has no volume token, so a "
    "move made from inside WSL is invisible",
    "a path built from a variable (robocopy $src $dst) exposes no path "
    "token at all",
    "a shell-within-a-shell (powershell -Command 'robocopy ...') hides the "
    "verb inside a quoted argument, so the command-position anchor -- which "
    "is what keeps this corpus's own prose out -- also silences it",
    "a separator inside a quoted string splits a segment it should not, which "
    "narrows the token pool and can only lose a detection, never invent one",
    "a backup written to a destination NOT named backup/archive/snapshot "
    "(D:\\2026-09-15\\julia) warns, and is a true false positive",
}


def verdict(script, payload):
    """True when running `script` on `payload` emits the warning."""
    out = subprocess.run(
        [sys.executable, script], input=json.dumps(payload),
        capture_output=True, text=True, timeout=60)
    return "additionalContext" in (out.stdout or "")


print("case tests (full payload through the hook):")
wrong = 0
for cid in sorted(CASES, key=lambda k: (k[0], int(k[1:]))):
    got = verdict(HOOK, CASES[cid])
    want = EXPECTED[cid]
    if got != want:
        wrong += 1
        failures.append(
            f"{cid}: got warn={got}, want warn={want} "
            f"({WHY.get(cid, 'must warn')})")
print(f"  {len(CASES) - wrong}/{len(CASES)} cases behaved as declared")

# ---------------------------------------------------------------------------
# Unit-level assertions on the pieces the payload tests cannot distinguish.
check("paths finds both volumes",
      sorted({v for v, _ in hook.paths(rf"robocopy {J} D:\julia")}),
      ["C", "D"])
check("paths ignores a bare drive with no separator",
      hook.paths("cd C: ; ls"), [])
check("media check recognised (PowerShell)",
      hook.command_is_media_check("Get-PhysicalDisk"), True)
check("media check recognised (Linux)",
      hook.command_is_media_check("lsblk -d -o NAME,ROTA,SIZE"), True)
check("plain lsblk is not a media check",
      hook.command_is_media_check("lsblk -f"), False)
check("missing transcript fails open as discharged",
      hook.transcript_has_media_check(os.path.join(TMP, "nope.jsonl")), True)
check("unchecked transcript is not discharged",
      hook.transcript_has_media_check(UNCHECKED), False)
check("checked transcript is discharged",
      hook.transcript_has_media_check(CHECKED), True)
# The diagnostic must name the real token, not a fragment recovered from
# elsewhere in the command -- a garbled name is how a guard loses credibility.
check("names the offending path",
      hook.find_risky_move(rf"robocopy {J} D:\julia /E")[2], J)
check("names both volumes",
      hook.find_risky_move(rf"robocopy {J} D:\julia /E")[1], ["C", "D"])
# FN-1: `wsl --import <Distro> <InstallLocation> <FileName>`. The note must
# name the live image's location, never the source tar -- the archive is the
# one argument in that command an HDD is unambiguously right for.
check("wsl --import names the install location, not the tar",
      hook.find_risky_move(
          r"wsl --import Ubuntu D:\WSL\Ubuntu C:\downloads\ubuntu-22.04.tar"
      )[2], r"D:\WSL\Ubuntu")
# FP-1: the MOUNT lookahead. `/mnt/backup` is a directory, not drive B:.
check("/mnt/backup is not drive B",
      hook.paths("rsync -a /mnt/c/x/ /mnt/backup/y/"),
      [("C", "/mnt/c/x/")])
# FP-2: tokens come from the relocator's own segment only.
check("tokens are scoped to the relocator's segment",
      hook.find_risky_move(
          rf"Get-ChildItem {J} -Recurse; robocopy C:\a D:\b /E"), None)

# ---------------------------------------------------------------------------
# MUTATION section. Break one load-bearing clause at a time and assert exactly
# which cases flip. `NOTHING FLIPPED` means the clause is untested.
MUTATIONS = {
    "M1_command_position_anchor": (
        "the relocation verb must sit at a COMMAND position, or this "
        "corpus's own prose about the rule trips the guard",
        [('    r"""(?:^|[;&|\\n({])\\s*\n        (?:sudo',
          '    r"""(?:)\\s*\n        (?:sudo')],
        # S11's quoted `robocopy` becomes a command. S12 does NOT flip here,
        # because `strip_noise` blanks the heredoc body before the anchor is
        # ever consulted -- that clause is M5's, and keeping the two apart is
        # what stops one mutation vouching for both.
        #
        # W4 flips the other way, from warn to MISS, which is the direction
        # that catches an over-broad carve-out: unanchored, `\bmove\b` matches
        # inside `--move`, so `wsl --manage ... --move` is read as a plain
        # `move` verb, loses the WSL arm's single-volume allowance, and goes
        # silent. The anchor is what keeps the two verbs apart.
        {"S11", "W4"},
    ),
    "M2_two_volumes_required": (
        "a relocation within ONE drive is not a media decision and must "
        "stay silent",
        [("if not volumes or (len(volumes) < 2 and not is_wsl):",
          "if not volumes or (len(volumes) < 1 and not is_wsl):")],
        # S18 joins S6 once the two-volume test is gone: `/mnt/c/...` is a
        # single volume, and `.julia` supplies the toolchain path.
        {"S6", "S18"},
    ),
    "M3_toolchain_path_required": (
        "the narrowing that makes this defensible: a cross-drive copy "
        "naming no package library, depot or disk image must be silent, "
        "because that is the population the HDD is RIGHT for",
        [("    if toolchain is None:\n        return None",
          "    if toolchain is None:\n        toolchain = tokens[0][1]")],
        # every ordinary cross-drive copy starts warning, including S17's
        # media move (whose tokens the segment scoping already isolates) and
        # S23, whose only token is a cold tar
        {"S2", "S3", "S15", "S17", "S23"},
    ),
    "M4_backup_exemption": (
        "a copy to a backup/archive/snapshot location is a backup, and an "
        "HDD is the correct destination for one even when the source is a "
        "depot",
        [("    if any(BACKUP.search(raw) for _, raw in tokens):\n"
          "        return None",
          "    if False:\n        return None")],
        # S1 does not flip: `Documents` -> `D:\Backup\Documents` names no
        # toolchain path either, so M3's clause already holds it silent. Only
        # the two backups OF a depot depend on this exemption, which is
        # exactly the overlap a per-clause expectation is meant to expose.
        {"S4", "S5", "S19"},
    ),
    "M5_heredoc_and_comment_strip": (
        "a heredoc body is content being written, not a command being run, "
        "and a `#` comment is prose -- both halves now have a case, after "
        "review found the comment half exercised by nothing (finding 3b)",
        [("    text = strip_noise(command)", "    text = command")],
        {"S12", "S21"},
    ),
    "M6_transcript_discharge": (
        "a session that already asked what the media are must not be "
        "nagged -- for a warn-only guard that is the expensive direction",
        [("        if transcript_has_media_check(payload.get("
          '"transcript_path") or ""):\n            return 0',
          "        if False:\n            return 0")],
        {"S7"},
    ),
    "M7_same_command_discharge": (
        "a media check chained into this very command discharges it too",
        [("        if command_is_media_check(command):\n            return 0",
          "        if False:\n            return 0")],
        {"S8"},
    ),
    "M8_wsl_export_excluded": (
        "`wsl --export` writes a cold tar and must not be treated as "
        "placing a live image, unlike `--import`/`--move`",
        [(r"--(?:import|move)\b", r"--(?:import|move|export)\b")],
        # S13 is now protected TWICE -- by this exclusion and by the archive
        # filter M15 covers -- so only S22, whose destination carries no
        # archive suffix, isolates this clause.
        {"S22"},
    ),
    "M10_mount_terminator": (
        "a `/mnt/<word>` path is a directory, not a drive letter -- the "
        "greedy spelling invented drive B: for `/mnt/backup` AND put the "
        "word `backup` beyond the exemption's reach",
        [(r"/(?:mnt|cygdrive)/([A-Za-z])(?=[/\s\"';|&,]|$)(?:/[^\s\"';|&,]*)?",
          r"/(?:mnt|cygdrive)/([A-Za-z])(?:/[^\s\"';|&,]*)?")],
        {"S18"},
    ),
    "M11_segment_scoping": (
        "path tokens come from the relocator's OWN segment; pooling them "
        "over the whole command makes a survey chained to an unrelated move "
        "warn, and names a directory the command does not touch",
        [("    segment = _segment_at(text, at)", "    segment = text")],
        {"S17"},
    ),
    "M12_toolchain_env_fallback": (
        "an env var naming a depot identifies the directory when neither "
        "path is recognisable on its own",
        [("    if toolchain is None and TOOLCHAIN_ENV.search(text):",
          "    if False:")],
        {"W9"},
    ),
    "M13_comment_needs_whitespace": (
        "a `#` only opens a comment at the start of a word -- the "
        "unanchored spelling truncated `/LOG:C:\\l#1.txt` and lost the "
        "second drive letter with it",
        [(r'COMMENT = re.compile(r"(?m)(?:^|(?<=[ \t]))(?<![\\$])#[^\n]*$")',
          r'COMMENT = re.compile(r"(?m)(?<![\\$])#[^\n]*$")')],
        {"W12"},
    ),
    "M14_rehearsal_flags": (
        "`robocopy /L`, `-WhatIf` and `rsync -n` move nothing, so warning "
        "about one is pure noise",
        [("    if REHEARSAL.search(text):\n        return None",
          "    if False:\n        return None")],
        {"S20"},
    ),
    "M15_archive_is_not_the_live_image": (
        "the `.tar` in a `wsl --import` is the SOURCE an HDD is right for; "
        "naming it instead of the install location inverts the advice",
        [("        live = [raw for _, raw in tokens "
          "if not ARCHIVE_FILE.search(raw)]",
          "        live = [raw for _, raw in tokens]")],
        # W11 still warns either way -- only the NAMED token changes there,
        # which `verdict()` cannot see, so the unit assertion above is what
        # pins that half. S23 is the boolean half: its only drive-bearing
        # token IS the archive, so losing the filter turns a silent command
        # into a warning about a cold tar.
        {"S23"},
    ),
    "M9_shell_tool_gate": (
        "a non-shell tool carrying a `command` key must never be evaluated",
        [('SHELL_TOOLS = ("Bash", "bash", "PowerShell", "powershell", '
          '"run_command",\n               "execute_command", "terminal", '
          '"shell")',
          'SHELL_TOOLS = ("Bash", "bash", "PowerShell", "powershell", '
          '"run_command",\n               "execute_command", "terminal", '
          '"shell", "Edit")')],
        {"S16"},
    ),
}

print("\nmutation tests (break one clause, see which cases flip):")
mutation_wrong = 0
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, replace in edits:
        count = mutated.count(find)
        if count != 1:
            sys.exit(f"FATAL: clause {clause}'s anchor is not present exactly "
                     f"once in {HOOK} (found {count}). The mutation harness is "
                     f"measuring nothing; re-derive the anchor.\n---\n{find}\n"
                     "---")
        mutated = mutated.replace(find, replace)

    # NOT `dir=HERE`: `scripts/test_hooks.py` globs `hooks/*.py` for subjects
    # and requires a `test-<stem>.py` for each, so a mutant left behind by an
    # interrupted run -- or merely present during a concurrent one -- reads as
    # a hook with no test and fails CI. This hook imports nothing relative to
    # its own location, so the system temp directory is safe for it
    # (adversarial review of a331d675, finding 3d).
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        flipped = {cid for cid in CASES
                   if verdict(path, CASES[cid]) != EXPECTED[cid]}
    finally:
        os.unlink(path)

    ok = flipped == expected_flips
    mutation_wrong += not ok
    if not flipped and expected_flips:
        note = "NOTHING FLIPPED -- this clause is untested"
    elif ok:
        note = "flipped " + ", ".join(sorted(flipped))
    else:
        note = f"flipped {sorted(flipped)}, expected {sorted(expected_flips)}"
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<30} {statement}\n"
          f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under mutation")
print(f"{len(KNOWN_LIMITS)} known limits recorded (see KNOWN_LIMITS)")

if failures or mutation_wrong:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
