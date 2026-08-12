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

(2026-08-01, `Morrison-Lab/ai-config` worked from a `d-morrison`-scoped
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
