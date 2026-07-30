#!/usr/bin/env python3
"""Tests for `find-near-duplicates.py`.

Run: `python3 scripts/test_find_near_duplicates.py`

Every assertion here was checked to FAIL against a deliberately broken
version before being committed, per `shared/workflow/ardi.md`: "a regression
test never seen to fail is a guess about what it covers." The two that matter
most are `test_alias_stubs_do_not_score_high` and
`test_conceptual_adjacency_is_not_detected`, because both encode a limitation
that ai-config#895 assumed away -- if a later change makes either pass for the
wrong reason, the docstring's stated scope has silently become false.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "find_near_duplicates", REPO_ROOT / "scripts" / "find-near-duplicates.py"
)
fnd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fnd)

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILURES.append(name)


def skill(slug: str) -> set:
    body, _ = fnd.body_of(REPO_ROOT / "skills" / slug / "SKILL.md")
    return fnd.shingles(body, fnd.DEFAULT_SHINGLE)


def is_alias(slug: str) -> bool:
    return fnd.body_of(REPO_ROOT / "skills" / slug / "SKILL.md")[1]


# --- the metric itself ------------------------------------------------------

def test_jaccard_bounds() -> None:
    a = {("x", "y", "z"), ("y", "z", "w")}
    check("identical sets score 1.0", fnd.jaccard(a, a) == 1.0)
    check("disjoint sets score 0.0", fnd.jaccard(a, {("p", "q", "r")}) == 0.0)
    check("empty set scores 0.0, no ZeroDivisionError", fnd.jaccard(set(), a) == 0.0)


def test_shingles_are_windows_not_tokens() -> None:
    s = fnd.shingles("the quick brown fox", 3)
    check(
        "3-shingling a 4-token body yields 2 windows",
        s == {("the", "quick", "brown"), ("quick", "brown", "fox")},
        f"got {s}",
    )
    # Shared vocabulary in a different order must NOT score as overlap; this is
    # the whole reason for shingles over bare tokens.
    check(
        "reordered words share no shingle",
        fnd.jaccard(fnd.shingles("alpha beta gamma", 3), fnd.shingles("gamma beta alpha", 3)) == 0.0,
    )


def test_short_body_falls_back_to_tokens() -> None:
    s = fnd.shingles("two words", 3)
    check("a body shorter than the window still yields tokens", s == {("two",), ("words",)}, f"got {s}")


def test_frontmatter_is_stripped() -> None:
    body, _ = fnd.body_of(REPO_ROOT / "skills" / "find-overlap" / "SKILL.md")
    check("frontmatter delimiter is gone from the body", not body.lstrip().startswith("---"))
    check(
        "a description-only phrase does not reach the body",
        "user-invocable" not in body,
        "frontmatter leaked, which double-counts trigger phrases",
    )


# --- the corpus facts the docstring's stated scope rests on -----------------

def test_alias_stubs_are_detected_structurally() -> None:
    check("a known alias stub is flagged", is_alias("find-duplicates"))
    check("its canonical skill is not flagged", not is_alias("find-overlap"))


def test_alias_stubs_do_not_score_high() -> None:
    """ai-config#895 predicted the opposite; measured, it is 0.002.

    This is why bucket-1 detection is structural rather than score-based. If
    this ever starts scoring high, the docstring's explanation is wrong.
    """
    score = fnd.jaccard(skill("find-duplicates"), skill("find-overlap"))
    check(
        "alias stub vs canonical scores below the default threshold",
        score < fnd.DEFAULT_THRESHOLD,
        f"score={score:.4f} -- if this is now high, update the docstring's alias rationale",
    )


def test_conceptual_adjacency_is_not_detected() -> None:
    """The documented limitation: shared idea, unshared wording.

    `tidy`/`simplify` is the pair `find-overlap` itself names as the canonical
    adjacent-but-distinct example. It scores near zero, which is the evidence
    for "supplements step 3's keyword pass rather than replacing it."
    """
    score = fnd.jaccard(skill("tidy"), skill("simplify"))
    check(
        "conceptually adjacent pair scores below threshold",
        score < fnd.DEFAULT_THRESHOLD,
        f"score={score:.4f}",
    )


def test_a_real_high_scoring_pair_exists() -> None:
    """Negative control for the above: the metric must find something.

    Without this, both limitation tests would also pass on a metric that
    returns 0.0 for everything.
    """
    score = fnd.jaccard(skill("prompt-me"), skill("prompt-me-all"))
    check(
        "the known single-vs-all pair scores well above threshold",
        score > 0.3,
        f"score={score:.4f} -- metric may be returning near-zero for everything",
    )


def test_corpus_resolution_is_git_tracked() -> None:
    paths = fnd.tracked_files(fnd.DEFAULT_CORPUS)
    check("default corpus resolves to many units", len(paths) > 50, f"got {len(paths)}")
    check("every resolved path exists", all(p.exists() for p in paths))
    check("a nonexistent pathspec resolves to nothing", fnd.tracked_files("nope/*.md") == [])


def main() -> int:
    for fn in sorted(
        (v for k, v in globals().items() if k.startswith("test_")),
        key=lambda f: f.__code__.co_firstlineno,
    ):
        print(f"{fn.__name__}:")
        fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): {', '.join(FAILURES)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
