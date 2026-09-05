#!/usr/bin/env python3
"""Report markdown records that look stale: orphaned, or old but still linked.

Two buckets, deliberately kept apart because they call for different actions:

* **orphans** -- zero inbound references from anywhere in the scanned corpus.
  Nothing points at them, so nothing reads them by accident.
* **old-but-referenced** -- older than the threshold AND still referenced from
  at least one file.  These are the harmful ones: a fresh agent walking the
  link graph reads them as current project state.

Two exemptions, both **reported** rather than silently applied, because an
exemption nobody can see is indistinguishable from a detector that missed the
file (shared/principles/fail-fast.md):

* **entry points** -- repository-root markdown files.  They are reached
  directly (a human landing on the repo, or the harness auto-loading
  `CLAUDE.md`) rather than through the link graph, so zero inbound references
  says nothing about them.
* **generated** -- files carrying a generator's own marker.  Nothing links to
  a generated wrapper by design, so counting them as orphans buries the
  hand-written records the orphan bucket exists to surface.

Both remain eligible for the old-but-referenced bucket, since a stale record
that something does link to is exactly as harmful whoever wrote it.

An inbound reference is a markdown link OR a line-initial `@path` auto-load
import.  The second matters: this repo's `CLAUDE.md` reaches most of `shared/`
through `@shared/...` imports and never links to them, so a link-only walk
reports those fragments as orphans while the harness loads them into every
session.

Sorted by age x inbound references, so the doc that is both oldest and most
referenced sorts first.

Last-modified comes from `git log`, not the filesystem: git resets mtimes on
checkout, so an mtime-based age is meaningless right after a clone or a pull
(see shared/workflow/keep-checkouts-fresh.md).

**In a shallow clone the age bucket is uninformative and says so.**  `git log`
cannot see past the fetch depth, so every file reads as no older than the
oldest fetched commit and the old-but-referenced count collapses toward zero
for a reason that has nothing to do with corpus health.  That is a vacuous
zero, so the report labels it rather than printing a bare `0`.

Advisory: always exits 0.  It reports what it examined, not only what it
found, so a run that scanned nothing is distinguishable from a clean corpus
(see shared/principles/fail-fast.md).

Usage:
    python3 scripts/check-stale-records.py
    python3 scripts/check-stale-records.py --stale-days 45 --json
    python3 scripts/check-stale-records.py --root /path/to/other/checkout
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import strip_code_spans, strip_fences  # noqa: E402

# Same link-graph vocabulary as scripts/check-links.py, so the two agree on
# what counts as a relative link.
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# A Claude Code auto-load import: `@` in the first column, then a path.  These
# are how CLAUDE.md pulls in shared/ fragments, and they are invisible to LINK.
AUTOLOAD = re.compile(r"^@(\S+)", re.M)

DEFAULT_SCAN_GLOBS = [
    "skills/**/*.md",
    "codex-skills/**/*.md",
    "commands/**/*.md",
    "docs/**/*.md",
    "memories/**/*.md",
    "references/**/*.md",
    "shared/**/*.md",
    "*.md",
]

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")

# Substrings that mark a file as machine-generated.  Deliberately narrow: a
# wrong exemption is a SILENT miss in the orphan bucket, so a loose marker
# (e.g. a bare "DO NOT EDIT", which ordinary prose about generated files can
# contain) would quietly shrink the bucket this script exists to fill.
# Extend per-repo with --generated-marker rather than by widening the default.
DEFAULT_GENERATED_MARKERS = (
    "@generated",
    "generated Codex wrapper",
)

# Only the header region is searched for a marker, so a fragment that merely
# discusses generated files further down is not exempted by mentioning one.
GENERATED_HEADER_CHARS = 4000

DEFAULT_STALE_DAYS = 30
SECONDS_PER_DAY = 86400


def is_external(target: str) -> bool:
    return target.startswith(SKIP_PREFIXES) or "://" in target


def _clean_target(target: str) -> str | None:
    """Normalize one raw target, or None if it is not a repo-relative path."""
    target = target.strip()
    if not target or is_external(target):
        return None
    if "<" in target or ">" in target:
        return None  # angle-bracket placeholder, e.g. <owner>/<repo>
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:
        return None  # pure in-page anchor
    if "/" not in path_part and "." not in path_part:
        return None  # bare-word placeholder in an example, e.g. (url)
    return path_part


def link_targets(text: str) -> list[str]:
    """Relative markdown-link targets in `text`, ignoring code."""
    stripped = strip_code_spans(strip_fences(text), replacement="")
    targets = []
    for target in LINK.findall(stripped):
        cleaned = _clean_target(target)
        if cleaned is not None:
            targets.append(cleaned)
    return targets


def import_targets(text: str) -> list[str]:
    """Every Claude Code auto-load import (`@path` in col 1) in `text`."""
    stripped = strip_code_spans(strip_fences(text), replacement="")
    targets = []
    for match in AUTOLOAD.finditer(stripped):
        target = match.group(1).strip()
        cleaned = _clean_target(target)
        if cleaned is not None:
            targets.append(cleaned)
    return targets


def reference_targets(text: str) -> list[str]:
    """Every inbound-reference target in `text`: links plus auto-load imports."""
    return link_targets(text) + import_targets(text)


def is_generated(text: str, markers: tuple[str, ...]) -> bool:
    """True if the file's header carries a generator's own marker."""
    return any(m in text[:GENERATED_HEADER_CHARS] for m in markers)


def scan_files(root: Path, globs: list[str]) -> list[Path]:
    seen: set[Path] = set()
    for glob in globs:
        for md in root.glob(glob):
            if md.is_file():
                seen.add(md.resolve())
    return sorted(seen)


def read_texts(files: list[Path]) -> dict[Path, str]:
    """Read every scanned file once; unreadable files map to an empty string."""
    texts: dict[Path, str] = {}
    for md in files:
        try:
            texts[md] = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            texts[md] = ""
    return texts


def inbound_counts(files: list[Path], texts: dict[Path, str]) -> dict[Path, int]:
    """Inbound reference count per scanned file.

    References pointing outside the scanned set are ignored -- this measures
    how reachable each scanned record is, not whether every link resolves
    (that is check-links.py's job).
    """
    counts: dict[Path, int] = {f: 0 for f in files}
    for md in files:
        for target in reference_targets(texts.get(md, "")):
            resolved = (md.parent / target).resolve()
            if resolved in counts and resolved != md:
                counts[resolved] += 1
    return counts


def git_last_modified(root: Path) -> dict[Path, int]:
    """Map each tracked path to the commit time of its most recent commit.

    One `git log` pass rather than one per file.  `@` prefixes the timestamp
    lines so they cannot be confused with paths.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--format=@%ct", "--name-only",
             "--no-renames"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}

    times: dict[Path, int] = {}
    current: int | None = None
    for line in out.splitlines():
        if not line:
            continue
        if line.startswith("@"):
            current = int(line[1:])
            continue
        if current is None:
            continue
        path = (root / line).resolve()
        times.setdefault(path, current)
    return times


def is_shallow(root: Path) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return out == "true"


def is_entry_point(md: Path, root: Path) -> bool:
    """True for a repository-root markdown file.

    An entry point is reached directly rather than through the link graph, so
    its inbound-reference count carries no information and it must not be
    reported as an orphan.  Depth is the whole test: `README.md` and
    `CLAUDE.md` sit at depth 0, every record this script exists to police sits
    deeper.
    """
    try:
        return md.resolve().parent == root.resolve()
    except OSError:
        return False


def classify(
    files: list[Path],
    counts: dict[Path, int],
    texts: dict[Path, str],
    times: dict[Path, int],
    now: int,
    stale_seconds: int,
    root: Path,
    markers: tuple[str, ...],
) -> dict[str, list[dict]]:
    """Split scanned files into the four report buckets plus unknown-age."""
    orphans: list[dict] = []
    old_referenced: list[dict] = []
    unknown: list[dict] = []
    entry_points: list[dict] = []
    generated: list[dict] = []

    for md in files:
        refs = counts.get(md, 0)
        mtime = times.get(md.resolve())
        if mtime is None:
            unknown.append({"path": md, "refs": refs, "age_days": None})
            continue
        age_days = (now - mtime) / SECONDS_PER_DAY
        record = {"path": md, "refs": refs, "age_days": age_days}
        if (now - mtime) > stale_seconds and refs > 0:
            old_referenced.append(record)
        elif refs == 0:
            # Reported rather than dropped, so each exemption stays visible.
            if is_generated(texts.get(md, ""), markers):
                generated.append(record)
            elif is_entry_point(md, root):
                entry_points.append(record)
            else:
                orphans.append(record)

    orphans.sort(key=lambda r: -r["age_days"])
    old_referenced.sort(key=lambda r: -(r["age_days"] * r["refs"]))
    unknown.sort(key=lambda r: str(r["path"]))
    entry_points.sort(key=lambda r: str(r["path"]))
    generated.sort(key=lambda r: str(r["path"]))
    return {
        "orphans": orphans,
        "old_referenced": old_referenced,
        "unknown_age": unknown,
        "entry_points": entry_points,
        "generated": generated,
    }


def collect(
    root: Path,
    globs: list[str],
    stale_days: int,
    now: int | None = None,
    times: dict[Path, int] | None = None,
    shallow: bool | None = None,
    markers: tuple[str, ...] = DEFAULT_GENERATED_MARKERS,
) -> dict:
    """Scan `root` and return the full report as data.

    `times` and `shallow` are injectable so tests can supply a synthetic
    history rather than depending on a real git repository.
    """
    files = scan_files(root, globs)
    texts = read_texts(files)
    counts = inbound_counts(files, texts)
    if times is None:
        times = git_last_modified(root)
    if now is None:
        now = int(time.time())
    if shallow is None:
        shallow = is_shallow(root)
    buckets = classify(
        files, counts, texts, times, now, stale_days * SECONDS_PER_DAY,
        root, markers,
    )
    return {
        "root": root,
        "examined": len(files),
        "stale_days": stale_days,
        "shallow_clone": shallow,
        # The age bucket compares against `git log`, which cannot see past a
        # shallow clone's fetch depth -- so its count is a fact about the
        # clone, not about the corpus, and must not be read as a verdict.
        "age_informative": not shallow,
        **buckets,
    }


def format_report(report: dict, limit: int) -> str:
    root: Path = report["root"]

    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(root))
        except ValueError:
            return str(p)

    def block(title: str, records: list[dict], show_refs: bool) -> list[str]:
        out = ["", title]
        for r in records[:limit]:
            age = "     ?" if r["age_days"] is None else f"{r['age_days']:6.0f}"
            refs = f" x {r['refs']:3d} refs" if show_refs else "            "
            out.append(f"  {age}d{refs}  {rel(r['path'])}")
        if len(records) > limit:
            out.append(f"  ... and {len(records) - limit} more")
        return out

    lines = [
        f"Examined {report['examined']} markdown files under {root} "
        f"(stale threshold: {report['stale_days']} days).",
    ]

    old = report["old_referenced"]
    if report["age_informative"]:
        header = f"Old but still referenced: {len(old)}"
    else:
        header = (
            f"Old but still referenced: {len(old)} "
            f"-- UNINFORMATIVE, see the shallow-clone note below"
        )
    lines += block(header, old, show_refs=True)
    lines += block(
        f"Orphans (no inbound links or imports): {len(report['orphans'])}",
        report["orphans"],
        show_refs=False,
    )

    if report["generated"]:
        lines += block(
            f"Generated (carry a generator marker, exempt from orphans): "
            f"{len(report['generated'])}",
            report["generated"],
            show_refs=False,
        )
    if report["entry_points"]:
        lines += block(
            f"Entry points (root-level, exempt from orphans): "
            f"{len(report['entry_points'])}",
            report["entry_points"],
            show_refs=False,
        )
    if report["unknown_age"]:
        lines += block(
            f"Unknown age (no commit found -- shallow clone or untracked): "
            f"{len(report['unknown_age'])}",
            report["unknown_age"],
            show_refs=False,
        )

    if report["shallow_clone"]:
        lines.append("")
        lines.append(
            "Note: shallow clone. `git log` cannot see past the fetch depth, "
            "so every file reads as no older than the oldest fetched commit "
            "and the age bucket above carries no information about the "
            "corpus. Re-run against a full clone "
            "(`git fetch --unshallow`) before reading it. The orphan bucket "
            "is unaffected: it is a link-graph fact, not an age one."
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root to scan (default: this repo)",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"age threshold in days (default: {DEFAULT_STALE_DAYS})",
    )
    parser.add_argument(
        "--glob",
        action="append",
        dest="globs",
        help="scan glob, repeatable (default: this repo's markdown trees)",
    )
    parser.add_argument(
        "--generated-marker",
        action="append",
        dest="markers",
        help=(
            "header substring marking a file as generated, repeatable "
            f"(default: {', '.join(DEFAULT_GENERATED_MARKERS)})"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="max rows to print per bucket (default: 20)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    globs = args.globs or DEFAULT_SCAN_GLOBS
    markers = tuple(args.markers) if args.markers else DEFAULT_GENERATED_MARKERS
    report = collect(root, globs, args.stale_days, markers=markers)

    if args.json:
        payload = {
            "root": str(root),
            "examined": report["examined"],
            "stale_days": report["stale_days"],
            "shallow_clone": report["shallow_clone"],
            "age_informative": report["age_informative"],
        }
        for bucket in (
            "old_referenced", "orphans", "generated", "entry_points",
            "unknown_age",
        ):
            payload[bucket] = [
                {
                    "path": str(r["path"].relative_to(root))
                    if r["path"].is_relative_to(root)
                    else str(r["path"]),
                    "refs": r["refs"],
                    "age_days": (
                        None if r["age_days"] is None else round(r["age_days"], 1)
                    ),
                }
                for r in report[bucket]
            ]
        print(json.dumps(payload, indent=2))
    else:
        print(format_report(report, args.limit))

    return 0  # advisory


if __name__ == "__main__":
    sys.exit(main())
