When several open PRs need syncing or conflict resolution, do them **together in
one pass**, not one at a time as each conflict flag appears.
Batch merge and resolve is the default, not a special-case recovery for when
serial chasing has already failed.

Worked-example case records for the rules below live in
[`batch-merge-and-resolve.cases.md`](batch-merge-and-resolve.cases.md), moved out of the auto-loaded context.

This is a third merge topology, alongside the two the corpus already covers.
[`sync-with-main`](sync-with-main.md) is one branch against a moving `main`.
[`ultracode-merge-conflicts`](ultracode-merge-conflicts.md) is many merge points
inside one orchestrated session.
This fragment is the **queue**: N independently driven PRs against one base that
moves while you drive them.
The unit of analysis is the set, and several of the properties below exist only
at the set level --- they are invisible to any amount of care taken per PR.

## Why serial resolution structurally cannot converge

The argument is quantitative rather than a matter of taste, so measure it rather
than judging it.

Two intervals decide it:

- **The base branch's merge interval** --- how often `main` moves.
- **The review round** --- how long from your push to a posted verdict at that
  head, including CI.

When the merge interval is **shorter** than a review round, per-PR conflict
chasing is a treadmill by construction.
You merge `main` in, CI starts, and `main` moves again before the verdict lands,
so the PR is dirty again at the moment it would otherwise have been ready.
Each lap costs a full CI cycle and a review round and converges on nothing.
Nothing reports this, because every individual lap looks like progress.

Both numbers are one command each, which makes this an
[`algorithmatize-checks`](algorithmatize-checks.md) case rather than a judgment
call:

```bash
# Merge interval on the base branch, over the last N landings.
git fetch origin main -q
git log origin/main --first-parent -10 --format='%ct' |
  awk 'NR==1{hi=$1} {lo=$1; n++} END{printf "n=%d span=%.1f min mean=%.1f min\n",
       n, (hi-lo)/60, (hi-lo)/60/(n-1)}'

# Review-round duration: your push to the review check completing.
gh pr checks <N> --repo <owner>/<repo> --json name,startedAt,completedAt
```

**Count first-parent commits, not merge commits.**
`git log --merges` returns nothing at all in a squash-merging repo, so a merge
rate measured that way reads as zero and silently argues that serial chasing is
fine.

## A `DIRTY` flag has two meanings, and only one is a defect

This is the operative half of the rule, because it decides what you do next.

- **Stale.** The PR's own content is clean; `main` has moved underneath it.
  Nothing about the PR is wrong.
  Staleness is resolved **once, at merge time**, and resolving it earlier buys
  nothing that lasts.
- **Defective.** The PR's own change genuinely disagrees with something that
  landed --- it edits a passage `main` rewrote, or duplicates work that merged.
  This needs a human decision and does not resolve itself.

Serial chasing treats every flag as the second kind.
That is what makes it expensive: a stale PR re-synced eagerly spends a CI cycle
and a review round to reach a state that will expire again within one merge
interval.

Tell them apart by asking whether the conflicting hunks are yours.
A conflict confined to regions your branch never edited is staleness.
A conflict inside your own added lines is a real disagreement.

- **Do:** batch the stale ones and resolve them in a single pass close to when
  they will actually merge.
- **Do:** treat a conflict inside your own hunks as immediate ARDI work,
  separately from the batch.
- **Don't:** re-sync a PR the moment its flag flips, when the merge interval is
  shorter than the round that re-sync will trigger.
- **Don't:** read `DIRTY` as "this PR is broken" --- most of the time it is a
  statement about `main`, not about the PR.

## A conflict your sweep found is not a conflict your merge caused

The section above splits a `DIRTY` flag by whether the PR's own content is
wrong, which is a question about the PR.
There is a second question, about **you**: of the conflicts a post-merge sweep
turns up, only some were caused by the merge you just made.
The rest predate you --- a stale backlog collides on `DESCRIPTION`, a word
list, a directory deleted months ago --- and were conflicting before you
arrived.

Both axes are needed, because a conflict can be stale by that section's test
and still be yours.
Collapsing them prescribes one action for both, and on a repo whose PRs have
been open for months that means claiming and resolving other people's branches
for no reason.

Attribution is mechanical, and it runs **before** the claim rather than after.
Deletions and renames are what to intersect, because they are what breaks a
branch that still references the old path:

```bash
git diff --name-status -M "$merge^1" "$merge" | grep -E '^(D|R)'
```

A conflicting path in neither set is drift.
The intersection subtracts as well as adds, which is the half a detector cannot
supply: a PR conflicting on a *similarly named* file that some older commit
deleted is exonerated outright, not merely deprioritized.
Settle that with `git log --diff-filter=D -- <path>`, noting that a shallow
clone answers "never deleted" for anything removed before its window
([`memories/claude-code.md`](../../memories/claude-code.md)).

**`git show --name-status <merge>` prints no file list at all on a true
merge**, and it is the natural command to reach for here.
A true merge has two parents, and `git show` defaults to the combined (`--cc`)
diff, which omits any path matching some parent --- on a clean merge that is
every path, so it yields an empty attribution set.
Grepping that output for `^[ADMR]` then returns 3, because `Merge:`, `Author:`
and `Date:` each begin with one of those letters.
A squash merge is an ordinary single-parent commit and is diffed normally, so
`git show` would serve there.
That is the reason to standardize on the `git diff` form: it is correct under
both merge styles, and which style produced the commit in front of you is a
property of the repo's settings rather than of the commit.
So its empty answer and its broken answer look alike, per
[`fail-fast`](../principles/fail-fast.md).
Use the `git diff <merge>^1 <merge>` form above.

Then match the response to scope, not only to cause.
A conflict you caused on a PR that fails `memories/reviewing-prs.md`'s scope
test is a report to the user naming the deletion or rename and where the
content went, and the PR is left untouched: no comment, no push.
On a PR that passes the test, [`sync-with-main`](sync-with-main.md) does
prescribe pushing the re-applied change to the sibling branch, and that fits
a CI workflow in a repo you drive.
It does not fit a release branch carrying an out-of-band process a push can
disrupt, which gets the report instead however it scores on the test.

- **Do:** derive the merge's own deleted and renamed paths, and intersect them
  with each conflict before claiming anything.
- **Do:** report both counts --- conflicts found, and conflicts caused --- so
  the gap between them is visible rather than implied.
- **Do:** report to the user rather than push or comment when a conflict you
  caused sits on a PR that fails the scope test.
- **Don't:** read a post-merge sweep's hit list as your work queue; on an old
  backlog most of it predates your merge.
- **Don't:** derive that path set with `git show` --- it reports nothing for a
  true merge, and a naive grep of its header reports three phantom paths.
  It happens to work on a squash merge, which is what makes reaching for it
  unreliable rather than simply wrong.

## A stacked PR is the one conflict that intersection cannot attribute

The section above is right about drift and blind in exactly one case, and it
is the case where the merge is unambiguously at fault.
A PR **stacked** on the PR you just merged conflicts on the paths that merge
**modified and added**, never on the ones it deleted or renamed.
So the intersection comes back empty, the rule reports drift, and the one hit
in the sweep your merge definitely caused is the one it tells you to skip.

The mechanism is the squash.
A squash merge writes a single new commit on the base branch, so the merged
PR's own branch commits never become ancestors of it.
A PR stacked on that branch therefore keeps its old merge base, and its diff
re-shows the merged content as though it were new.
Nothing in that requires a deletion or a rename, which is why a
deleted-or-renamed path set is the wrong instrument for it.

**The pre-merge check already exists and is scoped to the wrong trigger.**
[`memories/git-branches.md`](../../memories/git-branches.md) and
[`stack-prs`](../../skills/stack-prs/SKILL.md) both prescribe
`gh pr list --base <branch>` before merging, and both gate it on
`gh pr merge --delete-branch`, whose harm is the dependent PR being
auto-**closed**.
A plain squash merge passes no such flag, so neither rule fires, and the
dependent is orphaned regardless.
Omitting the flag does not help either in a repo that deletes merged head
branches on its own, since the branch goes away whatever you passed.

**The asymmetry is what makes this a rule rather than a call for more care.**
The merging party holds the information and pays none of the cost: the
dependent declares the dependency in its own body, and its base ref names the
branch.
The dependent's owner pays all of it and cannot prevent it.
`CLAUDE.md`'s three merge-order surfaces all sit on the **dependent** PR, so
not one of them is visible from the PR being merged.

So run the base query before **any** merge rather than before a
`--delete-branch` one, and treat a conflicting PR whose base was your merged
branch as caused by you whatever the intersection says.
[`cascade`](../../skills/cascade/SKILL.md) is the remediation once it has
happened.

**This is the merging party's half of a mechanism the corpus already covers
from the other side.**
[`use-existing-pr-branch`](use-existing-pr-branch.md)'s "A stacked PR reaches
that bloated state with no push of yours at all" section describes the same
squash-and-retarget from inside the **dependent** PR's own session, and owns
the recovery: read the diff and commit counts rather than resolving the
conflicts, since re-litigating already-merged content is what the apparent
conflict invites.
Neither section subsumes the other, and the split is the point --- one is a
pre-merge obligation on a party who will never see the symptom, the other is a
post-hoc recovery by the party who does.
Read that section when a PR of yours goes dirty for no reason you can find, and
this one before merging anything.

- **Do:** run `gh pr list --base <branch>` before merging any PR, not only one
  you are about to merge with `--delete-branch`.
- **Do:** exempt a PR stacked on your merged branch from the deleted-or-renamed
  intersection, since a squash orphans it without deleting anything.
- **Don't:** read an empty intersection as drift when the conflicting PR's base
  was the branch you just merged.
- **Don't:** rely on the merge-order surfaces to warn you --- every one of them
  sits on the dependent PR, which the merging party is not reading.

(Morrison-Lab/ai-config, 2026-08-16: PR #1504 was squash-merged as `41d82611`
with no check for dependents.
PR #1507 was stacked on its branch and said so in its own body.
The squash left `git merge-base --is-ancestor` reporting `#1504`'s branch tip
as unreachable from `main`, so `#1507`'s merge base stayed at `4a1e317b`, and
`git merge-tree` over that base reported 10 conflict markers where it had
reported none.
The attribution set is what settles the rule:
`git diff --name-status -M 41d82611^ 41d82611 | grep -E '^(D|R)' | wc -l`
returns 0, while `#1507` conflicts on `README.md`,
`scripts/check-hook-catalog.py`, and `scripts/test_check_hook_catalog.py` ---
paths that squash recorded as `M`, `A`, and `A`.
The remedy the existing rules prescribe was also inoperative: five of five
recently merged head branches whose PRs had closed were gone from
`git ls-remote --heads origin`, the sixth surviving only because an open PR
still used it, so this repo deletes merged head branches whatever
`--delete-branch` says.
The dependent was retargeted rather than closed, so the harm was the orphaned
base rather than the closure the existing rules guard against.)

## Independent per-PR checking cannot see pair collisions

Every PR can be individually clean against `main` while two of them conflict
with each other.
No amount of per-PR diligence finds this, because the comparison that would
reveal it is never made: each PR is checked against the base, and never against
its siblings.

The collision surfaces at merge time, on whichever PR merges second, as a
conflict its author did not create and has no context for.

### Start with the file-set sweep, then merge-tree what it flags

`scripts/pr-overlap.py` is this section's deterministic half.
It derives the open-PR set live for one or more repos and reports every pair sharing at least one file, alongside the number of pairs it examined:

```bash
python3 scripts/pr-overlap.py -R <owner>/<repo>
python3 scripts/pr-overlap.py -R <owner>/<repo> --strict --json
```

The two instruments answer different questions, and the file-set one is the cheaper and wider of the pair, so it goes first.
It flags many pairs `merge-tree` would call clean, since two PRs editing distant parts of one file share the file and still merge without conflict.
Run `merge-tree` on the flagged pairs to find which of them actually conflict.

Wider is not the same as a **superset**, though, and treating it as one would license stopping at whatever the sweep flagged.
A rename is the counterexample: GitHub's GraphQL API reports a renamed file by its new path only, so a PR renaming `foo.yml` and a PR still editing `foo.yml` would intersect empty while conflicting at merge time.
`pr-overlap.py` folds the pre-rename path back in from REST for exactly that reason, and a hand-run `gh pr diff --name-only` comparison does not.

One collision runs the other way, and is the reason the file-set sweep is not merely a cheap approximation of the conflict scan.
**Identical file sets** are often one change implemented twice, and when they are, both sides carry the same content and merge cleanly, so no conflict scan can see them at all.
Confirm the contents match before treating such a pair as a duplicate, since set equality is not content equality: two PRs editing the same two files differently have an identical file set and genuinely conflict.
That is why the script reports identical sets separately from partial overlaps rather than folding them together.

**When neither instrument is available, the fallback's *range* decides whether the intersection means anything, and the wrong one inflates it silently.**
`pr-overlap.py` needs `gh`, and so does the `gh pr diff --name-only` fallback beside it, so a session without `gh` reaches for raw git and has to pick a range.
`git diff --name-only <yours>..origin/main` is the natural-looking choice and is wrong: a two-tip comparison reports every file the two tips differ in, which includes **your own** changed files.
The intersection then comes back containing your entire file set, and the reading it invites --- that the base collides with everything you touched --- is the opposite of the truth, since those files are yours and the base has not touched them at all.

The failure direction is what makes it worth a rule.
An inflated intersection manufactures a merge-order constraint that does not exist, which `CLAUDE.md`'s "Surface merge-order constraints" section would then have you announce, draft-gate, or sequence around.
It is also self-corroborating: the paths it lists are real, they are genuinely in your diff, and every one of them checks out individually.

Take the other side's file list from the commits themselves --- `git show --name-only --format= <sha>`, or `git diff --name-only <base>...<head>` with three dots --- so the set is what that side changed rather than what the two tips differ in.
See [`git-diffing.md`](../../memories/git-diffing.md)'s "Picking the diff range" section for why the two-dot form behaves this way.

The zero this produces still needs the control the "Any conflict sweep needs a negative control" section below requires, and the wrong query above is **not** that control.
Swapping the query changes the input list, so its non-zero says nothing about whether the *correct* query can find a collision --- if the correct query returned empty for an unrelated reason (a mistyped SHA, a dropped `--format=`, a base that advanced by more than the one commit you looked at), the wrong query still returns your whole file set and still reads as discriminating.

Run the **correct** query against a base commit you already know touches one of your files, and confirm it comes back non-empty:

```bash
git diff --name-only origin/main...HEAD | sort > /tmp/mine.txt
git show --name-only --format= <known-colliding-sha> | sort > /tmp/known.txt
comm -12 /tmp/known.txt /tmp/mine.txt      # must be NON-empty
git show --name-only --format= <the-sha-you-care-about> | sort > /tmp/theirs.txt
comm -12 /tmp/theirs.txt /tmp/mine.txt     # the real question
```

The known-colliding SHA is usually free: any earlier commit on the base that touched a file this branch also touches will do.

- **Do:** derive each side's file list from that side's own commits, with `git show --name-only` or a three-dot range.
- **Do:** treat an intersection that contains your whole file set as a wrong-range symptom, not as a finding.
- **Don't:** use `git diff --name-only A..B` to derive a file-set intersection --- two-tip output carries your own files.
- **Don't:** announce a merge-order constraint off an intersection whose query has not been shown to find a collision it should find.
- **Don't:** treat the wrong query's large answer as a control --- a control varies the *input*, not the method, or it cannot tell a working query from a silently empty one.

(Measured 2026-08-28 while checking [ai-config#2529](https://github.com/Morrison-Lab/ai-config/pull/2529) against a `main` that had advanced by one commit.
The two-dot query returned all 9 of the PR's own files;
`git show --name-only` on the advancing commit returned its 2, and the intersection was empty.)

The script's own boundary is the one `CLAUDE.md`'s merge-order section already states, and it prints it on every run rather than only when it finds something.
An intersection sees **collisions** and never **dependencies**, so a PR asserting something another PR makes true is reported clean by construction.
A zero from it is not a merge-order all-clear.

Sweep the pairs directly:

```bash
git fetch origin "+refs/pull/*/head:refs/sweep/pr/*" -q
base="$(git merge-base refs/sweep/pr/<a> refs/sweep/pr/<b>)"
git merge-tree "$base" refs/sweep/pr/<a> refs/sweep/pr/<b>
```

Two mechanical facts about that command, both of which produce a confident false
all-clear if you do not know them:

- **The legacy three-arg form always exits 0**, whatever it finds.
  Keying a sweep on its exit status reports every pair clean.
  `git merge-tree --write-tree` does report conflicts by exit status, but it
  does not exist before git 2.38, and older git rejects the flag with **129**.
  Which direction that fails in depends on how the sweep reads the command.
  An exit-status sweep testing for non-zero reads 129 as a conflict on *every*
  pair, so it fails loudly and gets noticed.
  The grep form below fails quietly instead: the rejection goes to stderr and
  leaves stdout **empty**, so `grep -c` returns 0 and every pair reads clean.
  (Measured on git 2.53.0 against a known-conflicting pair: the legacy
  three-arg form exits 0, `--write-tree` exits 1, and an unknown flag exits 129
  having written nothing at all to stdout.)
- **Its conflict markers sit inside a unified-diff body**, so they are indented
  by the diff's own leading character.
  `grep -c '^<<<<<<<'` returns 0 on a genuine conflict.
  Match unanchored.

Check the git version before choosing the form, and grep rather than trusting a
status:

```bash
git merge-tree "$base" "$a" "$b" | grep -c '<<<<<<< '
```

**The two forms carry opposite signals, so pairing one form's command with the
other's test is a third way to a false all-clear --- and the likeliest one,
because each half is separately recommended.**
The bullets above establish that the legacy form needs the grep and
`--write-tree` needs the exit status.
Neither says what happens when they are crossed, and crossing them is the
natural mistake: `--write-tree` is what
[`resolve-conflicts`](../../skills/resolve-conflicts/SKILL.md),
[`ardi`](../../skills/ardi/SKILL.md), [`post-merge`](../../skills/post-merge/SKILL.md), and
[`wrap-up`](../../skills/wrap-up/SKILL.md) all reach for, while the grep is
what this fragment prints.

`--write-tree` emits **no `<<<<<<<` markers at all**.
On a conflict it writes the tree OID, the stage entries, and a
`CONFLICT (content): Merge conflict in <path>` line, so the marker grep returns
0 whether or not anything conflicted, and the unanchored-match fix above does
not help --- there is nothing to match.
The mirror error is equally quiet: the legacy form's status is always 0, so an
`rc`-keyed sweep over it reports every pair clean.

Pick one form and use its own test:

```bash
git merge-tree --write-tree "$a" "$b" >/dev/null 2>&1; echo "rc=$?"   # rc IS the signal
git merge-tree "$base" "$a" "$b" | grep -c '<<<<<<< '                 # grep IS the signal
```

If you must grep `--write-tree`, match `^CONFLICT` rather than a marker.

- **Do:** state which form a sweep used, next to the test it keyed on.
- **Don't:** grep `--write-tree` output for conflict markers, or read the
  legacy form's exit status --- each returns the clean answer unconditionally.

(Measured on git 2.50.1 against a two-commit synthetic conflict:
`--write-tree` exits 1 and prints a tree OID, three stage entries, and
`CONFLICT (content): Merge conflict in f.txt`, with zero `<<<<<<<` occurrences.
The legacy three-arg form on the same pair exits 0 and prints
`+<<<<<<< .our` --- diff-indented, as the bullet above says.
Hit live during a `post-merge` cascade scan on `ucdavis/bcs#536`, where a
`--write-tree` sweep reported `conflict_markers=0` for both open PRs; a
negative control against a known-conflicting pair is what exposed the grep as
vacuous, and the PRs happened to be genuinely clean.)

## Any conflict sweep needs a negative control

A matrix of zeros is indistinguishable from a detector that never ran.
This is not a hypothetical: all three failure modes above produce exactly that
matrix, and each looks like good news arriving from a real command.

So before trusting any zero, run the sweep against a pair you already know
conflicts, and confirm it reports the conflict.
Run the control **first**, not as a postscript, so a broken detector is caught
before its output has been read as a result.
Pair it with a known-clean control (a ref against itself) so the detector is
pinned in both directions.

**The known-clean half cannot stand in for the known-conflicting half, and it
is the one you will reach for**, since it needs no second branch and no prior
knowledge of anything that conflicts.
A ref merged against itself is clean by construction, so that control passes
whether the detector works or not.
That makes it the perfect impostor: it runs the real command, against real
refs, and returns exactly the clean result a working detector would --- so
running it alone produces the feeling of having controlled the instrument while
establishing nothing, which is the state this section exists to prevent.
Only a pair you know conflicts can show the detector is capable of reporting
one at all.

Report what the sweep **examined**, not only what it concluded.
`0 conflicts` is meaningless without `of N pairs examined`, and the count is
what distinguishes a clean queue from an empty loop.
Per [`fail-fast`](../principles/fail-fast.md), a check whose failure path and
whose pass path print the same thing is not yet a check.

- **Do:** run a known-conflicting pair through the detector before believing any
  zero it produces.
- **Do:** treat the self-merge as the optional second half of the control
  rather than the first, and say which halves you ran.
- **Do:** print the number of pairs examined alongside the number that
  conflicted.
- **Don't:** count a ref-against-itself run as having validated the detector
  --- it is the one input that cannot fail.
- **Don't:** key a `merge-tree` sweep on exit status --- the legacy form's status
  carries no information, and a rejected flag looks the same as a clean merge.
- **Don't:** report a zero matrix as "no collisions" when nothing established
  that the detector can produce a non-zero.

### A merge-simulation content check needs the same control, in a different shape

The section above validates a *conflict detector's* zero.
The same gap opens one step later,
when the question is no longer "did this pair conflict"
but "did the merge preserve a specific correction":
a scratch-merged result is checked for whether an earlier fix survived,
before that result is trusted enough to squash-merge a real PR.

A grep for the text a correction **removed** returns `0`,
and that `0` reads as "the correction is intact".
That grep is not the presence check the claim needs.
Absence of the old sentence is equally consistent with two different merges:
one where the fix survived,
and one where the whole passage, fix included, was dropped or never merged in.
An absence check cannot tell those two merges apart,
for the same reason the matrix of zeros above cannot tell a clean sweep from a detector that never ran:
the absence check was never confirmed capable of producing a non-zero.

The positive control here is not a known-conflicting pair,
since no conflict detector is in play.
The positive control is a grep for text the correction **added**.
A non-zero hit on the merged result confirms the replacement text is present,
and the absence check alone never confirms that.

- **Do:** pair every absence grep on a merge result (for text a correction removed)
  with a presence grep (for text that correction added),
  and require both to read as expected before trusting the merge.
- **Don't:** squash-merge on the strength of a zero count on removed text alone;
  that zero is equally consistent with the correction never having landed.

(Measured 2026-09-02 on `Morrison-Lab/ai-config`.
[#3029](https://github.com/Morrison-Lab/ai-config/pull/3029) was about to be squash-merged,
and its base predated the mid-file correction
[#3036](https://github.com/Morrison-Lab/ai-config/pull/3036) had made to `shared/workflow/pr-on-claim.md`.
A scratch worktree merged `origin/main`,
then [#3010](https://github.com/Morrison-Lab/ai-config/pull/3010), another PR queued for merge that day,
then [#3029](https://github.com/Morrison-Lab/ai-config/pull/3029),
and the session grepped the result for the sentence [#3036](https://github.com/Morrison-Lab/ai-config/pull/3036) had removed.
The count was `0`,
and the session read that as "correction intact".
A peer session pointed out that `0` is an absence check
and cannot distinguish "correction intact" from "whole passage dropped by the merge".
The positive control, a grep for "read a non-empty two-dot", the phrase [#3036](https://github.com/Morrison-Lab/ai-config/pull/3036) added,
returned `1` on the same scratch merge result.
That `1` is what confirmed the fix survived.)

## A `merge=union` driver makes the batch pass more necessary, not less

[`configure-gitattributes`](../../skills/configure-gitattributes/SKILL.md)
recommends `merge=union` for append-only log files, and it does prevent
conflicts.
Read that as a change in *where the cost lands*, not as a reduction in it.
Union resolves an append collision by keeping both sides, with **no conflict
raised and therefore nothing to review**.

So a union-attributed file raises the rate of silent defects exactly as it
lowers the rate of visible ones.
A queue whose changelog is union-merged will show fewer dirty flags and carry
more unreviewed splices, which is the opposite of what the quiet flags suggest.
Note also that GitHub's own mergeable indicator does not evaluate merge drivers
at all, so the platform's flag and a real local merge can disagree in either
direction --- see
[`ultracode-merge-conflicts`](ultracode-merge-conflicts.md), which owns that
fact.

## Five silent failure modes arrive through a merge nothing flags

The reason "no conflict" is not an all-clear.
All five landed through merges that left nothing in the PR diff to point at and no check turning red --- four through merges git resolved cleanly, and one through a marked conflict resolved the wrong way.

**Version parity.**
A clean merge of `main` can leave an R package's `DESCRIPTION` `Version:` at
*parity* with `main` rather than exceeding it, which is what `version-check`
requires.
There is no conflict, because neither side edited the other's line --- `main`
simply caught up.
Compare the two directly after every merge, per
[`sync-with-main`](sync-with-main.md)'s own version-parity rule.

**List-item splices.**
A clean merge can splice two Markdown bullets together by collapsing the blank
line between them.
Git resolves it as an ordinary insertion, and nothing turns red: as
[`sync-with-main`](sync-with-main.md) explains in the section that owns this
defect, `markdownlint`'s `blanks-around-lists` governs a list's **boundaries**
rather than the gaps **between** its items.
The result is a valid tight item that renders inconsistently beside its loose
neighbours.

**A branch-side fix, reverted line by line.**
A merge of `main` can restore a line the branch had deliberately changed, discarding the branch's fix.
In the measured case the region raised a real conflict marker and the manual resolution picked `main`'s side;
git's own heuristics can also resolve such a region cleanly, with no marker at all, when only one side appears to have changed it.
Either way the reversion is invisible afterwards: because the restored text is byte-identical to `main`'s copy, the reverted line produces zero diff against `main` and an ordinary PR-diff review cannot see it.
[`sync-with-main`](sync-with-main.md)'s "The same silent reversion happens one line at a time" section owns this case, including the pre-merge-tip-to-merge comparison that is the only check able to see it.

**A threshold breach that exists only in the sum.**
A file under a size, count, or coverage cap can take an append from two branches
that each stay under it and land over it once both merge.
Neither branch is at fault, and neither branch's checks can see it: each PR
measures the file as it would exist with only its own change applied, so the
breach is a property of the **combination** rather than of any member.
A pairwise `git merge-tree` sweep cannot find this either, since appends at different points in a file produce no textual conflict at all --- it shares that property with the identical-file-set duplicate described above.
The **file-set** half of the pair-collision section does flag the shared path, which is the cue to run the arithmetic below on it.
What no conflict scan above will report is the breach itself.

The instrument is arithmetic over three refs rather than a conflict scan:

```bash
lines() { git show "$1:$2" | wc -l; }
base="$(git merge-base "$a" "$b")"
echo $(( $(lines "$a" "$f") + $(lines "$b" "$f") - $(lines "$base" "$f") ))
```

Compare that projection against the cap **before merging either**, and note it
survives no reordering: both orders reach the same total, so this is not a
merge-order constraint that sequencing fixes.
One branch has to relocate its content, or the file has to be split first.

Two things make it worth checking rather than trusting CI.
The breach lands on `main`, so it goes red for **everyone** afterwards rather
than for whoever caused it.
And the step that enforces a cap is not reliably the one named for it: a step
labelled advisory may genuinely exit 0 while a self-test inside that same
check's **test suite** asserts the real corpus complies and gates the job.
Grepping a workflow for what enforces a threshold can therefore find the
advisory step and conclude wrongly.
[`review-verdict-pitfalls`](review-verdict-pitfalls.md) already owns the near
half of this, in its case covering a check "designed to NEVER fail regardless
of their own posted content, so their green color carries zero signal at
all".
What the capped-file case adds is that the signal is not merely absent but
**misdirecting**: a second step enforces the same threshold, so the advisory
label is accurate about its own step and false about the job.

**Clean auto-merge of independently grown logic (fail-open union).**
A merge uniting two independently developed versions of a file can be resolved
cleanly by git with zero textual conflicts, yet combine mechanisms that interact
pathologically or open silent loopholes.
Because git merges non-overlapping regions automatically, neither side's test
suite tests the cross-terms or combinations of both feature sets.
The resulting file passes both suites while failing open on inputs neither
side considered.
(Measured on PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736):
merge `80398b90` auto-merged `scripts/check-pr-fully-clean.py` with zero conflicts
--- 359 lines from `main`, 109 from the branch --- yet the post-merge adversarial
review of the cleanly merged files (`scripts/check-pr-fully-clean.py` and
`scripts/pre-push-review.py`, commit `cea1a533`) returned five fail-opens across the
newly combined review-matching, payload-extraction, and disclosure-footer mechanisms.
See Pattern 28 in [`mistake-patterns.md`](../../memories/mistake-patterns.md).)

### The instrument lesson, which is the transferable part

A check keyed on **added lines** is blind to the splice by construction.
The defect is a *deleted* blank line, and the bullet itself is unchanged --- it
appears in the diff as context, not as an addition.
So the whole family of diff-scoped, added-line checks this corpus relies on
cannot see it, however carefully they are written.

[`sync-with-main`](sync-with-main.md) states the generalization this case fits,
and owns it:

> when a defect can be introduced by **deleting** a line, any instrument keyed
> on added lines is unsound.

Quoted rather than pointed at because the count-delta instrument below is
unreadable without it.

The working instrument is a **count delta**: a merge must not increase the
number of spliced bullets.
The predicate itself is [`sync-with-main`](sync-with-main.md)'s own splice
detector, reused unchanged; only the count-delta framing around it is new.

```bash
splices() { awk 'prev !~ /^[[:space:]]*$/ && /^[*+-] / {n++} {prev=$0} END{print n+0}' "$1"; }
before="$(git show HEAD:path/to/file.md | splices /dev/stdin)"
git merge origin/main
after="$(splices path/to/file.md)"
[ "$after" -le "$before" ] || echo "merge introduced $((after - before)) splice(s)"
```

The delta form matters because the **absolute** count is unusable here.
That predicate flags every second-and-later bullet of a deliberately tight list,
and this corpus writes tight lists constantly --- every Do/Don't block is one ---
so its absolute count is mostly false positives.
Measured on this repo's own `CLAUDE.md` at `8923d068`: **57 hits, none of them
splices**, which is why the level is worthless and the delta is not.
Taking the difference across the merge cancels the baseline, whatever it is, and
leaves only what the merge changed.
That is the general escape from a noisy predicate: a detector too imprecise to
report a *level* can still be sound reporting a *change*, provided the same
predicate runs on both sides.

- **Do:** re-check version parity and run a splice-count delta after any merge
  that git resolved without conflict.
- **Do:** write adversarial tests against the union of independently grown logic
  even when git auto-merges with zero conflicts.
- **Do:** convert a noisy absolute-count check into a before/after delta rather
  than discarding it.
- **Do:** project a capped quantity as `a + b - base` across every pair of open
  branches that append to the same file, before merging either.
- **Don't:** treat "no conflict" as an all-clear --- the defects in this section
  arrive *through* clean merges, not around them.
- **Don't:** rely on an added-line-scoped check to catch a defect whose cause is
  a deleted line.
- **Don't:** read two green PRs as evidence their merge is green, or reach for a
  merge order to fix a breach that both orders reach.

## The batch pass

1. **Measure the two intervals** above, once, and say which is larger.
2. **Fetch every open head** and sweep, with the negative control first ---
   each head against the base, then the pairs.
3. **Classify each flag** as stale or defective, and act only on the defective
   ones individually.
4. **Resolve the stale ones together**, in one pass, ordered so that a PR another
   PR collides with goes first.
5. **Re-check the silent modes** on every merge the sweep produced, since none of
   them raise a conflict.
6. **Report what was examined**, not only what was found.

Stacking is the structural alternative when two PRs genuinely depend on each
other rather than merely colliding --- see
[`stack-dont-pause`](stack-dont-pause.md), which keeps the queue moving without
waiting for a human merge.
For repositories with strict branch protection,
enabling a platform merge queue ([`merge-queue`](merge-queue.md))
eliminates the need for manual batch chasing altogether by speculatively testing queued PRs on the forge side.
