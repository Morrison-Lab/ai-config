# Rationale: address every comment

The mechanism, evidence, and argument behind the rules in
[`address-every-comment.md`](address-every-comment.md),
moved here to keep it out of the auto-loaded `CLAUDE.md` context.
Each heading mirrors the fragment's own section, and each passage
opens with the bold rule statement it argues for, repeated from the
fragment; the fragment's copy is authoritative.

**When a finding is a pattern (a formatting/style rule broken in one spot),
apply it everywhere it recurs in the same file, not just the flagged line.**
A reviewer that flags one inconsistent list-item format is telling you about
the rule, not just that one item --- fix every occurrence in the same file that
breaks it in the same pass, rather than waiting for the reviewer to flag each
occurrence in a separate round. Re-scan the whole changed file for the same
pattern before pushing the fix.

**That rule's scope is "the same file", and a reviewer who enumerates the sites
is the reason the scope goes unquestioned.**
A pattern finding usually arrives with a list attached: three spots, named,
each with a file and a line.
That list is a snapshot of where the reviewer happened to look, never the
extent of the pattern.
A reviewer reports the instances it noticed while reading a diff, which is not
the same operation as sweeping for them.

Inheriting the list rather than deriving it reads as responsive rather than as
under-scoped, which is what lets it survive a round.
The reviewer found the problem, so its account of the problem carries the
authority of the finding itself, and fixing exactly what was named is
indistinguishable --- from the inside and from the thread --- from fixing the
pattern.
The failure then reproduces one round later in a file the enumeration did not
name, which is the round the rule above exists to save.

The tell is lexical, and it sits in your own reply: **"fixed all three spots
you named"**.
Quoting the reviewer's count is the signal that the set was inherited, since a
derived set has no reason to agree with a number someone else supplied.

So derive the site list with a command: pipe the whole diff through a grep for
the flagged phrase, and widen the search past the diff when that phrase was
copied in from somewhere else.

Pick the pattern shorter than the phrase, though.
This corpus mandates semantic line breaks, so a multi-word phrase routinely
straddles a newline, and a line-oriented grep for the whole thing then matches
nothing --- a derived set can come back empty for a formatting reason rather
than a factual one, which is the same false-negative this file treats at length
under its own semantic-line-break corollary.
A short distinctive fragment is the reliable choice.

Then report what was **swept** rather than what was fixed.
"Grepped the whole diff for `X|Y|Z`, four hits, all four fixed" is checkable,
while "fixed all three" asserts a scope nobody measured.

This is [`derive-dont-enumerate`](derive-dont-enumerate.md)'s principle applied
to a review finding's site list rather than to work items, and that is the
transferable part.
Every fix is individually correct while the coverage claim over them is false,
so the gap is a property of the **set** rather than of any member --- nothing
in the diff, the tests, or the thread reports it.

Distinct from
[`algorithmatize-checks`](algorithmatize-checks.md)'s "never predict which case
will fail; enumerate the class", which shares this remedy and has a different
trigger.
There the list is one **you** produced from intuition, so the rule fires on
your own naming of a member.
Here the list arrived from someone with more standing to write it than you had,
which is why nothing about accepting it feels like guessing.

**The remedy above names a search space --- "the whole diff" --- and a stack has one of those per branch.**
Everything above governs the *pattern*.
This governs the *corpus* the pattern runs over, which the remedy states in the singular because a session normally has one PR.

Running the sweep across the PR the finding landed on is the whole of what the rule asks for, and it produces exactly the reply the rule endorses: the pattern searched, the hit count, every hit fixed.
So the near-miss passes every check written above, and it does so while a sibling branch carries the same violation --- which the next round finds, on a PR whose review had nothing to do with the finding.

The trigger is worth stating because nothing about the finding announces it.
A reviewer reports on one PR, so the finding arrives scoped to that PR, and a stack is one unit of work in every way except this one.
When a finding names a *class* rather than an occurrence --- a convention, a banned token, a formatting rule --- the class is a property of the work, and the work spans the stack.

```bash
for b in <branch-A> <branch-B>; do
  printf '%s: ' "$b"
  git diff "origin/main...$b" | grep -c '<fragment>'
done
```

**Deriving the class is necessary and not sufficient, because you can derive the
wrong one --- and the growth rate across rounds is what says so.**
Everything above governs inheriting a reviewer's list instead of deriving your
own.
This is the failure that follows taking that advice.
You derive a class, extend the enumeration well past the reported members, and
report the sweep exactly as those bullets ask --- and the next round returns
more members, because the class you enumerated is not the one the defect lives
in.

Note what that does to the tell.
The lexical one above catches a reply quoting the reviewer's count, and a reply
reading "I derived the class rather than fixing the N reported instances" passes
it cleanly while being wrong in the same way.
Its replacement is quantitative and needs no insight: **if round 1 grew the list
by N and round 2 produces M more, the list is not one pass from done.**
The growth is itself the evidence that enumeration is the wrong lever, and it is
sitting in front of you the moment round 2 lands.

The reason the diagnosis loses is structural rather than careless.
A review that finds this usually supplies a diagnosis *and* example cases.
The examples are actionable and the diagnosis is not, so the examples get worked
and the sentence gets read past.
Worse, such a review will often pair its diagnosis with a suggested fix that is
itself another enumeration step --- so the actionable half points at the very
lever the diagnostic half just warned about, and following the review faithfully
reproduces the bug.

The way out is a lever on a **different axis**, picked by measurement rather
than by taste.
Ask what the enumeration is actually protecting against, and whether that is the
same property the enumeration is expressed in.
When it is not, the fix is solving one problem with another problem's
instrument, which is why it keeps costing rounds.
The measurement is cheap: relax the enumeration entirely and read which cases
change.
If the cases that move share some other property, that property is the axis the
fix belongs on.
A useful confirmation that the class is closed rather than the members patched
is that most of the resulting test cases were never reported by anyone.

**A narrower version of the same failure: the class is right, and it is
enumerated in more than one place.**
The block above governs deriving the wrong class.
This is what happens once the class is right --- you fix the site the round
reported, the concept turns out to live at two or three sites, and the next
round arrives through one of the others.
Each round then feels like a new finding while being the same room entered by a
different door.

The tell is that consecutive findings paraphrase to one sentence.
When three rounds all reduce to "text handed to something that runs it", the
recurrence is not about a class's members but about the number of **places that
class is written down**.
So the quantity to derive is the site count: grep for the concept rather than
for the construct that exposed it, and expect the review's own prose to have
named the sibling site already --- ours did, observing that one list "already
enumerates programs whose quoted argument is live" while the site that failed
had "no analogous carve-out".

The fix is DRY rather than another member: define the concept once and have
every site consume it, so the residual is a single reviewable list instead of
several that drift apart.
That converts an unbounded sequence of rounds into one artifact a reviewer can
check, which is the only form of "this is closed now" worth claiming.
See [`dont-incur-technical-debt`](../principles/dont-incur-technical-debt.md)
for why the second copy was the defect rather than the newest gap in it.

**The mirror case: the enumeration was complete and the fix was not.**
The rule above governs a reviewer's list that was too short.
This governs the one that was exactly right, and a reply that closed it anyway.
A finding naming two artifacts --- a stale equation *and* the prose describing
it, a constant *and* the comment above it --- is two findings sharing one
comment, so it earns two dispositions rather than one.
Fixing the first and writing "Addressed" under-delivers against a list nobody
had to derive, which is why no sweep rule catches it: the grep the section
above prescribes was never the missing step.

What makes it survive the round is that the source diff looks finished.
The flagged line is visibly changed, the commit message names the finding, and
a reviewer re-reading the diff sees a real fix where the finding pointed.
The unfixed half is *context* in that diff rather than a hunk, so nothing about
reading the diff distinguishes "both halves done" from "one half done".

So verify a prose or formula fix against the **rendered** artifact wherever the
project builds one --- a PR-preview deploy, a `gh-pages` build, generated docs.
The rendered page puts both halves of a finding in one view, in the order a
reader meets them, which the diff never does.
[`fact-check-prose`](../writing/fact-check-prose.md)'s rendered-artifacts bullet
owns the mechanics of locating that preview; the increment here is *when* to
reach for it --- closing out a finding, not only checking a computed figure.

**When syncing copies, search the diff for the claim, not the files or symptom
already in front of you.**
The paragraph above says to grep the diff, and both words matter.
A path-scoped grep over the files already open is not a diff search, however
real the hits it returns are.
The scope is the silent variable: the command succeeded, but it searched the
author's working memory rather than the change.
Pipe the diff itself, so the search space is the whole PR diff:

```bash
git diff origin/main...HEAD | grep -n "<figure-or-phrase>"
```

Run that after committing, not before.
Like `check-new-line-breaks`, any `origin/main...HEAD` scan reports on `HEAD`,
so a pre-commit run describes the old committed text and can make a fixed
working tree look unfixed.

The same failure can hide in the search term instead of the path.
When a review retires a rationale, search for statements of the retired
criterion, not only for the word or contradiction that exposed it.
The exposing detail usually appears once; the criterion is what got copied
around.

**That same search settles a narrower question about placement: a correction
written NEAR the flagged sentence reads as having replaced it, while the
flagged sentence survives and the file then states both.**
The natural fix for a false claim a reviewer named is to write the accurate
version close by --- a disclaimer above it, a qualifying clause after it.
That feels like correcting the flagged sentence.
The flagged sentence is untouched, though, so the file now states both, and a
reader who reaches the older one gets the false claim back with nothing
marking it as superseded.

This is the review-response instance of
[fact-check-prose's insertion rule](../writing/fact-check-prose.md#an-insertion-asserts-something-about-the-whole-file-not-just-the-added-lines):
not a distant sentence the author never noticed, but the very sentence the
reviewer just named.

It can survive a self-check, because the obvious check asks the wrong
question.
Confirming that the new, true sentence is present answers "did I write
something accurate", which a self-contradicting file answers yes to.
The check that can fail is the one the section above already prescribes ---
search for the claim rather than for the symptom --- run against the flagged
wording itself.

A commit message claiming to have "dropped" the false claim is a checkable
claim in its own right.
Read the diff for a deletion of that line, rather than for an addition beside
unchanged text.

**When the wrong thing is a figure, the unit of repair is the figure --- across
every artifact carrying the twin, not just the diff.**
The rules above all scope the search to the diff, or to the same file.
That is the right scope when the duplicate was created *by* this change.
It is the wrong one when two artifacts have carried near-duplicate prose for a
while --- a test file's explanatory header and a memory file, a docstring and a
design doc --- and only one of them is in your diff at all.
The other copy is outside every instrument above by construction, so a clean
whole-diff grep is not evidence about it.

So when a finding names a wrong number, treat the **value** as the search term
and the **set of artifacts known to carry the twin** as the search space.
`scripts/find-near-duplicates.py` already exists for locating that twin; reach
for it rather than recalling which files pair up.
Reporting the sweep the way the rule above asks --- the term searched and the
hit count, per artifact --- is what makes the coverage checkable rather than
asserted.

**And a reflow puts its neighbouring sentences into your change, for
fact-checking and not only for lint.**
[`ascii-punctuation-in-source`](../coding/ascii-punctuation-in-source.md) already
establishes the diff-attribution half: editing a line for an unrelated reason
makes its pre-existing violations yours, "because the check reads added lines,
and a modified line is an added line."
Its scope is mechanical --- banned glyphs, multi-sentence lines --- and its
remedy is to bring the line into compliance.
The same argument reaches further than that section claims.
If reflowing a paragraph makes its em-dash yours, it makes its **wrong figure**
yours too: the sentence is in your diff, and a sentence in your diff is a claim
you are asserting.
Re-read every sentence a reflow touched against
[`fact-check-prose`](../writing/fact-check-prose.md), not only against the
punctuation checks.

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

**Answering a body-staleness finding with a correction comment does not clear
it, and this corpus's own visible-correction convention is what makes that
move attractive.**
The paragraph above says to state the correction as history in the body.
It does not name the near-miss, which is to leave the body alone and post a
comment instead --- and that reads as compliance rather than as evasion,
because [`ardi`](ardi.md)'s rule for a published wrong SHA prescribes exactly a
visible note.

The two artifacts differ in who re-reads them, which is what decides it.
A claim in a comment thread is read once, so a later comment correcting it
reaches everyone the original reached.
A PR body is re-read from scratch by every subsequent reviewer, so the stale
figure is still the first thing the next round meets.
A comment therefore leaves the finding live, and the round buys nothing.

Both halves are needed rather than either alone.
Editing removes the false figure, and recording the correction inside the body
keeps earlier rounds that cite the old numbers resolvable --- which is the
thing the paragraph above is protecting.
A short "Corrections to this body" table does both at once.

The re-dispatch this costs is the part that usually goes unweighed, and it is
cheap.
A confirming round --- head unchanged, one finding to re-verify --- came in at
roughly 40% of the first full round's cost on the PR below, so fixing the body
and re-dispatching beats arguing the finding down.

**A body that reports volatile external state goes stale with no edit of
yours, so the trigger above never fires on it.**
That trigger is an action *you* take, and this is the case where you take
none.

A description of the **change** is anchored: the diff is fixed, so prose
about it stays true until the diff moves, which is exactly what the rule
above covers.
A description of **external state** --- CI status, mergeability, a blocker,
"waiting on X", a base-branch condition --- has no anchor.
It is a measurement with a timestamp nobody wrote down, published in a
document that is edited rarely and read constantly.
On a long-lived PR its staleness is not a risk but a certainty.

It composes badly with review timing, too.
A reviewer snapshots the body when its run starts, so a late correction is
invisible to it --- the same mechanism the timestamp check below describes
for a rebuttal posted after a run began.
The result is a finding about a paragraph that was already fixed, costing a
round trip on both sides.

The remedy is not more diligence, since the failure has no moment to be
diligent at.
It is to keep the volatile claim out of the body, or to date it so it reads
as a past observation rather than a present one.
This is
[`timestamp-volatile-claims`](../writing/timestamp-volatile-claims.md)
applied to the artifact a maintainer reads while deciding to merge.

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

Be honest about the residual: all of that can be applied and a further run
can still block, at which point the only remaining move is deleting the
history outright, which costs the earlier comments their referent.
That trade belongs to the human, not to the agent driving the PR.

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

And verifying once feels like verifying.
Running the check for the PR body produces a real sense of having established
the fact, which is what stops you checking the other place it appears.
The verification is genuine; the coverage is not.

Note the shape is the same as [`ardi`](ardi.md)'s "an instruction's own
suggested code is not exempt", one artifact over: content inherited from a
planning document does not feel authored, so the checks you apply to your own
claims do not fire on it.

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

**Inline markup breaks the same search, and that variant aims the false
negative at someone else's work rather than your own.**
Whitespace is the obvious thing a line-oriented tool gets wrong, so the fix
above normalizes it.
Markup is the one nobody normalizes, because the two strings *look*
identical: a rule titled ``Run a local session in an isolated `git worktree`
by DEFAULT`` is quoted in a citation as "Run a local session in an isolated
git worktree by DEFAULT", since prose quoting a title drops its code spans.
Grep the quoted form and the definition does not match; only the citation
does.

The consequence is worse than the line-break case, and in a specific way.
There a false negative says your own merged work is missing, so you re-do
something already done.
Here it says the **cited** thing is missing, which reads as a dangling
citation --- and the prescribed response to a dangling citation is to file
an issue.
So the wrong search does not merely waste effort, it puts a false claim
about the corpus into the tracker, against a citation that resolves.
A result of exactly one hit, in the citing file, is the tell: a genuinely
dangling citation and a formatting mismatch produce the same count, and only
reading the hit distinguishes them.

Normalize backticks along with whitespace, or search a distinctive
unformatted fragment rather than the whole title.

**Apply whatever normalization you choose to the search term as well as to
the text, or the fix produces a third false negative of its own.**
Both cases above are answered by transforming the haystack --- collapse
whitespace, strip backticks --- and that framing invites transforming only
the haystack, since the needle is the string you already know.
But a normalizer is a function, and testing `f(text)` against a raw needle
compares two different alphabets.
Strip `_` to catch `*emphasis*` and a snake_case identifier stops matching
itself: `SH_WORD_SPLIT` becomes `SH WORD SPLIT` in the file while your
pattern still carries the underscores, so a term that is present reports
absent.

This failure gets *more* likely as the normalizer gets better, which is the
part worth naming.
Every character class added to catch another markup form is another class
that occurs inside real identifiers, so the enumerate-what-to-strip approach
converges on breaking the searches it was extended to fix.
Enumerating is the wrong shape, not merely an incomplete list.

Running the same function over both sides dissolves the question, whatever
the function is:

```python
norm = lambda s: re.sub(r"[`*_\s]+", " ", s)
norm(needle) in norm(haystack)
```

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
the same reason.

**Reply-first collides with citing the fix's SHA, and the way out is to commit
between them rather than to pick one.**
The rule above is easy to agree with and still lose, because on a mixed round
the reply you want to write says "Addressed in `<sha>`" --- and that SHA does
not exist until you have committed.
So the two instructions read as mutually exclusive: reply first and you have no
SHA to cite, push first and the reply misses the next review's snapshot.
Pushing first wins that standoff by default, since it is the half that
*unblocks* the sentence you were trying to write.

The conflict is only apparent, because committing and pushing are separate
steps and only the push triggers review:

A commit that is never pushed is invisible to CI and to the reviewer, so step 2
is citing something real but not yet reachable --- which is fine for a few
seconds, and is exactly the window step 3 closes.
Note the one thing this does *not* license: the SHA you cite must come from
`git rev-parse HEAD` or `git log`, never from recollection, per the PR-body
bullet in [`ardi`](ardi.md).

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

**A reviewer's corrected citation is another factual claim, so verify the
replacement before adopting it.**
The finding can be right: the citation in the PR can name the wrong source.
That does not make the reviewer's proposed source right.
A replacement issue or PR number is a fresh provenance claim, and it needs the
same check as the original citation.
For text provenance, prefer history over word association:
`git log -S "<exact line>" -- <file>` asks which commit introduced the line,
while matching a word in another PR plus a nearby merge time only builds a
story.
Keep the review's conclusion when it is right, but set aside the replacement
when the evidence points elsewhere, and say which query decided it.

**The highest-yield version of that check: when a comment names an edge case
in its own prose and also supplies a fix, run the fix against that edge
case.**
The bullets above test a suggestion against the code, or against a repro the
reviewer provided.
This tests it against the reviewer's *other paragraph*, and it is the cheapest
of them, because the hazard has already been identified for you --- the
work left is only to check whether the proposed code handles it.

Nothing forces the two halves to agree.
A comment's prose and its suggestion are drafted separately, and a reviewer
who spots an edge case while reasoning about the problem does not necessarily
carry it into the snippet.
So a comment can read as unusually thorough --- it anticipated a failure mode
you had not --- while shipping a fix that falls into exactly it.
That thoroughness is what makes the suggestion persuasive, which is the trap.

Applying it is worse than ignoring the whole finding.
The prose half was right, so the reviewer's authority is real; the snippet
then lands under that authority carrying a defect the same comment already
described, and the thread reads as settled.
Worse still when the defect is one your own corpus documents, since the
review has now talked you out of a standing rule.

Keep the finding and reject the snippet.
Fix it your own way, quote the edge case back, and say plainly why the
suggested form was set aside --- silently deviating from a `suggestion` block
reads as having missed it.

**A quieter variant: the suggestion introduces no defect at all, it restates
the line above it --- so applying it deletes coverage while reading as
hardening.**
Every bullet above is about a snippet that would break something, so the
reviewer's authority is the trap and skepticism is the defence.
Here nothing breaks.
The tests still pass, the diff looks like a robustness improvement, and the
comment is *correct about the problem*.
What is lost is the only assertion covering a different property, replaced by
a second copy of one already present a line earlier --- so a two-assertion
test becomes a one-assertion test that still looks like two.

The reason it survives review is that the surviving copy passes, which is
indistinguishable from the fix working.
So the usual after-the-fact check --- run the tests --- cannot detect it, and
neither can CI.
It is a [`challenge-redundant-content`](challenge-redundant-content.md)
finding arriving from the reviewer, which is exactly the direction that makes
deferring feel appropriate.

Watch for the comment citing the neighbour as *support*: "the check on the
line above is already load-bearing for this claim" is the argument against the
replacement, and it reads as an argument for it.
Same structure as the edge-case bullet above --- prose and snippet drafted
separately, disagreeing --- one artifact over.

Compare a suggested predicate against its **neighbours**, not only against
the code it replaces, and evaluate both on real input rather than reasoning
about them; one command decides it, per
[`algorithmatize-checks`](algorithmatize-checks.md).
Then prefer removing whatever made the original fragile over swapping one
fragile sentinel for another.

**A finding can be right, and its fix adequate, while the *reason* it supplies
is too weak to ship --- and in a corpus of rules, the reason is the
deliverable.**
The bullets above all test whether the suggested fix *works*: against the code,
against the reviewer's repro, against an edge case their own prose named.
This one assumes it works, and asks whether the justification handed to you
still holds when someone leans on it.

That distinction is invisible in code and decisive in a rule.
A patch is judged by its behaviour, so a correct patch with a shaky rationale is
merely under-commented.
A `shared/` fragment is judged entirely by whether its reason forecloses the
workarounds, so adopting a weaker reason ships a rule the next reader can talk
themselves around --- while the thread records the item as settled.

The tell is a suggestion that explains *why* something is forbidden in a single
phrase, where the primary source carries a stronger provision.
So ask what the strongest *available* reason is, rather than whether the offered
one is defensible, and name the workaround the weaker reason would have
licensed --- that is what makes the choice checkable rather than a matter of
taste.

**And the mirror case: a finding can be wrong on its stated grounds while
still pointing at something real.**
The bullets above check the reviewer's *fix*; this one checks their
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

**A third direction, which evades the verification reflex rather than lacking
a rule: agreeing with a finding and then escalating it.**
The bullets above check the reviewer's *fix*, and the one above checks their
*premise*.
Both assume you are deciding whether the finding is right.
This is the case where it is right, and correctly scoped, and you tell the
reviewer it understated the problem.

The **obligation** is not new, and claiming otherwise would overstate this
entry.
[`metacognitive-monitoring`](metacognitive-monitoring.md) already requires
verifying a finding's particulars before restating them as fact, and its
**scope** claim type already governs an assertion of your own about how wide a
defect is, telling you to check the population rather than the sample that
came to mind.
An escalation is nothing but a new particular of exactly that kind: a wider
scope, a bigger count, one more failing case.
So it lands squarely in the class that fragment names as least dependable, and
it does so where the reviewer's credibility will carry it.

What is new is the **trigger**.
Both of those rules fire on an act you recognize as asserting something, and
agreeing does not present as one.
Rebutting is adversarial and prompts you to verify --- the reviewer's claim,
that is, which is not the same as your own counter-measurement, and the
rebuttal section below covers that gap.
Extending is agreement wearing extra diligence, and agreement is not a thing
anyone verifies.
So the rule is already there and nothing calls it, which is how the escalation
ships under the reviewer's authority with less scrutiny than a rebuttal would
have got.

Hold an escalation to the standard a rebuttal gets.
Measure with an instrument covering the whole scope your escalation claims,
not merely the narrower scope the finding covered, and say which instrument
that was.
Do not read the finding's narrowness as a bound on the reviewer's instrument.
A reviewer can inspect a whole field set and report only the member that is
broken, so a one-field finding can rest on a five-field probe.
The instrument you need may therefore be the reviewer's own, run without
whatever narrowed your view of it, rather than a new and wider one.
When the escalation turns out to be wrong, correct it on the thread that
carried it, not only in a later round's summary.
A reader who saw "it is worse than you reported" has no other way to learn
that it was not.

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

**A rebuttal's own evidence is the least-checked claim in a review round, and
the commonest way it goes wrong is being measured through a tool that adds a
shell layer.**
The section above governs rebuttal evidence that went stale, and its tell is
"a rebuttal whose evidence you did not generate yourself in this turn".
This case fails that tell.
The evidence WAS generated in the turn, by a command run on purpose to settle
the disagreement, and it was still wrong.

Each shell layer a command passes through collapses one level of backslash
quoting.
So a command typed into a tool that wraps it in a second shell is not the
command a reader runs from a file.
Two spellings differing by a doubled backslash pair then reach the program
identical, and a measurement comparing them reports them equivalent --- which
is a true statement about the harness and a false one about the command.
The remedy is positional rather than analytical: write each form to its own
file and run the file, so exactly one layer applies.
Reasoning about how many backslashes survive is the step that failed, and it
fails reliably enough to be worth not attempting.

Two things then make such a rebuttal persuasive rather than suspicious.
Disagreeing feels like the rigorous move, so a rebuttal draws LESS scrutiny
than accepting the finding would.
The escalation section above treats a rebuttal as the high-scrutiny baseline
it measures agreement against, and this is the counterexample to that: the
reflex disagreement triggers is real, and it points at the reviewer's claim
rather than at your own.
And naming a check settles the question for a reader whether or not the check
discriminates.
"Confirmed at the argv level" reads as a check performed, when that inspection
had passed through the same two layers and so confirmed the artifact rather
than the fact.

[`scripts/compare-shell-forms.py`](../../scripts/compare-shell-forms.py)
decides this mechanically, per
[`deterministic-tools`](../principles/deterministic-tools.md): it writes each
spelling to its own file, runs each under exactly one shell, and reports
IDENTICAL, DIFFERING, or HARNESS FAILURE --- exiting non-zero on the third so a
broken run cannot be read as a result about the forms.

**A finding carries a timestamp too, and its precondition can dissolve
between the round that raised it and the round that addresses it.**
Every check above interrogates a finding's **content** --- its literals, its
premise, its proposed fix, its cited source, its search scope.
All of them ask whether the finding was right.
None asks whether it is **still** right.

A finding is a measurement of the world at the moment it was raised, and
between that moment and your fix sit a CI run, a review round, and often a
night.
Anything the finding depends on can move in that window: a cited PR merges, a
quota resets, a dependency publishes, a host unblocks.

Applying the finding as written is then wrong, and it is wrong in the
direction that feels most compliant.
Hedging a citation to "not yet merged as of this writing" asserts something
false once the PR has merged --- and it does so **while quoting the
reviewer's own suggested wording**, which is the form least likely to be
questioned by you, by the next reviewer, or by anyone reading the thread.

**The claim is not thereby fixed either, which is the half that is easy to
miss.**
When a precondition dissolves in the direction that makes your original
sentence true, that sentence has become **accidentally true**.
Nothing checked it; the world simply moved underneath it.
And an accidentally-true claim is indistinguishable in the text from a
verified one, so leaving it banks the reviewer's finding as resolved while no
verification ever happened --- which is strictly worse than the original
defect, because the thread now records the matter as settled.

So neither disposition on the table is correct.
Address-as-written is false, and leave-it-alone is unverified.
The move is to **re-derive**: replace the claim with a checkable one, naming
the event's timestamp and the figures it actually produced, each with its
deriving command beside it, per
[`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md).
That is the one form that is true whichever way the gate went, and it is the
only one a later reader can falsify.

[`ardi`](ardi.md)'s "A blocker that was true when you published it can stop
being true while the PR is open" governs a caveat **you** published, not a
finding you received.
Its `main`-merge remedy is a sweep for hedge forms --- `still open`,
`not yet merged`, `once that merges`, `as of`, `will live at`, `proposed in`
--- so it is **structurally blind** to this case rather than merely silent on
it: the defect lives in an *unhedged* assertion, and a sweep keyed on hedges
has nothing to match.
Measured on the flagged assertion,
`which is what Morrison-Lab/ai-config#1413 then did`: **0 of those 6 forms**
occur in it.
The reviewer's proposed hedge contains **3 of the 6**, which is the point
rather than a contrast --- the sweep finds the remedy and never the defect.

The two timestamp-aware rules above are each one axis away.
"Timestamp the evidence before rebutting a finding with it" governs the
evidence you gather for a **Rebut**; this governs the precondition of an
**Address**.
"A bot that re-raises an item as not addressed may simply not have seen your
reply" governs a reviewer's snapshot going stale relative to **your reply**;
here it goes stale relative to **the world**, which no reply ordering can fix.

And [`keep-checkouts-fresh`](keep-checkouts-fresh.md)'s citation convention
--- the rule the reviewer correctly cited --- says to hedge while the gate is
uncleared and says nothing about what to do once it clears.
Its one sentence beginning "Once the citation does resolve" is about keeping
a local restatement rather than a bare pointer, which is an auto-loading
concern and not a tense one.

A mechanical half exists and is not built here: scanning a PR's touched files
for `#NNNN` citations and checking each against that PR's live state would
catch both directions at once, the unhedged citation of an open PR and the
stale hedge on a merged one.
That is decidable from one API field per citation, so it belongs in an
instrument rather than in this rule, and is tracked in
[ai-config#1445](https://github.com/Morrison-Lab/ai-config/issues/1445).

**A finding built on a *negative* result -- "I searched and it isn't there"
-- is only as strong as the paths that were searched, and the search scope
is the part reviewers state loosest.**
The bullets above all check a reviewer's positive evidence: the suggested
literal, the proposed fix, the cited source.
A negative result invites none of that scrutiny, because there is nothing
to look up: the claim is that looking up would fail.
It also arrives sounding the most settled of any finding -- "no file or
heading with that title anywhere" reads as exhaustive, and the reader's
natural move is to accept it and edit.

So read the search itself rather than the conclusion.
Ask which paths were actually covered, and whether the obvious location is
among them.
One command usually settles it, which makes this an
[`algorithmatize-checks`](algorithmatize-checks.md) case rather than a
judgment call -- and note the reviewer's own tooling may have failed the way
[`fail-fast`](../principles/fail-fast.md)'s hand-check section describes,
matching too narrowly against text that was wrapped or reformatted.

When it turns out the thing does exist, name the gap rather than only the
correction: which paths were searched, where it actually lives, and why the
two did not overlap.
That is what stops the same search being re-run the same way.
And check whether the finding still points at something real, per the mirror
case above -- an unresolvable-looking citation is often a genuinely
under-specified one.

**A note the reviewer declined to raise is still a claim, and so is your
refutation of it.**
Every bullet above checks a finding the reviewer actually **raised** --- the
suggested literal, the proposed fix, the cited source, the negative result.
A note dropped in passing, marked out of scope, or explicitly declined is
checked by nobody, precisely because nobody is asking you to act on it.

It can be right, and it can be wrong, and both directions cost something.
[`ardi`](ardi.md)'s "not a finding" section owns the right-and-ignored
direction: a reviewer can analyse a real convention violation correctly and
still grade it acceptable, so the part of a review most likely to be skimmed is
where a genuine violation sits.
This bullet is the other half --- what happens once you do go and check.

The trap is that **checking a declined note feels like the end of the
verification when it is the start of a second unverified claim.**
Overturning something reads as more rigorous than accepting it, so a refutation
draws less scrutiny than the note it overturns rather than more.
And a refutation is unusually cheap to get wrong here, because the artifact
nearest to hand is not evidence about the code: a PR title, a commit subject,
or a changelog line describing a refactor is a claim about **intent**, and the
code is whatever that intent left behind.
"Converted from a position push to a velocity impulse" and a function that
computes a velocity and then still writes the position on the next line are
entirely compatible, and only one of the two is the code.

So read the function rather than the sentence describing the change to it, and
read it at the current tip --- a checkout that predates the merge answers a
different question, and answers it confidently.

Holding is usually still right, and
[`efficient-pr-babysitting`](efficient-pr-babysitting.md) already gives one
reason: a declined note is not an open item, and a clean verdict standing over
it is a stop.
Verifying supplies a second and better one, because that rule's argument is
about **cost** --- a round of CI and re-review spent on something that was
never blocking --- which argues for holding whether the note is right or wrong.
Checking tells you which of those you are in, it is usually one command, and
the two compose: verify the note, then hold anyway unless it named a real
defect.

**A finding raised against someone else's implementation is measured, not adopted
or dismissed.**
Dismissal is wrong because the peer is reasoning about the same problem, often
having probed a part of it you did not. Adoption is wrong because the finding is
about a different implementation, so whether it transfers is an empirical
question about your code rather than a property of the finding. Both feel like a
response and neither is one: the first spends nothing, the second spends a round
on a fix that may repair nothing.

Run the peer's cases as concrete inputs, not as a reading of your own regex or
your own parser --- a reading of the code is exactly the confirmation the
diff-versus-standards rules elsewhere in this corpus rule out. Then say which
passed and which did not, so the peer learns something about the shape of the
problem whichever way it goes.

Pinning the shapes even when they all pass is the step that looks redundant and
is not. A case that passes today passes by construction of code nobody promised
to keep; what the peer supplied was a *reason to care about that shape*, and
that reason survives the measurement. So the deliverable is the test, not the
verdict.

