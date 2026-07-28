#!/usr/bin/env python3
"""Check that the installed AI config matches this repo, and optionally repair it.

`bootstrap.sh` installs this repo into a consumer directory (`~/.claude` by
default) by symlinking, so a `git pull` in the checkout is normally enough to
refresh what an agent loads. That assumption fails in two environments, and it
fails *silently* in both:

  1. **Remote/web containers pre-seed `~/.claude/skills/`** with their own real
     directories before `bootstrap.sh` runs. Bootstrap merges into a
     pre-existing real directory child by child and skips any name already
     present, so a pre-seeded copy of a skill we also ship is never replaced.
     It shadows the repo version for the whole session, and `git pull` cannot
     dislodge it.
  2. **On Windows, Git Bash `ln -s` silently makes real copies.** Every entry
     is then a snapshot that never tracks a later pull.

Both produce the same defect: an agent loads an older revision of a skill and
follows a procedure the repo has since changed, with nothing anywhere reporting
a problem. ai-config#755 measured it in a live container -- 42 of 172 skills
stale, several at well under half their current length, including the heaviest
review-loop skills.

Per `shared/workflow/algorithmatize-checks.md`, "does the install match the
repo" is decidable by computation over data already on disk, so it belongs in
an instrument rather than in anyone's memory of running a `diff` loop by hand.
Per `shared/principles/fail-fast.md`, this one always prints a count: bare
silence would otherwise mean either "all fresh" or "examined nothing", and the
second is exactly the failure this check exists to catch.

## Classifications

Each entry the installer would place gets exactly one status:

  ok           symlink resolving into this repo -- tracks future pulls
  stale        real copy whose content differs from the repo (ACTIVE defect:
               this is what shadows a newer skill)
  unlinked     real copy whose content currently matches the repo (LATENT
               defect: correct today, will not track the next pull)
  missing      the repo ships it; the consumer directory does not have it
  misdirected  symlink resolving somewhere other than this repo
  foreign      present in the consumer directory, absent from the repo

## Why `foreign` is reported but never removed

ai-config#755 suggested pruning entries with no repo counterpart, on the
reading that they are skills we deleted and whose removal never propagated.
That is not safe, because the category mixes two very different things. Of the
7 found in a live container, `docx`, `pdf`, `pptx`, `xlsx` and `skill-creator`
are Anthropic-provided built-ins that were never ours -- `docx` carries
`license: Proprietary. LICENSE.txt has complete terms` -- and deleting them
would remove working harness functionality.

Git history cannot separate the two either, which is the load-bearing reason
this stays manual rather than a heuristic. Remote containers check the repo out
**shallow** (50 commits in the container that motivated this script), so
`git log --diff-filter=D -- skills/<name>` returns nothing for a genuinely
deleted skill and for a foreign built-in alike. A classifier built on it would
report identical evidence for both in precisely the environment where this
check matters most. So `foreign` is listed for a human to judge and otherwise
left alone; `--fix` never touches it.

## Scope

This checks the Claude consumer directory. `bootstrap.sh` also installs Codex
wrappers into `~/.codex/skills` and skills into `~/.gemini`; those are not
covered here rather than half-covered. `--consumer-dir` retargets the check.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Mirrors bootstrap.sh's own exclusions, and must stay in step with them:
# references/ is example material rather than consumable config, and
# codex-skills/ is installed into ~/.codex, not ~/.claude. Dot-directories are
# excluded implicitly -- bootstrap's `for src in "$SCRIPT_DIR"/*/` loop runs
# without dotglob, so .github/ and .claude/ never enter it.
EXCLUDED_DIRS = {"references", "codex-skills", "node_modules"}

# bootstrap.sh links every top-level *.md except the repo's own README.
EXCLUDED_TOP_LEVEL_FILES = {"README.md"}

# Incidental files that appear beside installed content without being part of
# it. Counting these as content would report a spurious `stale` for an entry
# whose tracked files all match.
IGNORED_NAMES = {"__pycache__", ".DS_Store", ".git", ".pytest_cache"}

# Statuses `--fix` can repair, and those it reports without touching.
FIXABLE = ("stale", "unlinked", "missing")
REPORT_ONLY = ("misdirected", "foreign")

BACKUP_DIR_NAME = ".ai-config-backups"


class Entry:
    """One installable path, with the verdict comparing repo against consumer."""

    def __init__(self, group: str, name: str, status: str, repo_path: Path | None,
                 install_path: Path, detail: str = ""):
        self.group = group
        self.name = name
        self.status = status
        self.repo_path = repo_path
        self.install_path = install_path
        self.detail = detail

    @property
    def label(self) -> str:
        return f"{self.group}/{self.name}" if self.group else self.name


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_fingerprint(path: Path) -> dict[str, str]:
    """Map every file under `path` to a digest, keyed by path relative to it.

    Compares whole trees rather than just `SKILL.md`. The hand-run sweep in
    `CLAUDE.md` only diffed `SKILL.md`, so a skill whose supporting files
    (references/, scripts/) had drifted read as fresh.
    """
    if path.is_file():
        return {"": file_digest(path)}

    fingerprint: dict[str, str] = {}
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_NAMES]
        for filename in filenames:
            if filename in IGNORED_NAMES:
                continue
            full = Path(root) / filename
            rel = full.relative_to(path).as_posix()
            # A broken symlink inside an installed tree cannot be read; record
            # it by target so it compares unequal to a real file rather than
            # aborting the whole sweep.
            if full.is_symlink() and not full.exists():
                fingerprint[rel] = f"broken-symlink:{os.readlink(full)}"
            else:
                fingerprint[rel] = file_digest(full)
    return fingerprint


def resolves_into_repo(link: Path, repo_root: Path) -> bool:
    try:
        target = link.resolve()
    except OSError:
        return False
    return target == repo_root or repo_root in target.parents


def classify(repo_path: Path | None, install_path: Path, group: str, name: str,
             repo_root: Path) -> Entry:
    """Compare one repo path against its installed counterpart."""
    installed_exists = install_path.is_symlink() or install_path.exists()

    if repo_path is None:
        return Entry(group, name, "foreign", None, install_path)

    if not installed_exists:
        return Entry(group, name, "missing", repo_path, install_path)

    if install_path.is_symlink():
        if resolves_into_repo(install_path, repo_root):
            return Entry(group, name, "ok", repo_path, install_path)
        return Entry(group, name, "misdirected", repo_path, install_path,
                     detail=os.readlink(install_path))

    # A real file or directory sits where a symlink into the repo belongs. It
    # is a defect either way; content decides whether it is active or latent.
    if tree_fingerprint(repo_path) == tree_fingerprint(install_path):
        return Entry(group, name, "unlinked", repo_path, install_path)
    return Entry(group, name, "stale", repo_path, install_path)


def collect(repo_root: Path, consumer_dir: Path) -> list[Entry]:
    """Build the full verdict list, mirroring bootstrap.sh's install model."""
    entries: list[Entry] = []

    for src in sorted(repo_root.glob("*.md")):
        if src.name in EXCLUDED_TOP_LEVEL_FILES:
            continue
        entries.append(classify(src, consumer_dir / src.name, "", src.name, repo_root))

    for src in sorted(p for p in repo_root.iterdir() if p.is_dir()):
        if src.name.startswith(".") or src.name in EXCLUDED_DIRS:
            continue
        dest = consumer_dir / src.name

        # Whole group symlinked (or absent, or pointing elsewhere): one verdict
        # covers it, and its children need no enumeration -- they are the
        # repo's own files by construction.
        if dest.is_symlink() or not dest.exists():
            entries.append(classify(src, dest, "", src.name, repo_root))
            continue

        # A real directory is already here, so bootstrap merges child by child
        # and this check has to follow it in. This is where pre-seeded copies
        # shadow the repo.
        names = {c.name for c in src.iterdir()} | {c.name for c in dest.iterdir()}
        for name in sorted(names):
            if name in IGNORED_NAMES:
                continue
            child_src = src / name
            entries.append(classify(
                child_src if child_src.exists() else None,
                dest / name, src.name, name, repo_root,
            ))

    return entries


def backup_and_replace(entry: Entry, backup_root: Path, use_symlinks: bool) -> str:
    """Move an offending installed path aside, then reinstall it from the repo.

    Never deletes: the displaced copy is moved under `backup_root` so a
    pre-seeded entry that turns out to have been wanted is recoverable.
    """
    # Not an assert: `python -O` strips those, and a None repo_path reaching
    # shutil.move()/os.symlink() below would surface as a confusing TypeError
    # deep in the call rather than naming the entry that caused it.
    if entry.repo_path is None:
        raise ValueError(
            f"backup_and_replace called on non-repairable entry: {entry.label!r}"
        )

    if entry.install_path.is_symlink() or entry.install_path.exists():
        destination = backup_root / (entry.group or "_root") / entry.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(entry.install_path), str(destination))

    entry.install_path.parent.mkdir(parents=True, exist_ok=True)

    if use_symlinks:
        os.symlink(entry.repo_path, entry.install_path)
        return "linked"

    # Windows Git Bash and any other symlink-less environment: a copy is the
    # best available install, so keep it correct even though it cannot track
    # future pulls. Re-running this check after each pull is what closes that
    # gap, which is why the session-start hook runs it unconditionally.
    if entry.repo_path.is_dir():
        shutil.copytree(entry.repo_path, entry.install_path)
    else:
        shutil.copy2(entry.repo_path, entry.install_path)
    return "copied"


def symlinks_supported(probe_dir: Path) -> bool:
    probe = probe_dir / ".ai-config-symlink-probe"
    try:
        if probe.is_symlink() or probe.exists():
            probe.unlink()
        os.symlink(probe_dir, probe)
    except (OSError, NotImplementedError):
        return False
    finally:
        if probe.is_symlink():
            probe.unlink()
    return True


def summarize(entries: list[Entry], counts: dict[str, int]) -> None:
    by_status: dict[str, list[Entry]] = {}
    for entry in entries:
        by_status.setdefault(entry.status, []).append(entry)

    for status in ("stale", "unlinked", "missing", "misdirected", "foreign"):
        matching = by_status.get(status, [])
        if not matching:
            continue
        print(f"\n{status.upper()} ({len(matching)}):")
        for entry in matching:
            suffix = f"  -> {entry.detail}" if entry.detail else ""
            print(f"  {entry.label}{suffix}")

    total = len(entries)
    parts = ", ".join(f"{counts.get(s, 0)} {s}"
                      for s in ("ok", "stale", "unlinked", "missing",
                                "misdirected", "foreign"))
    print(f"\nchecked {total} installed entries: {parts}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--consumer-dir",
        default=os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude")),
        help="directory bootstrap.sh installs into (default: $CLAUDE_HOME or ~/.claude)",
    )
    parser.add_argument(
        "--repo-root", default=str(REPO_ROOT),
        help="ai-config checkout to compare against (default: this script's repo)",
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="repair stale/unlinked/missing entries, backing up whatever is displaced",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 when a repairable defect remains (default: advisory, always "
             "exits 0). misdirected/foreign entries never gate -- see the module "
             "docstring",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    consumer_dir = Path(args.consumer_dir).expanduser()

    print(f"ai-config install check: {consumer_dir} vs {repo_root}")

    if not consumer_dir.is_dir():
        # Not a defect: CI runners and fresh machines have no install yet.
        # Said out loud rather than exiting silently, so "nothing to check"
        # can never be mistaken for "everything is fine".
        print(f"no consumer directory at {consumer_dir} -- nothing installed to check")
        return 0

    entries = collect(repo_root, consumer_dir)

    repaired: list[str] = []
    if args.fix:
        fixable = [e for e in entries if e.status in FIXABLE]
        if fixable:
            use_symlinks = symlinks_supported(consumer_dir)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_root = consumer_dir / BACKUP_DIR_NAME / stamp
            for entry in fixable:
                action = backup_and_replace(entry, backup_root, use_symlinks)
                repaired.append(f"  {action:8} {entry.label}  (was {entry.status})")
                entry.status = "ok"
            noun = "entry" if len(repaired) == 1 else "entries"
            print(f"\nrepaired {len(repaired)} {noun} "
                  f"(displaced copies backed up under {backup_root}):")
            print("\n".join(repaired))

    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1

    summarize(entries, counts)

    # Gate on repairable defects only. `misdirected` and `foreign` are real
    # signals worth printing, but neither has an automatic remedy -- a symlink
    # into another checkout may be a deliberate developer setup, and `foreign`
    # is unclassifiable here for the shallow-clone reason above. Failing on
    # them would leave no action that clears the check, and an instrument that
    # cannot be satisfied is one everybody learns to ignore.
    defects = sum(counts.get(s, 0) for s in FIXABLE)
    if defects and not args.fix:
        print(f"\n{defects} entries do not track this repo. "
              f"Re-run with --fix to repair them.")

    if args.strict and defects:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
