#!/usr/bin/env python3
"""Report which pairs of open PRs share a file, deriving the PR set live.

`shared/workflow/batch-merge-and-resolve.md` states the property this
answers: every PR can be individually clean against `main` while two of them
conflict with each other. No amount of per-PR diligence finds that, because
the comparison that would reveal it is never made -- each PR is checked
against the base, and never against its siblings. The collision surfaces at
merge time, on whichever PR merges second, as a conflict its author did not
create and has no context for.

`CLAUDE.md`'s merge-order section prescribes the remedy in one sentence:
"disjoint" is a claim about their file *sets*, so derive both sets and check
the intersection before asserting it, rather than recalling what each PR is
"about". Until this script existed that derivation was done by hand every
time, which is `shared/principles/deterministic-tools.md`'s stated trigger
for building the instrument.

This is a sibling of `scripts/pr-sweep.py`, sharing its argument shape and
its habit of reporting what it examined. The two answer different questions:
`pr-sweep.py` asks which PRs are stalled, a property of each PR; this asks
which PRs collide, a property of the *set*.

WHAT THIS CANNOT SEE, stated here and in every run's output because a zero
here reads like a merge-order all-clear and is not one. File-set
intersection finds **collisions** -- two PRs editing one file. It cannot
find a **dependency**, where one PR asserts something another makes true,
because those PRs' file sets never overlap. A migration and its consumer, or
a PR whose prose cites content another PR adds, are ordering constraints
this instrument reports as clean. `CLAUDE.md` already says so; the script
repeats it rather than letting its own silence imply otherwise.

Four correctness properties, each of which a hand-run version got wrong:

  1. An IDENTICAL file set is a different finding from a partial overlap. A
     partial overlap is a collision to sequence; an identical set usually
     means two PRs implementing the same change, where the action is to
     close one rather than to order them. Reporting both as "collides"
     buries the duplicate. Identical sets are additionally grouped into
     clusters, since four PRs sharing one file set is one duplicate group
     rather than six unrelated pairs.
  2. The NEGATIVE CONTROL must exercise the detector in the direction that
     can fail. `batch-merge-and-resolve.md` names the trap: a control that
     is clean by construction "runs the real command, against real refs, and
     returns exactly the clean result a working detector would", so it
     establishes nothing. Comparing a file set with ITSELF is exactly that
     impostor -- in Python `s & s == s` holds for every set, so such a check
     reduces to `bool(s)` and cannot fail. The control below instead runs
     the real pair classifier over fixtures known to collide, known to be
     identical, and known to be disjoint, and refuses to examine any repo if
     the classifier misreports one of them.
  3. A file set that could not be DERIVED must not silently become an empty
     set. An empty set collides with nothing, so a `gh` failure would
     otherwise present as a clean pair and shrink the examined count with no
     visible trace. Such a PR is reported by name, excluded from the pair
     count, and forces the "could not run" exit status.
  4. A PR with a genuinely EMPTY diff is not underivable, and is also not
     "mergeable in any order". It shares no file with anything by
     construction, so folding it in with the independently-mergeable PRs
     states a conclusion nothing tested. Empty-diff PRs get their own line.

Exit status is three-valued, per `shared/principles/fail-fast.md`'s "when
exit codes carry meaning, an error path must set its own" and
`shared/workflow/fully-clean.md`'s account of the bug where "the check could
not run" is collapsed into "the check found something":

  0  the sweep ran; advisory, or `--strict` with no collision.
  1  the sweep ran and found a collision, under `--strict`. A verdict.
  2  the sweep could not answer -- usage error, `gh` failure, an
     underivable file set, or a failed negative control. NOT a verdict
     about any PR, and never suppressed by the absence of `--strict`.

Read-only. It reports; it never pushes, comments, closes, or merges.
Reporting two PRs as colliding is not authorization to drive either one --
`shared/workflow/ardi.md` limits that to PRs a session owns or has claimed.
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys

# `raise SystemExit("message")` prints the message but exits 1, which is this
# script's "found a collision" verdict -- so a usage or environment error
# would be read as a finding about the PRs. Set explicitly for that reason,
# matching `scripts/check-pr-fully-clean.py`.
USAGE_EXIT = 2

# Exit status for a real finding under `--strict`. Distinct from USAGE_EXIT
# so a caller can tell a collision from a broken check.
FINDING_EXIT = 1

# Maximum shared paths to print per colliding pair before eliding the rest.
MAX_SHARED_SHOWN = 4

# Files fetched per GraphQL page. A PR with more is paginated rather than
# truncated: a collision check over a truncated file set can report a clean
# pair whose shared file simply was not fetched, which is the vacuous zero
# `fail-fast.md` warns about.
FILES_PAGE = 100

# Printed on every run, including runs that find nothing. A zero here is the
# case most likely to be misread, so the caveat cannot be conditional on
# there being findings to caveat.
BOUNDARY_NOTE = (
    "NOTE: file-set intersection finds COLLISIONS (two PRs editing one "
    "file). It cannot\n"
    "      see a DEPENDENCY, where one PR asserts something another makes "
    "true -- those\n"
    "      PRs' file sets never overlap. A zero above is not a merge-order "
    "all-clear."
)

QUERY = """
query($owner:String!, $name:String!, $first:Int!, $files:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequests(states:OPEN, first:$first, orderBy:{field:CREATED_AT, direction:ASC}) {
      totalCount
      nodes {
        number title url isDraft createdAt
        author { login }
        files(first:$files) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { path }
        }
      }
    }
  }
}
"""

FILES_QUERY = """
query($owner:String!, $name:String!, $number:Int!, $files:Int!, $after:String!) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$number) {
      files(first:$files, after:$after) {
        pageInfo { hasNextPage endCursor }
        nodes { path }
      }
    }
  }
}
"""


class SweepError(Exception):
    """A repo could not be examined. Never silently downgraded to a clean result."""


def die(message):
    """Exit with the usage/environment status, never the finding status."""
    print(message, file=sys.stderr)
    raise SystemExit(USAGE_EXIT)


# --- pair classification -------------------------------------------------
# Pure over file sets, so the negative control and the tests run offline
# with no `gh` call.


def classify_pair(a_files, b_files):
    """Classify one pair of file sets.

    Returns `identical`, `overlap`, or `disjoint`. Two empty sets are
    `disjoint` rather than `identical`: an empty diff carries no content to
    duplicate, so calling two content-free PRs duplicates of each other
    would be a finding about nothing.
    """
    if not a_files or not b_files:
        return "disjoint"
    if a_files == b_files:
        return "identical"
    if a_files & b_files:
        return "overlap"
    return "disjoint"


def find_collisions(file_sets):
    """Every pair sharing at least one file, with the pair count examined.

    Returns `(collisions, pairs_examined)`, where each collision is
    `(a, b, sorted_shared_paths, kind)`. The pair count is returned rather
    than left for the caller to recompute, because "N colliding" is
    meaningless without "of M examined" -- a sweep that examined nothing
    prints the same zero as a clean one.
    """
    numbers = sorted(file_sets)
    collisions = []
    pairs = 0
    for a, b in itertools.combinations(numbers, 2):
        pairs += 1
        kind = classify_pair(file_sets[a], file_sets[b])
        if kind == "disjoint":
            continue
        shared = sorted(file_sets[a] & file_sets[b])
        collisions.append((a, b, shared, kind))
    return collisions, pairs


def identical_clusters(file_sets):
    """Group PRs sharing one file set exactly, largest cluster first.

    Four PRs implementing the same refactor appear as six identical pairs,
    which reads as six problems. It is one: a duplicate group whose members
    are interchangeable. PRs with an empty file set are excluded, per
    `classify_pair`.
    """
    by_set = {}
    for number, files in file_sets.items():
        if not files:
            continue
        by_set.setdefault(frozenset(files), []).append(number)
    clusters = [sorted(v) for v in by_set.values() if len(v) > 1]
    return sorted(clusters, key=lambda c: (-len(c), c))


def collision_partners(collisions):
    """Map each PR number to the set of PRs it collides with."""
    partners = {}
    for a, b, _shared, _kind in collisions:
        partners.setdefault(a, set()).add(b)
        partners.setdefault(b, set()).add(a)
    return partners


def split_non_colliding(file_sets, partners):
    """Split the non-colliding PRs into independent ones and empty-diff ones.

    A PR with a non-empty file set that shares nothing is genuinely
    mergeable in any order, as far as collisions go. A PR with an EMPTY file
    set shares nothing by construction, so reporting it in the same list
    would state a conclusion the comparison never tested.
    """
    independent, empty = [], []
    for number in sorted(file_sets):
        if partners.get(number):
            continue
        (independent if file_sets[number] else empty).append(number)
    return independent, empty


# --- the negative control ------------------------------------------------


# Each fixture pins the classifier in one direction. The known-COLLIDING
# ones are the load-bearing half: a detector that has silently stopped
# reporting collisions passes every disjoint fixture, and passing those is
# what a broken run would look like.
CONTROL_CASES = (
    ("known-colliding pair reports overlap", {"a.md", "b.md"}, {"b.md", "c.md"},
     "overlap"),
    ("known-identical pair reports identical", {"a.md", "b.md"},
     {"b.md", "a.md"}, "identical"),
    ("known-disjoint pair reports disjoint", {"a.md"}, {"z.md"}, "disjoint"),
    ("a single shared path is enough to collide", {"x/y.R"}, {"x/y.R"},
     "identical"),
    ("an empty set never reports a collision", set(), {"a.md"}, "disjoint"),
)


def run_negative_control():
    """Exercise the pair classifier before any repo is examined.

    `batch-merge-and-resolve.md`: "A matrix of zeros is indistinguishable
    from a detector that never ran", so run the control FIRST, "not as a
    postscript, so a broken detector is caught before its output has been
    read as a result."

    Returns `(ok, lines)`. The examined-pair count is checked too, since a
    classifier that works while the enumeration returns nothing produces the
    same clean matrix.
    """
    lines, ok = [], True
    for label, a_files, b_files, expected in CONTROL_CASES:
        actual = classify_pair(a_files, b_files)
        if actual != expected:
            ok = False
            lines.append(f"  FAILED: {label} (got {actual!r}, want {expected!r})")

    control_sets = {1: {"a.md", "b.md"}, 2: {"b.md", "c.md"}, 3: {"z.md"}}
    collisions, pairs = find_collisions(control_sets)
    if pairs != 3:
        ok = False
        lines.append(f"  FAILED: enumeration examined {pairs} pairs, want 3")
    if len(collisions) != 1:
        ok = False
        lines.append(
            f"  FAILED: enumeration found {len(collisions)} collisions, want 1"
        )

    verdict = "PASSED" if ok else "FAILED"
    header = (
        f"negative control: {verdict} "
        f"({len(CONTROL_CASES)} classifier cases + a 3-pair enumeration; "
        "includes a known-colliding case, so a detector that cannot report a "
        "collision is caught here)"
    )
    return ok, [header] + lines


# --- fetching ------------------------------------------------------------


def gh_graphql(query, fields, context):
    """Run one GraphQL query, raising rather than returning an empty result.

    Every failure path raises. A `gh` failure that returned `{}` would
    become an empty file set, which collides with nothing and so reads as a
    clean pair -- the pass path and the failure path printing the same
    thing, which `fail-fast.md` says is not yet a check.
    """
    proc = subprocess.run(
        ["gh", "api", "graphql"] + fields + ["-f", f"query={query}"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SweepError(
            f"gh failed for {context} (exit {proc.returncode}): "
            f"{proc.stderr.strip()}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SweepError(f"gh returned unparseable JSON for {context}: {exc}")
    if payload.get("errors"):
        raise SweepError(f"GraphQL errors for {context}: {payload['errors']}")
    data = payload.get("data")
    if not data:
        raise SweepError(f"GraphQL returned no data for {context}")
    return data


def split_repo(repo):
    """Split `owner/name`, failing loudly on anything else."""
    if repo.count("/") != 1 or not all(repo.split("/")):
        die(f"pr-overlap: --repo needs owner/name, got {repo!r}")
    return repo.split("/", 1)


def remaining_files(owner, name, number, cursor, page):
    """Page through a PR's remaining files.

    Truncating instead would let a shared file sit unfetched on page two and
    report the pair clean, so the pages are followed to the end.
    """
    paths, guard = [], 0
    while cursor:
        guard += 1
        if guard > 100:
            raise SweepError(
                f"#{number}: file pagination did not terminate after "
                f"{guard} pages"
            )
        data = gh_graphql(
            FILES_QUERY,
            [
                "-F", f"owner={owner}", "-F", f"name={name}",
                "-F", f"number={number}", "-F", f"files={page}",
                "-f", f"after={cursor}",
            ],
            f"{owner}/{name}#{number} files",
        )
        pull = ((data.get("repository") or {}).get("pullRequest") or {})
        files = pull.get("files") or {}
        paths.extend(
            n["path"] for n in (files.get("nodes") or []) if n.get("path")
        )
        info = files.get("pageInfo") or {}
        cursor = info.get("endCursor") if info.get("hasNextPage") else None
    return paths


def file_set_for(owner, name, pr, page):
    """Complete set of paths a PR changes.

    Raises rather than returning a partial set: a file set that is
    incomplete for an unreported reason produces a clean-looking pair.
    """
    files = pr.get("files") or {}
    paths = [n["path"] for n in (files.get("nodes") or []) if n.get("path")]
    info = files.get("pageInfo") or {}
    if info.get("hasNextPage"):
        paths.extend(
            remaining_files(owner, name, pr["number"], info.get("endCursor"), page)
        )
    if files.get("totalCount") and not paths:
        raise SweepError(
            f"#{pr['number']}: reported {files['totalCount']} changed files "
            "and returned none"
        )
    return set(paths)


def fetch(repo, limit, page):
    """Fetch every open PR in one repo, with its complete file set."""
    owner, name = split_repo(repo)
    data = gh_graphql(
        QUERY,
        [
            "-F", f"owner={owner}", "-F", f"name={name}",
            "-F", f"first={limit}", "-F", f"files={page}",
        ],
        repo,
    )
    repository = data.get("repository")
    if repository is None:
        raise SweepError(f"no such repository: {repo}")
    return owner, name, repository["pullRequests"]


def sweep(repo, limit, page, include_drafts):
    """Derive one repo's open-PR set and compare every pair of file sets."""
    owner, name, prs = fetch(repo, limit, page)
    nodes = prs.get("nodes") or []
    total = prs.get("totalCount", len(nodes))

    file_sets, meta, underivable, drafts_skipped = {}, {}, [], 0
    for pr in nodes:
        number = pr.get("number")
        if pr.get("isDraft") and not include_drafts:
            drafts_skipped += 1
            continue
        meta[number] = {
            "title": pr.get("title") or "",
            "url": pr.get("url"),
            "isDraft": pr.get("isDraft", False),
            "created": (pr.get("createdAt") or "")[:10],
            "author": (pr.get("author") or {}).get("login"),
        }
        try:
            file_sets[number] = file_set_for(owner, name, pr, page)
        except SweepError as exc:
            underivable.append({"number": number, "error": str(exc)})

    collisions, pairs = find_collisions(file_sets)
    partners = collision_partners(collisions)
    independent, empty_diff = split_non_colliding(file_sets, partners)
    clusters = identical_clusters(file_sets)

    # Pairs lost because a file set could not be derived. Printed rather
    # than left implicit: without it the examined count simply shrinks, and
    # a smaller sweep looks exactly like a smaller repo.
    examined = len(file_sets)
    unexaminable = (
        len(underivable) * examined + len(underivable) * (len(underivable) - 1) // 2
    )

    return {
        "repo": repo,
        "open_total": total,
        "returned": len(nodes),
        "drafts_skipped": drafts_skipped,
        "examined": examined,
        "numbers": sorted(file_sets),
        "file_sets": {n: sorted(f) for n, f in file_sets.items()},
        "pairs_examined": pairs,
        "pairs_unexaminable": unexaminable,
        "underivable": underivable,
        "collisions": [
            {"a": a, "b": b, "shared": shared, "kind": kind}
            for a, b, shared, kind in collisions
        ],
        "identical_clusters": clusters,
        "independent": independent,
        "empty_diff": empty_diff,
        "partners": {n: sorted(p) for n, p in partners.items()},
        "meta": meta,
        # Truncation counts as incomplete: a collision sweep that did not
        # fetch every open PR can report a clean queue whose colliding pair
        # simply was not fetched.
        "ok": not underivable and len(nodes) >= total,
    }


# --- rendering -----------------------------------------------------------


def render(result):
    """Render one repo's result, leading with what was examined."""
    lines = []
    truncated = ""
    if result["returned"] < result["open_total"]:
        truncated = (
            f" [TRUNCATED: {result['returned']} of {result['open_total']} "
            "fetched; raise --limit]"
        )
    lines.append("=" * 72)
    lines.append(
        f"{result['repo']}: examined {result['examined']} of "
        f"{result['open_total']} open PRs "
        f"({result['drafts_skipped']} draft(s) skipped){truncated}"
    )
    lines.append("=" * 72)

    if result["underivable"]:
        lines.append(
            f"  COULD NOT DERIVE {len(result['underivable'])} file set(s) -- "
            f"{result['pairs_unexaminable']} pair(s) were NOT examined. "
            "This sweep is INCOMPLETE:"
        )
        for item in result["underivable"]:
            lines.append(f"    #{item['number']}: {item['error']}")

    lines.append(
        f"pairs examined: {result['pairs_examined']}; "
        f"pairs sharing >=1 file: {len(result['collisions'])} "
        f"({sum(1 for c in result['collisions'] if c['kind'] == 'identical')} "
        "with identical file sets)"
    )

    if not result["examined"]:
        lines.append("  (no open PRs to compare)")

    clusters = result["identical_clusters"]
    if clusters:
        lines.append("")
        lines.append(
            "DUPLICATES -- identical file sets. Usually one change implemented "
            "more than"
        )
        lines.append(
            "once, where the action is to close all but one rather than to "
            "order them:"
        )
        for cluster in clusters:
            # Every member shares one file set by definition, so any
            # member's own set describes the whole cluster.
            shared = result["file_sets"].get(cluster[0], [])
            listed = ", ".join(f"#{n}" for n in cluster)
            lines.append(f"  {listed}  ({len(shared)} file(s), identical)")
            for path in shared[:MAX_SHARED_SHOWN]:
                lines.append(f"      {path}")
            if len(shared) > MAX_SHARED_SHOWN:
                lines.append(
                    f"      ... and {len(shared) - MAX_SHARED_SHOWN} more"
                )
            for number in cluster:
                title = result["meta"].get(number, {}).get("title", "")
                lines.append(f"      #{number}  {title[:58]}")

    overlaps = [c for c in result["collisions"] if c["kind"] == "overlap"]
    if overlaps:
        lines.append("")
        lines.append(
            "COLLISIONS -- partial overlap. These need a merge order, and the "
            "second to"
        )
        lines.append("merge will see a conflict its author did not create:")
        for coll in sorted(overlaps, key=lambda c: -len(c["shared"])):
            lines.append(
                f"  #{coll['a']} x #{coll['b']}: {len(coll['shared'])} shared"
            )
            for path in coll["shared"][:MAX_SHARED_SHOWN]:
                lines.append(f"      {path}")
            if len(coll["shared"]) > MAX_SHARED_SHOWN:
                lines.append(
                    f"      ... and {len(coll['shared']) - MAX_SHARED_SHOWN} more"
                )

    if result["examined"]:
        lines.append("")
        lines.append("per-PR collision count (most entangled first):")
        for number in sorted(
            result["numbers"],
            key=lambda n: (-len(result["partners"].get(n, ())), n),
        ):
            info = result["meta"].get(number, {})
            count = len(result["partners"].get(number, ()))
            draft = " (draft)" if info.get("isDraft") else ""
            lines.append(
                f"  #{number}  {info.get('created', '?')}  "
                f"collides with {count:2d}{draft}  {info.get('title', '')[:52]}"
            )

    listed = ", ".join(f"#{n}" for n in result["independent"])
    lines.append("")
    lines.append(
        "mergeable in any order (shares no file with another open PR): "
        f"{listed if result['independent'] else 'none'}"
    )
    if result["empty_diff"]:
        empty = ", ".join(f"#{n}" for n in result["empty_diff"])
        lines.append(
            f"empty diff, so compared against nothing (NOT a clean result): "
            f"{empty}"
        )

    lines.append("")
    lines.append(BOUNDARY_NOTE)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Report which pairs of open PRs share a file, deriving the PR "
            "set live. Finds collisions, not dependencies."
        )
    )
    parser.add_argument(
        "--repo", "-R", action="append", required=True, metavar="OWNER/NAME",
        help="Repository to sweep; repeat for several.",
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Maximum open PRs to fetch per repo (default 100).",
    )
    parser.add_argument(
        "--files-per-page", type=int, default=FILES_PAGE,
        help=f"Files fetched per GraphQL page (default {FILES_PAGE}).",
    )
    parser.add_argument(
        "--exclude-drafts", action="store_true",
        help=(
            "Skip draft PRs. Included by default, unlike pr-sweep.py: a "
            "draft's file set collides at merge time just as a ready one's "
            "does, so excluding drafts hides real collisions."
        ),
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help=(
            f"Exit {FINDING_EXIT} when any pair collides (default: advisory, "
            f"0). A check that could not run exits {USAGE_EXIT} either way."
        ),
    )
    args = parser.parse_args(argv)

    # Validate usage before anything else runs, so a typo in --repo is not
    # reported underneath a negative-control banner that implies work began.
    for repo in args.repo:
        split_repo(repo)
    if args.limit < 1:
        die(f"pr-overlap: --limit must be at least 1, got {args.limit}")
    if args.files_per_page < 1:
        die(
            "pr-overlap: --files-per-page must be at least 1, got "
            f"{args.files_per_page}"
        )

    # The control runs before any repo is touched, so a broken detector is
    # caught before its output has been read as a result.
    control_ok, control_lines = run_negative_control()
    if not args.json:
        print("\n".join(control_lines))
    if not control_ok:
        print(
            "pr-overlap: negative control FAILED; refusing to report any "
            "result, since a detector that cannot report a known collision "
            "would print the same zeros as a clean queue.",
            file=sys.stderr,
        )
        return USAGE_EXIT

    results, failed = [], []
    for repo in args.repo:
        try:
            results.append(
                sweep(repo, args.limit, args.files_per_page,
                      not args.exclude_drafts)
            )
        except SweepError as exc:
            # Bounded, reported degradation at the per-repo boundary: one
            # unreachable repo must not hide the others, and must not be
            # mistaken for a clean one either -- hence the explicit record
            # and the USAGE_EXIT below.
            failed.append({"repo": repo, "error": str(exc)})

    if args.json:
        print(json.dumps(
            {
                "control_passed": control_ok,
                "control_report": control_lines,
                "boundary": BOUNDARY_NOTE,
                "repos": results,
                "failed_repos": failed,
            },
            indent=2, sort_keys=True,
        ))
    else:
        if results:
            print("\n\n".join(render(r) for r in results))
        for item in failed:
            print(
                f"\npr-overlap: COULD NOT EXAMINE {item['repo']}: "
                f"{item['error']}",
                file=sys.stderr,
            )

    incomplete = failed or any(not r["ok"] for r in results)
    if incomplete:
        return USAGE_EXIT
    collisions = sum(len(r["collisions"]) for r in results)
    return FINDING_EXIT if (args.strict and collisions) else 0


if __name__ == "__main__":
    sys.exit(main())
