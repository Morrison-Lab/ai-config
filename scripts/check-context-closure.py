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

Three modes; the first two are from ai-config#1028, the third from #1373:

  1. **Budget** -- walk a checkout's closure and compare the total against
     `--budget`. Works for ai-config itself and for any consumer repo whose
     `.ai-config` submodule is populated.

  2. **Pin-bump delta** -- with `--compare REV`, re-measure the same import
     list with `.ai-config/...` paths resolved at REV instead, and report
     the difference. A consumer's import list is fixed; what changes under a
     bump is what those files weigh. Measured on `ucdavis/bcs` at a pin
     three days old, the same 33 imports had grown +62%, and nothing
     reported it -- the gitlink diff is one line.

  3. **Same-repo baseline** -- with `--baseline REV`, re-measure this repo's
     OWN closure at REV and report the delta against the working tree. Mode
     2 cannot answer this: it varies a submodule and needs a gitlink to
     baseline against, and ai-config has no submodule of itself, so nothing
     reported what a given branch added to the closure. That is the gap
     ai-config#1373's first comment names -- "the total is a sum nobody owns
     while each fragment has an author who can be asked" -- and a per-PR
     delta is what gives each increment an owner at the moment it lands.

     Advisory by construction: it reports and never changes the exit code.
     Gating the LEVEL is unsatisfiable while the corpus sits several times
     over budget, and gating the DELTA would need a threshold nobody has
     agreed -- which is the mushy threshold `algorithmatize-checks.md` says
     trains everyone to ignore the instrument. See the `--baseline` block in
     `main` for why baseline-side defects are reported rather than failed on.

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

Threshold rationale (`--fragment-cap`, default below):

  The budget above governs the closure's TOTAL, and the root cap governs one
  file. Neither constrains an individual `@shared/...` fragment, so the
  corpus grows one justified-looking fragment at a time with no per-file
  owner to ask. Measured over 2026-08-10 to 08-12, `CLAUDE.md` was trimmed
  52 KB while the total still rose 42 KB: trimming the one file anybody
  watches did not slow the total, because the growth is distributed.

  The default is a round policy line, not an aspiration and not a ratchet.
  An aspirational cap would turn CI red immediately on several files, which
  per `shared/workflow/algorithmatize-checks.md` trains every reader to
  ignore it and takes the real cases with it. A ratchet a few hundred bytes
  above the current largest fragment fails the other way: at the growth rate
  measured while writing this, it is red within a day on a PR that never
  touched the file. See DEFAULT_FRAGMENT_CAP_BYTES for the figures.

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

**One limit here is not advisory**, and it is not ours. The root file also
has the Claude Code harness's own hard cap, stated in CHARACTERS, past which
it is not auto-loaded whole (`--root-char-cap`, default 150,000). That is a
defect rather than a size finding, so it fails regardless of `--strict`,
like a dangling anchored import -- and it fails silently everywhere else,
since a rule that never loaded and a rule that loaded and was followed look
identical from the outside. The count is reported on every run, passing or
failing, with a warning band below the cap, because on a file that has grown
thousands of characters in a day the remaining headroom is the actionable
number (ai-config#897, #1258).
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

# The root file has a SECOND limit, and it differs from the budget above in
# kind rather than in size. The budget is ours: a soft target over the whole
# closure, advisory by design (ai-config#695). This is the Claude Code
# harness's own hard cap on the auto-loaded `CLAUDE.md`, denominated in
# CHARACTERS rather than bytes, which the harness reports as e.g.
#
#     /Users/<u>/.claude/CLAUDE.md is over the 150.0k-char limit (150.9k chars)
#
# Crossing it is not a prompt to consider splitting. It is a file the harness
# will not load whole, which fails silently: a rule that never loaded and a
# rule that loaded and was followed look identical from the outside. So it
# fails regardless of `--strict`, like a dangling anchored import, rather
# than joining the advisory budget (ai-config#897, #1258).
DEFAULT_ROOT_CHAR_CAP = 150_000

# Measured 2026-08-07: at 153,217 raw characters the harness reported
# "150.9k", so its count runs about 2,300 below a raw `len()` of the decoded
# text. What it excludes is NOT established -- HTML comments (2,750 chars)
# and `@import` lines (2,839) were each checked and neither matches the gap.
# Gating on the raw count is the conservative direction under that
# uncertainty, since raw >= the harness's figure in the one case measured.
# Re-derive rather than trusting this note if the margin ever matters.
#
# The warning band exists because the cap is a cliff: at the corpus's
# observed growth this file can cross it between one session and the next,
# and a check that only speaks once it is too late gives no room to act.
DEFAULT_ROOT_CHAR_WARN_FRACTION = 0.90

# Per-file cap on the NON-root closure files, denominated in bytes like the
# budget. 100,000 is a round policy line rather than a ratchet, and the
# difference was forced by measurement rather than chosen.
#
# The ratchet this started as -- a cap a few hundred bytes above the current
# largest fragment -- is unimplementable here. Measured on 2026-08-12,
# `ardi.md` grew 87,448 -> 93,326 B and `fail-fast.md` 89,175 -> 91,835 B in
# roughly two hours, so a cap pinned to "today's largest" is red by tomorrow
# on a PR that never touched those files. Any threshold within a day's growth
# of the maximum is a coin flip on merge timing rather than a policy.
#
# So the line is round, states a rule a reader can hold ("no auto-loaded
# fragment over 100 KB"), and leaves the two largest 6-8 KB of runway. At the
# growth rate above that is days, not months -- which is the point rather
# than a defect: when it fires, the answer is to split case records out to a
# `.cases.md` companion, which several fragments already have.
#
# Unlike `--budget` this FAILS rather than warning, and deliberately so: a
# ratchet that only warns is the advisory-check-nobody-reads failure
# `shared/writing/semantic-line-breaks.md` records for `check-new-line-breaks`,
# where a green job and a warned job look identical to anyone reading exit
# codes. The budget can stay advisory because crossing it is a prompt to
# decide what comes out; crossing this means one file grew past the largest
# thing anyone had accepted, which is a decision someone should make on
# purpose.
DEFAULT_FRAGMENT_CAP_BYTES = 100_000

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
# The anchored form tolerates trailing horizontal whitespace and a CR.
# Without that, a CRLF checkout downgrades EVERY anchored import: `$` will
# not match before the `\r` and `[^\s`]+` cannot consume it, so the
# anchored matcher finds nothing while the inline matcher still finds the
# token -- turning a hard dangling-import failure into a non-fatal warning
# on Windows checkouts, silently and repo-wide.
_ANCHORED_IMPORT_RE = re.compile(r"^@([^\s`]+)[ \t]*\r?$", re.MULTILINE)
_INLINE_IMPORT_RE = re.compile(r"(?<![\w`])@([^\s`]+?)(?=[.,;:!?)\]]*(?:\s|$))")

# Both delimiters must match a RUN of markers, not a fixed one. A fenced
# block may open with three or more backticks or tildes, and a code span
# with any number of backticks -- so ``@a.md`` survived a single-backtick
# pattern (it stripped the two empty pairs and left the token), and a `~~~`
# block was not recognised at all. Either way a documented example became
# a counted import.
#
# Both follow CommonMark's own bounds:
#
#   * A fence may be indented up to three spaces, and its closer may be
#     indented independently. An unindented pattern leaves the block's
#     contents in the text, so an `@path` inside a documented example is
#     counted as a real import.
#   * An UNCLOSED fence is REPORTED but not swallowed to EOF, which is a
#     deliberate departure from CommonMark and the only one here. The spec
#     says an unclosed fence runs to the end of the document, and
#     implementing that verbatim is catastrophic on real content: this
#     repo's own CLAUDE.md contains same-length nested fences (an outer
#     ``` wrapping an inner ```{r}), so the outer closer reads as a fresh
#     unclosed opener and everything after it becomes code. Measured, that
#     dropped 19 genuine imports, taking the closure from 70 files to 51.
#     Under-reporting the closure by a quarter to be spec-correct about a
#     malformed fence is the wrong trade for a measuring instrument, so
#     unbalanced fences surface as a warning and the operator decides.
#   * A code span may contain line endings but NOT a blank line. That bound
#     is load-bearing rather than pedantic: an unbounded `[\s\S]*?` pairs a
#     stray backtick with another far later in the file and strips
#     everything between. Measured on this repo's own CLAUDE.md, that cut
#     the anchored-import count from 69 to 50 and the closure from 70 files
#     to 51. Stopping at a blank line keeps multi-line spans working while
#     confining any mismatch to a single paragraph.
_UNCLOSED_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[^\n]*$", re.MULTILINE)
# Backtick and tilde fences are separate alternatives so a closer must use
# the SAME character as its opener, and each opening run carries `(?!x)` so
# it cannot BACKTRACK to a shorter capture. Without that, `+`/`{3,}` shrinks
# on demand and a four-backtick fence is "closed" by three, or a
# double-backtick span pairs with a single-backtick closer -- stripping
# content that is not code and hiding the imports inside it.
_FENCE_RE = re.compile(
    r"^ {0,3}(?:(`{3,})(?!`)[^\n]*$[\s\S]*?^ {0,3}\1`*[ \t]*\r?$"
    r"|(~{3,})(?!~)[^\n]*$[\s\S]*?^ {0,3}\2~*[ \t]*\r?$)",
    re.MULTILINE,
)
# A code span's delimiters must also be maximal runs, and its opener must
# not be preceded by a backtick -- otherwise ``@a.md` pairs its SECOND
# backtick with the closer and strips an import that is not in a span.
#
# Every line-ending construct here accepts CRLF, and the omission bit twice.
# A fence closer whose `[ \t]*$` cannot consume the `\r` leaves a BALANCED
# block looking like two orphan markers, so `strip_code` drops the marker
# lines and keeps the body -- counting the `@path` examples inside a
# documented code block as real imports. And a blank-line bound written
# `\n(?![ \t]*\n)` never fires on CRLF, which reopens the swallow bug this
# module already fixed once for LF.
_CODE_SPAN_RE = re.compile(
    r"(?<!`)(`+)(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
)


def strip_code(text: str) -> str:
    """Remove fenced blocks, orphan fence markers, and code spans.

    Orphan markers are dropped between the two passes. A leftover opener
    from an unclosed fence is a block-level marker, not a span delimiter,
    so leaving it in lets the code-span pass pair it with a later marker
    and swallow real content. Only the marker line goes -- its body stays,
    per the deliberate no-swallow decision above.
    """
    return _CODE_SPAN_RE.sub(
        " ", _UNCLOSED_FENCE_RE.sub("", _FENCE_RE.sub("", text))
    )

# Claude Code stops following imports after this many hops: its docs say
# "Imported files can recursively import other files, with a maximum depth
# of four hops". A deeper file is not loaded, so counting it would inflate
# both the closure total and the pin-bump delta.
MAX_IMPORT_DEPTH = 4


def unbalanced_fences(text: str) -> int:
    """How many fence markers are left over after pairing closed blocks.

    An unclosed fence makes this parser's answer ambiguous: CommonMark says
    the rest of the document is code, while this module deliberately does
    not swallow it (see `_UNCLOSED_FENCE_RE`'s comment). Rather than pick
    silently, count the leftovers so the report can say so.
    """
    return len(_UNCLOSED_FENCE_RE.findall(_FENCE_RE.sub("", text)))


def import_paths(text: str) -> tuple[list[str], list[str]]:
    """The `@path` imports a CLAUDE.md-style file declares.

    Returns (anchored, inline). Code spans and fenced blocks are stripped
    first, per Claude Code's own parsing. A path appearing both ways is
    reported only as anchored, so callers can union the two without
    double-counting.
    """
    stripped = strip_code(text)
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
    ambiguous: list[tuple[str, int]] = []
    # Two caches, not one. Caching every ATTEMPTED path meant an unresolved
    # inline token could claim a path and suppress a later anchored import
    # of the same path -- so a genuinely dangling anchored import was
    # downgraded to a non-fatal inline warning, purely by traversal order.
    # Only successful reads are cached unconditionally; a failed inline
    # attempt is recorded but must not block a stronger anchored one.
    #
    # `loaded` maps a path to the SHALLOWEST depth it has been processed
    # at, not merely to the fact that it was seen. A plain set makes the
    # result depend on traversal order: reach a file first down a depth-4
    # chain and its own imports are skipped for exceeding the limit, then
    # reach it again directly at depth 1 and the set suppresses the revisit,
    # so those imports are never counted although they are well inside the
    # four-hop limit. Re-walking on a strictly shallower route fixes that;
    # bytes are still counted once, on first load.
    loaded: dict[str, int] = {}
    failed: dict[str, bool] = {}  # path -> was it attempted as anchored?

    def visit(path: str, depth: int, cited_by: str, anchored: bool) -> None:
        if depth > max_depth:
            return
        if path in loaded and loaded[path] <= depth:
            return
        if path not in loaded and path in failed and (failed[path] or not anchored):
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
        if path not in loaded:
            files.append((path, len(blob), depth))
        elif depth < loaded[path]:
            # Correct the RECORDED depth too, not just the cache. Otherwise
            # the report shows the deeper route a file happened to be found
            # by first, which is not its effective depth.
            for i, (p_, n_, d_) in enumerate(files):
                if p_ == path:
                    files[i] = (p_, n_, depth)
                    break
        loaded[path] = depth
        text = blob.decode("utf-8", errors="replace")
        stray = unbalanced_fences(text)
        if stray and all(a[0] != path for a in ambiguous):
            ambiguous.append((path, stray))
        child_anchored, child_inline = import_paths(text)
        for child in child_anchored:
            visit(resolve(child, path), depth + 1, path, True)
        for child in child_inline:
            visit(resolve(child, path), depth + 1, path, False)

    visit(root, 0, "(root)", True)
    return files, missing, unresolved_inline, ambiguous


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
    files, missing, unresolved_inline, ambiguous, budget, bytes_per_token, label,
    top_n=10,
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
    if ambiguous:
        # An unclosed fence makes this file's parse ambiguous: CommonMark
        # would treat the remainder as code, this parser does not. Say so
        # rather than resolving it silently in either direction.
        lines.append("")
        lines.append(
            f"  {len(ambiguous)} file(s) have unbalanced code fences, so their "
            f"import parse is ambiguous:"
        )
        for path, n in ambiguous[:top_n]:
            lines.append(f"    {path}  ({n} unclosed fence marker(s))")
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


def render_fragment_caps(files, cap):
    """Report non-root closure files over the per-file cap.

    Returns `(over, text)`, where `over` is True if any fragment breaches.

    The root file is excluded -- it is the only depth-0 entry, since
    `walk_closure` starts there -- because `--root-char-cap` already governs
    it, under a different limit in a different unit; double-gating one file
    invites a report where the two disagree about the same path.
    """
    fragments = [(path, size) for path, size, depth in files if depth > 0]
    breaches = sorted(
        ((size, path) for path, size in fragments if size > cap), reverse=True
    )
    # Report what was examined, not only what was found: a walk that
    # resolved no fragments and a corpus with none over the cap both print
    # zero breaches otherwise, per shared/principles/fail-fast.md.
    lines = [
        "",
        f"  {len(fragments)} fragment(s) examined against the "
        f"{cap:,}-byte per-file cap; {len(breaches)} over.",
    ]
    for size, path in breaches:
        lines.append(f"    {size:>8,}  (+{size - cap:,})  {path}")
    if breaches:
        lines.append(
            "  Split the case records out to a `.cases.md` companion, or "
            "raise --fragment-cap"
        )
        lines.append("  deliberately and say why.")
        # Naming the sweep here rather than only in prose: this message is
        # the observable moment the split is decided, and a positional
        # reference the split strands is invisible to every other check --
        # its referent is context that did not move, so no diff-scoped
        # check sees it, and it is prose rather than a link, so
        # check-links.py cannot either. See
        # shared/writing/reorganize-prose.md.
        lines.append(
            "  Then sweep both sides for positional references the split "
            "strands:"
        )
        # Reproduce forward-references.md's canonical pattern verbatim,
        # `this (section|file)` included. That section's own warning is that
        # a sweep narrowed to the wording the mover happens to recall is
        # "far narrower than the ordinary phrasing the real danglers wear",
        # so dropping an alternative here would commit the exact error the
        # cited rule exists to prevent.
        lines.append(
            "    rg -niE "
            "'\\b(above|below|here|earlier|later)\\b|this (section|file)' "
            "<companion> <fragment>"
        )
        lines.append(
            "  Fix each by naming its subject, not by repointing at the "
            "other file."
        )
    return bool(breaches), "\n".join(lines)


def render_delta(
    before_total,
    after_total,
    bytes_per_token,
    heading,
    before_label,
    after_label,
) -> str:
    """Human-readable before/after closure delta.

    Two modes share this renderer and they have different subjects: the
    pin-bump comparison measures one import list against two submodule
    revisions, while `--baseline` measures this repo's own closure at a rev
    against its working tree. So the heading and both row labels come from
    the caller rather than being hard-coded.

    Keeping one renderer keeps the arithmetic and the column formatting in a
    single place. Keeping the *wording* out of it is the other half: a
    hard-coded "Pin-bump delta (submodule resolved at ...)" would make the
    baseline mode assert a purpose it does not have, which is the structural
    reuse `shared/workflow/check-purpose-before-reusing.md` warns about --
    same shape, wrong claim.
    """
    delta = after_total - before_total
    pct = (100 * delta / before_total) if before_total else 0
    width = max(len(before_label), len(after_label), len("change"))
    # The sign goes in the format spec rather than a separate string. Prefixing
    # a manual "+" spends a column that the "-" of a negative number takes from
    # the field itself, so the two cases came out a character apart -- and the
    # negative case is a trim, which is exactly the run someone reads closely.
    # `//` also floors toward negative infinity, so a shrink reported one token
    # more than it saved; truncating toward zero keeps both directions honest.
    delta_tok = int(delta / bytes_per_token)
    return (
        f"\n{heading}\n"
        f"    {before_label:<{width}} {before_total:>10,} B  "
        f"~{before_total // bytes_per_token:>8,} tok\n"
        f"    {after_label:<{width}} {after_total:>10,} B  "
        f"~{after_total // bytes_per_token:>8,} tok\n"
        f"    {'change':<{width}} {delta:>+10,} B  "
        f"{delta_tok:>+9,} tok  ({pct:+.0f}%)"
    )


def root_char_count(base: Path, root: str) -> int | None:
    """Characters in the root file, or None if it cannot be read.

    Characters rather than bytes, because the harness's cap is stated in
    characters and this corpus's prose is not pure ASCII -- the two diverge
    by every multi-byte glyph in the file.
    """
    try:
        return len((base / root).read_text(encoding="utf-8"))
    except OSError:
        return None


def render_root_chars(chars: int | None, root: str, cap: int, warn_fraction: float):
    """(over, text) for the root file's hard character cap.

    Always reports the count, passing or failing. A check that prints only
    on failure leaves a reader unable to tell a comfortable margin from one
    that is about to close -- and on this cap the margin is the actionable
    part, per `shared/principles/fail-fast.md` on reporting what was
    examined rather than only what was found.
    """
    if chars is None:
        return False, f"\n  {root}: unreadable, so the character cap was NOT checked."
    pct = 100 * chars / cap
    if chars > cap:
        return True, (
            f"\n  OVER THE HARD CHARACTER CAP: {root} is {chars:,} characters "
            f"against the harness's {cap:,} ({pct:.1f}%),\n"
            f"  so it is over by {chars - cap:,}. The harness will not load it "
            f"whole, and nothing else reports that.\n"
            f"  Move content into an @-imported fragment or a linked companion "
            f"file (see ai-config#1259 for the pattern)."
        )
    text = (
        f"\n  {root}: {chars:,} characters against the harness's {cap:,}-char "
        f"cap ({pct:.1f}%), {cap - chars:,} to spare."
    )
    if chars >= cap * warn_fraction:
        text += (
            f"\n  WARNING: within {100 * (1 - warn_fraction):.0f}% of the cap. "
            f"This file has grown by thousands of characters in a day before, "
            f"so treat this as the moment to trim rather than the moment to "
            f"note it."
        )
    return False, text


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
        "--root-char-cap",
        type=positive_int,
        default=DEFAULT_ROOT_CHAR_CAP,
        help=(
            "hard character cap on the root file, failing regardless of "
            f"--strict (default: {DEFAULT_ROOT_CHAR_CAP:,})"
        ),
    )
    parser.add_argument(
        "--root-char-warn-fraction",
        type=float,
        default=DEFAULT_ROOT_CHAR_WARN_FRACTION,
        help=(
            "warn once the root file reaches this fraction of the cap "
            f"(default: {DEFAULT_ROOT_CHAR_WARN_FRACTION})"
        ),
    )
    parser.add_argument(
        "--fragment-cap",
        type=positive_int,
        default=DEFAULT_FRAGMENT_CAP_BYTES,
        help=(
            "per-file byte cap on non-root closure files, failing regardless "
            f"of --strict (default: {DEFAULT_FRAGMENT_CAP_BYTES:,})"
        ),
    )
    parser.add_argument(
        "--baseline",
        metavar="REV",
        help="measure THIS repo's own closure at REV and report the delta "
        "against the working tree. Distinct from --compare, which resolves "
        "a submodule at REV; this answers 'what did this branch add to the "
        "closure', which --compare cannot (it needs a gitlink). Advisory: "
        "reports, never fails. See ai-config#1373.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if over budget (default: advisory, exits 0). In --compare "
        "mode this covers the compared total too, so a bump that would cross "
        "the budget fails even while the current pin is under it.",
    )
    args = parser.parse_args(argv)

    if args.baseline and args.compare:
        # Not merely redundant: the two measure different closures. `--compare`
        # holds this tree fixed and varies a submodule's revision; `--baseline`
        # varies this tree against its own history. Running both would print
        # two deltas whose "current" sides are not the same number, which reads
        # as one comparison and is two.
        print(
            "error: --baseline and --compare measure different things and "
            "cannot be combined; pass one.",
            file=sys.stderr,
        )
        # Literal 2 to match this file's other usage-error returns, which are
        # all bare. 2 is deliberately distinct from 1, so "you invoked this
        # incorrectly" is never read as a size finding.
        return 2

    base = Path(args.base).resolve()
    files, missing, inline, ambiguous = walk_closure(args.root, local_reader(base))

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
        render(
            files, missing, inline, ambiguous, args.budget,
            args.bytes_per_token, str(base),
        )
    )

    root_over, root_text = render_root_chars(
        root_char_count(base, args.root),
        args.root,
        args.root_char_cap,
        args.root_char_warn_fraction,
    )
    print(root_text)

    frag_over, frag_text = render_fragment_caps(files, args.fragment_cap)
    print(frag_text)

    total = sum(size for _, size, _ in files)
    after_total = None

    if args.baseline:
        # `--compare` cannot answer this. It re-resolves the same import list
        # against two SUBMODULE revisions and needs a gitlink to baseline
        # against, so in ai-config's own repo -- which has no `.ai-config`
        # gitlink of itself -- there is nothing for it to compare. The
        # question left unanswered was "what did this branch add", which is
        # the one that has an owner: the total is a sum nobody owns, while a
        # per-PR delta lands on the PR that caused it (ai-config#1373).
        before_files, before_missing, before_inline, before_amb = walk_closure(
            args.root, git_reader(base, args.baseline)
        )
        if not before_files:
            print(
                f"error: could not read {args.root} at {args.baseline} in "
                f"{base}; nothing to baseline against.",
                file=sys.stderr,
            )
            return 2
        before_total = sum(size for _, size, _ in before_files)

        # Baseline-side defects are REPORTED, not failed on, which is the
        # opposite stance from `--compare`. Two reasons, and the second is
        # the load-bearing one.
        #
        # The baseline is history: a dangling import at an old rev is not
        # something the current branch can fix, so failing on it would make
        # the tool unusable against exactly the revs you want to measure
        # from.
        #
        # And the error direction is the safe one. An import that does not
        # resolve at the baseline is not counted there, so `before_total` is
        # low and the delta OVER-reports growth. For a growth watchdog,
        # over-reporting is the direction that fails loudly rather than
        # silently (shared/principles/fail-fast.md's safe/dangerous
        # asymmetry). `--compare` errs the other way for the same reason
        # read in mirror: there the miss is on the TARGET side, which makes
        # a bump look favourable.
        for path, cited_by in before_missing:
            print(
                f"  note [baseline {args.baseline}]: anchored @{path} did not "
                f"resolve (cited by {cited_by}); the delta over-reports growth "
                f"by whatever it weighed"
            )
        for path, cited_by in before_inline:
            print(
                f"  note [baseline {args.baseline}]: inline @{path} did not "
                f"resolve (in {cited_by}; not counted)"
            )
        for path, n in before_amb:
            print(
                f"  note [baseline {args.baseline}]: {path} has {n} unclosed "
                f"fence marker(s), so its import parse is ambiguous"
            )

        print(
            render_delta(
                before_total,
                total,
                args.bytes_per_token,
                f"Closure delta (this tree against {args.baseline}):",
                f"at {args.baseline}",
                "this tree",
            )
        )

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
        before_files, before_missing, before_inline, before_amb = walk_closure(
            args.root, submodule_reader(base, args.submodule, pin)
        )
        before_total = sum(size for _, size, _ in before_files)
        after_files, after_missing, after_inline, after_amb = walk_closure(
            args.root, submodule_reader(base, args.submodule, args.compare)
        )
        after_total = sum(size for _, size, _ in after_files)
        if not after_files:
            print(
                f"error: could not resolve the closure with {args.submodule} "
                f"at {args.compare}; is the submodule populated and fetched?",
                file=sys.stderr,
            )
            return 2
        # Validate the two closures INDEPENDENTLY. The previous condition,
        # `after_missing and not before_missing`, silently accepted three
        # wrong states: a baseline whose own dangling import the target
        # happens to fix, a new target-side miss whenever the baseline also
        # had one, and any baseline defect at all -- since in compare mode
        # the working-tree `missing` list is measured at whatever the
        # submodule is checked out to, which during a pin bump is the
        # target. So neither side was actually being checked.
        for label, misses in (
            (f"the recorded pin ({pin[:8]})", before_missing),
            (f"the target ({args.compare})", after_missing),
        ):
            if misses:
                print(
                    f"error: {len(misses)} dangling anchored import(s) at "
                    f"{label}:\n"
                    + "\n".join(f"    {p}  (cited by {c})" for p, c in misses),
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
        # Local mode reports unresolved inline tokens and ambiguous parses;
        # compare mode measures two DIFFERENT closures, neither of which is
        # the one local mode just reported, so its diagnostics have to be
        # emitted too or the delta is the only thing a reader sees.
        for label, inl, amb in (
            (f"recorded pin ({pin[:8]})", before_inline, before_amb),
            (f"target ({args.compare})", after_inline, after_amb),
        ):
            for path, cited_by in inl:
                print(f"  note [{label}]: inline @{path} did not resolve "
                      f"(in {cited_by}; not counted)")
            for path, n in amb:
                print(f"  note [{label}]: {path} has {n} unclosed fence "
                      f"marker(s), so its import parse is ambiguous")
        print(
            render_delta(
                before_total,
                after_total,
                args.bytes_per_token,
                f"Pin-bump delta (submodule resolved at {args.compare}):",
                "current",
                f"at {args.compare}",
            )
        )
        if after_total > args.budget >= before_total:
            print(f"\n  This bump would cross the {args.budget:,}-byte budget.")
        total = before_total

    if missing:
        # A dangling anchored import is a defect rather than a size finding,
        # so it fails regardless of --strict. Unresolved INLINE tokens do not
        # fail: they are reported above, being usually prose.
        return 1
    if root_over:
        # Same reasoning as `missing` above, and deliberately NOT gated on
        # --strict: the byte budget is ours to miss, while this cap belongs
        # to the harness and crossing it means the file is not fully loaded.
        # See the DEFAULT_ROOT_CHAR_CAP comment for why that failure is
        # silent everywhere else.
        return 1
    if frag_over:
        # Same stance as root_over above, and NOT gated on --strict. See
        # DEFAULT_FRAGMENT_CAP_BYTES for why this one fails rather than warns.
        return 1
    # --strict covers the compared total too. Gating only on the current
    # total would print "this bump would cross the budget" and then exit 0,
    # which contradicts what the flag says it does.
    if args.strict and max(total, after_total or 0) > args.budget:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
