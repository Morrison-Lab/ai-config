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
