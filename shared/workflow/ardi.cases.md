# Case records: ardi

Worked-example case records for the rules in
[`ardi.md`](ardi.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## A clean verdict does not certify what you meant

(Morrison-Lab/ai-config#922, 2026-07-30: a replacement string written to add
one block silently dropped the three `Do`/`Don't` bullets belonging to the
entry above it, leaving that entry with prose and a case record but no
labelled pair --- which `CLAUDE.md`'s "Record both the pattern and the
anti-pattern" specifically asks for.
`claude-review` returned Ready for merge, analysed all three deletions, and
concluded they were "appropriate", reasoning that two restated surviving
prose and the third was superseded.
The third point was right and the other two were not; the bullets were
restored, one reworded, and the deletion count fell from seven lines to two.)

## Regex/string patches can silently over-delete

(Morrison-Lab/ai-config#1167, round 12, 2026-08-05: a `re.sub` DOTALL patch to
`scripts/check-pr-fully-clean.py`'s second `for r in reviews:` loop anchored on
that same text, which also opens an earlier `author_latest_state` loop, so the
match ran from the first occurrence and deleted both it and the intervening
`for c in comments:` loop.
The self-check `src.count('all_items.append(("review"') == 1` passed anyway,
because the lost comment-append and the one added review-append balanced, and
an `is_review_header == 0` check passed because both loops that used it were
gone.
Reading `git diff` before committing surfaced the deletion; the fix reverted
and redid it with the Edit tool plus survival assertions, verified by a
negative control.)

## A clean verdict doesn't discharge self-review against conventions

(Morrison-Lab/ai-config#965 at `b85941c`, 2026-07-31: a diagnostic block ran
both `git merge-base --is-ancestor HEAD origin/main` and
`git rev-list --count origin/main..HEAD`, where `CLAUDE.md`'s `wrap-up`-sweep
section says verbatim to "resist adding an ancestry check beside the first of
those", since the two confirm one thing twice rather than two things once.
`claude-review` returned Ready for merge, called the pair "logically
equivalent (both express `HEAD <= origin/main` in ancestry)", judged that
"presenting both is reasonable as belt-and-suspenders for a diagnostic
block", and closed the item "Not a finding"; a second reviewer comment
returned Ready for merge at the same head.
The same block's `--is-ancestor ... && echo "pure upstream history"` was
graded the same way, although `address-every-comment`'s own ai-config#868
case record already establishes that `--is-ancestor` exits 2 or higher on a
pruned ref and `&&` fails on any non-zero status --- measured here, a bogus
ref gives rc=128 and the two-arm form still reports "not ancestor".
Both verdicts were wrong; fixed in `0c19d3c`.)

## A fix is not pushed until it's on the PR's head commit

(d-morrison/altdoc#54, 2026-07-25: two review fixes were edited locally and a
PR comment said they were "addressed in the latest push"; the head sat at the
pre-fix commit for over an hour, with 14 green checks validating a branch
carrying neither fix, until a scheduled check-in compared the SHAs.)

## A cited SHA must be read, never recalled

(ai-config#871, 2026-07-30: the PR body credited a sentence-boundary fix to
`1f79a4a`, which existed nowhere in the branch or the repository ---
`git cat-file -e` returned `Not a valid object name`.
The real commit was `fcb605f`.
Two review rounds read that body without flagging it; it surfaced only when the
body was re-read against the diff before declaring the PR ready, which is the
`address-every-comment` check above doing work its own rule did not anticipate.)

## A read SHA can answer a different question

(Morrison-Lab/ai-config#1396, 2026-08-12: the issue body read "Measured
2026-08-12, `origin/main` at `3f8b2f1`", and `git rev-parse origin/main` had
never been run.
`3f8b2f1` came off a `git stash list` line produced seconds earlier ---
`stash@{1}: WIP on main: 3f8b2f1 Add R-package test/lint/spellcheck
verification lessons (#205)` --- which names the commit an unrelated stash was
taken on.
That commit is dated 2026-06-25, roughly seven weeks before the measurement it
was being offered as the base for, and it is an ancestor of `origin/main`
rather than its tip.
The real tip was `b323a4fc`.
The body has since been edited to drop the claim, though
`gh search issues "3f8b2f1" --owner Morrison-Lab` still returns the issue, so
the search index is what records that the string was there.)

## The read side of a push-verification comparison can lag

(Morrison-Lab/ai-config#845, 2026-07-29: `git rev-parse HEAD` and
`git rev-parse origin/<branch>` both read `9a3e722` and `git push` said
`Everything up-to-date`, while `gh pr view --json headRefOid` still returned
the prior commit `4bf5063`.
`pull_request_read` `get` returned `9a3e722` moments later, so the two
surfaces disagreed and the git-native one was right.)

## A brand-new branch can read back at the wrong commit

(Morrison-Lab/ai-config#985, 2026-07-31:
`git push -u origin ums/prose-count-adjacent-to-block`, carrying commit
`1611ccc`, printed `* [new branch]`, set the upstream, and exited 0.
`git ls-remote` showed that ref at `98102a2`, which was `main`'s tip.
The local `origin/ums/prose-count-adjacent-to-block` agreed with the wrong
value, so the two-ref comparison reported the push as landed.
`create_pull_request` then returned a 422 reading
`No commits between main and ums/prose-count-adjacent-to-block`.
`git push origin HEAD:refs/heads/ums/prose-count-adjacent-to-block` reported
`98102a2..1611ccc`.
Neither `git rev-parse ums/prose-count-adjacent-to-block` nor a second plain
`git ls-remote` was run, so the branch ref's own value at push time is the
fact the record is missing.
Describing that push as "carrying commit `1611ccc`" was an inference from the
commit just made, not a reading of the ref that was pushed.)

## An inherited "already fixed" claim needs its own check

(Morrison-Lab/ai-config#804, 2026-07-29: the PR's own review workflow posted
"Three fixes landed in two commits", naming `bootstrap.sh`, `validate.yml`,
and `validate-skills.py`.
The head was still the original commit plus a `main` merge, and
`gh pr diff --name-only` returned four paths, none of them those three.
All ten checks were green, because `validate` did not yet check out the
submodule the fixes were about.
This is the ownerless cousin of the parallel-session case in
[`claim-pr`](claim-pr.md), which assumes a real commit exists to cross-check;
here there was none.)

## A branch can be green on every check with no implementation

(2026-07-30/31, a `ucdavis/bcs` session: a PR was reported `CLEAN` with every
check passing, on a branch holding the empty claim commit plus a `main` merge
and nothing else.
Nothing had gone wrong with any instrument.
The implementation had never been pushed, and no check, no reviewer, and no
rule in this file was asking whether there was one.)

## Verify a blocker you assert before publishing it

(d-morrison/altdoc#76, 2026-07-27: the PR body said roxygen2 8.0.0 --- the
version `DESCRIPTION` pins --- was unavailable, inferred from one failed
`packageVersion()` call with no install attempted. The review built a
"this may need a follow-up" recommendation on top of it. A single
`install.packages()` disproved it, and the regeneration landed in the same
round the finding did.)

## Attempting the base form is not attempting its variants

(2026-08-05, `Morrison-Lab/ai-config`: `git worktree remove <path>` on a
worktree holding a checked-out submodule failed with `fatal: working trees
containing submodules cannot be moved or removed`, and a memory entry was
written asserting that `--force` "does not help" and that git "declines this
case unconditionally".
`--force` had never been run.
A reviewer challenged it against git's own documentation, which says
"Unclean worktrees or ones with submodules can be removed with `--force`".
Measured on git 2.37.2.windows.2: the plain form exits 128, while
`git worktree remove --force <path>` exits 0, deletes the directory, and
deregisters the worktree.
The wording was genuinely unconditional for `git worktree move`, which is the
half-truth that made it survive re-reading.
[`memories/git-worktrees.md`](../../memories/git-worktrees.md) now records the
working form.)

## Name the specific gate, not a category word

(2026-08-01, `Morrison-Lab/ai-config` worked from a `the repository owner`-scoped
session: an unresolvable review thread was reported as blocked "for scope
reasons" across roughly six status updates, while the failure actually
observed under that spelling was the node-versus-declared-string comparison.
`memories/github-mcp-tools.md` records both gates and their verbatim errors.)

## When the blocker is a hang, inspect the process

(2026-08-02, `Morrison-Lab/ai-config#1056`: a claim that `claude setup-token`
"needs a TTY" was written into a skill without measurement, then replaced
with "it hangs when non-interactive" on the strength of a probe that returned
exit 142 and no output.
Both were guesses, and the second read as the correction of the first.
`ps -o pid=,stat= -p <pid>` then reported `S` -- alive and blocked -- *after*
the browser authorization had completed, and `lsof -p <pid> -a -d 0` showed
fd 0 as a unix socket rather than a terminal.
So the gate is a post-authorize read on stdin, not a startup capability
check, and the same claim was wrong three times in one session before anyone
measured it.
Recorded in [`memories/claude-code.md`](../../memories/claude-code.md).)

## Withdraw a blocker that stopped being true

(ai-config#774, 2026-07-28: the PR body said four `adv-r.hadley.nz` anchors
could not be verified because the host was egress-blocked, which was
accurate when written.
The host was unblocked mid-session, and all 16 URLs then verified 200 with
every anchor resolving.
The review had already absorbed the caveat --- it listed those anchors as
"unverified per the PR body's own caveat ... not a new finding" --- so
leaving it would have shipped a limitation that no longer existed, blessed
by a reviewer who could not have known.)

## A `main` merge can falsify a hedge with no conflict

(Morrison-Lab/ai-config#981: its fragment said ai-config#959 was still open as
of 2026-07-31 and that, once merged, the fragment would live at
`shared/workflow/flag-practice-slippage.md`.
PR #959 merged at 2026-07-31T16:24:34Z, and commit `df243ee9` merged `main` into
PR #981 on 2026-08-01, pulling in that very file.
The merge conflict was in `CLAUDE.md`, so the cleanly merged fragment was not
re-read, and a reviewer caught the stale hedge afterward.)

## Landing a fix falsifies prose that documented the defect

(`ucdavis/bcs#534`, 2026-07-30/31: standardizing a G-computation CIF over the
observed age distribution falsified two documents at once.
`compute_gcomp_cif_ab507bs()`'s roxygen had read "this function follows the SAS
pipeline's plug-in-at-the-mean approach", which the SAS program does not do ---
false before the fix, and quoted by the fix's own changelog entry as such.
A row in `inst/docs/program_steps.qmd` described the retired behaviour and was
refreshed in a separate commit.
Concurrently, ai-config#951 diff-scoped `scripts/semantic-line-breaks.py`, which
falsified `memories/tools.md`'s entry prescribing "format new prose by hand" as
the workaround; that entry was kept and marked `**Fixed in ai-config#951.**`,
which is the first shape handled correctly.)

## Read a third-party tool's own docs, don't infer its behavior

(d-morrison/altdoc#78, 2026-07-27: a generator-to-extension map gave mkdocs
`.html`, reasoning that mkdocs compiles Markdown to HTML. Its
`use_directory_urls` default is `TRUE`, so it serves `/man/foo/` and never
`/man/foo.html` --- every reference link the feature emitted for that
generator would have 404'd. Caught in review, not by the 39 tests.)

## A regression test written alongside its fix can lock the bug in

(d-morrison/altdoc#78, 2026-07-27: twice.
A `.pdf` vignette test asserted
the entry's extension but never its label, so an extension leaking into the
label passed; and a nested-article test built no source tree, so top-level
and nested resolved identically and a nested-only title bug was pinned as
expected output.
Both were found by review reading the test, not the code.)

## A systematic audit done by skimming is worse than one-at-a-time

(d-morrison/altdoc#78, 2026-07-27: a commit written to get ahead of a
one-finding-per-round loop claimed mkdocs' sidebar matched only `\.md`.
It matches `\.md$|\.pdf$`; the grep had returned a different function 120
lines above the sidebar builder in the same file.
Caught by the very next review round.)

## An added explanation can contradict a passage nobody re-reads

(ai-config#770, 2026-07-28: an added explanation established that seven
reported orphans were misclassifications, while the note two lines below went
on calling them "already deleted from the repo."
Caught by review, in the same hunk as the text that contradicted it.)

## The same contradiction within a single diff

(ai-config#801, 2026-07-28: a new UMS entry argued against the `/clear`
section's "disclose the owed pass in the flag" line while the same PR rewrote
that line to say the opposite.
Review caught it before merge; the fix was to drop the cross-reference and
state the point inline.)

## A vanished symptom is a landed fix until checked otherwise

(ai-config#827, 2026-07-29: the Jules AI reviewer approved a diff carrying
both of its known false-positive triggers, and the first explanation
drafted was that the false positives are nondeterministic.
ai-config#817 had in fact merged an `extra_instructions` fix at
`21:30:51Z`, between #820's block at `19:43` and #827's approve at `22:51`.
The nondeterminism claim was about to be posted to gha#366 as evidence,
where it would have argued against porting the fix that actually worked.)

## Verify a command or flag you invent for a doc

(Morrison-Lab/ai-config#834, 2026-07-29: a `GET_LABEL` registry row shipped
`gh label view <name>`, which does not exist --- cli/cli's
`pkg/cmd/label/label.go` registers `list`, `create`, `clone`, `edit`,
`delete`.
Caught by review, in the same file where the previous round had declined to
extend an untested claim from `gh issue create --label` to `gh issue edit`.
The reviewer's own enumeration of the real subcommands also missed `clone`,
which is why the fix cited the registration list rather than the finding.)

## Run the literal-verification check over your own fix too

(Morrison-Lab/ai-config#929, 2026-07-30: a review found `--failed`
documented from recollection.
The fix quoted `gh run rerun --help` correctly and anchored it to "`gh`
2.83.0" --- a version invented in the same breath, where `gh --version`
reported `2.96.0`.
Caught before committing only by running this rule against the fix, which is
the entire mechanism; the round-2 review confirmed the corrected text and
would have confirmed the wrong version just as readily.)

## Running a script is not running its tests

(Morrison-Lab/ai-config#1067, 2026-08-02: a UMS pass took `memories/git.md`
from 1172 to 1315 lines.
`scripts/check-memory-file-size.py` exits 0 and its `validate.yml` step is
labelled advisory, both genuinely so, and the threshold was therefore reported
as non-blocking on #1007.
`scripts/test_check_memory_file_size.py` asserts this repo's own `memories/`
are under the default and hard-fails, turning `validate` red on the next push.
The claim had to be retracted on #1007 as well as fixed in the PR.)

(Morrison-Lab/ai-config#1325, 2026-08-08: the same pair one script over, and
this time the gating assertion was an exact count rather than a threshold.
A new `@shared/writing/ambiguous-reference.md` import was added to this repo's
own `CLAUDE.md`, and the pre-push sweep reported, verbatim, that
"`check-context-closure.py` exits 0 and reports the same 1 unbalanced
`CLAUDE.md` fence before and after; its over-budget figure is pre-existing".
Every clause of that is true, and the script does exit 0 while over budget by
roughly 894,000 bytes.
`scripts/test_check_context_closure.py` pins the number of anchored imports
`CLAUDE.md` yields, so the new import took it past the pin and `validate` went
red on `FAIL: this repo's CLAUDE.md still yields 71 anchored imports`.
The two steps sit about thirty lines apart in one job, and the advisory one
carries a comment explaining that it reports rather than gates --- so reading
the workflow around the script confirms the harmless reading and never reaches
the twin.
Recorded as an execution miss rather than a coverage gap: the rule above
already said to run the test files, so the follow-up was to make the failure
self-documenting and to write the repo-specific mechanism down, not to restate
the rule a fourth time.)

(d-morrison/altdoc#95 and #96, 2026-07-29: twice in one session.
On #95 a test asserting "aborts when no venv is configured" read that
precondition from the ambient environment; the local run missed it because
`NOT_CRAN` was unset and `skip_on_cran()` skipped that very test, and
Windows R-CMD-check caught it.
On #96 `test-llms_txt.R` asserted non-recursive discovery for `docsify` ---
the exact behaviour the PR changed, with a comment stating the now-false
rationale --- and was not among the files run locally, even though
`.llms_txt_vignettes()` was one of the functions edited.
Windows caught that one too.
The subsequent full-suite run was itself misleading in the opposite
direction: run *with* an env var CI does not set, it reported two failures
belonging to the sibling PR.)

## A third failure mode: the suite holds no case that could have failed

(`Morrison-Lab/ai-config#1287`, 2026-08-08: the PR narrowed
`hooks/no-unauthorized-merge.py`'s command-position anchor, and its "Checks run"
section offered `test_hooks` (15/15 suites) and every `scripts/test_*.py` as the
verification, all run after committing so the diff-scoped ones read `HEAD`.
Both statements were true.
Review then found a high-severity fail-open: five executable bash forms ---
a leading `!`, a `time` wrapper, a `nohup` wrapper, a brace-group body, and a
`then` branch body --- reached the blocked merge command while the guard
returned allow, all five having blocked before the change.
No case in the suite covered a keyword-prefixed command, so no amount of running
it could have failed, and un-gating skips or widening the run would have changed
nothing.
The reviewer's method is the remedy this rule prescribes: it loaded the PR's own
hook at `552cd0a`, called `offending()` on the five constructed inputs, and
tabulated the results against `main`'s pre-change version --- two columns over
an input class, rather than a suite total.
Reproduced independently before fixing, on `769ac87c`, with the same five
allowing and the bare baseline blocking.
The PR body had even noted that "the merge guard's only scoped authorization
path had no test at all, which is how these went unnoticed", so the absence was
observed and never generalized into distrust of the suite total quoted beside
it.)

## A merge gate is not a work gate

(`ucdavis/bcs#578`, 2026-08-07: a CI change adding Gemini/Antigravity as review
options, with one unusual property --- no external reviewer had produced a
verdict at any head.
Every verdict-shaped comment on it was the session's own self-review posted
under the maintainer's account.
Copilot had refused nine times on quota,
and the repo's `claude-review` ran twice at the current head with
`conclusion: success` and posted nothing either time.
The session correctly and repeatedly declined to **merge** it without being
told to.
`main` then advanced by four PRs and #578 went `CONFLICTING`/`DIRTY`.
The status report carried a boxed RECOMMENDATION --- "let me resolve #578's
conflict and re-run its review ...
Say the word and I'll drive it;
I won't merge it either way" --- and stopped there.
The user replied "do it", then corrected: "you should have done it without
waiting for approval".
Both halves of the rule were already written down --- `CLAUDE.md`'s "never ask
'should I watch this?' or 'should I iterate it?' first", and this fragment's own
"a conflict ... is ARDI work immediately".
The failure was conflating a correct gate on one action with a gate on the whole
PR.)

## A fix that reinstantiates the class it just closed

(`Morrison-Lab/ai-config#1287`, 2026-08-08, rounds 3 and 4: the guard in
`hooks/no-unauthorized-merge.py` has a command-position anchor, `LEAD`, whose
narrowness had already produced one fail-open in round 1.
Round 3's fix consolidated three drifted copies of the executor list into a
single `EXEC_PROGS` consumed by all three sites --- a real DRY repair, reported
as such --- and in the same commit, `28cb5366`, hand-rolled a new anchor,
`HEREDOC_EXECUTOR`, instead of composing `LEAD`.
Round 4 duly found the round-1 keyword gap reproduced in that new anchor:
`sudo bash <<EOF`, `time bash <<EOF`, `! bash <<EOF`, a `then` branch body, and
a brace group all reached a blocked merge command while the guard returned
allow.
The author's own reply names the mechanism:
"I fixed one duplicated concept and forked a different one in the same breath,
which is why the round-1 keyword gap reappeared in a fourth place."
The same reply records that the review had already said so --- its paragraph
explaining why `EXEC_WRAP` did not save `mask_heredocs` is a statement that one
idea lived in two places --- and that it was read as context for the heredoc bug
rather than as the finding it was.
Round 4's fix, `500204d3`, rebuilt the anchor as `LEAD + ENV_WRAP + executor`,
which is the compose-the-shared-definition remedy this rule prescribes.
The two later rounds are a different failure, recorded against
[`check-purpose-before-reusing`](check-purpose-before-reusing.md): round
4's fix was strictly wider than the hand-rolled anchor it replaced, so it
introduced no gap --- it composed the narrow variant of an anchor that also had
a permissive one, which rounds 5 and 6 then found insufficient.)

## A per-push dispatch cancels its own review, invisibly

(`Morrison-Lab/ai-config#1361`, 2026-08-09: three review runs were dispatched
across one ARD round on a repo whose `claude-review.yml` carries
`workflow_dispatch` and nothing else.
Runs `31341027707` and `31341383018` were each cancelled mid-review by the next
dispatch; only `31341502912`, issued after the pushing stopped, survived and
posted a verdict.
Roughly nine minutes of review time produced nothing, twice.

The concurrency group was read rather than inferred, at the ref the runs
actually used, per
[`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md).
Run `31341027707`'s `referenced_workflows[]` reports
`Morrison-Lab/gha/.github/workflows/claude-code-review.yml@v2` resolved to
`c05ca95cdb33a93ad7f7f51a90b67cedfa7afe56`, and at that commit the
`claude-review` job carries, at lines 328 to 330:

```yaml
    concurrency:
      group: claude-review-${{ github.event.pull_request.number || inputs.pr-number }}
      cancel-in-progress: true
```

The caller declares no `concurrency` block of its own, so reading the caller
alone would have found nothing --- the case
[`memories/github-actions.md`](../../memories/github-actions.md) records as "a
caller with no `concurrency:` block can still have its runs cancelled".
gha's own comment above that block already documents the consequence, that "a
CANCELED claude-review run makes require-review FAIL outright (cancelled !=
skipped)".

The invisibility was measured on the same run: `head_branch` reads `main` and
`head_sha` reads `92787c408b07d8e8aed0dbe029de663f07db173b`, which is the
default branch's tip rather than the PR's head, because the dispatches passed no
`--ref`.
`shared/workflow/ardi.md`'s own dispatch command omitted the flag at the time,
while the recovery command in `skills/ardi/SKILL.md` and `memories/preferences.md`
carried it --- so the routine path used every round lacked the fix that the
rarely-taken path had.)

## A third-party push cancels an idle-dispatched review

(`Morrison-Lab/ai-config#1841`, 2026-08-21, all times UTC:

- `22:13:44` --- `claude-review.yml` was dispatched with `pr_number=1841`.
  The PR head was `158a82f2`, and nothing had been pushed since `21:39` --- no per-push rhythm was in play.
  Run `32532076386`, `event=workflow_dispatch`, `headBranch=main`.
- `22:17:02` --- run `32532310435` was created on branch `fix/check-install-worktree`, `event=pull_request`.
  Cause: the `@claude` bot pushed `c29ecbd2`, a merge of `main` (`bd92faad`) into the PR branch --- a `synchronize` event.
- The dispatched run ended `cancelled` (`updated=22:17:41`): `gather-context` succeeded, `review / claude-review` was cancelled, `review / require-review` failed.

The right response was to do nothing.
The newer `pull_request`-triggered run superseded at a newer, better head, and it went on to post the real verdict.
Re-dispatching at that point would have cancelled the survivor instead.

This is the mirror of the direction [`memories/github-actions.md`](../../memories/github-actions.md)'s "A caller with no `concurrency:` block can still have its runs cancelled" section measured the day the config changed: there, on `Morrison-Lab/ai-config#1724` (2026-08-20, the same day `claude-review.yml` gained the `pull_request` trigger), a `workflow_dispatch` run cancelled a `pull_request` run.
Here a `pull_request` run cancelled a `workflow_dispatch` run, one day later, with no per-push rhythm on the dispatching session's side at all --- the push that triggered the cancelling run came from the `@claude` bot's own `main`-sync, not from any push of this session's.)

## A cancelled dispatch that fired a failure webhook against the superseded SHA

(`Morrison-Lab/ai-config#1526`, 2026-08-16: a review was dispatched with
`--ref` at `1847c964`, a subagent then pushed a `main` merge and a
pronoun-fix commit, and the run was cancelled deliberately because it was
reading a commit that was no longer the head.
The run object is what settled that, rather than the elapsed time:

```
run 31964345687   event: workflow_dispatch   head_sha: 1847c964
pull_requests[0].head.sha: b8a9cb45
```

Both halves of the visibility question were then observed within one event.
`pull_request_read` `get_check_runs` returned 7 runs, every one of them for the
new head, with the failed `require-review` absent --- so the sibling case above
is right that a cancelled run is invisible to a session reading the PR.
The cancel nonetheless fired a `check_run.completed` carrying
`conclusion: failure`, `check: review / require-review`, and
`head_sha: 1847c964f458eabeac64002354bd8379567351a1`, waking the subscribed
session with a red required check on its own PR.

Note the two runs differ in why the SHA was wrong, which is why this is a
distinct case rather than the sibling restated.
There the dispatch omitted `--ref`, so the run never pointed at the PR at all.
Here `--ref` was passed and correct, and the branch simply moved between the
dispatch and the cancel --- so the defect survives the sibling's own fix.

The cancel itself was the right call, on
[`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s criterion that
whether to cancel a slow review turns on whether the head has moved rather
than on how long it has run.
Re-dispatching at the real head produced a clean verdict at `eaf052d9`.)

## An invented `Closes` in a merge commit message

(`Morrison-Lab/ai-config#1361`, 2026-08-09: the squash commit `62ea72b3` ends
`Closes #1358`.
That number names an unrelated pull request from a parallel session, and #1361
had no tracking issue at all, having come from a subagent dispatch rather than the
issue-first flow --- so the number was typed to fill a habitual slot rather than
read from anywhere.

The damage assessment first published on the PR read: "GitHub's closing keywords
act on issues, not pull requests, and #1358 was already closed regardless."
The second clause is right and the first is wrong.
GitHub's documentation states that a closing keyword referencing another pull
request links them and that "Merging the referencing pull request also closes
the referenced pull request"
(`github/docs@1ef6cd3`,
`content/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue.md`,
line 47; read 2026-08-09).

Nothing changed state here for the reason the second clause gives rather than
the first: #1358 merged at `23:27:32Z` and #1361 merged at `23:31:39Z`, so the
target was already terminal when the reference landed.
That is a fact about the target's timing, not about the keyword, and the
instance therefore cannot support the general claim it was offered as evidence
for --- the shape
[`fail-fast`](../principles/fail-fast.md) records as "a proxy that answers a
narrower question passes the same way".
Had #1358 still been open, merging #1361 would have closed it.)

## A negated closing-keyword sentence still closes the issue

(`Morrison-Lab/ai-config#1718`, squash `b67a4cfe`, 2026-08-20: the squash
message contained `Closes #1717 is deliberately NOT used`, then `Refs #1717`.
The PR body used only `Refs #1717` and did not contain a closing keyword.
GitHub still closed [#1717](https://github.com/Morrison-Lab/ai-config/issues/1717)
at `2026-08-20T06:40:40Z`.

The number was the right tracker, and the sentence was trying not to close it.
GitHub's parser matches `KEYWORD #N` as a substring and does not read the rest
of the sentence
(docs retrieved 2026-08-26:
<https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue>).
The authoring PR therefore closed the registration follow-up it had left
unregistered, and the hook stayed out of `hooks/hooks.json`
until #2275 / #2294 recovered it.

This is the sibling of "An invented `Closes` in a merge commit message"
above, not a restatement of it: there the number was wrong, here the number
was right and the negation was ignored.
It is also not the partial-ship case in
[`issue-first.md`](issue-first.md), where `Closes #N` is used on purpose and
closes leftover sub-items.

Keep the number off the keyword (`the closing keyword was not used for #1717`;
`Refs #1717` only).
Do not write a sentence that places a closing keyword next to `#N` in order
to say you are not using it.)

## A review round surfacing five findings your own conventions already covered

([gha#219](https://github.com/Morrison-Lab/gha/issues/219)/[#220](https://github.com/Morrison-Lab/gha/pull/220): one review round surfaced five findings --- a DRY
duplication, an incomplete-coverage doc overclaim, a wrong changelog
category, an uncited claim, and missing test coverage for new logic --- all
catchable this way, since each was a direct match against gha's own
`CLAUDE.md` conventions, not new information the review surfaced.)

## Two correct fixes composing into a defect neither introduces alone

(Morrison-Lab/gha#440, 2026-08-09: round 1 made a notice-posting step
best-effort (`|| echo "::warning::"`) in response to one finding, and in the
same commit extended a collapse step's `if:` to that step's path in response to
another.
Each was correct.
Together, a run whose post failed would fold the *previous* run's notice and
post nothing, leaving the PR with a gray gate and no explanation --- the exact
symptom the PR existed to fix, reproduced in a single run.
Round 2 caught it; reading the two-item commit message against itself would
have.)

## Self-correcting a rationale before the reviewer re-raises it

([d-morrison/rme#989](https://github.com/d-morrison/rme/pull/989) /
[ucdavis/epi204#363](https://github.com/ucdavis/epi204/pull/363): after telling both reviewers `references.bib` didn't
share `CLAUDE.md`'s union-merge corruption risk, a follow-up merge
simulation showed it does --- posted the correction with repro steps on
both PRs before either reviewer re-raised it.)

## A verification table in the PR body going stale as rounds change the diff

(`Morrison-Lab/ai-config#1353`, 2026-08-09, review finding 2.
The PR body claimed the guard's suite "grew from 226 to 238 cases (12 new
BLOCK, 10 new ALLOW)".
Neither number was derived: the base had never been counted at all, and the
BLOCK delta was stale from an earlier drafting round that later rounds had
added cases past.
The reviewer counted the `BLOCK`/`ALLOW` list lengths with `ast.parse` rather
than trusting the file's own runner, and reported 202 to 228 at the review head
`7d063f2`.
Round 1's own fix then added five more regression cases, so by `2f0b697` the
real figures were 202 to 233 list cases (BLOCK 157 to 178, +21; ALLOW 45 to 55,
+10), or 212 to 243 including the runner's ten inline checks.
That second movement is the point rather than a footnote: the *reviewer's*
correctly-derived count went stale within one round too, so the defect is not
carelessness at any one desk but a figure published where nothing re-measures
it.
The corrected body now shows the base, head and delta per group, states the
`ast.parse` derivation, and keeps the wrong figures on the record rather than
silently overwriting them, since the review thread refers to them.)

## A round-one confirmation laundering a body the next round contradicts

(`Morrison-Lab/ai-config#1522`, 2026-08-16, merged as `bc89ec93`.

Round 1, posted at 18:04:08Z, verified the body's verification table in detail,
reporting that it had "independently confirmed every reported figure --- 1646
links/503 files (0 broken) ... and +67/+71/+10 additions per file --- all match
the PR body precisely", and separately that it had "independently scanned the
diff's 148 added lines".
Every one of those figures was correct at the head it ran on, `cd8cfb03`:
`git diff --numstat` over that commit returns `67 / 71 / 10` across three
files, summing to 148.

Commit `339645c3` then addressed both round-1 findings and widened the diff
from three files to six.
`git diff --numstat` over `339645c3` returns `15 / 67 / 85 / 8 / 10 / 11`,
summing to 196.

Round 2, posted seven minutes after round 1 at 18:11:22Z, opened by saying it
had "re-scanned all **196** added lines across the full PR diff (all three
commits)", found nothing new, and returned **Ready for merge**.
The body at that moment still read 148 added lines, 1646 links, and 134 prose
lines.
So the correct figure and the stale one sat one round apart in the same comment
thread, and the round holding the correct one never looked at the other.

The staleness was caught by the author re-reading the body at the merge gate
rather than by either review, and the merged body records that catch in a
"Corrections to this body" entry naming the same three stale values.)

## Validating against a real consumer repo covers what fixtures cannot

(d-morrison/altdoc#34: running the new reference-index generator
against `Morrison-Lab/rpt` covered a `\docType{package}` topic, the singular
form of a missing-topic warning, and the documented "existing settings files
do not pick this up automatically" caveat --- confirmed by the page
generating while `grep -c reference.html docs/index.html` returned `0`.
None of the three were reachable from the repo's own fixture packages.)

## An instruction's own suggested code breaking a project convention

(d-morrison/altdoc#73: the issue proposed ending a function with a bare
trailing `hashes`, which reads as a fix for the fragility it names but is
still an implicit return, so a statement added after it silently becomes
the return value.
The lab manual asks for an explicit `return()` regardless.
Review caught it; the project's own stated convention would have, one step
earlier.)

## A staging step the unit fixtures could not reach

(d-morrison/altdoc#76: a guard checked for the copied logo under `docs/`,
but the `quarto_website` path stages into `_quarto/` first, so the logo
line was dropped on every render of the one generator the feature wired up.
Seventeen unit assertions passed throughout; one throwaway render found it
immediately.)

## A mechanism claim whose population held no true positive

(ai-config#770, same day: a `git log -- skills/<name>` probe was said to
separate "deleted from the repo" from "never ours" *exactly*, on the evidence
that it reported zero false orphans.
The repo contained no deleted-but-still-installed skill at all, so there was
nothing for it to get wrong; and `git rev-parse --is-shallow-repository`
returned `true`, meaning anything deleted before the shallow boundary would
have been silently misread as harness-provided.
The claim went into a PR reply before either check was run, and ai-config#765
had independently reached the correct conclusion.)

## Editing generated output, then being read as pollution once regenerated

(Morrison-Lab/ai-config#834, same day: a fix was applied to the generated
`tool-mappings.md`, which `sync-codex-skill-wrappers.py` then overwrote,
failing `validate` with `stale tool-mappings.md`.
Redoing it in `tool-mappings.yml` regenerated 175 `codex-skills/` wrappers,
and Jules returned `VERDICT: block` twice for "bulk pollution", its second
verdict noting it had read only a truncated diff.
`claude-review` called the same finding a false positive at the same head.)

## A generator's environment, not its version, changed the committed artifact

(`UCD-SERG/serodynamics#291`, 2026-08-12: `docs-check` reported exactly two
changed files, `DESCRIPTION` and `NAMESPACE`.
Re-documenting locally with roxygen2 8.1.0 --- CI's own version, from CI's own
RSPM binary repo --- changed **three**, the extra one being
`man/expect_snapshot_data.Rd`, because `testthat` sits in `Suggests` and was
not installed, so that file's
`@inheritDotParams testthat::expect_snapshot_file` could not resolve and
roxygen emitted the topic without the inherited arguments.
`rjags` was absent too and was flagged on a different topic, which is worth
separating: only the `testthat` gap changed a file, so the missing-package
count and the changed-file count are not the same number.
Committing that would have shipped a silently degraded help page.
Installing the full `Suggests` set reproduced CI's two-file result exactly,
with no warnings --- and the contrast between the two runs' warning output is
itself the cheapest check that the environment is now right.)

## A brand-new branch reading back at `main`'s tip, reproduced offline

Reproduced in a local bare repo, where no replica and no race exists: the
push printed `* [new branch]` and exited 0, `git ls-remote` and the tracking
ref both read `main`'s tip, `main..<branch>` held zero commits, and
`git push origin HEAD:refs/heads/<branch>` then reported a real range.
That last command is a test as much as a fix, since it answers
`Everything up-to-date` when the branch ref and `HEAD` already agree.

Two things weigh against the read-side story, which an earlier draft of this
entry weighted equally against the write-side one.
A lagging replica cannot invent a value for a ref that never existed before,
so its failure mode is the ref reading **absent** rather than reading one
specific wrong commit.
And a tracking ref is set from what the push sent, which makes its value a
client-side fact rather than a later network read.

What stays genuinely unsettled is narrower than either reading claimed: the
branch ref's own value at push time was never recorded, so the local
explanation is the best supported one rather than a proven one.
Note the shape of that, since it is the failure this entry is about.
The entry has now over-claimed twice, first asserting a write-side fault, then
asserting a parity between two hypotheses that the record does not support
either.
The practical advice survives all three readings, because the
`git ls-remote origin <branch>` and `git rev-parse HEAD <branch>` checks are
cheap whichever is right.

## A suite whose branch coverage varies by host

(Morrison-Lab/ai-config#1327 / #1395, 2026-08-12: `skills/session-lock`'s
`is_stale()` tests `session_liveness()` first and consults the heartbeat only
when liveness reads `unknown`, so which of its three branches a test reaches
depends on whether the machine running the test has a live `claude` process in
its ancestry.
`scripts/test_ai_session.py` ages a session's heartbeat to make it stale, which
works only on the `unknown` branch.

Measured on a host where it does not.
`find_agent_pid` returned PID 513 with `comm=claude`, so a registered record
carries a live PID, `session_liveness()` returns `alive`, and `is_stale()`
returns not-stale without reading the heartbeat at all.
Running the pre-change suite there --- `python3 scripts/test_ai_session.py` at
`e448b8ec` --- printed `4 FAILED`, among them
`a stale session exits 2, not 1: rc=0`.
The same file passes in CI, where no such ancestor exists.

So one environment exercised `unknown)`, the other exercised `alive)`, and the
`dead)` branch --- the one a crashed session actually takes --- was exercised
by neither.
Nothing was skipped in either run, so the skip count gave no sign that the two
runs had traversed different code.
The **failed** counts did differ, 4 against 0, and that is what surfaced the
divergence.
The fix was a case that registers a genuinely dead PID and leaves the heartbeat
**fresh**, so only the liveness branch can decide it, whatever the host
supplies.)

## A corrections entry expires with the next push

(`Morrison-Lab/ai-config#1395`, 2026-08-12: the PR body's derived counts went
stale in two consecutive rounds, on the same two figures.

Round 1's body stated 100 insertions and 264 lines at `4c5d71e`.
Commit `b11fe4a9` made the real figures 106 and 270, and the body was corrected
with a numbered `Corrections to this body` entry recording both as "re-derived
rather than adjusted".
Round 2's self-review finding then prompted `737b7c06`, which added a
retry-loop rationale comment and moved the same two figures to 111 and 275 ---
expiring the entry that had just refreshed them.
They were re-derived only in the sweep immediately before merging, and the
merged body carries a fourth entry recording that second refresh.

The rule was not unknown, which is the point of the record.
That fourth entry cites this fragment's own "any round that changes the diff
expires every figure the body already states" while making the correction, so
the round had the rule in hand and applied it once.
What it lacked was the trigger: the pause point fired at both pushes and the
checklist item was discharged at one of them, with a durable note in the body
asserting the figures were current in between.

Note which push did it.
`737b7c06` answered a self-review finding rather than a reviewer's, so it did
not feel like a round that changed anything a reviewer would re-read --- and
its content was a comment explaining a retry loop, which is exactly the kind of
edit that reads as not touching the diffstat.
It changed both figures.)

## A whole-body staleness check that reported a correct fix as failed

(`Lacaedemon/sparta#1303`, 2026-08-16: a review round moved the PR body's
figures from `484 added` and `2723 / 2723 passing` at head `dbfe12d8` to
`532 added` and `2725 / 2725` at `5c145fce`.
The body was rewritten with both new figures and a `### Corrections to this
body` entry naming the two superseded ones, which is exactly what the section
above asks for.

The post-PATCH verification then searched the whole body for each old figure
and reported `False` for both --- reading as though the rewrite had missed
them.
It had not.
The only remaining occurrences were inside the corrections entry, where they
belong, since an entry that says what changed cannot say it without naming the
old value.

Re-run section-scoped, the same two strings were absent from the verification
table and present in the corrections entry, which is the intended end state
rather than a defect.
The wrong reading was available and cheap: deleting the quoted figures would
have silenced the check and destroyed the record the entry exists to carry.)

## A genuinely-read prefix, extended into a fabricated link

(`Lacaedemon/sparta#1244`, 2026-08-13: a close-as-duplicate comment linked
the sibling PR's head commit, and the short SHA `974c83b` in that link was
genuine --- read off real `git log` output moments earlier.
The markdown link format wanted all 40 characters, and the remaining 33 were
typed as `b1683e2e60ae23662ce35eb46be13a8bc` where the real tail was
`66573e699e1bba5b2b7ede09deeeec244`, so the published link 404'd on a commit
that existed.
Caught seconds later by self-review running `git rev-parse 974c83b`, and
corrected with a visible follow-up comment naming the real SHA, per this
block's own correct-visibly bullet.
The near-miss worth the entry: the read-never-recall check reported itself
satisfied because a SHA genuinely had been read --- just 7 characters of the
40 the sentence asserted.)

## A trust-gate fix that revealed a tool-name mismatch behind it

(`ucdavis/bcs#620` / `Morrison-Lab/gha#463`, 2026-08-16.
`gemini-code-review` had failed 7 of 7 runs on `ucdavis/bcs`, and the captured
error was read as a startup banner.
The real last line of that capture named its own cause:
`Gemini CLI is not running in a trusted directory`.
`Morrison-Lab/gha` set `GEMINI_CLI_TRUST_WORKSPACE: 'true'` in `1c270f2f` on
2026-08-15 and slid `v2` the same day.

A review dispatched after the slide **failed again**, which reads at first as
the diagnosis having been wrong.
It was not.
The two runs used different dependency versions, and comparing the errors
rather than the outcomes settles it in one read:

| run | `referenced_workflows[].sha` | env var | error |
| --- | --- | --- | --- |
| 2026-08-14 | `695fbf56` | absent | `not running in a trusted directory` |
| 2026-08-16 | `3ee5a0b8` | present | `FatalTurnLimitedError`, code 53 |

The second cause was structural and had been unobservable while the first
stood: the CLI registers the MCP tools as `mcp_github_pull_request_read`,
while the reusable workflow's prompt names them bare as `pull_request_read`.
Gemini tried four spellings, found none, fell back to `run_shell_command`,
was denied eight times by `settings.tools.core`, and exhausted
`model.maxSessionTurns: 25`.
So the turn limit is the symptom rather than the cause, and raising it would
buy more failed tool calls.

Two things the case turns on.
The pre-fix run is not evidence about the fix --- reading
`referenced_workflows[].sha` per run, rather than the current `v2` tag, is
what establishes that, per
[`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)'s mirror-direction
section.
And the earlier hypothesis was tested by dispatching a real review rather than
inferred from the upstream commit having landed, which is the only reason the
second cause was found at all.)

## A green check credited to a timeout raise that never ran

(ucdavis/bcs#761, 2026-08-28: the PR carried one red required check, `docs`, which had been killed twice at a 40-minute `Build site` step timeout.
bcs#763 had since raised that step's limit from 40 to 90 minutes on `main`, post-dating the branch's merge-base, so `main` was merged into the branch and the PR thread was told the fix for the red check was being ported.

The next run passed, and the pass was reported as the ported fix having unblocked the PR.

The passing run took 22 minutes 44 seconds --- comfortably inside the *old* 40-minute limit, so the raised ceiling was never reached and the same head would very likely have passed without the merge at all.
Three runs of identical content within nine hours went killed-at-40-min, killed-at-40-min, passed-in-23-min, which is variance rather than a fix.

The duration was computed from the job's start and end timestamps after the merge, out of ordinary diligence rather than suspicion.
Nothing about the green check prompted it, and without it a false causal claim would have stood on a merged PR and in an issue thread.
The merge itself was correct to perform under [`sync-with-main`](sync-with-main.md) and stays;
only the causal claim was wrong.)

## A mutation test whose reverted run never reached its assertion

(`UCD-SERG/serocalculator#668`, 2026-09-01: a regression test guarded a fix
to a save/restore pair for the RNG kind.
Mutation-testing the guard --- revert the fix, re-run, expect the test to
fail --- was run against `pkgload::load_all()` rather than an installed
build.
The test spun up a `parallel::parLapplyLB()` cluster, whose PSOCK workers
`require()` the package by name and cannot see a `load_all()` session's
environment, so both the fixed and the reverted run **errored** before
reaching the guard's assertion at all.
`testthat`'s summary read `FAILED: 0` in both runs, which a glance reads as
"the guard doesn't discriminate" when the true story is "neither run tested
anything".
Installing the package for real (`R CMD INSTALL .`) before re-running the
mutation surfaced the difference the test was written to catch: `FAILED: 0`
with the fix in place, a real assertion failure with it reverted.

The tell, worth generalizing past this one platform quirk: any regression
test reaching a code path that behaves differently under a development
loader than under an installed package --- a parallel cluster, `system.file()`
resolution, anything that spawns a second process --- can silently fail to
execute under the loader without failing loudly, and a mutation count taken
under that loader proves nothing either way.
`memories/r-quarto.md`'s "`pkgload::load_all()` cannot serve a PSOCK cluster"
section carries the mechanism.)

## Prose staled by its own fixes, round after round

(`Morrison-Lab/gha#811`, 2026-09-02.
Six adversarial pre-push review rounds ran on it.
The final commit `0262c1c6` names the recurring class as "the class this branch
has spent five rounds on -- a comment describing code inaccurately".
That is wider than this record's subject, which is the part of it staled by the
branch's own fixes, and the commit messages do not separate the two --- so the
record argues from one worked instance rather than from a count.

`gha`'s `CLAUDE.md` is not merely a contributor guide.
It runs to several thousand lines recording, per capability, which composite
does what, which exit code means what, which default each of two YAML files
declares, and which mutation kills which test case.
Almost any behavioural fix therefore falsifies a sentence in it, and a later
reader who finds code and prose disagreeing has good reason to take the prose.

The sharpest instance: a group-acceptance rule was changed, to close an earlier
finding, from "an integer is accepted, a bool is refused" to "every non-string
is refused".
`CLAUDE.md` went on saying an integer "round-trips and is accepted", and went
on prescribing that bool be tested before int --- an ordering the new rule makes
meaningless.
Both sentences had been accurate when written, and the change that falsified
them was in a different file --- `audit_example_concurrency.py` --- so nothing
in the *code* diff put either sentence in front of the author.
`CLAUDE.md` was not untouched, though, which is the sharper version: `385d4f43`
edited it in the same commit, and that edit's hunk runs to line 2884 while the
first of the two stale sentences sits at 2887 --- three lines below the hunk's
last context line, six below its last changed line.
So the file was open and the region was on screen, and the round still pushed.
Proximity is not the remedy; a grep for the replaced value is.

What makes it recur rather than merely happen is that each round's fix creates
the next round's stale sentence, which is what
[`ardi`](ardi.md)'s grep bullet now says explicitly: the grep is owed after
every round's fix, not once when the PR's headline defect is closed.)
