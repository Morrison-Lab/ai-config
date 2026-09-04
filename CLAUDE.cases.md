# Case records: user-wide CLAUDE.md

Worked-example case records for the rules in [`CLAUDE.md`](CLAUDE.md), moved
here to keep them out of the auto-loaded context.
Each heading names the section and the rule the record supports.

The wording is unchanged from `CLAUDE.md`, word for word.
Three things about the text itself did change in the move, because relocated
prose is the mover's per
[`ascii-punctuation-in-source`](shared/coding/ascii-punctuation-in-source.md):
em-dashes became `---`, some lines were split at sentence boundaries per
[`semantic-line-breaks`](shared/writing/semantic-line-breaks.md), and one
record's positional "the correction above" now names its target, since the
records no longer sit where that phrase was written.

## Run UMS proactively, as learnings accumulate --- In a multi-PR/multi-issue session (GII-style), treat each PR merge as a concrete...

(Corrected in a sparta `gii-mwc` session, 2026-07-19: three PRs merged back-to-back with real, worth-saving learnings at each one --- a subagent-resume/restart pattern, a diff-scoped-check no-op, a stale benchmark baseline --- and UMS never ran until the user asked why `/clear` was suggested with UMS still outstanding, which is exactly the failure mode this fragment exists to prevent.)

## Run UMS proactively, as learnings accumulate --- Offering to run UMS is not running it

(Corrected 2026-07-28: a flag reading "worth running `ums` before this session ends" named a real, specific learning and still produced no pass, until the user said "you should have run ums already.")

## Run UMS proactively, as learnings accumulate --- The offer also survives being phrased as a decision, and that form is harder to see

(Corrected 2026-07-30, a bcs session.
After a day of findings, a recap closed "I owe a UMS pass ...
I'll run it now unless you'd rather I do something else first."
The correction was "cai: stop asking for approval for ums passes;
just run them.")

## Run UMS proactively, as learnings accumulate --- A new instruction arriving at a checkpoint does not cancel the checkpoint

(Same 2026-07-28 session as the "Offering to run UMS is not running it" correction: three checkpoints passed -- two merges and a clean verdict -- each immediately followed by a new user request, plus a `post-merge` run reported done whose UMS step never executed.)

## Run UMS proactively, as learnings accumulate --- A merge you discover rather than perform is still a checkpoint, and it is the one that...

(Corrected 2026-07-29: eight PRs from a multi-repo migration merged overnight and were discovered in a morning status check.
The session read the table, reported 14 of 22 done, and continued driving the remaining PRs for several more turns before the user said "you should have done the ums pass already.")

## Run UMS proactively, as learnings accumulate --- "I am low on context" does not exempt it, and that claim needs the same test any other...

(Corrected 2026-07-28, this session: a `gia` run flagged the owed pass three times, then recommended starting a fresh session to run it, citing exhausted context.
The correction was "you should have run ums before telling me to start a fresh session".
The pass then ran to completion in the same session, which is the evidence that the blocker was never real.)

## Run UMS proactively, as learnings accumulate --- "That would mean another open PR" is the same deferral wearing repo hygiene, and it is...

(Corrected 2026-07-30: a status report identified the zsh word-splitting learning, said it was owed, and closed with "I'll write it once #917 lands rather than opening a fourth PR mid-flight."
The user's correction was "no; do it right away."
This entry and its `memories/tools.md` sibling were then written immediately, in one short pass, against a `main` that #917 had not yet touched --- which is the evidence that nothing was blocking it.)

## Run UMS proactively, as learnings accumulate --- Correcting your own understanding of a technical issue is itself a trigger, and it...

(Directive from the user, 2026-07-30: "when you correct your understanding of a technical issue like you just did, run ums immediately."
The correction was a Quarto binary reported broken twice that turned out to be environment misuse both times, recorded in [`growth-mindset`](shared/workflow/growth-mindset.md)'s "First check the limitation is real" section.)

## Run UMS proactively, as learnings accumulate --- Delegate the pass

(Directive from the user, 2026-07-30: "cai: every time you find out you were wrong about something, run ums immediately (you should give this to a subagent, as always, and algorithmatize it, in addition to editing memories and skills)."
From a `ucdavis/bcs` session carrying six such discoveries, none of which triggered a pass:

- a private repo described as publicly exposed for a day, when `gh api repos/<r> --jq .private` settles it in one call
- a claim that this corpus ships no hooks, from a grep against a checkout 27 commits behind
- a PR reported green from a query predating three of its own pushes
- a changelog count of 9 that was 10, from a regex matching only one of two link forms
- a review suggestion applied without checking it resolved the same path
- a duplicate issue filed because a dupe-check and a create ran in one command.)

## Flag good moments to `/clear` in long-running sessions --- That PR clause is a bright line, not a judgment call, and it was narrowed deliberately

(Corrected 2026-07-29: a session flagged a clean stopping point while its own `ums` PR sat open awaiting review, having reasoned that the PR was "just awaiting review" and therefore not live.
The correction was "don't flag stopping points when you still have PRs open".)

## Flag good moments to `/clear` in long-running sessions --- Run wrap-up's state sweep before flagging a stopping point, not after the user asks...

(gha#318/ai-config#733/#736, 2026-07-26: a clean stopping point was flagged twice on the strength of "my three PRs are merged."
The `wrap-up` sweep the user then asked for found a stale draft PR (`gha#316`, a bot claim-commit for an issue closed hours earlier) and an unused harness-assigned branch still sitting in the `gha` checkout.)

## Flag good moments to `/clear` in long-running sessions --- Two mechanical details about that leftover-branch case, one of which reads as the...

(2026-07-29/30, this session: after gha#376 and ai-config#849 merged, the sweep found the assigned branch `claude/gha-pr-374-cf7138` checked out in the `altdoc` and `rpt` clones, neither of which the session ever touched.
Both carried 0 unique commits, were ancestors of `origin/main`, and were absent from the remote.
`altdoc`'s pointed two merged PRs behind its own `origin/main`.
The first `git branch -D` failed with the worktree message, and `git worktree list` showed one entry --- the main checkout itself.)

## Flag good moments to `/clear` in long-running sessions --- Starting a new PR is itself a moment to weigh compacting, clearing, or a fresh session...

(Directive from the user, 2026-08-04: "cai: before starting a new pr, consider whether we should compact/clear/start a new session.")

## Keep ai-config and repo checkouts fresh --- Point 1 is a precondition for this one, not merely an earlier item in a list

(2026-07-28, an altdoc `gii` session: `~/.claude` held one real-copy `skills/` and nothing else, and the local checkout was 13 commits behind -- so `scripts/check-install.py` did not exist on disk at either path and a hand sweep against the stale checkout was run instead, reporting counts that changed once the pull landed.
   That hand sweep was also the approach this very entry had already retired, which is the failure mode the staleness causes rather than a separate mistake.)

## Keep ai-config and repo checkouts fresh --- The clobber happens after bootstrap.sh, not before it, so don't diagnose this as...

(ai-config#755, 2026-07-28: 42 of 172 skills were stale in a web session, most at under half their real length -- `ardi` 80 lines vs 403, `ums` 94 vs 365, `ard` 134 vs 308 -- plus 3 latent unlinked copies the old `SKILL.md`-only sweep counted as identical.
   Caught only because a `ums` step contradicted a change known to have merged.
   The damage stayed small because `CLAUDE.md` itself was symlinked and restates most operative rules inline, which is the concrete argument for keeping local restatements alongside citations rather than trimming to bare pointers.)

## Keep ai-config and repo checkouts fresh --- Point 1 governs this instrument too, and its stale run is the more dangerous of the two

(2026-08-05, this machine: `install-hooks.py` run against a checkout 31 commits behind read a stale manifest and reported `registered=12 missing=0 stale=0` / `All hooks registered.`
   After `git pull --ff-only` the same command reported `examined 15 ... registered=12 missing=3`.
   Running `--fix` then bound all three to scripts absent from `~/.claude/hooks/`, one of them a `PreToolUse` `Bash` hook, which blocked every Bash call until `/reload-plugins` placed the symlinks.
   `memories/claude-code-hooks.md` carries the mechanism and the recovery.)

## Keep ai-config and repo checkouts fresh --- Point 1 governs this instrument too, and its stale run is the more dangerous of the two (2)

(2026-08-04, this machine: `check-install.py` reported 32 of 34 entries ok while `install-hooks.py` reported `registered=3 missing=8`, so 8 of 11 guards had never been bound to an event.
   Among them was `flag-unassigned-worktree.py`, and in that same session two `Agent` calls were launched with no `isolation` --- exactly what it exists to warn about --- with no warning possible.
   The lapse was first self-attributed to ignoring the hook, which was wrong in a way worth recording: the guard was never installed, so there was nothing to ignore.
   `install-hooks.py --fix` took it to `registered=11 missing=0`, and merging the then-open #1139 made it 12.)

## Keep ai-config and repo checkouts fresh --- An entry that genuinely IS a symlink resolves through the checkout's CURRENT BRANCH

(2026-08-08, this machine, minutes after #1287 merged its fix to the merge guard.
   `~/.claude/hooks/no-unauthorized-merge.py` is a real symlink (`lrwxrwxrwx`) into the checkout, which was parked on another session's `ums/session-learnings-redo`.
   `git show origin/main:hooks/no-unauthorized-merge.py | grep -c EXEC_AT_CMD_POS` returned 6 and the same grep on the resolved file returned 0, so the merged fix was not the guard running.
   `git merge-base --is-ancestor origin/main ums/session-learnings-redo` exits 1, confirming the branch predates the merge rather than the file having been edited.
   Both instruments were clean at that moment: `check-install.py` reported `268 ok, 0 stale, 0 unlinked, 0 missing, 0 misdirected, 0 foreign`, and `install-hooks.py` reported `registered=15 missing=0 stale=0` / `All hooks registered.`
   The exposed surface is not hook-shaped.
   `~/.claude/shared/principles` is a symlink too, so that session's own `@shared/principles/fail-fast.md` import loaded 831 lines against `origin/main`'s 1246, and `git diff origin/main --stat -- shared hooks skills memories CLAUDE.md` in that checkout reported 52 files changed, 850 insertions, 5870 deletions.
   Run `check-install.py` from a *worktree* instead and it reports `268 misdirected`, since it compares against its own root --- a different and equally misleading answer, so the instrument is not rescued by running it elsewhere.)

## Keep ai-config and repo checkouts fresh --- The same "diverged" failure from point 1 above can hit any repo's main, not just...

(Hit in both `ai-config` and `gha` checkouts in the same session, 2026-07-06: `gha`'s local `main` tip commit didn't match `origin/main` by hash *or* message at all --- unlike the milder "same content, rewritten hash" case documented in point 1 --- but was still just a stale checkout snapshot with nothing of value, confirmed once the working tree was verified clean.)

## Keep ai-config and repo checkouts fresh --- The same "diverged" failure from point 1 above can hit any repo's main, not just... (2)

(First done on `Lacaedemon/sparta` [PR #651](https://github.com/Lacaedemon/sparta/pull/651): the pin was 325 commits (~9 days) stale, unreferenced by CI, and not checked out by default.)

## Keep ai-config and repo checkouts fresh --- When the current checkout isn't main itself

(Re-discovered on `Lacaedemon/sparta`'s `claude/infallible-lewin-5841e9` branch, 2026-07-04: the branch's own pin read 344 commits stale while `main`'s was only 19 commits behind.)

## Keep ai-config and repo checkouts fresh --- When adding a new citation to an ai-config shared fragment inside a...

(`rme`#988/`epi204`#362: both cited `shared/writing/math-derivation-steps.md` in present tense while `ai-config`#502 was still open and each repo's `.ai-config` pin predated it --- flagged as a dangling reference by review in both, fixed by bumping the pin once #502 merged and hedging the still-open `gha`#228 half of the same citation.)

## Surface merge-order constraints --- Draft-gating is the last resort, not the default

(`UCD-SERG/ucd-serg.github.io`
[#110](https://github.com/UCD-SERG/ucd-serg.github.io/pull/110) /
[#111](https://github.com/UCD-SERG/ucd-serg.github.io/pull/111), 2026-08-24:
two PRs with a genuine ordering dependency and **zero** file overlap --- #110
added a `workflow_dispatch` trigger to `claude-code-review.yml`, and #111
granted the `actions: write` permission used to dispatch that trigger.
Rungs 1 and 2 were both applied exactly as the section prescribes: a
`MERGE ORDER` box in chat, twice, and an ordering note leading each PR body.
PR #111 was merged first anyway, at `17:49:30Z`, leaving #110 open and behind
until a branch update landed it at `17:56:00Z`.
Rung 3 was correctly withheld: both PRs were clean at the same moment, so
drafting one would have stalled its own review loop over a constraint whose
violation cost six and a half minutes.
What bounded that cost was the callee rather than any surface on the PRs ---
gha's dispatch step falls back and posts a warning comment instead of failing
the run, so an `actions: write` dispatch pointed at a workflow still lacking
the trigger degraded gracefully.
The moral: rung 2 failed open, rung 3 was correctly withheld, and the callee's
graceful degradation is what priced the violation at minutes rather than
breakage.
Recorded as [ai-config#2163](https://github.com/Morrison-Lab/ai-config/issues/2163),
with no rule change proposed.)

## Re-check for latest review findings before reporting PR status --- A process question is still a status fetch

(Morrison-Lab/gha#511, 2026-08-18: the user asked why the session had not
waited for CI, then why it had not answered
[that review comment](https://github.com/Morrison-Lab/gha/pull/511#issuecomment-5336851477).
The session answered the first question from chat and never opened the
thread, so a Needs more work review of `89e3702` sat unanswered until
asked.)

## Re-check for latest review findings before reporting PR status --- Filter on the body marker, not on an author login

(Morrison-Lab/ai-config#1054, 2026-08-03: the round-3 verdict --- **Ready for merge**, all four findings independently re-verified --- posted as `github-actions[bot]` at `03:04:19Z`.
The login-filtered query returned the round-2 comment from `02:12:52Z` instead, so a clean PR read as unreviewed.)

## Re-check for latest review findings before reporting PR status --- A bot's `COMMENTED` review is the same blind spot

(Morrison-Lab/ai-config#3084, 2026-09-03: three Copilot reviews at head `6f10014`, `5098574802` among them, were submitted in state `COMMENTED` --- two headed "Changes recommended", the third "Needs a closer look" --- with their findings under a suppression block, so they produced no review thread and no inline comment object.
The pre-merge check queried review threads, got two threads and both resolved, reported clean, and the defect reached `main`.
This section was loaded in context throughout and did not fire, because it named "a human's `CHANGES_REQUESTED`" and the reviewer was a bot.
Filed as [ai-config#3121](https://github.com/Morrison-Lab/ai-config/issues/3121).)

## Use the existing PR branch, not the harness-specified branch --- Prefer stacking the fix, not superseding the PR

(Corrected on ai-config#493 → #498, 2026-07-05: first reflex was to supersede per the fallback below;
the user redirected to stacking, and the maintainer then merged the stacked PR directly into #493's branch, folding the fix in before #493 itself merged --- exactly the outcome stacking was meant to produce.)

## Use the existing PR branch, not the harness-specified branch --- A stacked PR reaches that bloated state with no push of yours at all, and it announces...

(Morrison-Lab/ai-config#957 → #974, 2026-07-31: #974 sat untouched while #957 squash-merged as `3893dd51`.
The rebuild restored `+82/-0` over 2 commits and `mergeable_state: clean`, and both cherry-picks applied without conflict.)

## Use the existing PR branch, not the harness-specified branch --- A live variant of the same check: the human can merge the branch's PR out from under...

(`UCD-SERG/serocalculator#568` → `#572`, 2026-07-20: pushed a `Var(y_obs | y_true)` derivation commit just as #568 merged;
recovered by cherry-picking it onto a new branch off `main`, filing #571 to track the follow-on `Var(y_obs | T=t)` derivation it was a prerequisite for, and opening #572 stacked on nothing but current `main`.)

## Use the existing PR branch, not the harness-specified branch --- A live variant of the same check: the human can merge the branch's PR out from under... (2)

(`ai-config#778` → `#783`, 2026-07-28: the squash-merge counterpart.
A commit fixing a review nit was mid-push when #778 merged;
`git push` printed `* [new branch]`, `git merge-base --is-ancestor` returned false, and `git show origin/main:<path>` confirmed the fix was absent from `main` --- so a PR comment claiming the nit was addressed would have been false.
Recovered by cherry-picking onto a fresh branch off current `main` and opening #783, with a comment on #778 saying which of its findings did not ship in that merge.)

## Use the existing PR branch, not the harness-specified branch --- A live variant of the same check: the human can merge the branch's PR out from under... (3)

(`Morrison-Lab/ai-config#986`, 2026-07-31: the review posted a verdict plus a
non-blocking inline finding at head `147ee69` at `23:08:35Z`, the PR merged at
`23:27:15Z`, and the fix for that finding was pushed as `7416b16` at
`23:32:46Z`, five minutes later.
`git merge-base --is-ancestor 7416b16 origin/main` returns non-ancestor, and a
whitespace- and backtick-normalized comparison found 25 of the commit's 26
prose additions absent from `main`, so the finding shipped unaddressed.
The PR's timeline records "deleted the ums/push-reported-success-wrong-ref
branch" at `23:27`, so the branch was already gone when that push ran and the
push recreated it, which is the `* [new branch]` case.
Three head branches merged around the same time
(`chore/claude-review-v2-pin`, `docs/fully-clean-verdict-measurement`,
`ums/prose-count-adjacent-to-block`) no longer resolve; this one does, at
`7416b16` rather than at the merged head `147ee69`, which is the recreation.
The push's own output is not in the record, so whether it was read and
misjudged or never read at all cannot be established.
What is in the record is a later comment on that thread asserting the tell was
unavailable here, which each of these checks refutes.
Recovered as #1003.)

## Use the existing PR branch, not the harness-specified branch --- The harness-assigned branch name itself can already exist locally, pointing at...

(ai-config#481: the assigned branch name `claude/resolve-pr-481-conflicts-dz9v4w` already existed locally, pointing at a commit that turned out to be an ancestor of `main` from an earlier session --- switched to the actual PR branch instead, per this section's own primary rule.)

## Use the existing PR branch, not the harness-specified branch --- A PR whose head branch lives in a different repo entirely (not just a scope-restricted...

(`d-morrison/altdoc#20` → `#22`, 2026-07-14: `#20` compared `etiennebacher/altdoc:main` against the fork's `main` and hit a real `NEWS.md`/`tests/testthat/helper.R` conflict with no push access to fix it on that PR;
`#22` redid the sync from a fork-local branch and merged clean.)

## Do the review yourself when the @claude workflow doesn't produce a verdict --- Stub review

(Hit repeatedly on gha#193/gha#198, where `claude-review` produced escalating permission-denial-driven stub reviews across many runs before the actual fix --- a same-prompt retry composite, gha#201 --- landed.)

## Do the review yourself when the @claude workflow doesn't produce a verdict --- No review workflow configured at all is a third failure mode, and the one nothing...

(2026-08-06: MRs pushed to two sibling GitLab repos on the same afternoon.
One included its own `@claude` review template and produced a genuine
auto-review within a minute of the push.
The other's `.gitlab-ci.yml` `include:` list omitted the template entirely,
so its MR sat with a green pipeline and zero review comments until the gap
was checked for directly rather than assumed absent.)

## Do the review yourself when the @claude workflow doesn't produce a verdict --- Post the self-review before doing anything else --- don't stall the PR waiting for the...

(`ucdavis/epi204`#361: attempt 1 and its automatic same-run retry both stubbed;
self-reviewed and posted a verdict;
a manual `rerun_failed_jobs` on that same workflow run then produced a genuine review --- and it wasn't a rubber stamp, it caught a real one-sentence-per-line violation the self-review's own added text had introduced.)

## Do the review yourself when the @claude workflow doesn't produce a verdict --- A fallback self-review is prone to being shallow, so hold it to the same bar as the...

(Morrison-Lab/ai-config#1092, 2026-08-03: a FALLBACK self-review was posted while `claude-review` was erroring on infra failures, and it reported "no findings / ready" while missing two content bugs the recovered bot then caught.
One was a false mechanism claim --- the prose said a directional-word grep "passes because the direction ('above') stays right", when that grep's word list is exclusively forward-pointing and never evaluates "above" at all.
The other was a misattributed citation --- prose credited a "name the target, don't count to it" preference to `shared/writing/definition-crossrefs.md`, which is about formal Quarto crossref-div ordering and says no such thing.
Both are semantic errors that escape mechanical checks, which is the very subject the reviewed section was about;
the self-review had run the structural checks and not `fact-check-prose`.)

## Watch and ARDI every PR you touch --- don't ask first

(Hit on ai-config#406: posting the mention right after a push canceled the review and cost three extra polling rounds to recover.)

(Corrected 2026-08-25, Lacaedemon/sparta#1397: after a line-break fix the session answered "no, I was not monitoring" and declined to start a persistent loop because the user had only asked a status question.
Subscribe-or-babysit plus a one-shot poll still read as compliance from the inside.
The standing yes lives in `AGENTS.md`, not only in this Claude manual.)

## Use subagents when helpful --- and delegate rather than queue --- Research and reading are dispatchable by default, and the test is the size of the...

(2026-07-30, a `ucdavis/bcs` session: recaps repeatedly closed with "I still owe you a PR for X" and "I owe a UMS pass", carried across many turns, with the user having to ask again before several of them started.
Each was independent of the critical path.
The directive was "when you think you 'owe me' something, ask yourself, should I have dispatched it to a subagent already?"
The reading half surfaced separately, when the user asked why fetching and digesting a Wikipedia article had not been dispatched --- a question no output could have prompted, since the article had been read correctly.)

## Detect concepts defined only in prose, never formalized

(Found by hand on `d-morrison/rme#706`: a "conditional predicted risk" quantity introduced only as plain prose right before two definitions that depended on it, and a "collapsibility bias" concept defined in one sentence crammed inside a *different* concept's definition div.)

## Detect hypothetical examples where real data is already available

(Found by hand on `d-morrison/rme#706`: a logistic-regression chapter's worked examples used invented covariate-specific risks and made-up exposure proportions throughout, even though the chapter already loads and fits models on its real running WCGS dataset elsewhere.)

## Encoding reusable feedback into ai-config --- Put the memory in the repo where it belongs, and don't wait for confirmation to do it

(Corrected 2026-08-03: after an rpt workflow migration, two reusable learnings were saved to session-local auto-memory and then *offered* for upstreaming rather than committed.
The directive was "always put memories in the repos where they belong;
don't wait for confirmation.")

