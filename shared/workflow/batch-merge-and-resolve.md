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

## Independent per-PR checking cannot see pair collisions

Every PR can be individually clean against `main` while two of them conflict
with each other.
No amount of per-PR diligence finds this, because the comparison that would
reveal it is never made: each PR is checked against the base, and never against
its siblings.

The collision surfaces at merge time, on whichever PR merges second, as a
conflict its author did not create and has no context for.

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

## Three silent failure modes arrive through a conflict-free merge

The reason "no conflict" is not an all-clear.
All three landed through merges that git resolved cleanly, with nothing in the
diff to point at and no check turning red.

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

**A threshold breach that exists only in the sum.**
A file under a size, count, or coverage cap can take an append from two branches
that each stay under it and land over it once both merge.
Neither branch is at fault, and neither branch's checks can see it: each PR
measures the file as it would exist with only its own change applied, so the
breach is a property of the **combination** rather than of any member.
This is also the one mode a pairwise `git merge-tree` sweep cannot find, since
appends at different points in a file produce no textual conflict at all --- so
the section above on pair collisions does not cover it.

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
[`fully-clean`](fully-clean.md) already owns the near half of this, in its case
covering a check "designed to NEVER fail regardless of their own posted
content, so their green color carries zero signal at all".
What the capped-file case adds is that the signal is not merely absent but
**misdirecting**: a second step enforces the same threshold, so the advisory
label is accurate about its own step and false about the job.

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
