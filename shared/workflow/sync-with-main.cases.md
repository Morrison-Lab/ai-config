# Case records: sync-with-main

Worked-example case records for the rules in
[`sync-with-main.md`](sync-with-main.md), moved here verbatim to keep them
out of the auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## A CI failure on a new PR's first commit can be `main` having moved

(`stack-prs` #359: an
empty-commit draft PR failed `validate` on a stale `codex-skills/` generated
tree, and the `require-changelog` job on a newly-added `CHANGELOG.md`
requirement from PR #354 --- both were `main` having advanced past a
checkout that predated the session, not a defect in the new skill.)

## A branch named after a PR's followup can predate that PR's merge

(`ai-config#637`: a worktree named `pr-636-followup-...` was cut from a
`main` snapshot that predated #636's own merge; an edit referencing "the
bullet above" -- added by #636 -- was written and committed before the
bullet actually existed on the branch, caught only when `git push` reported
`main has moved` and the subsequent merge produced a real conflict.)

## A conflict in a file whose logic is copied elsewhere needs the copy re-synced

(gha#176: `main` landed #173's lenient verdict-matching
fix to `claude-code-review.yml`'s inline fail-check logic while a PR extracting
that same logic to `scripts/check-review-execution.sh` was still open; the
conflict resolution updated the script to match verbatim and added two new
fixtures for #173's specific fix, verified to fail against the pre-fix logic.)

## When `main` deletes a file, grep the whole tree for the deleted path

(ai-config#696: `main` retired `scripts/check-new-line-breaks.py` via #703
while the PR was open. The `validate.yml` conflict was visible and
resolved, but `scripts/check-memory-file-size.py`'s docstring cited the
deleted script as its advisory-exit-code precedent --- a file the conflict
never touched, caught only by grepping for the path afterward.)

## A textual conflict in a skill file can signal a conceptual duplicate

(PR #352's `check-info-quality` landed alongside `#344`'s
independently-authored `fact-check-prose` this way --- distinct enough to
keep both, resolved by adding an explicit boundary in each skill's
Relationship section rather than consolidating.)

## The same collision can land before you write a line

(ai-config#774, 2026-07-28: a planned `profile-before-optimising` fragment
was mooted by `skills/measure-performance`, which merged via #762 during the
session and covered the same two chapters --- including the specific gap the
fragment was meant to fill.
It surfaced only because the new skill appeared in the session's skill list
after a routine fast-forward; the plan had been written before it existed.
Dropped before implementation, with the reasoning recorded in both the issue
and the PR body, and the neighbouring fragments cross-linked to the skill
instead.)

## A routine merge from `main` can create the duplicate inside your own diff

(Morrison-Lab/ai-config#969, 2026-08-01: #969 added
`shared/workflow/batch-merge-and-resolve.md` with a blockquote generalizing
that an added-lines-only instrument is unsound when a defect can be introduced
by deleting a line.
PR #966 independently added the same generalization to
`shared/workflow/sync-with-main.md` and merged after #969's branch was written.
`git show 50afe818:shared/workflow/sync-with-main.md`, normalized for
whitespace and markup, did not contain the phrase, so the duplication did not
exist at #969's pre-merge head.
The round-2 merge from `main` brought #966's copy in, and the round-3 review
correctly flagged the two uncited copies.)

## Two PRs appending a terminal numbered subsection collide on merge

(gha#211: `main` merged #209's own new
`### 5. Check for AI-generated prose tells` subsection between this PR's
clean review and its actual merge --- `git merge-tree` surfaced a real
conflict that neither PR's own CI nor review status had flagged, since
neither had rerun since `main` advanced.)

## Check other open PRs after merging an extraction

(gha#201 extracted
`claude-code-review.yml`'s `claude_args` block into a new
`run-claude-review-attempt` composite action to support a retry; gha#202,
open in parallel, edited that same inline block to allowlist `WebFetch`/
`Bash(curl:*)`. Proactively rebasing #202 and re-applying its allowlist
change to the new composite action --- rather than leaving its author to
discover a conflict --- let it merge within the hour instead of stalling.)

## An add/add conflict on a shared config file

(`Morrison-Lab/altdoc#7` vs `#18`: both independently added a `jarl.toml`
excluding the same fixture directory for the same `jarl-check` failure;
`#18` merged first, `#7`'s merge conflicted on the new file, resolved by
keeping `#18`'s more detailed comment and re-confirming `#7`'s diff against
`main` was back down to just its own four files. This same "append-collision"
pattern struck a third time one insertion point over: this bullet and the
two above it were each added by independent PRs landing in quick succession,
all appending after the same "PR #352's `check-info-quality`..." paragraph
--- resolved, per the guidance above, by keeping all three rather than
picking one.)

## A `dirty` `mergeable_state` can mean a sibling PR already closed the issue

(`ai-config#501`: issue #500
was independently resolved twice --- `#502` merged first, adding
`shared/writing/math-derivation-steps.md` and closing #500, but never wiring
it into `CLAUDE.md`; `#501` added a second copy of the same fragment plus the
missing `CLAUDE.md` wiring. Resolved by keeping `main`'s published fragment
and `#501`'s wiring, turning a `dirty` merge into a clean `+8/-0` diff.)

## A whole-file split can make files vanish from your diff

(Morrison-Lab/ai-config#966, merging `origin/main` after #973 landed as
`ea11bc9a`, hit `CONFLICT (add/add)` on `memories/github-mcp-tools.md`.
Both branches had split that file out of `memories/github.md`; the two split
versions were byte-identical apart from #966's own 49-line addition, so keeping
`origin/main:memories/github-mcp-tools.md` was correct.
The final PR diff collapsed from 13 files, 1093 insertions, and 661 deletions
to 8 files, 429 insertions, and 6 deletions.
Five files disappeared entirely:
`memories/claude-bot-workflows.md`, `memories/claude-code.md`,
`shared/workflow/efficient-pr-babysitting.md`,
`shared/workflow/fully-clean.md`, and
`skills/purge-hallucinations/SKILL.md`.
Each had contained only a cross-reference repointing from `memories/github.md`
to `memories/github-mcp-tools.md`, and
`git show origin/main:<file> | grep -c github-mcp-tools` returned `1` for each.)

## When the whole PR is superseded, close it rather than resolve it

(Morrison-Lab/ai-config#1188, 2026-08-06: an idle PR with a "Needs more work"
verdict, driven toward clean, revealed on merging `origin/main` that all four
of its `memories/preferences.md` bullets were already there in corrected form,
landed by the already-merged #1189; resolving toward `main` would have left an
empty diff, so the PR was superseded and the correct action was closure.)

## A merge into a growing numbered list can drop a heading's blank line

(gha#208: an out-of-band merge from
`main` --- done by a different session, not the one that opened the PR ---
landed a new item 7 directly against the PR's own item 6 with no blank
line; `lint-markdown`'s MD022 failed with no conflict marker anywhere in
the diff to point at.)

## The same splice happens to list items, where `markdownlint` stays green

(ucdavis/bcs#422/#430, 2026-07-26: a clean three-way merge spliced one PR's
`## Bug fixes` bullet against another's; the check above then found **four**
pre-existing instances in the same `NEWS.md`, in a repo that had no Markdown
linting at all.)

## Run the splice check as a whole-file count, before and after

(`ucdavis/bcs#534`, 2026-07-31: merging `main` spliced its `NEWS.md` bullet
directly beneath the branch's own with no blank line between.
markdownlint stayed green, since `blanks-around-lists` governs a list's
boundaries rather than the gaps between its items.
A pre-push check asking which flagged bullets were among the branch's added
lines returned 0 --- `git diff -U0 origin/main...1b74899d -- NEWS.md |
grep -c '^+\* Say that the'` --- and that zero was reported to the user as
"none of these are mine", which was false.
The count delta settles it: 14 spliced bullets on `origin/main`, 15 at
`1b74899d` after the merge, 14 again at `9f5dab34` after the fix.
Evidence filed on ucdavis/bcs#437; the `merge=union` driver proposed in
ucdavis/bcs#438 would raise this defect's rate, so it is explicitly blocked on
the detector landing first.)

## A commit claiming to have merged `main` can be lying

(`Lacaedemon/sparta#1070`, 2026-07-27: an automated PR-authoring agent pushed
two consecutive commits both titled "Resolve merge conflicts", each claiming
to have pulled `main`; both were single-parent commits that never touched
`main`'s actual current state, so the PR kept showing `CONFLICTING` no matter
how many times the agent "fixed" it. A real `git merge origin/main` --- the
first one actually run against this branch in three attempts --- surfaced
the genuine conflicts and resolved them for good.)
