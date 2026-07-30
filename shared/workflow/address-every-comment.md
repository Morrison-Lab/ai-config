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

**The PR description is on that list and is the one copy grepping the diff
cannot find, so check it separately.**
A PR body is not a file, so it appears in no diff and no reviewer reads it as
part of the change under review.
That makes it the copy most likely to survive a fix, and the copy most
likely to be *read* by someone deciding whether to merge --- so a stale one
teaches the reader exactly the thing the diff was corrected to remove.

The tell is a fix to something the PR body summarizes: a behaviour change, a
mechanism, a rationale.
Re-read the description against the corrected diff before declaring the round
done, and say in the update that it was corrected, so a reader who saw the
original knows it was revised rather than always having said this.
Where the correction has history worth keeping --- a claim that was wrong and
is now right --- state it as history in the body rather than silently
overwriting, since the wrong version is what earlier comments respond to.

- **Do:** re-read the PR description after any Address that changes what the
  PR does or why, alongside the changelog check above.
- **Don't:** treat a clean `grep` over the diff as evidence every paraphrase
  is synced --- the description was never in it.

(ai-config#829, 2026-07-29: a review nit led to correcting a gha#350
attribution in `memories/github-actions.md`.
Both reviewers then approved, and the PR body still carried the original
wrong claim verbatim --- "`continue-on-error` there, the dropped implicit
`success()` here" --- because it had been written before the correction and
was not part of the diff either reviewer read.
Caught only while assembling the ready-for-merge summary.)

**Following that "state it as history" advice is what produces the next
block, because an automated reviewer reads the body as a flat statement of
intent.**
The paragraph above is right that a correction with history worth keeping
should be recorded rather than silently overwritten, since earlier comments
respond to the old version.
It has a failure mode it does not warn about, and the failure lands precisely
on the authors who follow it.

A past-tense paragraph saying a thing *was* excluded is, to a bot, not
distinguishable from a claim that it *is* excluded.
Tense is doing all the work, and nothing in the reviewer's reading of the
document preserves it.
So the more faithfully the reversal is recorded, the more confidently the
reviewer reports the diff as contradicting its own description --- and the
remedy it proposes is to revert the change, which means undoing whatever the
reversal was.

Distinguish this from an ordinary stale snapshot before answering.
A reviewer that started before your edit never saw the correction and needs
only a pointer to it.
The timestamp check further down is written about a missed *rebuttal*, but
the same `started_at` comparison decides a missed *body edit*: a body
corrected after the run began is invisible to it for exactly the same
reason, since the whole PR is snapshotted once at run start.
This one re-raises *at the corrected text*, so the timestamps clear and the
finding still stands.
Compare the run's start time against the edit, then read which passage the
new verdict quotes --- if it is quoting your history section, this is the
case, not that one.

- **Do:** state the current content first, marked as current, before any
  history.
- **Do:** put the reversal in its own section that opens by saying it is
  history.
- **Do:** make sure the "what is excluded" section does not name the reversed
  item at all, in any tense.
- **Don't:** rely on past tense alone to carry the distinction.
- **Don't:** revert a maintainer-requested change because a reviewer read the
  history as current --- rebut, and escalate rather than comply.

Be honest about the residual: all of that can be applied and a further run
can still block, at which point the only remaining move is deleting the
history outright, which costs the earlier comments their referent.
That trade belongs to the human, not to the agent driving the PR.

(Morrison-Lab/ai-config#843, 2026-07-30: the maintainer asked for a fourth
tool on an allowlist that had shipped with three.
Jules blocked twice.
The first was an ordinary stale snapshot --- its run started at `02:56:28Z`,
two seconds before the body was corrected.
The second re-ran at `03:00:31Z` against the corrected body, with a new
session id and a different cited line number, read the reversal-history
section, and praised the description for "explicitly documenting which
permissions should be intentionally excluded" while demanding the requested
tool be removed.
`claude-review` saw the same inconsistency at the same stale head and graded
it a minor, explicitly non-blocking prose note.
Escalated; the human merged past it.)

**The same sync is needed when the review fix is to CODE BEHAVIOR rather than
to wording --- and that case is easier to miss, because nothing about fixing a
bug points at the changelog.**
The rule above fires on a recognizable trigger: a reviewer quotes a phrase, so
you go looking for that phrase.
A behavior finding gives you no phrase to grep.
You change the code, update the PR body's description of what it now does, and
the `NEWS.md`/`CHANGELOG.md` entry --- written before the review, in prose that
described the *old* behavior correctly --- goes on asserting it.
Every later round then reviews a diff whose changelog contradicts its own code,
and no reviewer flags it, since each file reads plausibly on its own.
The shipped result is worse than a stale paraphrase: a user reading the release
notes is told the opposite of what the release does.
So after any Address that changes behavior, re-read the PR's changelog entry
against the new behavior --- not just the code and the PR body.
Fold it into the same pre-push self-review pass [`ardi`](ardi.md) already
requires; a changelog entry is a claim about the diff, so
[`fact-check-prose`](../writing/fact-check-prose.md) applies to it exactly as
it applies to any other prose in the PR.
(d-morrison/altdoc#78, 2026-07-27: review round 2 established that mkdocs
serves `/man/foo/`, not `/man/foo.html`; the code and the PR body were
corrected that round, while `NEWS.md` kept saying links point at `.html` under
"`mkdocs` and `quarto_website`" through two further clean review rounds.
Caught by a `main`-sync merge conflict that happened to land in that entry ---
not by any review, and not by any check.)

**Tighter still: a changelog entry can contradict its own commit message, in
the same commit, with no review in the loop at all.**
Both cases above need a review round to set them up --- a reviewer quotes a
phrase, or a finding changes behaviour --- so the trigger to go looking is
external.
Here there is none.
The commit message and the changelog entry are written minutes apart, by you,
in the same commit, and disagree.

The reason it survives is that the two are drafted in different registers.
A commit message argues for the change and reaches for the sharpest true
statement of the mechanism; a changelog entry describes the change for a
release note and reaches for the tidiest one.
Nobody reads them side by side afterwards.
A diff review sees one, a `git log` sees the other, and no check compares
them --- so the contradiction ships, and the release notes are the half a
user actually reads.

The check is mechanical and belongs in the pre-push self-review pass
[`ardi`](ardi.md) already requires: after writing a rationale into a commit
message, grep that same commit's prose changes for a claim about the same
mechanism, and read the two together before pushing.
Where they differ, the commit message is usually the correct one, because it
was written while the mechanism was in front of you.

(`ucdavis/bcs#463`, 2026-07-30: `a0f4113d`'s commit body said `update_trigger`
"can set `enabled: false` and rewrite a routine's prompt and cron outright".
The `NEWS.md` entry edited by that same commit justified excluding a different
tool on the grounds that the allowed set only changes *when* routines run ---
which the commit body directly refutes, and which is wrong about
`create_trigger` too, since it authors a whole new routine.
Caught by `claude-review` as an inline finding, not by any check, and the
correct framing turned out to be deferred versus immediate effect.)

**One step further back: a figure inherited from the tracking issue is both
the copy git keeps and the copy nobody verified.**
The entry above explains a mismatch by *register* --- a commit message argues
for the change while a changelog describes it, so they get drafted differently
and never read together.
Here both claims sit in the same register and describe the same fact.
Only one of them was checked.
What separates them is **provenance**: a number produced by running something,
versus a number carried over from the issue you wrote before you had anything
to run.

Two properties make it worse than an ordinary wrong number.

One of the two copies becomes permanent, and you cannot tell which from
inside the PR.
A PR body stays editable forever, while a commit message does not survive a
merge in editable form --- but which text a squash merge actually keeps is a
repository setting, and it can be either.
Configured one way the commit messages land on `main` and the PR body is
discarded; configured the other the PR body becomes the commit body and the
commit messages are dropped.

That is why the rule is *both must be right* rather than *check the important
one*.
The copy that survives is chosen by a setting most authors have never looked
at, so treating either as the draft is a coin flip.
And the odds are not even: the commit message is the one written earliest,
from the least evidence, so the configuration that keeps it is the one that
makes the weaker copy permanent.

Read a recent squash commit on `main` if you want to know which way a given
repo is set --- `git log -1 --format=%B <a squash merge>` shows it directly,
and beats reasoning about settings pages.
(Checked this way on this repo, 2026-07-30: `5670f9f`, the squash of
[#855](https://github.com/Morrison-Lab/ai-config/pull/855), carries that PR's
commit message rather than its body.
So here the weaker copy is the one that persists.)

And verifying once feels like verifying.
Running the check for the PR body produces a real sense of having established
the fact, which is what stops you checking the other place it appears.
The verification is genuine; the coverage is not.

Note the shape is the same as [`ardi`](ardi.md)'s "an instruction's own
suggested code is not exempt", one artifact over: content inherited from a
planning document does not feel authored, so the checks you apply to your own
claims do not fire on it.

- **Do:** re-run the check when a figure moves from an issue into a commit
  message, even having verified it once for the PR body.
- **Do:** read `git log -1 --format=%B` before pushing, against the same
  source the body's claims came from --- a commit message is not greppable
  from the working tree once written.
- **Don't:** copy a count, version, or path out of the tracking issue on the
  strength of having written that issue.
- **Don't:** treat "permanent in history" as settled while the PR is
  unmerged --- `git commit --amend` still works, and is usually worth a fresh
  CI round against a wrong figure reaching `main`.

(`ucdavis/bcs#465`, 2026-07-30: a submodule-pin bump whose PR body said
`CLAUDE.md` resolves 33 `@.ai-config/...` imports and whose commit message,
written minutes apart, said 25.
33 came from a script; 25 came from the tracking issue, written from
recollection.
Review named the mechanism exactly --- inherited from the issue rather than
re-checked against the file --- and graded it non-blocking on the grounds that
it was already permanent, which was the one part that was not yet true.)

**A corollary for checking any of this in a semantic-line-break corpus: a
single-line `grep` returns false negatives on your own prose.**
The instruments above and elsewhere in this file assume you can search for a
phrase you wrote.
In a corpus that mandates one clause per line, a phrase of any length
routinely spans a newline, so `grep 'flat statement of intent'` reports zero
against a file that plainly contains it.
The failure direction is the dangerous one: a missing-content check that
answers "absent" when the content is present reads as a merge having dropped
your work, which invites re-doing something already done.
Normalize whitespace before matching --- read the file, collapse `\s+` to a
single space, then search --- rather than trusting a line-oriented tool
against deliberately broken lines.
(Same day, verifying that
[#855](https://github.com/Morrison-Lab/ai-config/pull/855) had landed: two of
three greps reported present and the third reported absent, purely because
that phrase happened to straddle a line break.)

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

**The same check applies to a fix a reviewer describes in prose rather than
in a `suggestion` block, and the sharpest test is the reviewer's own
example.**
A finding that ships a concrete repro case has handed you a test fixture:
run the proposed fix against that very case before adopting it.
A reviewer reasoning about a fix in the abstract can propose one that is
directionally right and still insufficient -- it closes the failure mode
they named while leaving the case they cited broken -- and adopting it
verbatim converts their partial diagnosis into your shipped bug, with the
review thread reading as though the item were settled.
When the proposed fix falls short, prefer eliminating the failure mode
outright over layering another patch onto it, and post the evidence
(the fix applied to their example, and what it still produces) rather than
just asserting it was insufficient.
(gha#318, 2026-07-26: a review correctly found that a heredoc-terminator
regex lacked an end-of-line anchor, and suggested adding one.
Tested against the reviewer's own indented-`EOF` example, the suggested
anchor still truncated the body, because the terminator's leading `[ \t]*`
accepted a space-indented closing line real bash rejects.
Matching whole lines against the tag -- how bash itself ends a heredoc --
removed the whole lazy-quantifier/anchor failure mode instead of narrowing
it; the reply carried the failing output of the suggested form.)

**And the mirror case: a finding can be wrong on its stated grounds while
still pointing at something real.**
The two bullets above check the reviewer's *fix*; this one checks their
*premise*.
A confidently reasoned factual claim -- this pattern is valid, that value is
in range, this call is safe -- invites one of two lazy responses: accept it
because it sounds authoritative, or dismiss the whole item once you notice
the claim is false.
Both lose information, because a reviewer usually arrives at a wrong premise
while looking at something that genuinely bothered them.

So reproduce the claim before answering it, and answer the concern
separately from the premise.
When the premise turns out to be false, say so with the command and its
output rather than by assertion, and then address what prompted it anyway --
a reader who tested your example and got a different result has a real
problem even if their explanation of it was wrong.
Expect the corrected mechanism to be more useful than the original text:
a premise worth disputing usually sits on something you had not fully
explained.
(ai-config#756, 2026-07-28: a review held that `[\x{2014}]` is valid PCRE
and so could not produce the "code point value too large" error the fragment
described, and proposed an out-of-range `[\x{110000}]` instead.
Running it showed the original failing exactly as written -- the cause is
the locale, since PCRE in non-UTF mode rejects any `\x{}` above `0xFF`, and
the same command succeeds under `LC_ALL=C.UTF-8`.
The proposed replacement would have been worse, failing unconditionally and
hiding that environment-dependence, which is the whole reason the swallowed
error is dangerous.
The reviewer's actual worry -- that a reader might not reproduce it -- was
right, and sharper than stated.)

**When a finding cites a source, read the cited source before reproducing
anything -- it is the cheaper instrument, and it is the one that can show the
finding backwards rather than merely unsupported.**
The bullet above says to reproduce the claim.
That is right, and it is the second thing to do when a citation is on the
table, because reproduction tests the *behavior* while the citation tests the
*reasoning*, and only the second can catch a finding whose own evidence
contradicts it.
A citation is also the most persuasive part of a review and the least likely
to be checked: a linked changelog entry reads as settled fact, so the finding
inherits authority it never earned, and a one-click `suggestion` block turns
that borrowed authority into an applied edit.

Grep the cited document for the mechanism the finding names.
One command usually decides it, which makes this an
[`algorithmatize-checks`](algorithmatize-checks.md) case rather than a
judgment call, and a fabricated mechanism produces a clean zero-hit result
that is hard to argue with.
Then quote the entry in the reply rather than paraphrasing the disagreement,
and reproduce the behavior as the independent second leg.

Do not stop at winning the point.
A finding that misread a source usually did so because the claim it
questioned had nothing checkable next to it, so fold the citation into the
file itself, per [`fully-clean`](fully-clean.md)'s note that a fresh review
run re-derives from scratch and will not read the thread.
(ai-config#762, 2026-07-28: a review held that
`htmlwidgets::saveWidget(selfcontained = TRUE)` no longer needs pandoc,
citing htmlwidgets 1.6.0 as having "switched to `base64enc::dataURI()`", and
supplied a suggestion block deleting the `rmarkdown::pandoc_available()`
gate.
`grep -inE 'pandoc|base64'` over that NEWS file returned six pandoc hits and
zero base64 hits, and the 1.6.0 entry says the path "now uses the
`{rmarkdown}` package to discover and call pandoc" -- so the citation
established the opposite of the finding, and incidentally made the gate the
*same lookup* htmlwidgets performs rather than a proxy for it.
Applying the suggestion would have removed the only warning before a hard
error, in the one step that exists for running headless.
The reviewer accepted the rebuttal on the next round and called its own prior
claim a hallucination.)

**When a reviewer hedges a finding because it depends on code it cannot
see, check whether *you* can see it --- the hedge is an invitation, not a
verdict.**
Automated reviewers work from the diff, so a finding that turns on a
reusable workflow, a dependency's internals, or another repo's behavior
arrives with language like "moderate rather than high confidence",
"depends on behavior not visible in this diff", or "worth the author
confirming intent".
That hedge is a fact about the *reviewer's* visibility, not about how
likely the finding is.
You frequently have access it lacks: the repo cloned locally, a pinned
dependency vendored in, or permission to fetch the source.

Reading it converts a maybe into a settled yes or no, and that changes
the disposition.
Confirmed, it earns a fix or a precisely-scoped follow-up issue with the
mechanism recorded; disproved, it earns a Rebut with evidence instead of
a vague "I think this is fine".
Either way the next reader is spared re-deriving it.
Quote the specific lines you checked, since a follow-up issue that merely
repeats the reviewer's hedge is barely more useful than the review
comment it came from.

(`UCD-SERG/serodynamics#274`, 2026-07-28: a review flagged possible
duplicate review dispatch at moderate confidence, explicitly because the
reusable workflow in `d-morrison/gha` was not visible to it.
That repo was cloned locally.
Reading both matchers showed the reusable fires on `@claude[[:space:]]+review`
and the local job on a punctuation-tolerant superset, so the plainest
phrasing --- `@claude review` --- matches both and dispatches twice.
The follow-up issue could then record the exact overlap table and note
that the upstream gap motivating the local job had since been closed,
making "broaden upstream, delete the local job" a real option.)

**Timestamp the evidence before rebutting a finding with it --- during a live
incident, a log from twenty minutes ago describes a different system.**
The bullets above all say to verify a finding rather than accept it, and they
assume verification is a fixed target: read the source, run the command,
reproduce the case.
That assumption quietly fails while something is actively breaking, because
the evidence you gather is a *measurement*, and measurements expire.
Re-reading an existing CI log feels like verification --- it is concrete, it
is specific, it is right there --- but it only tells you what was true when
that job ran.

The tell is a rebuttal whose evidence you did not generate yourself in this
turn.
A log you fetched, a check-run conclusion you read, a status you were told
about: each carries a timestamp, and the question is whether anything could
have changed since.
When the finding is *about* an outage, a migration, a permission change, or
anything else in flight, the answer is almost always yes.

So prefer evidence you can regenerate now over evidence you can only cite.
Re-running the failing thing is usually cheap and settles it outright --- and
in the best case it produces the cleanest possible proof, two attempts of the
same run on the same commit disagreeing, which no amount of reading could
have given you.
When regenerating is genuinely not possible, say how old the evidence is in
the rebuttal itself, so the reader can weigh it.

This matters more than an ordinary wrong rebuttal because of who it lands on.
Telling an author their diagnosis is contradicted by the logs is a strong
claim that invites them to stop investigating.
Getting it wrong can stall a correct fix for the exact bug still breaking
everything.
(gha#351, 2026-07-28: a PR correctly diagnosed that Actions had stopped
resolving `uses:` after a repo transfer.
Its premise was disputed on the strength of two run logs showing the
workflow resolving fine --- logs from 45 and 30 minutes before the PR was
opened, spanning the cutover.
Re-running one of those very workflows reproduced `startup_failure`
immediately, and the retraction had to be published in the same thread.)
