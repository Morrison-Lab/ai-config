Whenever `main` has moved ahead of a PR branch you're working on, **merge
`main` into the PR branch** before the next push or review trigger. Don't wait
for a conflict to surface or for someone to ask.

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
the failure as something to fix in the diff. (`stack-prs` #359: an
empty-commit draft PR failed `validate` on a stale `codex-skills/` generated
tree, and the `require-changelog` job on a newly-added `CHANGELOG.md`
requirement from PR #354 --- both were `main` having advanced past a
checkout that predated the session, not a defect in the new skill.)

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
(`ai-config#637`: a worktree named `pr-636-followup-...` was cut from a
`main` snapshot that predated #636's own merge; an edit referencing "the
bullet above" -- added by #636 -- was written and committed before the
bullet actually existed on the branch, caught only when `git push` reported
`main has moved` and the subsequent merge produced a real conflict.)

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
fails, then restore). (gha#176: `main` landed #173's lenient verdict-matching
fix to `claude-code-review.yml`'s inline fail-check logic while a PR extracting
that same logic to `scripts/check-review-execution.sh` was still open; the
conflict resolution updated the script to match verbatim and added two new
fixtures for #173's specific fix, verified to fail against the pre-fix logic.)

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
(ai-config#696: `main` retired `scripts/check-new-line-breaks.py` via #703
while the PR was open. The `validate.yml` conflict was visible and
resolved, but `scripts/check-memory-file-size.py`'s docstring cited the
deleted script as its advisory-exit-code precedent --- a file the conflict
never touched, caught only by grepping for the path afterward.)

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
at merge time too. (PR #352's `check-info-quality` landed alongside `#344`'s
independently-authored `fact-check-prose` this way --- distinct enough to
keep both, resolved by adding an explicit boundary in each skill's
Relationship section rather than consolidating.)

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

Dropping the planned work is the cheap outcome, so record why in the issue
and the PR body rather than deleting it silently --- otherwise the next
person re-proposes it.
(ai-config#774, 2026-07-28: a planned `profile-before-optimising` fragment
was mooted by `skills/measure-performance`, which merged via #762 during the
session and covered the same two chapters --- including the specific gap the
fragment was meant to fill.
It surfaced only because the new skill appeared in the session's skill list
after a routine fast-forward; the plan had been written before it existed.
Dropped before implementation, with the reasoning recorded in both the issue
and the PR body, and the neighbouring fragments cross-linked to the skill
instead.)

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
CI run. (gha#211: `main` merged #209's own new
`### 5. Check for AI-generated prose tells` subsection between this PR's
clean review and its actual merge --- `git merge-tree` surfaced a real
conflict that neither PR's own CI nor review status had flagged, since
neither had rerun since `main` advanced.)

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
their branch and flag what you did in a PR comment. (gha#201 extracted
`claude-code-review.yml`'s `claude_args` block into a new
`run-claude-review-attempt` composite action to support a retry; gha#202,
open in parallel, edited that same inline block to allowlist `WebFetch`/
`Bash(curl:*)`. Proactively rebasing #202 and re-applying its allowlist
change to the new composite action --- rather than leaving its author to
discover a conflict --- let it merge within the hour instead of stalling.)

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
(`d-morrison/altdoc#7` vs `#18`: both independently added a `jarl.toml`
excluding the same fixture directory for the same `jarl-check` failure;
`#18` merged first, `#7`'s merge conflicted on the new file, resolved by
keeping `#18`'s more detailed comment and re-confirming `#7`'s diff against
`main` was back down to just its own four files. This same "append-collision"
pattern struck a third time one insertion point over: this bullet and the
two above it were each added by independent PRs landing in quick succession,
all appending after the same "PR #352's `check-info-quality`..." paragraph
--- resolved, per the guidance above, by keeping all three rather than
picking one.)

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
never did), rather than re-adding a second copy. (`ai-config#501`: issue #500
was independently resolved twice --- `#502` merged first, adding
`shared/writing/math-derivation-steps.md` and closing #500, but never wiring
it into `CLAUDE.md`; `#501` added a second copy of the same fragment plus the
missing `CLAUDE.md` wiring. Resolved by keeping `main`'s published fragment
and `#501`'s wiring, turning a `dirty` merge into a clean `+8/-0` diff.)

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
just after a merge with conflicts. (gha#208: an out-of-band merge from
`main` --- done by a different session, not the one that opened the PR ---
landed a new item 7 directly against the PR's own item 6 with no blank
line; `lint-markdown`'s MD022 failed with no conflict marker anywhere in
the diff to point at.)

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
(ucdavis/bcs#422/#430, 2026-07-26: a clean three-way merge spliced one PR's
`## Bug fixes` bullet against another's; the check above then found **four**
pre-existing instances in the same `NEWS.md`, in a repo that had no Markdown
linting at all.)

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
(`Lacaedemon/sparta#1070`, 2026-07-27: an automated PR-authoring agent pushed
two consecutive commits both titled "Resolve merge conflicts", each claiming
to have pulled `main`; both were single-parent commits that never touched
`main`'s actual current state, so the PR kept showing `CONFLICTING` no matter
how many times the agent "fixed" it. A real `git merge origin/main` --- the
first one actually run against this branch in three attempts --- surfaced
the genuine conflicts and resolved them for good.)
