Whenever `main` has moved ahead of a PR branch you're working on, **merge
`main` into the PR branch** before the next push or review trigger. Don't wait
for a conflict to surface or for someone to ask.

Worked-example case records for the rules below live in
[`sync-with-main.cases.md`](sync-with-main.cases.md), moved out of the auto-loaded context.

This fragment covers the single-branch-vs-`main` case. When orchestrating a
multi-agent `ultracode` session, merges can happen at more points than that —
see [`ultracode-merge-conflicts`](ultracode-merge-conflicts.md) for the
broader check (worktree-isolated agent branches, concurrent `parallel()`
results) and the note on GitHub's mergeable indicator not evaluating custom
`.gitattributes` merge drivers.

**Always check for merge conflicts with main before pushing results to remote.**
Run this before every push, not just before triggering a review:

```bash
git fetch origin main
git log --oneline ..origin/main | head    # any commits? main is ahead --- merge it in
git merge origin/main
```

If the push is rejected because `main` has moved (`! [rejected]` with
`(fetch first)` or `(non-fast-forward)`), fetch and merge before retrying --- don't
force-push.

Always do this before triggering a fresh review too, so the reviewer evaluates
the PR against current `main` rather than a stale snapshot.

Don't rebase or squash-rewrite a published PR branch unless explicitly asked ---
a merge commit is the right move because it matches GitHub's "Update branch"
button and preserves the PR history.

If the merge has conflicts, resolve them, run the project's standard pre-commit
checks (render / lint / spell / tests), commit, then push. Don't push a
half-resolved merge.

**A sync-only push invalidates the previous commit's review verdict --- never arm auto-merge after syncing.**
Merging `origin/main` in and pushing creates a new HEAD commit ref.
Even if the prior HEAD was verified 100% clean and the sync contained no changes of yours,
the new HEAD commit ref is unreviewed until fresh reviews land.
Arming `gh pr merge --auto` after a sync push risks merging the new HEAD as soon as CI passes
without any review at the new SHA ([Pattern 12](../../memories/mistake-patterns.md)).
Always wait for fresh reviews and CI on the new head,
re-verify with `check-pr-fully-clean.py`,
and merge directly/synchronously.

- **Do:** re-run verification on the new head after every sync push and merge directly once fully clean.
- **Don't:** arm `gh pr merge --auto` after syncing with `main` to avoid repeating the review wait.

**After merging main, re-check version parity.** In R packages with a
`version-check` CI job, the branch's `DESCRIPTION` `Version:` must *exceed*
main's. A conflict-free merge can silently put them at parity — main advanced
(e.g. another PR merged between when you last bumped and now). After every merge
of main, compare versions:

```bash
git fetch origin main
git show origin/main:DESCRIPTION | grep ^Version
grep ^Version DESCRIPTION
```

If they match, bump the branch's `Version:` by one patch level before pushing.

**Re-check `main` again right before the final push, not just at the start of
a merge.** Resolving a conflict (rerunning generators, fixing prose, updating
a CHANGELOG entry) can take long enough for `main` to advance a second time.
A `git fetch origin main` immediately before `git push` --- after conflict
resolution is done, not only before it started --- catches that case; an
earlier CI failure on a commit you thought was current is a symptom of
skipping this second check.

**A conflict-free merge does not mean derived artifacts are in sync.** If your
branch regenerates a generated tree (e.g. `codex-skills/`, a lockfile, rendered
docs) and `main` added a new *source* input the generator consumes (a new
skill, a new dependency), git merges both cleanly --- but the generator never
ran against the new input on your branch, so its output is missing or stale and
the sync check fails on `main` after both land. After merging `main`, re-run the
generator and commit the result whenever main touched the generator's inputs ---
don't trust the absence of conflicts. (Concretely: merge the PR that adds the
new skill *first*, then sync the wrapper-regenerating branch and rerun
`scripts/sync-codex-skill-wrappers.py` before merging it.)

**A CI failure on a brand-new PR's very first commit (e.g. the empty
claim-commit from `pr-on-claim`) is a signal to check `main`'s position
before debugging the failure itself.** A local checkout that sat around since
before the session started can already be many commits behind `main` --- the
failure (a stale generated-tree check, a check `main` has since added or
dropped) often isn't a real problem with your change at all, just `main`
having moved. `git fetch origin main && git log --oneline ..origin/main`
first; if `main` is ahead, merge it in and re-run the checks before treating
the failure as something to fix in the diff.

**The same staleness trap has a silent variant with no CI failure to flag
it: a worktree/branch named after a PR's followup can still be based on a
`main` from before that PR actually merged.** A worktree directory or
branch name suggesting "after PR #N" (e.g. `pr-N-followup-...`) is not
proof the branch's actual base commit postdates #N's merge --- it can have
been created earlier and simply named for its intended purpose. Trusting
that naming, then reasoning from `git show <hash>` for a commit found via
`git log --all` (which lists every reachable commit across all refs, not
just your branch's ancestry) can make content look present when it isn't
actually in your branch yet. Verify with `git log --oneline HEAD..origin/main`
or by reading the actual blob your branch would produce (`git show
HEAD:<path>`, or the working tree itself before assuming what it contains),
not a commit hash pulled from `--all`. If `main` has moved, merge it in
before building further edits on the assumption the missing content exists.

**A real conflict inside a file whose logic is also copied elsewhere (an
extracted script, a doc example) needs the copy re-synced too, not just the
conflicted file resolved.** When a PR extracts inline logic (e.g. a workflow
step's shell block) into a standalone script for testability, and `main`
independently changes that same inline logic while the PR is open, resolving
the merge conflict in the workflow file is not enough — the extracted script
must be updated to match `main`'s new logic exactly, or the PR silently
reverts `main`'s fix the moment it merges. Diff the extracted copy against
`main`'s current inline version line-for-line (strip indentation, `diff`) to
confirm an exact match, not just "looks about right." If the PR carries tests
against the extracted copy (fixtures, unit tests), add regression coverage for
whatever `main`'s change fixed — the merge is the natural moment to catch a
gap the original PR's tests didn't anticipate, and to prove the new fixtures
actually catch the regression (temporarily revert the fix, confirm the test
fails, then restore).

**When `main` DELETES a file your branch references, resolving the marked
conflict is not enough --- grep the whole tree for the deleted path.** Git
only conflicts where both sides edited the same lines, so a merge that
brings in a deletion flags the file that *used* the thing, and nothing
else. Any other reference to the deleted path --- a docstring citing it as
precedent, a comment, a doc cross-reference --- merges cleanly and silently
becomes a dangling reference, because those files were never in the
conflict's scope. After resolving any merge that removed a file, run
`grep -rn "<deleted-path>"` across the repo and re-point or reword each
hit; then distinguish live references (must be fixed) from historical
citations of the removal itself (correct as-is, leave them). This is the
deletion counterpart to the extracted-copy case above: there the logic
moved and a copy went stale, here it vanished and the pointers went dead.

**A textual conflict in a skill file can be the symptom of a conceptual
duplicate, not just competing edits to the same line.** When merging `main`
into a branch that's authoring a new skill, if the conflict lands in a
`## Relationship to other skills` section (or `main` added an entirely new
skill in the same territory), that's a signal to re-run `skill-builder`'s
Step 0 judgment --- not just resolve the diff mechanically. Compare the new
skill against whatever landed on `main`: are they the same concern (fold
into one, redirect), or genuinely distinct (cross-link both directions so
neither reads as an unexplained near-duplicate)? `skill-builder`'s
in-flight-work scan only runs once, at the start; `main` can grow a
colliding skill in the time a PR is open, so the check has to be repeated
at merge time too.

**The same collision can land before you write a line, and then it produces
no conflict at all --- just duplicated work nobody flags.**
The bullet above catches a duplicate at merge time, via a conflict.
When `main` gains the colliding content while your change is still *planned*
rather than written, there is nothing to conflict with: you write the
duplicate, push it, and the review has to argue you out of content that was
already redundant on arrival.
So re-run the dupe check after any fetch that brings in new commits, not
only at merge --- a plan researched an hour ago was researched against a
different `main`.

The cheap version is to read what actually arrived rather than only the
count: `git log --oneline <old>..origin/main` plus `git diff --stat` over
the same range, then ask whether any of it covers something still on your
list.
In a session that loads skills or plugins from the repo, a new one appearing
in the session's own skill listing is the same signal arriving for free.

This is a *timing* gap, and it composes with the *scope* gap rather than
replacing it.
[`check-open-prs-before-duplicating`](check-open-prs-before-duplicating.md)
covers work that is still in flight, unmerged, and therefore invisible to
any check against `main`; run that one too, since a duplicate is just as
wasted whether the collision has landed yet or not.
Both checks share the same weakness --- each runs once, at the start, and
answers for the moment it ran.

Dropping the planned work is the cheap outcome, so record why in the issue
and the PR body rather than deleting it silently --- otherwise the next
person re-proposes it.

**A routine merge from `main` can create the duplicate inside your own diff.**
The collision above lands before you write, so the duplicate is redundant on
arrival.
A later `main` merge is quieter: both branches were non-duplicative when they
were written, and the duplicate appears only when you bring the other branch's
text into yours.
Git reports a clean merge because the two copies sit in different files.
Diff-scoped added-line checks do not help either, because the duplicated lines
already existed on one side or the other.
So after merging `main` into a prose branch, run the duplicate check against
the branch's full current diff and the neighbouring corpus, not only against
lines added by the merge commit.

- **Do:** after a `main` merge, re-run a cross-file duplication check over the
  merged branch's whole prose diff.
- **Do:** treat a reviewer finding on such duplication as correct even when
  each copy was independently right before the merge.
- **Don't:** assume a conflict-free `main` merge preserved DRY, or that the
  duplicate would have appeared in an added-lines-only scan.
- **Don't:** answer by asking which branch "introduced" the duplication;
  the merge introduced the state that made both copies coexist.

**Two PRs that each append a new terminal numbered subsection to the same
file (e.g. `### 5. ...` in a `CLAUDE.md` review-guidelines list) will
conflict on merge even when neither side's content actually disagrees.**
This isn't an editorial clash --- it's two authors both writing to "the next
number" at the same insertion point. Resolve by keeping **both** additions
and renumbering sequentially from the collision point on, not by dropping
either side; then grep the file for any other place that names the old
numbering (a cross-reference, an index). This is also a reason
[`fully-clean`](fully-clean.md)'s CI-green-and-review-clean verdict is a
snapshot, not a mergeability guarantee --- `main` can pick up its own append
in the same spot after your last review round, so a PR can go from
"reviewed clean" to "needs a merge conflict resolved" with no defect in its
own diff. Before reporting a PR ready to merge, re-check with
`git fetch origin main` plus the `git merge-tree` command from
`resolve-conflicts`, not just a cached `mergeable` flag or an earlier green
CI run.

**After merging a PR that extracts an inline block into a reusable unit
(a composite action, a shared script/function), check other open PRs that
still edit that same inline block --- your merge just broke their textual
diff, even though their intended change is usually trivial to re-apply to
the new location.** This is the mirror image of the case above: there,
you're the one resyncing after `main` moved a copy of your logic; here,
*you* are the one who moved the logic, so the burden of noticing and fixing
the resulting conflict falls on you, not on the sibling PR's author waiting
to hit it. Don't wait for that PR's own merge/CI to surface the conflict ---
check every open PR touching the same file right after your extraction
merges: `git merge-tree "$(git merge-base origin/main origin/<sibling-branch>)" origin/main origin/<sibling-branch>`
(or `gh pr diff <N>` against the new `main`) shows whether it still applies
cleanly. Re-apply the
sibling PR's actual semantic change (not a mechanical `--theirs`) to the new
location, verify with a direct diff that the extracted unit now differs from
`main` by exactly that PR's intended change and nothing else, then push to
their branch and flag what you did in a PR comment.

See [`sync-with-main.cases.md`](sync-with-main.cases.md), "Check other open
PRs after merging an extraction".

**That "push to their branch" is scoped by standing, not only by cause.**
gha#201/#202 were CI workflow files in a repo the author drove, where a push
saves the sibling's author a round and risks nothing they were relying on.
The same push onto a branch you do not own --- a colleague's active work, and
most sharply a release branch carrying an out-of-band process --- can disrupt
something a comment would not.
There, name the extraction, the deletion, or the rename
and where the content went in a PR comment,
and leave the push to whoever owns the branch.
Causing the conflict obliges you to *surface* it.
It does not by itself license editing someone else's branch.
See [`batch-merge-and-resolve`](batch-merge-and-resolve.md),
"A conflict your sweep found is not a conflict your merge caused",
for the attribution step that says which conflicts are yours in the first
place.

**An add/add conflict on a *shared config file* usually means two PRs
independently fixed the same root cause --- reconcile the reasoning, don't
just pick a side.** This generalizes the skill-file case above beyond
skills: a repo-wide CI/lint/build config fix (a new tool config file, a
workflow tweak) is exactly the kind of change multiple sessions or bots are
likely to attempt in parallel once a check starts failing on `main` for
everyone. When the conflict is a whole-file add/add (not just competing
edits to an existing file), read both sides' reasoning --- code comments,
commit messages, the PR discussion --- before resolving; usually one side's
explanation is more complete (covers a case the other missed, cites the
tool's actual constraint) and should win outright rather than mechanically
merging fragments of both. Re-diff the PR against `origin/main` after
resolving to confirm the PR's remaining changes are its own original scope,
not a reintroduction of what the other, now-merged PR already added.

**A `dirty` `mergeable_state` on a bot-opened PR can mean a sibling PR already
closed the same issue, not just that `main` drifted.** An issue-triggered
`@claude` workflow can fire twice on the same issue in quick succession
(a duplicate dispatch, or two people independently routing the same request),
producing two independent PRs that both fully resolve it --- including adding
the identical new file. The second PR's merge conflict is an add/add on that
new file, and it looks like ordinary main-drift, but treating it that way and
mechanically resolving in favor of "ours" silently reintroduces a duplicate
the other PR's merge already published. Before resolving, check the PR's
linked issue for **other** cross-referenced PRs/closing events --- if one
already merged and closed it, diff the conflicting file against `main`: if
it's the sibling PR's already-published version, keep `main`'s content and
keep only this PR's genuinely distinct remainder (a piece the sibling PR
never did), rather than re-adding a second copy.

**The same parallel resolution can be a whole-file split, and then files can
vanish from your diff with no deletion hunk to read.**
The add/add and duplicate-issue cases above both say to keep `main` when a
sibling PR already published the same new file.
The split case adds a second check, because resolving the one conflict can also
make other files disappear from your PR's diff entirely.
Those files look harmlessly gone, and there is no deleted line for
[`ardi`](ardi.md)'s pre-push deletion sweep to inspect.
Two causes are indistinguishable from the final diff alone:
`main` absorbed your cross-reference edit, or the merge dropped your work.
So verify each vanished file against the pre-merge head before calling the
collapse correct.
For each file that left the diff, compare the original head against the
merge-base to recover what your branch intended, then confirm current `main`
now carries that same change.
Search `main`'s whole corpus for that change rather than the path it used to
live at: a sibling PR that relocated the content --- a companion-file split, a
rename, a section moved between files --- leaves it present but elsewhere, so a
path-scoped confirmation reports it missing and invites you to re-add a copy
`main` already has.
[`ardia`](../../skills/ardia/SKILL.md)'s `Superseded` terminal state carries
the measurement.
Only after that per-file check is it safe to treat the smaller diff as a
successful conflict resolution rather than as lost work.

- **Do:** save or read the original pre-merge head, list the files that left
  the PR diff after the merge, and verify each one's intended change is already
  on `main`.
- **Do:** keep `main`'s version for the overlapping split file when the sibling
  PR has already published the same refactor, then carry forward only this
  PR's distinct remainder.
- **Don't:** infer that a vanished file was safely absorbed merely because the
  final diff got smaller.
- **Don't:** rely on the deleted-lines sweep for this case; content that left
  the diff has no deletion hunk for that sweep to show.

**The same silent reversion happens one line at a time, and there the file
never vanishes from the diff at all.**
The bidirectional check above triggers on a *file* disappearing from the PR's
diff.
A merge can revert a single sentence inside a file that stays in the diff for
other reasons, and then nothing about the diff's shape changes to prompt a
look.
`main` resolves the conflicting region toward its own side, the branch's fix
is gone, and the restored text is byte-identical to `main`'s copy --- so
`git diff origin/main...HEAD` for that region shows **zero lines**, the same
as if the branch had never touched it.

This is the near-miss worth naming: reviewing the PR's diff against `main`
feels like reviewing what the merge did, and it is not.
The PR diff answers "how does the branch currently differ from `main`", and a
reverted line that now matches `main` again answers that question with
nothing, by construction.
The only comparison that can see the revert is the branch's own pre-merge tip
against the merge result --- a different diff than any ordinary review runs.

```bash
git diff <pre-merge-branch-tip> <merge-commit> -- <file>
```

A line that appears there as a **deletion**, with no corresponding line
re-added elsewhere in that hunk, is a fix the merge discarded.
"No conflict marker" says nothing about this case either: the region may
never have raised a `<<<<<<<` at all, since a merge is free to resolve a
three-way diff silently in favor of one side when git's own heuristics call it
unambiguous.

The general form is [`batch-merge-and-resolve`](batch-merge-and-resolve.md)'s
survival check, generalized past whole files: for every line the branch added
between the merge-base and its pre-merge tip, confirm that line --- not just
the file it lived in --- survives unchanged in the merge result.
A whole-file diff-stat delta cannot substitute, since the file's total line
count can be unchanged or even larger while one specific sentence inside it
was swapped back to `main`'s wording.

- **Do:** diff the branch's pre-merge tip against the merge commit, per file,
  and treat any line that appears only as a deletion there as a discarded fix.
- **Do:** run this check even when the file in question is still present and
  still shows other changes in the PR's diff against `main`.
- **Don't:** treat `git diff origin/main...HEAD` as evidence about what a
  merge did --- a reverted line that now matches `main` produces no diff
  there, which is exactly what makes the revert invisible.
- **Don't:** read "no conflict marker in this region" as evidence nothing was
  discarded; a silent three-way resolution needs no marker to still pick the
  wrong side.

(Morrison-Lab/ai-config#2243, 2026-08-25/26: commit `6a537734` fixed a
sentence in `CLAUDE.md` ("This webhook-driven loop never formally invokes..."
to "This subscription never formally invokes...").
The later merge of `main`, commit `061bffcc`, resolved that region toward
`main`'s side and restored the pre-fix wording verbatim, byte-identical to
`main`'s copy.
An adversarial re-review caught it only via
`git diff b42b344d 061bffcc -- CLAUDE.md`, the pre-merge-tip-to-merge-result
comparison above, and fixed it in `c0c658d2`.
Tracked as [ai-config#2374](https://github.com/Morrison-Lab/ai-config/issues/2374).)

**When the whole PR is superseded, not just one file, the conflict is telling
you to close it rather than resolve it.**
The two cases above keep `main`'s version of a file a sibling PR already
published, and carry forward the current PR's distinct remainder.
The remainder can be empty.
When a `main`-merge conflict pits *every* added line of an idle PR against a
better-formatted copy already on `main` --- a sibling PR having landed the same
content --- resolving toward `main` leaves nothing, and the PR's own prior
review findings are moot.
Confirm by grepping `origin/main` for the PR's distinctive added phrases before
resolving anything: all present means superseded.
The right action is then to recommend closing the PR, since its content is
preserved on `main`, not to push an empty diff to a clean verdict.
For an ARDIA sweep this is a terminal state of its own --- see
[`ardia`](../../skills/ardia/SKILL.md)'s `Superseded`, which also gives the
up-front check that catches it before rounds are spent.

**A merge into a growing numbered list (e.g. `gha`'s `CLAUDE.md` "Code
review guidelines" section) can produce zero blank lines between two
adjacent headings
even with no textual conflict --- lint catches it, git doesn't.** When a
section is a hotspot several PRs independently append items to (each PR
adding its own `### N.` block at the end), a clean three-way merge can
still splice one PR's closing line directly against the next PR's heading
with no blank line between them --- this doesn't produce a `<<<<<<<`
conflict marker (git resolves it as a straightforward insertion), so it's
easy to push without noticing. `markdownlint`'s MD022
(blanks-around-headings) is what actually catches it, as a CI failure with
no proximate code change to explain it. Re-run the repo's markdown lint (or
at minimum re-read the diff around every `### N.` boundary you didn't
personally write) after any merge that touches a shared growing list, not
just after a merge with conflicts.

**The same splice happens to LIST ITEMS, and there `markdownlint` most
likely does NOT catch it --- so nothing turns red at all.** The case above
is a heading spliced against preceding text, which MD022 decides. The
changelog case is a *bullet* spliced onto the previous item's continuation
line:

```markdown
  `data-raw/precompute-true-effects-chunk.R` (#429).
* The `docs` workflow's "Build site" step no longer times out intermittently.
```

That is a valid **tight** list item, so a list in which every other entry is
blank-line separated silently starts mixing tight and loose items and renders
inconsistently. `markdownlint`'s blanks-around-lists rule governs the
boundaries *of* a list, not the gaps *between* its items, and no default rule
enforces consistent looseness within one list --- so unlike the heading case,
CI stays green and only a human reading the merged section notices.

Check it mechanically instead of by eye; one line decides it:

```bash
awk 'prev !~ /^[[:space:]]*$/ && /^[*+\-] / {print FILENAME":"NR": "$0} {prev=$0}' NEWS.md
```

Use `[[:space:]]*` rather than a bare `/^$/` --- a whitespace-only preceding
line is not a violation and produces false positives.
The pattern `[*+\-]` covers all three common Markdown unordered-list markers;
`^\* ` alone would miss `-` and `+` bullets.

Two consequences. Run this after any merge into a changelog or other growing
bulleted list, alongside the heading check above. And note that a
`merge=union` driver on such a file (see
[`configure-gitattributes`](../../skills/configure-gitattributes/SKILL.md))
*increases* the rate of this defect, since union resolves an append collision
by keeping both sides with no conflict to review --- so confirm a detector is
wired into CI before enabling one, not after.

**Run that check as a whole-file count, and compare it before and after ---
scoping it to the lines you added cannot see this defect at all.**
The check above is the right instrument; the natural way to apply it is the
wrong one.
Having found the file's spliced bullets, the obvious next question is which of
them are yours, and the obvious way to answer is to intersect them with the
lines the branch added.
That question is unanswerable, because the defect is a **deleted blank line**
before a bullet that was already there.
The bullet is *context* in the diff, never an addition, so the intersection is
empty by construction and the check reports a confident zero.

Note how this differs from the scope failures elsewhere in this corpus, where
a check's **inputs** were too narrow --- a glob, a missing flag, a two-dot
range.
Here the inputs were right and the **question** was wrong, which no widening
fixes.
And it fails in the direction that reads as an all-clear, on the one file a
reviewer will not re-derive.

The sound form is a count delta over the whole file, which needs no judgment
about ownership and no diff at all:

```bash
git show origin/main:NEWS.md   | awk '...' | wc -l   # before
awk '...' NEWS.md              | wc -l               # after
```

A merge must not increase the count.
That is an [`algorithmatize-checks`](algorithmatize-checks.md) instrument in
the strict sense --- two integers decide it --- and it holds whoever authored
the surrounding lines.

Generalize past changelogs, because the property is about the defect rather
than the file: **when a defect can be introduced by deleting a line, any
instrument keyed on added lines is unsound.**
Ask instead whether a whole-file measurement got worse.
The version-parity rule above is the same shape --- a conflict-free merge
leaves the branch at parity with `main`, `version-check` goes red, and there is
nothing in the diff to point at --- which is why that rule is a direct
comparison of two `DESCRIPTION` versions rather than a diff inspection.

The shared trigger is the practical part: **a conflict-free merge is exactly
when nothing prompts anyone to look.** Both defects arrive through one, both
are invisible to diff-scoped checking, and the merge reports success.

- **Do:** measure the whole file before and after a merge, and treat any
  increase as the merge's fault regardless of who wrote the lines.
- **Do:** ask, of every diff-scoped check, whether the defect it targets could
  be caused by a deletion --- and replace it with a count if so.
- **Don't:** intersect a whole-file finding with the branch's added lines to
  decide ownership; for a deletion-caused defect that always returns zero.
- **Don't:** read a conflict-free merge as a merge that changed nothing beyond
  what the diff shows.

**A commit claiming "I've pulled main and resolved the merge conflicts" can be
lying --- verify it actually merged before trusting the claim.** A genuine
conflict-resolution commit is a merge commit (two
parents); a commit that just hand-edits files to *look* resolved, without
running a real `git merge`, is an ordinary single-parent commit --- and it
never actually incorporates whatever new state of `main` prompted the
"resolve conflicts" request in the first place. This is easy to miss because
GitHub's own `mergeable`/`mergeStateStatus` fields don't distinguish the two:
both look identical from the PR page until you check the commit graph.
Verify with `git show -s --format="%P" <commit>` --- one hash means no real
merge happened, regardless of what the commit message says. If a branch
needed conflict resolution more than once and each attempt claimed success
but the PR still shows `CONFLICTING`, check every "resolved conflicts" commit
in its history this way before trying yet another resolution attempt on top
of a foundation that was never actually re-merged.
