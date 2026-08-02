#!/usr/bin/env python3
"""Measure the context a repo auto-loads, and what a pin bump would add.

`scripts/check-memory-file-size.py` measures files that are read **on
demand**. This measures the ones that are **always** read: `CLAUDE.md` and
the transitive closure of its `@path` imports, which Claude Code loads in
full at launch. That is an unconditional per-session cost, paid whether or
not any of it turns out to be relevant, so it is the expensive half and was
the unmeasured one (ai-config#897).

A per-file line count cannot catch this, and never could -- no single
fragment in this corpus is unreasonable, and the total is. Nor does
splitting a fragment into more imports help, because Claude Code's memory
docs are explicit that "splitting into `@path` imports helps organization
but doesn't reduce context, since imported files load at launch". Only a
split *across* the auto-load boundary reduces loaded bytes. So the budget
has to be closure-level.

Two modes, from ai-config#1028:

  1. **Budget** -- walk a checkout's closure and compare the total against
     `--budget`. Works for ai-config itself and for any consumer repo whose
     `.ai-config` submodule is populated.

  2. **Pin-bump delta** -- with `--compare REV`, re-measure the same import
     list with `.ai-config/...` paths resolved at REV instead, and report
     the difference. A consumer's import list is fixed; what changes under a
     bump is what those files weigh. Measured on `ucdavis/bcs` at a pin
     three days old, the same 33 imports had grown +62%, and nothing
     reported it -- the gitlink diff is one line.

Per `shared/workflow/algorithmatize-checks.md`, "how many bytes does this
repo load before it starts" is decidable over data already on disk, so it
belongs in an instrument rather than in anyone's periodic judgment.

Threshold rationale (`--budget`, default below):

  200,000 bytes is roughly 50k tokens, a quarter of a 200k-token context
  window. The closure is a tax levied before any work happens, so the
  question the budget answers is how much of the window remains for the
  task -- the files an agent must actually read, its tool output, and the
  conversation. Leaving three quarters is a defensible line; leaving half
  would be generous for a fixed overhead that grows monotonically. Both this
  and `--bytes-per-token` are parameters rather than literals, per
  `shared/coding/configurable-parameters.md`.

Reports what it examined, not only what it found: a closure that resolved
zero files must be distinguishable from one that is comfortably under
budget, since both would otherwise print a small number and exit 0. A
dangling **anchored** import is reported and fails even without `--strict`,
being a broken reference rather than a size finding -- see
`shared/principles/fail-fast.md` on checks whose failure path and pass path
look alike. An unresolved **inline** `@token` is reported but does not fail,
since most are prose (`@claude` mentions, email addresses) rather than
mistyped imports.

Advisory otherwise: exits 0 over budget unless `--strict` is passed. The
same stance ai-config#695 settled for the memory-file check -- crossing the
line is a prompt to decide what comes out, not a defect that should block an
unrelated PR. Under `--strict` in `--compare` mode, a bump that would cross
the budget fails too, even while the current pin is under it.
"""
from __future__ import annotations

import argparse
import posixpath
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_BUDGET_BYTES = 200_000
DEFAULT_ROOT = "CLAUDE.md"

# English prose runs roughly 3.5-4.5 bytes per token, so a token figure from
# any single divisor is an estimate with about +/-15% in it. Byte counts are
# exact, which is why the budget itself is denominated in bytes and tokens
# are only ever shown alongside as a reader aid.
DEFAULT_BYTES_PER_TOKEN = 4

# Claude Code evaluates an import written as `@path` but NOT one inside a
# code span or fenced code block -- its docs say "Import parsing skips
# Markdown code spans and fenced code blocks". Both are stripped before
# matching for that reason; a corpus that documents its own `@`-import
# syntax in examples would otherwise import whatever those examples name.
#
# Imports are NOT line-anchored. The docs say to "reference them with `@`
# syntax anywhere in your CLAUDE.md", and their own example is inline
# prose: "See @README for project overview". So both forms are matched.
#
# The two are tracked separately, because they warrant different failure
# behaviour rather than different counting. An unresolved ANCHORED import
# is almost certainly a broken reference. An unresolved INLINE token is
# usually prose -- `@claude` mentions, email addresses, and roxygen tags,
# all of which this corpus contains in quantity. Failing on those would
# make the check cry wolf, which is the failure mode
# `shared/workflow/algorithmatize-checks.md` warns about; silently
# dropping them would under-report a consumer's real closure, which is
# the failure `shared/principles/fail-fast.md` warns about. Counting both
# when they resolve, and failing only on the anchored ones, is what
# avoids each.
_ANCHORED_IMPORT_RE = re.compile(r"^@([^\s`]+)$", re.MULTILINE)
_INLINE_IMPORT_RE = re.compile(r"(?<![\w`])@([^\s`]+?)(?=[.,;:!?)\]]*(?:\s|$))")

# Both delimiters must match a RUN of markers, not a fixed one. A fenced
# block may open with three or more backticks or tildes, and a code span
# with any number of backticks -- so ``@a.md`` survived a single-backtick
# pattern (it stripped the two empty pairs and left the token), and a `~~~`
# block was not recognised at all. Either way a documented example became
# a counted import.
#
# The code span is deliberately bounded to ONE LINE (`[^\n]*?`, not
# `[\s\S]*?`). A newline-spanning version pairs a stray backtick with
# another one much later in the file and strips everything between,
# swallowing real imports: measured on this repo's own CLAUDE.md, it cut
# the anchored-import count from 69 to 50 and the closure from 70 files to
# 51. Bounding to a line also matches CommonMark, where a code span cannot
# contain a blank line.
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})[^\n]*$[\s\S]*?^\1[`~]*[ \t]*$", re.MULTILINE)
_CODE_SPAN_RE = re.compile(r"(`+)[^\n]*?\1(?!`)")

# Claude Code stops following imports after this many hops: its docs say
# "Imported files can recursively import other files, with a maximum depth
# of four hops". A deeper file is not loaded, so counting it would inflate
# both the closure total and the pin-bump delta.
MAX_IMPORT_DEPTH = 4


def import_paths(text: str) -> tuple[list[str], list[str]]:
    """The `@path` imports a CLAUDE.md-style file declares.

    Returns (anchored, inline). Code spans and fenced blocks are stripped
    first, per Claude Code's own parsing. A path appearing both ways is
    reported only as anchored, so callers can union the two without
    double-counting.
    """
    stripped = _CODE_SPAN_RE.sub(" ", _FENCE_RE.sub("", text))
    anchored = _ANCHORED_IMPORT_RE.findall(stripped)
    seen = set(anchored)
    inline = []
    for path in _INLINE_IMPORT_RE.findall(stripped):
        if path not in seen:
            seen.add(path)
            inline.append(path)
    return anchored, inline


def resolve(child: str, parent: str) -> str:
    """Resolve `child` as Claude Code does: relative to the citing file.

    Its docs say "Relative paths resolve relative to the file containing
    the import, not the working directory". For a root-level `CLAUDE.md`
    the two coincide, which is why a working walk over this repo says
    nothing about a consumer whose imports nest.

    `..` segments are normalised textually, so two spellings of one path
    collapse to a single cache key and the file is counted once. Purely
    lexical, deliberately: this resolves paths that may live in a git
    revision rather than on disk, so it must not touch the filesystem or
    follow symlinks the way `Path.resolve()` would.
    """
    if child.startswith(("/", "~")):
        return child
    return posixpath.normpath(posixpath.join(posixpath.dirname(parent), child))


def walk_closure(root: str, read, max_depth: int = MAX_IMPORT_DEPTH):
    """Walk `root`'s import closure using `read(path) -> bytes | None`.

    Returns (files, missing, unresolved_inline). `files` is a list of
    (path, n_bytes, depth) in discovery order; `missing` is a list of
    (path, cited_by) for anchored imports that did not resolve; and
    `unresolved_inline` is the same for inline ones, kept separate because
    an unresolved inline token is usually prose rather than a broken
    reference. `read` is injected so the same walk serves a working tree, a
    git revision, and a test fixture.
    """
    files: list[tuple[str, int, int]] = []
    missing: list[tuple[str, str]] = []
    unresolved_inline: list[tuple[str, str]] = []
    # Two caches, not one. Caching every ATTEMPTED path meant an unresolved
    # inline token could claim a path and suppress a later anchored import
    # of the same path -- so a genuinely dangling anchored import was
    # downgraded to a non-fatal inline warning, purely by traversal order.
    # Only successful reads are cached unconditionally; a failed inline
    # attempt is recorded but must not block a stronger anchored one.
    loaded: set[str] = set()
    failed: dict[str, bool] = {}  # path -> was it attempted as anchored?

    def visit(path: str, depth: int, cited_by: str, anchored: bool) -> None:
        if path in loaded or depth > max_depth:
            return
        if path in failed and (failed[path] or not anchored):
            # Already failed at this strength or stronger; nothing to gain.
            return
        blob = read(path)
        if blob is None:
            if anchored:
                # Upgrade: drop any earlier inline record of the same path,
                # so it is reported once, at its true strength.
                unresolved_inline[:] = [u for u in unresolved_inline if u[0] != path]
                missing.append((path, cited_by))
            else:
                unresolved_inline.append((path, cited_by))
            failed[path] = anchored or failed.get(path, False)
            return
        loaded.add(path)
        files.append((path, len(blob), depth))
        text = blob.decode("utf-8", errors="replace")
        child_anchored, child_inline = import_paths(text)
        for child in child_anchored:
            visit(resolve(child, path), depth + 1, path, True)
        for child in child_inline:
            visit(resolve(child, path), depth + 1, path, False)

    visit(root, 0, "(root)", True)
    return files, missing, unresolved_inline


def local_reader(base: Path):
    """Read blobs from a working tree rooted at `base`.

    A `~`-prefixed import is expanded rather than joined to `base`. Claude
    Code supports these -- its docs give
    `@~/.claude/my-project-instructions.md` as the way to share personal
    instructions across worktrees -- so joining would look under
    `<base>/~/...`, find nothing, and report a genuinely loaded file as a
    dangling import.
    """

    def read(path: str) -> bytes | None:
        candidate = Path(path).expanduser() if path.startswith("~") else base / path
        try:
            return candidate.read_bytes()
        except OSError:
            return None

    return read


def git_reader(base: Path, rev: str):
    """Read blobs from `rev` in the git repo at `base`."""

    def read(path: str) -> bytes | None:
        result = subprocess.run(
            ["git", "-C", str(base), "show", f"{rev}:{path}"],
            capture_output=True,
        )
        return None if result.returncode else result.stdout

    return read


def gitlink_rev(base: Path, submodule: str) -> str | None:
    """The commit the parent repo RECORDS for `submodule`, or None.

    Deliberately not the submodule's checked-out HEAD. During a normal
    pin-bump workflow those differ: you check the submodule out at the
    target revision first, and the parent still records the old pin until
    you `git add` it. Measuring the baseline from the working tree then
    compares the target against itself and reports a zero delta -- the one
    number this tool exists to produce, silently wrong at exactly the
    moment it is consulted.
    """
    result = subprocess.run(
        ["git", "-C", str(base), "ls-tree", "HEAD", submodule],
        capture_output=True,
        text=True,
    )
    if result.returncode or not result.stdout.strip():
        return None
    fields = result.stdout.split()
    # `<mode> commit <sha>\t<path>` for a gitlink; anything else is not one.
    return fields[2] if len(fields) >= 3 and fields[1] == "commit" else None


def submodule_reader(base: Path, submodule: str, rev: str):
    """Read the consumer's own files from disk, `submodule/...` at `rev`.

    A pin bump changes only what the submodule contributes, so the
    consumer's own fragments are read from the working tree either way and
    the delta isolates the pinned content. `rev` is resolved inside the
    submodule's own checkout, since its objects live there.
    """
    prefix = submodule.rstrip("/") + "/"
    from_disk = local_reader(base)
    from_git = git_reader(base / submodule, rev)

    def read(path: str) -> bytes | None:
        if path.startswith(prefix):
            return from_git(path[len(prefix) :])
        return from_disk(path)

    return read


def render(
    files, missing, unresolved_inline, budget, bytes_per_token, label, top_n=10
) -> str:
    """Human-readable report for one closure measurement."""
    total = sum(size for _, size, _ in files)
    lines = [
        f"{label}: {len(files)} file(s), {total:,} bytes "
        f"(~{total // bytes_per_token:,} tokens at {bytes_per_token} B/token)"
    ]
    if files:
        lines.append("")
        lines.append(f"  largest {min(top_n, len(files))}:")
        for path, size, depth in sorted(files, key=lambda f: -f[1])[:top_n]:
            share = 100 * size / total if total else 0
            lines.append(f"   {size:>8,}  {share:>4.1f}%  d{depth}  {path}")
    if missing:
        lines.append("")
        lines.append(f"  {len(missing)} import(s) did not resolve:")
        for path, cited_by in missing:
            lines.append(f"    {path}  (cited by {cited_by})")
    if unresolved_inline:
        # Reported rather than counted or failed on: most are prose
        # (`@claude`, an email address), but a genuine inline import that
        # was mistyped would look the same, so the operator gets to see
        # them instead of the check silently under-reporting.
        lines.append("")
        lines.append(
            f"  {len(unresolved_inline)} inline @token(s) did not resolve "
            f"(probably prose, not imports; not counted):"
        )
        for path, cited_by in unresolved_inline[:top_n]:
            lines.append(f"    @{path}  (in {cited_by})")
        if len(unresolved_inline) > top_n:
            lines.append(f"    ... and {len(unresolved_inline) - top_n} more")
    lines.append("")
    if total > budget:
        over = total - budget
        lines.append(
            f"  OVER BUDGET by {over:,} bytes "
            f"(~{over // bytes_per_token:,} tokens); budget is {budget:,}."
        )
    else:
        lines.append(f"  Under the {budget:,}-byte budget by {budget - total:,}.")
    return "\n".join(lines)


def render_delta(before_total, after_total, bytes_per_token, rev) -> str:
    """Human-readable pin-bump delta."""
    delta = after_total - before_total
    pct = (100 * delta / before_total) if before_total else 0
    sign = "+" if delta >= 0 else ""
    return (
        f"\nPin-bump delta (submodule resolved at {rev}):\n"
        f"    current   {before_total:>10,} B  "
        f"~{before_total // bytes_per_token:>8,} tok\n"
        f"    at {rev:<7} {after_total:>10,} B  "
        f"~{after_total // bytes_per_token:>8,} tok\n"
        f"    change    {sign}{delta:>9,} B  "
        f"{sign}{delta // bytes_per_token:>8,} tok  ({sign}{pct:.0f}%)"
    )


def positive_int(value: str) -> int:
    """An argparse type that rejects zero and negatives.

    `--bytes-per-token 0` would otherwise pass parsing and reach `render`
    as a ZeroDivisionError traceback, and a negative would silently produce
    a nonsense estimate. Per `shared/principles/fail-fast.md`, bad input
    should stop at the boundary with a clear message.
    """
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer")
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {parsed}")
    return parsed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=str(REPO_ROOT),
        help="repo checkout to measure (default: this repo)",
    )
    parser.add_argument(
        "--root",
        default=DEFAULT_ROOT,
        help=f"auto-loaded root file (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--submodule",
        default=".ai-config",
        help="path of the vendored ai-config submodule (default: .ai-config)",
    )
    parser.add_argument(
        "--compare",
        metavar="REV",
        help="also measure with the submodule resolved at REV, and report the "
        "delta (the pin-bump report)",
    )
    parser.add_argument(
        "--budget",
        type=positive_int,
        default=DEFAULT_BUDGET_BYTES,
        help=f"closure bytes above which to flag (default: {DEFAULT_BUDGET_BYTES:,})",
    )
    parser.add_argument(
        "--bytes-per-token",
        type=positive_int,
        default=DEFAULT_BYTES_PER_TOKEN,
        help=f"divisor for the token estimate (default: {DEFAULT_BYTES_PER_TOKEN})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if over budget (default: advisory, exits 0). In --compare "
        "mode this covers the compared total too, so a bump that would cross "
        "the budget fails even while the current pin is under it.",
    )
    args = parser.parse_args(argv)

    base = Path(args.base).resolve()
    files, missing, inline = walk_closure(args.root, local_reader(base))

    if not files:
        # A closure that resolved nothing is not a small closure. Fail loudly
        # rather than printing "0 bytes, under budget", which is what an
        # unreadable root or a wrong --base would otherwise look like.
        print(
            f"error: could not read {args.root} under {base}; nothing measured.",
            file=sys.stderr,
        )
        return 2

    print(
        render(files, missing, inline, args.budget, args.bytes_per_token, str(base))
    )

    total = sum(size for _, size, _ in files)
    after_total = None
    if args.compare:
        # Baseline the CURRENT side on the parent's recorded gitlink, not on
        # the submodule's checked-out tree -- see gitlink_rev's docstring for
        # why the two differ exactly when this tool is being used.
        pin = gitlink_rev(base, args.submodule)
        if pin is None:
            print(
                f"error: {args.submodule} is not a recorded submodule of "
                f"{base}; --compare needs a gitlink to baseline against.",
                file=sys.stderr,
            )
            return 2
        before_files, before_missing, before_inline = walk_closure(
            args.root, submodule_reader(base, args.submodule, pin)
        )
        before_total = sum(size for _, size, _ in before_files)
        after_files, after_missing, after_inline = walk_closure(
            args.root, submodule_reader(base, args.submodule, args.compare)
        )
        after_total = sum(size for _, size, _ in after_files)
        if not after_files or (after_missing and not before_missing):
            print(
                f"error: could not resolve the closure with {args.submodule} "
                f"at {args.compare}; is the submodule populated and fetched?",
                file=sys.stderr,
            )
            return 2
        # An inline import that resolves at the pin but not at the target
        # makes `after_total` shrink for the wrong reason, so the delta would
        # read as a favourable bump rather than an incomplete comparison.
        resolved_before = {p for p, _, _ in before_files}
        lost = sorted(
            p for p, _ in after_inline if p in resolved_before
        ) + sorted(p for p, _ in after_missing if p in resolved_before)
        if lost:
            print(
                "error: these imports resolve at the current pin but not at "
                f"{args.compare}, so the delta would be incomplete:\n"
                + "\n".join(f"    {p}" for p in lost),
                file=sys.stderr,
            )
            return 2
        print(
            render_delta(before_total, after_total, args.bytes_per_token, args.compare)
        )
        if after_total > args.budget >= before_total:
            print(f"\n  This bump would cross the {args.budget:,}-byte budget.")
        total = before_total

    if missing:
        # A dangling anchored import is a defect rather than a size finding,
        # so it fails regardless of --strict. Unresolved INLINE tokens do not
        # fail: they are reported above, being usually prose.
        return 1
    # --strict covers the compared total too. Gating only on the current
    # total would print "this bump would cross the budget" and then exit 0,
    # which contradicts what the flag says it does.
    if args.strict and max(total, after_total or 0) > args.budget:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
