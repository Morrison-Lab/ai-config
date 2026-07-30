#!/usr/bin/env python3
"""Rank pairs of corpus files by near-duplicate content, for find-overlap step 3.

`skills/find-overlap/SKILL.md` step 3 says to "group units that share
keywords, titles, or the same outcome" and then read the bodies of each
candidate cluster. That grouping step is model judgment over a list of ~175
skills, so whichever pairs nobody thinks to compare are never compared, and
nothing reports the omission. Pairwise token overlap has a numeric definition
over data already on disk, so per `shared/workflow/algorithmatize-checks.md` it
belongs in an instrument.

What this does NOT do, deliberately. It ranks candidates; it does not classify
them. `algorithmatize-checks`' own "Limits" section reserves the semantic
residue for a reviewer, and here that residue is the whole of find-overlap
step 4: sorting each pair into intentional-alias / adjacent-but-distinct /
genuine-duplicate, and applying the litmus ("can you name a capability that
would be lost by removing one member?"). Two consequences:

  - A high score is not a verdict. The output is a reading list in priority
    order.
  - Alias stubs are detected STRUCTURALLY (`--include-aliases`, flagged
    `alias?`), not by score, and this corrects an assumption worth recording
    because it was stated in ai-config#895 before being measured. The
    expectation was that a stub would score high against its canonical skill,
    so scoring would surface alias families for find-overlap's bucket 1. It
    does not: a stub's body is a six-line pointer, so `find-duplicates` vs
    `find-overlap` scores 0.002. What scores high is stub against *other
    stub* -- shared boilerplate, carrying no information at all. So the
    similarity metric cannot serve bucket 1, and the structural `_ALIAS_RE`
    check is what does.

Scope, stated plainly because it is narrower than ai-config#895 assumed. This
ranks reused *phrasing*, which is find-overlap's genuine-duplicate bucket. It
does not detect conceptual adjacency: `tidy` and `simplify` are the corpus's
canonical adjacent-but-distinct pair and score 0.019, because they are
adjacent in idea while sharing almost no wording. So this supplements step 3's
keyword pass and must not replace it -- dropping that pass would trade a
judgment step that can see meaning for an instrument that can only see words.

Metric: Jaccard similarity over word n-gram shingles (`--shingle`, default 3).

  Shingles rather than bare tokens, because our corpus shares heavy technical
  vocabulary -- "review", "PR", "finding", "skill" appear everywhere, so
  single-token Jaccard scores unrelated skills as similar. A 3-word window
  keeps a score high only when phrasing is actually reused.

  Jaccard rather than `difflib.SequenceMatcher`, which was the obvious
  don't-reinvent-the-wheel candidate (`shared/principles/dont-reinvent-wheel.md`)
  and was measured before being rejected:

    - It is quadratic in document size, not just in pair count. One pair of
      `memories/` files (79KB, 65KB) took 0.60s, so the memories corpus alone
      would run into minutes, and the cost grows as files do.
    - Its character-level ratio is the wrong quantity. That same pair -- two
      files of dense technical prose on adjacent topics -- scored 0.008,
      because the matching-block algorithm finds only short runs in long
      texts. It under-reports exactly the topical overlap we are looking for.

  Set arithmetic over shingles is linear per file, then a cheap intersection
  per pair, and it scores reused phrasing rather than matching character runs.

Thresholds and corpus are arguments, not literals, per
`shared/coding/configurable-parameters.md`.

Advisory: exits 0 unless `--strict`. This is a detector feeding a read-only
skill, not a gate -- the same stance `check-memory-file-size.py` takes.
"""
from __future__ import annotations

import argparse
import itertools
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Calibrated against this corpus rather than picked round, because
# `algorithmatize-checks` warns that an instrument with a mushy threshold
# trains everyone to ignore it. Measured over the 15,225 non-alias skill
# pairs (`--calibrate`): p50 0.0020, p99 0.0260, p99.9 0.0949, max 0.4726.
# 0.05 sits near p99.5 and yields ~21 candidate pairs -- a corpus audit's
# worth of reading. Re-run `--calibrate` after the corpus grows; these
# figures are a 2026-07-30 snapshot, not a constant of nature.
DEFAULT_THRESHOLD = 0.05
DEFAULT_SHINGLE = 3
DEFAULT_CORPUS = "skills/*/SKILL.md"

# A stub whose whole body is a pointer at its canonical skill. Matches the
# convention in `skills/*/SKILL.md`: "Alias for `x`" in the description, or a
# body arrow to another SKILL.md.
_ALIAS_RE = re.compile(r"alias for\s+[`\[]|→\s*\*\*\[|\.\./[a-z0-9-]+/SKILL\.md", re.I)
_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tracked_files(pattern: str) -> list[Path]:
    """Resolve a pathspec through git, so untracked scratch files are excluded.

    `:(glob)` magic is explicit because git's default pathspec lets `*` match
    `/` -- the same trap `check-memory-file-size.py` documents.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--", f":(glob){pattern}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO_ROOT / line for line in out.splitlines() if line]


def body_of(path: Path) -> tuple[str, bool]:
    """Return (prose body, is_alias_stub). Frontmatter is stripped from the body.

    The frontmatter's `description` is deliberately dropped: it restates the
    body's triggers, so including it double-counts the very phrases most
    likely to be shared, inflating every score toward the mean.
    """
    text = path.read_text(encoding="utf-8")
    head = text[:600]
    body = _FRONTMATTER_RE.sub("", text)
    return body, bool(_ALIAS_RE.search(head) or _ALIAS_RE.search(body[:400]))


def shingles(body: str, n: int) -> set[tuple[str, ...]]:
    tokens = _TOKEN_RE.findall(body.lower())
    if len(tokens) < n:
        # Too short to shingle at this width; fall back to the token set so a
        # very short stub still compares rather than silently scoring 0
        # against everything.
        return {(t,) for t in tokens}
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def evidence(a: set, b: set, limit: int = 3) -> str:
    """A few of the longest shared shingles, as the reason for the score."""
    shared = sorted(a & b, key=lambda s: (-len(" ".join(s)), s))[:limit]
    return "; ".join(" ".join(s) for s in shared)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--corpus",
        default=DEFAULT_CORPUS,
        help=f"git pathspec for the comparable units (default: {DEFAULT_CORPUS})",
    )
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--shingle", type=int, default=DEFAULT_SHINGLE)
    p.add_argument("--top", type=int, default=25, help="max pairs to report")
    p.add_argument(
        "--include-aliases",
        action="store_true",
        help="report alias-stub pairs too (flagged `alias?`); off by default "
        "because they are the target state, not a finding",
    )
    p.add_argument("--calibrate", action="store_true", help="print the score distribution")
    p.add_argument("--strict", action="store_true", help="exit 1 if any pair is reported")
    args = p.parse_args()

    paths = tracked_files(args.corpus)
    if not paths:
        # Fail loudly rather than reporting a clean corpus we never read --
        # `shared/principles/fail-fast.md`: an instrument whose failure path
        # and pass path look alike is not yet an instrument.
        print(f"error: no tracked files matched {args.corpus!r}", file=sys.stderr)
        return 2

    units = {}
    for path in paths:
        body, is_alias = body_of(path)
        units[path] = (shingles(body, args.shingle), is_alias)

    scored = []
    for a, b in itertools.combinations(sorted(units), 2):
        sa, alias_a = units[a]
        sb, alias_b = units[b]
        score = jaccard(sa, sb)
        scored.append((score, a, b, alias_a or alias_b))
    scored.sort(key=lambda row: -row[0])

    # Count what was examined, not only what was found: a zero-hit result has
    # to be distinguishable from a run that compared nothing.
    print(
        f"compared {len(scored)} pairs across {len(paths)} units "
        f"({args.shingle}-word shingles, threshold {args.threshold})"
    )

    # Alias-stub pairs are counted separately, never folded into the headline
    # numbers. 76 of 175 skills are stubs whose whole body is boilerplate
    # ("Alias for `x`. Read and follow the canonical skill"), so stub-to-stub
    # pairs are near-identical to each other and dominate any distribution
    # they are included in: at threshold 0.10 they are 1,070 of the 1,074
    # pairs above it. A calibration figure that mixes them in reads as
    # "thousands of duplicates" and is pure boilerplate self-similarity.
    suppressed = sum(1 for score, _, _, is_alias in scored if score >= args.threshold and is_alias)

    if args.calibrate:
        # Distribution over the REPORTABLE set, for the reason above -- the
        # whole-set distribution measures the boilerplate, not the corpus.
        vals = [score for score, _, _, is_alias in scored if args.include_aliases or not is_alias]
        for q in (0.5, 0.9, 0.99, 0.999):
            idx = min(len(vals) - 1, int((1 - q) * len(vals)))
            print(f"  p{q * 100:<5g} {vals[idx]:.4f}")
        print(f"  max   {vals[0]:.4f}")

    reported = 0
    print()
    print(f"{'score':>7}  {'':5}  pair")
    for score, a, b, is_alias in scored:
        if score < args.threshold or reported >= args.top:
            break
        if is_alias and not args.include_aliases:
            continue
        reported += 1
        flag = "alias?" if is_alias else ""
        ra, rb = a.relative_to(REPO_ROOT), b.relative_to(REPO_ROOT)
        print(f"{score:>7.3f}  {flag:5}  {ra}  <->  {rb}")
        print(f"{'':16}shared: {evidence(units[a][0], units[b][0])}")

    if not reported:
        print("  (no pairs above threshold)")
    print()
    if suppressed and not args.include_aliases:
        print(f"suppressed {suppressed} alias-stub pair(s); --include-aliases to see them")
    print(
        f"{reported} candidate pair(s) to read. These are CANDIDATES, not verdicts: "
        "classify each per find-overlap step 4 by reading the bodies."
    )
    print(
        "Scope: this ranks REUSED PHRASING, so it finds find-overlap's "
        "genuine-duplicate bucket. It does NOT find conceptually adjacent "
        "skills that share no wording (measured: tidy/simplify score 0.019), "
        "so it supplements step 3's keyword pass rather than replacing it."
    )

    return 1 if (args.strict and reported) else 0


if __name__ == "__main__":
    sys.exit(main())
