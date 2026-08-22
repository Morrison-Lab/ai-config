When reviewing code or prose --- including mathematical content (derivations,
proofs, restated formulas) --- check for redundant content that could be
consolidated, and question it rather than silently accepting duplication.
Redundancy is doubly costly: more to read, and more to keep in sync when one
copy changes and the other doesn't.

**The litmus test: only flag content as redundant when consolidating it would
lose nothing.** If removing one copy would drop a case, an edge condition, a
generality, or a distinct meaning, it is not redundant --- it's merely similar.
Flagging similar-but-distinct content as a duplicate recommends a merge that
loses something; that's a worse outcome than leaving the duplication alone.
Question the content, don't assume either way: check what each copy actually
covers before deciding whether one subsumes the other.


**The inverse failure: consolidation can gain a trigger even while removing
duplication.**
The litmus test above asks whether consolidating copies would lose a case.
The mirror image is whether it would add one.
A shared helper can be called from places whose old predicates differed, or from
a place that had no guard at all, so the helper is not automatically any one
call site's old behavior.
A state where exactly one call site used to fire, or where a newly guarded call
site did not fire before, is where a shared helper can silently widen or narrow
the system.

Before extracting, enumerate the states each old predicate fired in, including
"no guard" for newly covered call sites, and decide whether the union is
intended.
If the predicates differ, DRY may still be right, but the helper's name and
call sites need to state the chosen predicate rather than smuggling it in as a
cleanup.
When the triggering state depends on an environment fact, check the unchanged
context in front of you for that fact before treating the finding as speculative.
That is the same move
[`address-every-comment`](address-every-comment.md) requires for findings whose
evidence is outside the reviewer-visible diff.

- **Do:** write each call site's old predicate down before extracting a shared
  helper, including newly guarded sites whose old predicate was "no guard".
- **Do:** make the shared predicate an explicit design choice, then test the
  uncommon state that distinguishes the call sites.
- **Don't:** infer that two checks are redundant because they agree in the case
  you usually see.
- **Don't:** treat an environment-dependent finding as speculative when the PR's
  unchanged context gives you the missing environment fact.

(Morrison-Lab/ai-config#994, merged 2026-08-01T20:29:11Z: at head `11b5a3d`,
`cnode` had a refuse-to-nest guard and `tui-alloc` gained the shared guard
during the cleanup.
`cnode`'s old guard tested whether the hostname was in `sinfo`'s node list,
while the extracted `refuse_if_nested` draft tested only `[ -n "$SLURM_JOB_ID" ]`.
On shiva those differ because `LaunchParameters = (null)` leaves a bare
`salloc` shell on the login node while setting `SLURM_JOB_ID`; only
`srun --pty` moves the session to a compute node.
That draft therefore fired after a bare `salloc`, printed
`already inside SLURM job 4242 on shiva` while naming the login host, and
advised the bare command that would have run on the login node.
Review caught the widened trigger before merge, and commit `bd1bf356` restored
the missing branch by checking `on_compute_node()` inside the `SLURM_JOB_ID`
case.)

## What this looks like in each domain

- **Prose.** The same claim or explanation restated in two places --- a README
  section and a doc page saying the same thing in different words, two
  paragraphs in the same document making the same point --- that could become
  one statement plus a cross-reference to it.
- **Math.** A general formula and a separately derived special case that the
  general formula already covers; the same derivation carried out twice in
  different notation with no added insight; a theorem re-proved in place
  instead of cited. Consolidating here means stating the general result once
  and deriving the special case from it (or citing it), not deleting the
  special case's meaning if it actually adds a constraint the general form
  doesn't capture.
- **Code.** Duplicated logic across functions, files, or configuration that
  could be extracted into one shared unit without narrowing what either call
  site needs. Two functions that look alike but branch on genuinely different
  conditions are not this case --- extracting a shared unit there would need a
  parameter or flag for the branch, and that's a judgment call, not an
  automatic win.

## A fix for restated-fact drift can reintroduce it inside its own diff

The checks above are about facts already restated when you read the
diff.
This is a narrower trap that surfaces only inside a PR whose whole
purpose is removing that duplication: the fix itself can restate the
fact once more, in the copy being fixed, without also updating every
sibling the fact lives in.

The new sentence does not read as a fresh restatement.
It reads as an ordinary caveat or clarification added while editing
one file, so nothing marks it as the same category of defect the PR
exists to close.

- **Do:** before pushing a fix for restated-fact drift, diff the
  fixed copy against every sibling the fact appears in, and check
  whether the fix itself only touched one.
- **Do:** ask, of any new sentence added to the file being fixed,
  whether it states a fact that also lives in a sibling copy.
- **Don't:** trust that fixing the drift you found rules out adding
  new drift in the same diff.
- **Don't:** read "this PR is about de-duplication" as evidence the
  PR's own additions are free of duplication.

**A mechanised guard built to catch this class of drift can only
prove what its own scope covers, and that scope belongs beside the
check, not only in the PR that added it.**

A guard comparing a delimited list catches drift inside that list and
says nothing about free prose sitting next to it.
A reader who only sees the check passing has no way to tell the
difference, because a check that exists reads as a check that is
sufficient.

- **Do:** state a mechanised check's scope in a comment where the
  check itself lives.
- **Do:** name what the check does NOT cover --- free prose outside
  its delimited target, a sibling file it never reads --- rather than
  leaving the boundary implicit.
- **Don't:** let a check's mere presence stand in for its coverage;
  read what it actually compares before trusting a green run.

(Measured 2026-08-21 on `Morrison-Lab/gha#577`, merged.
The PR's purpose was stopping one fact from being independently
restated in `README.md` and a website page and drifting apart.
Review found the PR itself had added a caveat sentence to `README.md`
and not to the website page --- the identical defect, inside the fix
meant to close it.
The guard the PR added could not have caught it: it compares a
delimited list, and the caveat was free prose outside the markers.)

## Applies at the scale of what's in front of you

This is a review-time check on the document or diff already being read, not a
mandate to sweep an entire corpus for duplication --- that's a separate,
larger job with its own tooling. When the redundancy found here turns out to
span more than the current diff (the same fact duplicated across many files,
the same procedure copied into several unrelated places), say so and route it
to `find-overlap` (or `consolidate-skills`/`consolidate-memory` for
skills/memories), rather than trying to fix everything found along the way in
the current review.

## Use the overlap instrument, not literal grep

A redundancy finding is exactly where phrase grep is most tempting, and where
it is least trustworthy.
This corpus uses semantic line breaks and inline markup, so a copied claim can
span a newline or differ only by backticks while still being the same prose.
Use the existing overlap instrument for the broad sweep:
`scripts/find-near-duplicates.py` ranks corpus pairs by normalized word
shingles and reports the number of units and pairs it examined.
Its default target set and top-pair threshold are tuned for near-duplicate
files, not for proving that a short copied run between long `shared/` files is
absent.
So treat it as the reusable starting point and corpus-wide reading list, not as
a clean-result certificate for a narrow review finding.
When the question is a narrower single-file audit, use the same algorithmic
shape with a run-reporting matcher:
normalize whitespace and markup on both sides, lower-case, compare word
n-grams, and report the examined scope and every overlapping run.

- **Do:** run `scripts/find-near-duplicates.py` for the broad candidate list,
  or run an equivalent normalized n-gram matcher that reports overlapping runs
  for the files under review.
- **Do:** report the examined files, pairs, or runs alongside any overlap found,
  then read the overlapping bodies before deciding whether consolidation loses
  nothing.
- **Don't:** use literal grep as evidence that no matching prose exists in a
  semantic-line-break corpus.
- **Don't:** treat `scripts/find-near-duplicates.py`'s default no-finding result
  as proof a short copied passage is absent from long shared files.
- **Don't:** treat a high shingle score as the disposition; it is a pointer to
  read, not a duplicate verdict.

(Morrison-Lab/ai-config#969, 2026-08-01: after review flagged one uncited
copy between `batch-merge-and-resolve.md` and `sync-with-main.md`, a
10-gram shingle sweep normalized backticks, asterisks, underscores, whitespace,
and case across `shared/workflow/`, `shared/writing/`, and
`shared/principles/`.
It found four overlapping runs: the flagged generalization, a second uncited
copy about `markdownlint`'s `blanks-around-lists` explanation that review had
missed, and two already-cited overlaps.
A literal grep for the `blanks-around-lists` wording in `sync-with-main.md`
returned nothing because the phrase crossed a semantic line break.)
