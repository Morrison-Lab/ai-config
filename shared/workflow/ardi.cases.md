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

## A merge gate is not a work gate

(`ucdavis/bcs#578`, 2026-08-07: a CI change adding Gemini/Antigravity as review
options, with one unusual property --- no external reviewer had produced a
verdict at any head.
Every verdict-shaped comment on it was the session's own self-review posted
under the maintainer's account; Copilot had refused nine times on quota, and the
repo's `claude-review` ran twice at the current head with `conclusion: success`
and posted nothing either time.
The session correctly and repeatedly declined to **merge** it without being
told to.
`main` then advanced by four PRs and #578 went `CONFLICTING`/`DIRTY`.
The status report carried a boxed RECOMMENDATION --- "let me resolve #578's
conflict and re-run its review ... Say the word and I'll drive it; I won't merge
it either way" --- and stopped there.
The user replied "do it", then corrected: "you should have done it without
waiting for approval".
Both halves of the rule were already written down --- `CLAUDE.md`'s "never ask
'should I watch this?' or 'should I iterate it?' first", and this fragment's own
"a conflict ... is ARDI work immediately".
The failure was conflating a correct gate on one action with a gate on the whole
PR.)
