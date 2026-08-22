When iterating on a PR with a reviewer, **address every in-scope flagged item**,
regardless of severity label. The reviewer's "Not a blocker", "minor", "nit",
"optional", "consider", or "if you want" labels are for prioritization, not a
free pass for the implementer.

Extended rationale --- the mechanism, evidence, and argument behind
each rule below --- lives in
[`address-every-comment.rationale.md`](address-every-comment.rationale.md),
moved out of the auto-loaded context.
Each rule here keeps its statement and its Do/Don't pair;
read the companion when the reasoning or the evidence is the question.

Worked-example case records for the rules below live in
[`address-every-comment.cases.md`](address-every-comment.cases.md), moved out of the auto-loaded context.

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
requester.

**A round count is never a reason to stop, and "the reviewer keeps finding
things" is not a finding about the reviewer.** There is no threshold after
which unaddressed items become acceptable: keep requesting reviews and keep
dispositioning findings until a review comes back with none. The only exits
are a totally clean review, a genuine per-item deadlock, or the user calling
it. Reasoning of the form "we have done N rounds, shall we accept the current
state?" is the same hedging this paragraph bans, moved up from one finding to
the whole loop --- see
[`ardi`](../../skills/ardi/SKILL.md)'s "Stopping conditions" for why it fails
and for the case record.

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
unilaterally to either keep re-processing it or silently drop it.

**When a finding is a pattern (a formatting/style rule broken in one spot),
apply it everywhere it recurs in the same file, not just the flagged line.**

**That rule's scope is "the same file", and a reviewer who enumerates the sites
is the reason the scope goes unquestioned.**

- **Do:** derive the site list by grepping the whole diff for the flagged
  phrase, and fix what the grep returns.
- **Do:** report the sweep --- the pattern searched and the hit count ---
  rather than the number of sites you fixed.
- **Don't:** treat a reviewer's enumeration as the extent of the pattern; it is
  the extent of that reviewer's read.
- **Don't:** write "all N spots you named" into a reply, since quoting the
  reviewer's count is the tell that no sweep ran.
- **Don't:** read a null result as "no further sites"; it means no further hit
  for that pattern, and a differently-worded instance would not have matched.

**The remedy above names a search space --- "the whole diff" --- and a stack has one of those per branch.**

- **Do:** run the derived sweep over every branch in the stack, and report the per-branch counts.
- **Do:** treat a finding that names a convention as scoped to the work rather than to the PR it was filed on.
- **Don't:** read "the whole diff" as satisfied by the diff of the PR the reviewer commented on --- that is one of N.

See [`address-every-comment.cases.md`](address-every-comment.cases.md),
"A finding's site list spans every branch in the stack".

**Deriving the class is necessary and not sufficient, because you can derive the
wrong one --- and the growth rate across rounds is what says so.**

- **Do:** read growth in the list across rounds as evidence about the lever, not
  as a count of members still to add.
- **Do:** state a reviewer's diagnosis back in your own words before acting on
  its examples, so a redirect cannot be worked past in silence.
- **Do:** relax the enumeration and read which cases move --- a property shared
  among them names the axis.
- **Don't:** treat "I derived the class rather than fixing the reported
  instances" as discharging the rule above; it is that claim one level up, and
  it fails the same way.
- **Don't:** prefer the actionable half of a review to the diagnostic half
  merely because it is the half you can start on.

**A narrower version of the same failure: the class is right, and it is
enumerated in more than one place.**

- **Do:** paraphrase the last two or three findings into a single sentence, and
  read a match as evidence that a concept is duplicated rather than incomplete.
- **Do:** derive how many sites encode the concept, then consolidate them into
  one definition every site consumes.
- **Don't:** answer a third instance by extending a third list --- that is the
  same round again with a new door.
- **Don't:** skip the review's own prose naming a sibling site; it is frequently
  there, in the paragraph explaining why some other mechanism did not save you.

**The mirror case: the enumeration was complete and the fix was not.**

- **Do:** count the artifacts a single comment names, and give each one its own
  disposition before replying.
- **Do:** read the rendered page rather than the diff when confirming that a
  prose or formula fix landed completely.
- **Do:** grep the whole file for the underlying concept once a second half
  surfaces --- a document stale in two places is usually stale in three.
- **Don't:** let a visibly-changed flagged line stand in for the finding being
  closed; the unfixed half appears in the diff as context.
- **Don't:** reach for the derive-the-site-list remedy above here --- that list
  was complete, and the shortfall was in the delivery.

**When a prose fix changes wording that's also paraphrased elsewhere in the
same PR (a CHANGELOG entry, a PR description, a cross-reference), sync that
copy too.** A CHANGELOG entry written before the review lands often quotes or
paraphrases the exact phrase a reviewer later flags; fixing the source
prose but leaving the paraphrase stale reintroduces the same wording issue
one file over. Grep the diff for the flagged phrase before considering the
finding closed.

**A scope-widening fix makes its stale copies invisible to every diff-scoped
sweep, so there the search space is the whole file, not the diff.**
The whole-diff rules below are right for a fix that changes a claim's
wording: the synced copies entered the diff when you edited them.
A fix that *broadens* a concept's scope inverts that.
The restatements that are now too narrow are precisely the lines the fix did
**not** touch, so they appear in the diff as context or not at all, and an
added-lines sweep structurally cannot see them --- it reports a confident
zero over exactly the population the finding is about.
Grep the whole file (and any file restating the concept) for the concept
that widened, and read each hit against the new scope.

- **Do:** after a broadening fix, sweep every restatement of the concept in
  the whole file, not the diff's added lines.
- **Don't:** read a clean added-lines sweep as closing a broadened-scope
  finding --- the stale copies are unchanged lines by construction.

(Morrison-Lab/ai-config#1490, 2026-08-15/16: rounds 1, 2, and 4 each found a
sentence still Copilot-only after the surrounding passage was broadened to
cover human reviews.
The round-2 fix swept the diff's added lines for `Copilot` --- 17 hits, all
legitimately Copilot-specific --- and round 4 still found an un-broadened
copy in the `## Output` section, because that copy was an unchanged line the
added-lines sweep could never have matched.)

**When syncing copies, search the diff for the claim, not the files or symptom
already in front of you.**

- **Do:** run whole-diff searches for synchronized figures and phrases, after
  committing the fix, and report the before/after counts.
- **Do:** when a rationale is retired, search for every wording that states that
  rationale or criterion, not only for the symptom word that made it fail.
- **Don't:** substitute `grep -rn <term> <files-you-had-open>` for grepping the
  diff.
- **Don't:** accept a search for the visible contradiction as proof that the
  retired claim itself is gone.

**When the wrong thing is a figure, the unit of repair is the figure --- across
every artifact carrying the twin, not just the diff.**

**And a reflow puts its neighbouring sentences into your change, for
fact-checking and not only for lint.**

- **Do:** grep for the figure's value across every artifact carrying the twin,
  before replying that the finding is closed.
- **Do:** fact-check the sentences a reflow pulled into your diff, exactly as
  you would the ones you wrote.
- **Don't:** treat the named occurrence as the unit of repair when the same
  value appears elsewhere.
- **Don't:** read a clean whole-diff grep as covering a twin the diff never
  touched.

See [`address-every-comment.cases.md`](address-every-comment.cases.md),
"The unit of repair is the figure, across every artifact carrying the twin".

**The PR description is on that list and is the one copy grepping the diff
cannot find, so check it separately.**

- **Do:** re-read the PR description after any Address that changes what the
  PR does or why, alongside the changelog check above.
- **Don't:** treat a clean `grep` over the diff as evidence every paraphrase
  is synced --- the description was never in it.

**Answering a body-staleness finding with a correction comment does not clear
it, and this corpus's own visible-correction convention is what makes that
move attractive.**

- **Do:** edit the body **and** record the correction inside it, so nothing is
  silently overwritten and earlier rounds still resolve.
- **Don't:** answer a body-staleness finding with a comment --- the next
  reviewer re-reads the body, so the finding survives it.
- **Don't:** treat the drift risk in rewriting a long body as a reason to leave
  it; re-deriving every figure is what the round already requires.

See [`address-every-comment.cases.md`](address-every-comment.cases.md),
"A body-staleness finding is answered by editing the body".

**A body that reports volatile external state goes stale with no edit of
yours, so the trigger above never fires on it.**

- **Do:** describe the change, and let CI report CI.
- **Do:** timestamp and scope any status you must state ("red as of `<sha>`,
  cause was X"), so it cannot be read as a present claim.
- **Don't:** put current CI status, mergeability, or a blocker in a PR body
  undated --- the body is the one place nothing re-measures.
- **Don't:** expect the "after any Address" trigger to catch it; that fires
  on your edits, and this goes stale without one.

**Following that "state it as history" advice is what produces the next
block, because an automated reviewer reads the body as a flat statement of
intent.**

- **Do:** state the current content first, marked as current, before any
  history.
- **Do:** put the reversal in its own section that opens by saying it is
  history.
- **Do:** make sure the "what is excluded" section does not name the reversed
  item at all, in any tense.
- **Don't:** rely on past tense alone to carry the distinction.
- **Don't:** revert a maintainer-requested change because a reviewer read the
  history as current --- rebut, and escalate rather than comply.

**The same sync is needed when the review fix is to CODE BEHAVIOR rather than
to wording --- and that case is easier to miss, because nothing about fixing a
bug points at the changelog.**

**Tighter still: a changelog entry can contradict its own commit message, in
the same commit, with no review in the loop at all.**

**One step further back: a figure inherited from the tracking issue is both
the copy git keeps and the copy nobody verified.**

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

**Correcting a flagged false claim means removing it, not adding a truer
sentence beside it.**
The natural fix for a false claim a reviewer named is to write the accurate
version near it --- a disclaimer above, a qualifying clause after.
That feels like correcting the wrong sentence.
It has not: the file now states both, and a reader who reaches the older
sentence gets the false claim back, with nothing marking it as superseded.
This is the review-response instance of
[fact-check-prose's insertion rule](../writing/fact-check-prose.md#an-insertion-asserts-something-about-the-whole-file-not-just-the-added-lines):
not a distant, unrelated sentence the author never noticed, but the very
sentence the reviewer just named.

This survives review because the check that would catch it asks the wrong
question.
Confirming the new, true sentence is present answers "did I write something
accurate", which a self-contradicting file answers yes to.
The check that can actually fail is the narrower one: grep the file for the
**original** wording, and require zero hits.

Where the old sentence is worth keeping as a record of why something was
done, keep it, but mark it explicitly as superseded rather than letting the
newer text imply a correction it never performed.
A commit message claiming to have "dropped" the false claim is itself a
checkable claim --- read the diff for a deletion of that line, not an
addition beside unchanged text.

- **Do:** delete or rewrite the flagged sentence itself, rather than adding a
  correction nearby that leaves it standing.
- **Do:** grep the file for the original wording after the fix, and require
  zero hits --- confirming the new wording is present is a different, weaker
  check.
- **Do:** mark superseded text as superseded, explicitly, when it is worth
  keeping as history.
- **Don't:** read "the file now contains a true sentence" as having addressed
  a finding about a false one.
- **Don't:** let a commit message assert a deletion that the diff shows as an
  addition beside unchanged text.

(Morrison-Lab/gha#578, 2026-08-22, review round 2: a source comment overstated
that "the checkout under review stays untouched."
Round 1 flagged the block for other reasons.
The fix added an accurate disclaimer a few lines above the overstated
sentence --- "guard rails, NOT a security boundary ... writes wherever the
runner account can" --- and left the overstated sentence itself standing.
Round 2 caught the resulting self-contradiction and noted that the commit
message's claim to have "drop[ped] the false boundary claim" was only half
true: it was contradicted, not dropped.
The actual fix deleted the sentence outright, and the next round's grep for
the phrase returned nothing.)

**A corollary for checking any of this in a semantic-line-break corpus: a
single-line `grep` returns false negatives on your own prose.**

**Inline markup breaks the same search, and that variant aims the false
negative at someone else's work rather than your own.**

- **Do:** account for inline markup as well as whitespace before concluding a
  quoted phrase is absent --- see the next block for which side to normalize.
- **Do:** read the single hit when a search for a citation's target returns
  only the citation itself.
- **Don't:** file a dangling-citation issue while the only evidence is a
  literal grep that found nothing but the citation --- that is the search
  failing, until a normalized one agrees.

**Apply whatever normalization you choose to the search term as well as to
the text, or the fix produces a third false negative of its own.**

- **Do:** normalize the needle with the identical function applied to the
  text, so the comparison is between two transformed strings.
- **Do:** re-test any earlier absent verdict after extending a normalizer,
  since the extension can break a term the previous version matched.
- **Don't:** enumerate which markup to strip and treat that list as the fix.
- **Don't:** test a raw search term against normalized text, however plain
  the term looks.

**Symmetry is necessary and not sufficient once the haystack is source code,
because a line-comment leader is inserted by the medium rather than by the
author.**
The rule above governs inline markup --- backticks, asterisks, underscores ---
which an author types *inside* a phrase, so stripping it with a character class
is the right shape.
A `##`, `#`, `//`, or `--` leader differs in two ways that each defeat that
class.
It appears at a **line start** rather than mid-token, so it interrupts a phrase
only where the phrase happens to wrap.
And `#` is not in the class at all, so applying the same normalizer to both
sides leaves it in the haystack and absent from the needle --- which is exactly
the asymmetry the rule was written to remove, arriving through a character
nobody enumerated.

The failure direction is the expensive one.
A verbatim phrase that *is* present reports absent, so the natural response is
to re-add content that was never missing.

Widening the class is the wrong repair, and the Do/Don't block one paragraph up
already says so: **don't** enumerate which markup to strip and treat that list
as the fix.
The rationale companion puts it more sharply --- "Enumerating is the wrong
shape, not merely an incomplete list."
Adding `#` to ``[\`*_\s]`` also strips a `#` a phrase legitimately contains ---
an issue reference, a colour literal, a quoted shell comment --- so the
normalizer starts erasing content in order to find it.

Strip the leader **per line, anchored**, before collapsing whitespace:

```python
strip_leader = lambda s: re.sub(r"(?m)^[ \t]*(##|#|//|--)(?=[ \t]|$)[ \t]?", "", s)
norm = lambda s: re.sub(r"[\`*_\s]+", " ", strip_leader(s))
norm(needle) in norm(haystack)
```

The anchor is what keeps this from being the wider-class move.
`^` under the `(?m)` flag confines the strip to a position the medium owns, so a
`#` inside a line is untouched.

The lookahead is load-bearing rather than decorative, and dropping it
reintroduces the exact defect this section removes.
A bare optional separator (`\s?`) lets the pattern strip any line-initial `#` or
`--` whatever follows it: the `#` of a wrapped `#1257` reference, and --- worse
in a corpus that writes them constantly --- a line-initial `---`, which is left
as a stray `- `.
Requiring the separator to be present, or the line to end there, leaves both
intact while still stripping `## text`, `-- text`, and a bare `##`.
Prefer `[ \t]` over `\s` for that separator, since `\s` matches the newline and
would join the stripped line to the next one.

- **Do:** strip a line-comment leader with an anchored per-line pattern before
  whitespace collapse, whenever the haystack is source code.
- **Do:** apply that strip to both sides --- this adds a stage, it does not
  replace the symmetry rule above.
- **Do:** require the leader to be followed by whitespace or a line end, so a
  line-initial `#1257` or `---` survives the strip.
- **Don't:** add `#`, `/`, or `-` to the inline-markup character class; that
  strips them wherever they appear, including inside the content you are
  searching for.
- **Don't:** read an absent verdict against a source file as evidence the phrase
  is missing until the leader has been accounted for.

(2026-08-16, verifying `Lacaedemon/sparta` PR #1257 after merge: a probe
checking that two merged doc-comment phrases had landed on `main` reported both
missing.
Both were present.
Each phrase wraps across lines in `scripts/SoldierEnemyContact.gd`, and every
continuation line opens with GDScript's `##` doc-comment leader, so the haystack
carried `## ` mid-phrase where the needle carried a space.
The normalizer was applied to both sides, exactly as the rule above requires,
and `#` is not in its character class --- so the symmetry held and the check
still failed.)

**A flagged item that came in via a `main`-sync merge, not your own diff, is still a Defer --- just one where the follow-up is fixing it on `main` directly, not filing a per-PR issue.** This is not the ARD skill's "Acknowledge" disposition: `skills/ard/SKILL.md` reserves Acknowledge for praise or a no-ask observation, and explicitly warns against stretching it to dodge a real finding --- a redundant config line a reviewer flags is a real finding with an implied fix request, so it needs a real disposition, not a label that means "no change requested." When a reviewer flags something (a redundant config line, a stale pattern) inside a file your branch only touches because you merged `main` in to resolve a conflict, check provenance before fixing it: `git log`/`git blame` the flagged line, or just compare against `origin/main`'s current content. If it's identical to `main`, "fixing" it on your branch alone doesn't fix anything --- it just makes your branch disagree with `main` on unrelated content the next person to touch that file will have to reconcile again. Reply agreeing the finding is correct but out of scope for this PR, and leave it for whoever owns that file's actual content to fix on `main` directly --- no follow-up issue needed, since the fix target is `main` itself, not this PR's own change.

**This generalizes to a skill's own inline restatement of a fragment it
links to.** A `SKILL.md` that links a backing `shared/` fragment for the
full detail often *also* restates the fragment's approach or word list
inline (in its `description` field, or a short procedure-step summary) so
a reader doesn't have to open the linked file. Fixing a bug in the
fragment doesn't automatically fix these inline restatements --- they're a
second, independent copy of the same claim, and a review round after the
fragment fix can catch them going stale exactly like a CHANGELOG paraphrase
does. Grep the whole PR diff for the fixed phrase/word-list, not just the
fragment file, before considering a fragment fix complete.

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

**Reply-first collides with citing the fix's SHA, and the way out is to commit
between them rather than to pick one.**

1. **Commit** the round's fixes.
   The SHA now exists and is stable.
2. **Reply** on each thread, citing that SHA.
3. **Push.** The next review's snapshot already contains the replies.

- **Do:** commit, reply citing the committed SHA, then push --- in that order.
- **Don't:** treat "I need the SHA for the reply" as a reason to push before
  replying; that is the ordering the bullet above exists to prevent.

**A finding can be right while its `suggestion` block is wrong --- verify
the suggested literal before applying it.**

**The same check applies to a fix a reviewer describes in prose rather than
in a `suggestion` block, and the sharpest test is the reviewer's own
example.**

**A reviewer's corrected citation is another factual claim, so verify the
replacement before adopting it.**

- **Do:** verify a proposed replacement citation with the source's own history
  before editing the PR to use it.
- **Do:** use `git log -S "<exact line>" -- <file>` or an equivalent
  provenance query when the question is which PR introduced text.
- **Don't:** adopt a reviewer's corrected issue or PR number because the
  original was wrong.
- **Don't:** use word overlap and same-day timing as a substitute for source
  history.

**The same check one artifact over: a reviewer's replacement DIFFSTAT is a
factual claim too, and the usual way it goes wrong is summing per-commit
churn rather than diffing the merge base.**

A branch that edits the same lines across review rounds accumulates churn.
Round 1 adds a line and round 2 rewrites it, so a per-commit sum counts that
line twice and reports a deletion the merge-base diff never sees.
The inflation is therefore worst on exactly the branches most likely to carry
a verification table worth checking, which are the multi-round ones.

What makes this cost more than one wrong number is that
[`ardi`](ardi.md)'s pre-push checklist already requires every figure in a PR
body to be re-derived by command at each push.
A reviewer supplying replacement figures looks like that derivation having
been done for you, so the natural move is to paste them straight in.
That substitutes an unverified figure for a stale one and leaves the body
just as wrong, while feeling like the finding was addressed.

- **Do:** re-derive a reviewer's replacement figures with
  `git diff --numstat <merge-base> <head>` before pasting them into a PR body.
- **Do:** cross-check against GitHub's own `additions`/`deletions` fields,
  which are computed against the merge base and so agree with that command.
- **Don't:** treat a reviewer's supplied figures as discharging the re-derive
  requirement --- a correct finding about staleness says nothing about the
  replacement's accuracy.
- **Don't:** sum per-commit `--numstat` to get a branch's diffstat.
  On a multi-round branch that double-counts rewritten lines and reports
  deletions the merge base never sees.

See [`address-every-comment.cases.md`](address-every-comment.cases.md),
"A reviewer's replacement diffstat summed per-commit churn".

**The highest-yield version of that check: when a comment names an edge case
in its own prose and also supplies a fix, run the fix against that edge
case.**

- **Do:** check a suggested fix against every failure mode the same comment
  names, before checking anything else about it.
- **Do:** name the reviewer's own caveat in the reply, so the rebuttal rests
  on their evidence rather than on your say-so.
- **Don't:** let a comment's demonstrated thoroughness transfer to its
  snippet --- they are separate claims.
- **Don't:** discard a finding because its fix is wrong; the half that named
  the hazard usually still stands.

**A quieter variant: the suggestion introduces no defect at all, it restates
the line above it --- so applying it deletes coverage while reading as
hardening.**

- **Do:** evaluate the suggested predicate and its neighbours on real input,
  and keep the finding while rejecting the snippet when they coincide.
- **Do:** fix the underlying coupling instead, and say in the reply why the
  suggested form was set aside.
- **Don't:** accept a `suggestion` block that restates an adjacent check ---
  passing tests afterward prove nothing, since the survivor passes for both.
- **Don't:** read a reviewer's own "the line above already covers this" as
  support for their replacement.

**A finding can be right, and its fix adequate, while the *reason* it supplies
is too weak to ship --- and in a corpus of rules, the reason is the
deliverable.**

- **Do:** read the primary source for the strongest reason before adopting a
  suggested rationale, even when the suggestion's conclusion is right.
- **Do:** say in the reply which reason you took and why the offered one was set
  aside, since deviating from a `suggestion` block silently reads as having
  missed it.
- **Don't:** accept a defensible-sounding mechanism because the conclusion it
  supports is correct.
- **Don't:** treat this as grounds to reject the finding --- the conclusion
  usually stands, and only its reason needs strengthening.

**And the mirror case: a finding can be wrong on its stated grounds while
still pointing at something real.**

**A third direction, which evades the verification reflex rather than lacking
a rule: agreeing with a finding and then escalating it.**

- **Do:** verify an escalation against the full scope it claims, which is
  wider than the scope the finding reported, and which the finding's own
  instrument may already cover.
- **Do:** post the correction to the thread that carried the escalation.
- **Don't:** treat agreeing-and-extending as exempt from the checks a rebuttal
  gets, since agreement suppresses the reflex that disagreement triggers.
- **Don't:** report a finding as understated on a measurement you have not
  shown covers the whole field set.

**When a finding cites a source, read the cited source before reproducing
anything -- it is the cheaper instrument, and it is the one that can show the
finding backwards rather than merely unsupported.**

**When a reviewer hedges a finding because it depends on code it cannot
see, check whether *you* can see it --- the hedge is an invitation, not a
verdict.**

**Timestamp the evidence before rebutting a finding with it --- during a live
incident, a log from twenty minutes ago describes a different system.**

**A rebuttal's own evidence is the least-checked claim in a review round, and
the commonest way it goes wrong is being measured through a tool that adds a
shell layer.**

- **Do:** write each command spelling to its own file and run the file when
  comparing them, so exactly one shell layer applies.
- **Do:** hold your own rebuttal to the standard you would apply to the
  finding, and say which instrument produced the counter-measurement.
- **Do:** re-run the measurement outside the harness when a reviewer holds
  their ground, before rebutting a second time.
- **Don't:** read a rebuttal as self-verifying because disagreeing felt like
  the rigorous move.
- **Don't:** cite a named check as settling a question without saying what it
  ran through; a named check reads as a performed one.
- **Don't:** compare two command spellings by typing both into the same tool,
  which is the one measurement guaranteed to make them look alike.

**A finding carries a timestamp too, and its precondition can dissolve
between the round that raised it and the round that addresses it.**

**The claim is not thereby fixed either, which is the half that is easy to
miss.**

- **Do:** re-check what a finding presupposes at the moment you address it,
  not at the moment it was raised.
- **Do:** replace a claim whose gate has cleared with a derived one --- the
  timestamp and the figures the event produced --- rather than hedging it or
  leaving it.
- **Don't:** apply a reviewer's suggested wording without re-checking what
  that wording presupposes; a hedge is false once the thing it hedges has
  happened.
- **Don't:** read a claim that has become true as a claim that has been
  checked --- nothing verified it, and the two read identically.

**Four neighbours sit close enough to be mistaken for this, and the boundary
is worth drawing because three of them fire on the same PR.**

See [`address-every-comment.cases.md`](address-every-comment.cases.md),
"A finding's precondition can dissolve before you address it".

**A finding built on a *negative* result -- "I searched and it isn't there"
-- is only as strong as the paths that were searched, and the search scope
is the part reviewers state loosest.**

- **Do:** ask which paths a negative finding actually searched, and check the
  obvious location yourself before editing anything.
- **Do:** name the gap when the thing does exist -- paths searched versus
  where it lives -- so the same search is not re-run the same way.
- **Don't:** accept "it isn't there anywhere" as settled because it is stated
  more confidently than a positive finding would be.
- **Don't:** discard the finding once its negative result is disproved -- the
  thing it tripped over is often a real ambiguity.

**A note the reviewer declined to raise is still a claim, and so is your
refutation of it.**

- **Do:** verify a declined, out-of-scope, or passing note against the code
  before either acting on it or writing it off.
- **Do:** hold the change regardless when the note turns out correct but
  genuinely optional --- verifying decides what is true, not what ships.
- **Don't:** treat a PR title, commit subject, or changelog line as evidence
  about what the code does; each states an intent, and a refactor can keep the
  very thing it says it replaced.
- **Don't:** let your own refutation past the check you would have applied to
  the reviewer's finding --- it is a fresh claim, and overturning something
  feels like having verified it.

**Count a round's findings before pushing its fix, because disposing of one
correctly generates no evidence about the others.**

The rule above governs the finding you decline to act on.
This governs the finding you never see, having already acted on its sibling.

A round can carry several findings, and acting on one produces every artifact
that handling the whole round produces: a verified claim, a commit, a reply, a
resolved thread.
Completeness is a property of the **set**, so nothing in that sequence reports
that a second finding existed.
There is no moment that feels like stopping early, because each step was
performed properly --- which is why this needs a count rather than more care.

**The body-only finding is where it hides**, and
[`fully-clean`](fully-clean.md) already names why: a finding about something
the diff did not touch cannot be attached as an inline comment, so it appears
in the verdict body alone.
Inline threads produce a visible checklist and a body-only finding produces
nothing to tick off, so "all threads resolved" reads as "round handled".
A **PR title** is the pure case, being out-of-diff by construction --- and on a
multi-commit PR a squash merge takes its commit subject from that title under
GitHub's default, so an overclaiming title can outlive the PR page it was
raised on.

The remedy is mechanical, and it is a count rather than a judgment: before
pushing, re-read the verdict body **and** re-fetch the thread list, then state
how many findings the round raised and dispose of all of them in one push.
Say explicitly which are deferred, per [`issue-first`](issue-first.md).

- **Do:** state the round's finding count before pushing, derived from both the
  body and the thread list.
- **Do:** read a title, a changelog line, and a PR body as reviewable surfaces
  --- a finding about any of them can only arrive in the body.
- **Don't:** read "every thread is resolved" as "every finding is handled";
  the thread list cannot see an out-of-diff finding.
- **Don't:** treat a correct, complete disposition of one finding as evidence
  about the round --- that is a per-finding claim wearing a per-round shape.

(Measured twice within half an hour on 2026-08-21, in both available shapes.
On [ai-config#1833](https://github.com/Morrison-Lab/ai-config/pull/1833) round
1 posted two inline findings; the first was fixed and pushed, and round 2
opened by re-raising the second --- "the text at this location is essentially
unchanged from what was flagged before" --- at a cost of $2.20.
On [gha#550](https://github.com/Morrison-Lab/gha/pull/550) round 1 posted three
inline findings and a fourth in the verdict body only, about the PR title
claiming work that had been deferred to another issue.
All three threads were addressed, resolved, and pushed; the body-only one was
missed.
The second occurrence came after the first had already been written up, which
is the argument for a count rather than for intending to look harder.
The two are anchored by the re-raise at 17:12:39Z and by noticing the second
miss at 17:41:36Z --- derived from the PR timestamps rather than carried over
from a figure quoted in a live comment, which is how "ninety minutes" reached
the first draft of this entry.)
