When iterating on a PR with a reviewer, **address every in-scope flagged item**,
regardless of severity label. The reviewer's "Not a blocker", "minor", "nit",
"optional", "consider", or "if you want" labels are for prioritization, not a
free pass for the implementer.

For each flagged item, do exactly one of:

1. **Fix it in this PR.** The default path --- most nits are 1--3 line changes.
2. **Defer.** Only when the fix expands the PR's scope (new feature, broader
   refactor, separate concern), the requester has explicitly said this PR
   shouldn't grow, or the flagged content isn't actually yours to fix here
   (see the `main`-sync case below). File a follow-up issue and reference it
   in a PR comment so the item isn't lost --- except in the `main`-sync case,
   where the "follow-up" is fixing it on `main` directly, not a new issue.

Then trigger another review and repeat until the PR is **fully clean** --- zero
flagged items under any heading, no "non-blocking", "harmless", "minor
observation", or "could improve" sections. "Looks good" / "no findings" /
"approved" with no follow-on bullets is the bar. Resolve every inline review
thread along the way, leaving only the final all-clear exchange.

**Always resolve an inline thread the moment its comment is successfully
addressed** --- the fix pushed and a reply posted naming it --- in the same
pass, whatever workflow you're in: a formal `ard`/`ardi` round, a CI-monitor
nudge, or a one-off fix outside any loop. Addressing without resolving leaves
a thread that reads as outstanding work to every later reviewer, blocks
[`fully-clean`](fully-clean.md)'s every-inline-thread-resolved criterion, and
drags stale noise into the next review round. The per-disposition settlement
rules in `ard` step 4b still govern the exceptions: a **Rebut** stays open
until the reviewer drops it, and an **Address** you're not confident fully
settles the concern gets a reply asking for confirmation instead of a
resolve. The `resolve-pr-threads` skill sweeps any stragglers, but it's a
backstop --- resolve-on-address is the default, not a cleanup step.

Do **not** report "ready to merge with one minor nit noted" / "harmless as-is" /
"can address if you want" --- that hedging just pushes triage back to the
requester. If after 3--4 rounds the reviewer keeps generating new nits each
cycle (asymptotic noise), surface that and ask whether to keep going or accept
the current state.

**Noise is per-item, not per-round --- don't stop the whole loop over one
recurring flag.** A long-running PR can have both real findings (worth fixing
every round) and one specific item the reviewer re-raises verbatim round after
round even though it's already deferred/tracked (e.g. a file-length guideline
already split into a follow-up issue). Keep fixing every *new* finding as it
appears --- don't let the recurring item make you stop processing genuinely
new ones. But stop re-litigating *that one item* every round: reply once
pointing at the tracked issue, and hold on it specifically rather than
re-deferring it on each pass. Surface the pattern to the user (which item, how
many rounds, where it's tracked) and let them decide whether to resolve it now
(e.g. do the split) or leave it as accepted recurring noise --- don't decide
unilaterally to either keep re-processing it or silently drop it. (rme#706 ran
100+ review rounds: each round's *new* findings --- a missing derivation step,
a missing i.i.d. hypothesis, an unverified citation locator --- got fixed
every time; the one recurring file-length flag got a single reply-and-hold
each round until the user weighed in.)

**When a finding is a pattern (a formatting/style rule broken in one spot),
apply it everywhere it recurs in the same file, not just the flagged line.**
A reviewer that flags one inconsistent list-item format is telling you about
the rule, not just that one item --- fix every occurrence in the same file that
breaks it in the same pass, rather than waiting for the reviewer to flag each
occurrence in a separate round. Re-scan the whole changed file for the same
pattern before pushing the fix.

**When a prose fix changes wording that's also paraphrased elsewhere in the
same PR (a CHANGELOG entry, a PR description, a cross-reference), sync that
copy too.** A CHANGELOG entry written before the review lands often quotes or
paraphrases the exact phrase a reviewer later flags; fixing the source
prose but leaving the paraphrase stale reintroduces the same wording issue
one file over. Grep the diff for the flagged phrase before considering the
finding closed. (ai-config#373: fixed "routing/dispatch site" in the skill
per review, but the CHANGELOG entry still said it until a follow-up commit.)

**A flagged item that came in via a `main`-sync merge, not your own diff, is still a Defer --- just one where the follow-up is fixing it on `main` directly, not filing a per-PR issue.** This is not the ARD skill's "Acknowledge" disposition: `skills/ard/SKILL.md` reserves Acknowledge for praise or a no-ask observation, and explicitly warns against stretching it to dodge a real finding --- a redundant config line a reviewer flags is a real finding with an implied fix request, so it needs a real disposition, not a label that means "no change requested." When a reviewer flags something (a redundant config line, a stale pattern) inside a file your branch only touches because you merged `main` in to resolve a conflict, check provenance before fixing it: `git log`/`git blame` the flagged line, or just compare against `origin/main`'s current content. If it's identical to `main`, "fixing" it on your branch alone doesn't fix anything --- it just makes your branch disagree with `main` on unrelated content the next person to touch that file will have to reconcile again. Reply agreeing the finding is correct but out of scope for this PR, and leave it for whoever owns that file's actual content to fix on `main` directly --- no follow-up issue needed, since the fix target is `main` itself, not this PR's own change. (`UCD-SERG/serocalculator#503`: a review flagged `.Rbuildignore`'s `^\.posit/assistant$` as redundant with the existing `^\.posit$` pattern above it --- both lines had landed together in an already-merged `main` commit (#579), picked up via a routine `main`-sync merge, not introduced by #503's own diff. Deferred to `main` instead of fixed on the branch.)

**This generalizes to a skill's own inline restatement of a fragment it
links to.** A `SKILL.md` that links a backing `shared/` fragment for the
full detail often *also* restates the fragment's approach or word list
inline (in its `description` field, or a short procedure-step summary) so
a reader doesn't have to open the linked file. Fixing a bug in the
fragment doesn't automatically fix these inline restatements --- they're a
second, independent copy of the same claim, and a review round after the
fragment fix can catch them going stale exactly like a CHANGELOG paraphrase
does. Grep the whole PR diff for the fixed phrase/word-list, not just the
fragment file, before considering a fragment fix complete. (`ai-config#507`:
fixing `forward-references.md`'s regex left `fix-forward-references/SKILL.md`'s
own `description` field and Step 2 summary describing the old, already-fixed
approach --- caught in a second review round.)

**A bot that re-raises an item as "not addressed" may simply not have seen
your reply --- check the timestamps before treating it as an impasse.** An
automated reviewer gathers the PR's comments once, when its run starts. A
rebuttal posted after that snapshot is invisible to it, so the next round
reports the item as still open and unaddressed even though a substantive
reply is sitting in the thread. The tell is a re-raise that repeats the
original finding verbatim and speaks only to whether the *code* changed,
without engaging any argument you made. Before escalating, compare your
reply's timestamp against the review run's `started_at` (`gh run view <id>
--json startedAt`, or the `started_at` field each run carries in
`get_check_runs` when `gh` is absent): if the reply landed after the run
began, it is a stale re-raise, not a genuine disagreement.
Reply once pointing at the earlier rebuttal (link it directly --- the next
run will see it), and don't count that round toward the
rebuttal-didn't-convince-them test in `fully-clean.md`.

The ordering fix is cheap: when a round is Rebut-only, post the rebuttal
**before** anything that triggers the next review (a push, an `@claude`
mention), so it is in the snapshot the next run reads. When a round mixes
Address and Rebut, post the rebuttals first and push the code second, for
the same reason. (d-morrison/altdoc#34: a `\pkg{}` rendering rebuttal
carrying a `pandoc` run that disproved the finding's implied hazard was
posted about a minute before the follow-up review job started; that review
reported the item "wasn't addressed in `9398d5d`" and re-posted the
identical suggestion.)

**A finding can be right while its `suggestion` block is wrong --- verify
the suggested literal before applying it.**
A GitHub ```` ```suggestion ```` block is one-click-appliable, which is
exactly what makes an unverified one dangerous: the surrounding prose
argues for a change you agree with, so the concrete replacement rides in
on that agreement without being checked itself.
Treat any file path, version, flag, or command inside a suggestion as a
claim to verify, not as text to accept --- the same standard
[`fact-check-prose`](../writing/fact-check-prose.md) applies to the diff.
Accepting a bad literal is worse than ignoring the finding, because it
publishes a specific wrong value under the reviewer's apparent authority.
When the suggestion is wrong but its point stands, fix the underlying
issue your own way and say in the reply why the suggested form was set
aside --- silently deviating reads as having missed it.
(ai-config#726: a review correctly flagged that a `<path>` placeholder
didn't say where a script came from, but suggested
`<path-to-gha-checkout>/check-new-line-breaks.py` --- one directory level
too high, since the composite action's directory and the script inside it
share a name. `git ls-files` in the gha checkout settled it in one command.
Applying the suggestion verbatim would have documented a nonexistent path
in the entry whose whole purpose is getting someone to run that script.)
