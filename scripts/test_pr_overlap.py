#!/usr/bin/env python3
"""Regression tests for pr-overlap.py.

The classification, clustering, and rendering functions are pure over file
sets, so these run offline with no `gh` call. The two tests that need a
fetch monkeypatch one in.

Several fixtures below encode a defect in the hand-run prototype this script
replaces rather than an invented edge case, so a failure here names the
mistake it prevents. The load-bearing one is
`negative control FAILS when the classifier is broken`: the prototype's
control compared a file set with itself, which in Python is a tautology, so
it passed whether or not the detector worked.
"""
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "pr_overlap", Path(__file__).parent / "pr-overlap.py"
)
pr_overlap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr_overlap)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def pr_node(number, paths, draft=False, title=None, total=None, cursor=None):
    """Build a PR node matching the GraphQL payload shape."""
    return {
        "number": number,
        "title": title or f"PR {number}",
        "url": f"https://example.invalid/{number}",
        "isDraft": draft,
        "createdAt": "2026-08-20T00:00:00Z",
        "author": {"login": "someone"},
        "files": {
            "totalCount": len(paths) if total is None else total,
            "pageInfo": {
                "hasNextPage": cursor is not None,
                "endCursor": cursor,
            },
            "nodes": [{"path": p} for p in paths],
        },
    }


def fake_fetch(nodes, total=None):
    """A `fetch` replacement returning fixture nodes, so no `gh` call runs."""
    def _fetch(repo, limit, page):
        owner, name = repo.split("/", 1)
        return owner, name, {
            "totalCount": len(nodes) if total is None else total,
            "nodes": nodes,
        }
    return _fetch


def run_main(argv, fetch=None):
    """Run main() with stdout captured, returning (exit_code, output)."""
    original = pr_overlap.fetch
    if fetch is not None:
        pr_overlap.fetch = fetch
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            try:
                code = pr_overlap.main(argv)
            except SystemExit as exc:
                code = exc.code
    finally:
        pr_overlap.fetch = original
    return code, buffer.getvalue()


# --- 1. A duplicate is not a collision -----------------------------------
# The issue this script closes turned on the distinction: four altdoc PRs
# had IDENTICAL file sets and implemented the same refactor, where the
# action is to close three, not to sequence them. Reporting both findings as
# "collides" buries the duplicate in the noise.
check(
    "a partial overlap is classified as overlap",
    pr_overlap.classify_pair({"a.md", "b.md"}, {"b.md", "c.md"}) == "overlap",
)
check(
    "an identical file set is classified as identical, not overlap",
    pr_overlap.classify_pair({"a.md", "b.md"}, {"a.md", "b.md"}) == "identical",
)
check(
    "sets sharing nothing are disjoint",
    pr_overlap.classify_pair({"a.md"}, {"z.md"}) == "disjoint",
)
check(
    "a single shared path is enough to collide",
    pr_overlap.classify_pair({"x/y.R", "p.R"}, {"x/y.R", "q.R"}) == "overlap",
)
# An empty diff has no content to duplicate, so two content-free PRs are not
# duplicates of each other -- that would be a finding about nothing.
check(
    "an empty set never collides, even with another empty set",
    pr_overlap.classify_pair(set(), set()) == "disjoint",
)
check(
    "an empty set does not collide with a populated one",
    pr_overlap.classify_pair(set(), {"a.md"}) == "disjoint",
)

# --- 2. Report pairs EXAMINED, not only pairs found ----------------------
# `batch-merge-and-resolve.md`: "0 conflicts is meaningless without of N
# pairs examined, and the count is what distinguishes a clean queue from an
# empty loop."
_, pairs = pr_overlap.find_collisions({1: {"a"}, 2: {"b"}, 3: {"c"}, 4: {"d"}})
check("find_collisions reports the pair count it examined", pairs == 6)
collisions, pairs = pr_overlap.find_collisions({1: {"a"}, 2: {"a"}, 3: {"z"}})
check("a clean-but-nonempty sweep still reports its pair count", pairs == 3)
check("find_collisions finds the one colliding pair", len(collisions) == 1)
check(
    "an empty PR set examines zero pairs, distinguishably from a clean sweep",
    pr_overlap.find_collisions({}) == ([], 0),
)
check(
    "a single PR examines zero pairs",
    pr_overlap.find_collisions({7: {"a.md"}}) == ([], 0),
)
check(
    "shared paths are reported sorted, so output is stable across runs",
    pr_overlap.find_collisions({1: {"b", "a"}, 2: {"b", "a"}})[0][0][2]
    == ["a", "b"],
)

# --- 3. The negative control must be able to FAIL ------------------------
# The prototype's control tested `f and (f & f) == f`, which reduces to
# `bool(f)` for every Python set -- the "perfect impostor"
# `batch-merge-and-resolve.md` names, which "runs the real command, against
# real refs, and returns exactly the clean result a working detector would".
# These two tests are the pair that matters: the control passes on a working
# classifier AND fails on a broken one.
ok, report = pr_overlap.run_negative_control()
check("the negative control passes against the real classifier", ok)
check(
    "the control report names its verdict in the first line",
    report[0].startswith("negative control: PASSED"),
)

_real_classify = pr_overlap.classify_pair
try:
    pr_overlap.classify_pair = lambda a, b: "disjoint"
    broken_ok, broken_report = pr_overlap.run_negative_control()
finally:
    pr_overlap.classify_pair = _real_classify
check(
    "negative control FAILS when the classifier cannot report a collision",
    not broken_ok,
)
check(
    "the failing control says so in its verdict line",
    broken_report[0].startswith("negative control: FAILED"),
)

_real_classify = pr_overlap.classify_pair
try:
    # A classifier that calls everything a collision is broken in the other
    # direction, and a control testing only the colliding case would miss it.
    pr_overlap.classify_pair = lambda a, b: "overlap"
    noisy_ok, _ = pr_overlap.run_negative_control()
finally:
    pr_overlap.classify_pair = _real_classify
check(
    "negative control FAILS when the classifier collides everything",
    not noisy_ok,
)

# --- 4. Identical sets group into clusters -------------------------------
# Four PRs sharing one file set appear as six identical pairs, which reads
# as six problems. It is one duplicate group.
CLUSTER_SETS = {
    105: {"R/rd2qmd.R"},
    108: {"R/rd2qmd.R"},
    111: {"R/rd2qmd.R"},
    112: {"R/rd2qmd.R"},
    113: {"R/other.R"},
}
check(
    "four PRs with one file set form a single cluster",
    pr_overlap.identical_clusters(CLUSTER_SETS) == [[105, 108, 111, 112]],
)
check(
    "that same set yields six identical PAIRS, which is why clustering matters",
    sum(
        1 for c in pr_overlap.find_collisions(CLUSTER_SETS)[0]
        if c[3] == "identical"
    )
    == 6,
)
check(
    "a lone PR is not a cluster",
    pr_overlap.identical_clusters({1: {"a.md"}, 2: {"b.md"}}) == [],
)
check(
    "empty file sets do not cluster together",
    pr_overlap.identical_clusters({1: set(), 2: set()}) == [],
)
check(
    "clusters are ordered largest first",
    pr_overlap.identical_clusters(
        {1: {"a"}, 2: {"a"}, 3: {"b"}, 4: {"b"}, 5: {"b"}}
    )
    == [[3, 4, 5], [1, 2]],
)

# --- 5. An empty diff is not "mergeable in any order" --------------------
# A PR with no files shares nothing by construction, so folding it into the
# independently-mergeable list states a conclusion the comparison never
# tested. `pr-on-claim.md` opens every issue PR as an empty commit, so this
# shape is routine rather than exotic.
SPLIT_SETS = {1: {"a.md"}, 2: {"a.md"}, 3: {"solo.md"}, 4: set()}
split_collisions, _ = pr_overlap.find_collisions(SPLIT_SETS)
split_partners = pr_overlap.collision_partners(split_collisions)
independent, empty = pr_overlap.split_non_colliding(SPLIT_SETS, split_partners)
check("a genuinely independent PR is reported as independent", independent == [3])
check("an empty-diff PR is reported separately, not as independent", empty == [4])
check(
    "colliding PRs appear in neither list",
    1 not in independent and 2 not in independent,
)
check(
    "collision_partners is symmetric",
    split_partners.get(1) == {2} and split_partners.get(2) == {1},
)

# --- 6. The boundary caveat prints even when nothing is found ------------
# Issue #2072's Boundary section: file-set intersection sees collisions and
# not dependencies, and "the script's output should say so rather than
# reading as a merge-order all-clear". A zero is exactly the case that would
# otherwise be misread, so the caveat cannot be conditional on findings.
clean_code, clean_out = run_main(
    ["-R", "o/r"],
    fetch=fake_fetch([pr_node(1, ["a.md"]), pr_node(2, ["b.md"])]),
)
check("a clean sweep still prints the dependency caveat", "DEPENDENCY" in clean_out)
check(
    "a clean sweep says a zero is not a merge-order all-clear",
    "not a merge-order all-clear" in clean_out,
)
check(
    "a clean sweep reports the pair count it examined",
    "pairs examined: 1" in clean_out,
)
check(
    "a clean sweep reports how many of the open PRs it examined",
    "examined 2 of 2 open PRs" in clean_out,
)
check("a clean sweep runs the negative control first", clean_out.startswith(
    "negative control:"
))
check("a clean advisory sweep exits 0", clean_code == 0)

# --- 7. Exit status is three-valued --------------------------------------
# `fail-fast.md`: "reserve a distinct status for usage and internal errors
# whenever any other status carries a verdict, and set it explicitly", and
# assert the CODE rather than merely that SystemExit was raised.
COLLIDING = [pr_node(1, ["a.md"]), pr_node(2, ["a.md", "b.md"])]
advisory_code, advisory_out = run_main(["-R", "o/r"], fetch=fake_fetch(COLLIDING))
check("a collision is advisory by default, exiting 0", advisory_code == 0)
check("the collision is still reported", "COLLISIONS" in advisory_out)
strict_code, _ = run_main(["-R", "o/r", "--strict"], fetch=fake_fetch(COLLIDING))
check("--strict exits 1 on a real collision", strict_code == pr_overlap.FINDING_EXIT)
strict_clean, _ = run_main(
    ["-R", "o/r", "--strict"],
    fetch=fake_fetch([pr_node(1, ["a.md"]), pr_node(2, ["b.md"])]),
)
check("--strict exits 0 when nothing collides", strict_clean == 0)
check("the two statuses are distinct", pr_overlap.FINDING_EXIT != pr_overlap.USAGE_EXIT)


def usage_exit(argv):
    try:
        pr_overlap.main(argv)
    except SystemExit as exc:
        return exc.code
    return None


check(
    "a malformed --repo exits with the usage status, not the finding status",
    usage_exit(["-R", "not-a-repo"]) == pr_overlap.USAGE_EXIT,
)
check(
    "a --repo with too many slashes is rejected",
    usage_exit(["-R", "a/b/c"]) == pr_overlap.USAGE_EXIT,
)
check(
    "an empty owner is rejected",
    usage_exit(["-R", "/name"]) == pr_overlap.USAGE_EXIT,
)
check(
    "a zero --limit is rejected rather than silently examining nothing",
    usage_exit(["-R", "o/r", "--limit", "0"]) == pr_overlap.USAGE_EXIT,
)

# --- 8. A gh failure must never read as a clean pair ---------------------
# The single most important property. An underivable file set becomes an
# empty set, which collides with nothing, so the failure path would
# otherwise print exactly what the clean path prints.
def exploding_fetch(repo, limit, page):
    raise pr_overlap.SweepError("gh failed for o/r (exit 4): bad credentials")


boom_code, boom_out = run_main(["-R", "o/r"], fetch=exploding_fetch)
check(
    "a gh failure exits with the usage status, not 0",
    boom_code == pr_overlap.USAGE_EXIT,
)
check(
    "a gh failure does NOT print a clean-looking zero result",
    "pairs examined: 0" not in boom_out,
)
check(
    "a gh failure still exits non-zero without --strict",
    run_main(["-R", "o/r"], fetch=exploding_fetch)[0] != 0,
)

# A PR whose file set could not be derived is reported by name, and the
# pairs it would have participated in are counted as NOT examined -- so a
# shrunken sweep is visible rather than looking like a smaller repo.
UNDERIVABLE = [
    pr_node(1, ["a.md"]),
    pr_node(2, ["b.md"]),
    pr_node(3, [], total=7),  # claims 7 files, returns none
]
under_code, under_out = run_main(["-R", "o/r"], fetch=fake_fetch(UNDERIVABLE))
check(
    "an underivable file set forces the usage status",
    under_code == pr_overlap.USAGE_EXIT,
)
check("the underivable PR is named", "#3" in under_out)
check("the sweep declares itself INCOMPLETE", "INCOMPLETE" in under_out)
check(
    "the pairs that could not be examined are counted",
    "2 pair(s) were NOT examined" in under_out,
)

# --- 9. Truncation is incomplete, not clean ------------------------------
# A --limit below the open-PR count means the colliding pair may simply not
# have been fetched, which is the vacuous zero `fail-fast.md` warns about.
trunc_code, trunc_out = run_main(
    ["-R", "o/r"],
    fetch=fake_fetch([pr_node(1, ["a.md"]), pr_node(2, ["b.md"])], total=40),
)
check("a truncated fetch is reported as TRUNCATED", "TRUNCATED" in trunc_out)
check(
    "a truncated fetch exits with the usage status rather than reporting clean",
    trunc_code == pr_overlap.USAGE_EXIT,
)

# --- 10. Drafts are included by default, unlike pr-sweep.py --------------
# `check-purpose-before-reusing.md`: the sibling skips drafts because a
# draft's empty diff is a false "empty-diff" finding. Here a draft's file
# set collides at merge time exactly as a ready one's does, so the sibling's
# default would hide real collisions. The purpose did not transfer.
DRAFTS = [pr_node(1, ["a.md"], draft=True), pr_node(2, ["a.md"])]
draft_code, draft_out = run_main(["-R", "o/r", "--strict"], fetch=fake_fetch(DRAFTS))
check(
    "a draft PR's collision is found by default",
    draft_code == pr_overlap.FINDING_EXIT,
)
check("a draft is labelled as such in the per-PR table", "(draft)" in draft_out)
excl_code, excl_out = run_main(
    ["-R", "o/r", "--strict", "--exclude-drafts"], fetch=fake_fetch(DRAFTS)
)
check("--exclude-drafts skips them", "1 draft(s) skipped" in excl_out)
check("excluding the draft leaves nothing to collide with", excl_code == 0)

# --- 11. JSON output ------------------------------------------------------
json_code, json_out = run_main(
    ["-R", "o/r", "--json"], fetch=fake_fetch(COLLIDING)
)
parsed = json.loads(json_out)
check("--json emits parseable JSON", isinstance(parsed, dict))
check("JSON carries the boundary caveat", "DEPENDENCY" in parsed["boundary"])
check("JSON records that the control passed", parsed["control_passed"] is True)
check(
    "JSON reports pairs examined alongside collisions",
    parsed["repos"][0]["pairs_examined"] == 1
    and len(parsed["repos"][0]["collisions"]) == 1,
)
check(
    "JSON names the shared paths",
    parsed["repos"][0]["collisions"][0]["shared"] == ["a.md"],
)
check("JSON does not print the control banner to stdout", json_code == 0)

# --- 12. Render surfaces the duplicate/collision split -------------------
DUPES = [pr_node(n, ["R/rd2qmd.R"]) for n in (105, 108, 111)] + [
    pr_node(113, ["R/rd2qmd.R", "R/other.R"])
]
dupe_code, dupe_out = run_main(["-R", "o/r"], fetch=fake_fetch(DUPES))
check("identical sets are rendered under DUPLICATES", "DUPLICATES" in dupe_out)
check("partial overlaps are rendered under COLLISIONS", "COLLISIONS" in dupe_out)
check(
    "the duplicate cluster lists all three members on one line",
    "#105, #108, #111" in dupe_out,
)
check(
    "the identical-set count is reported beside the collision count",
    "with identical file sets" in dupe_out,
)
check("the sweep examined all six pairs", "pairs examined: 6" in dupe_out)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
