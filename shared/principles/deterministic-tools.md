**Automate everything.**
Never do by hand any work that can be automated.

Prefer deterministic, inspectable algorithms over model judgment ---
and where none exists, build one.
The goal is to write ourselves out of a job: every task we perform by
reading and deciding is a candidate to become a script whose output we
merely consume.

Read "work" broadly.
Model judgment is the case this fragment was written for and the hardest to
displace, but the rule is not about judgment --- it is about **doing by hand
what something else already computes**,
which includes work carrying no judgment at all.
A hand-typed section number is not a decision anyone made;
it is a value the renderer was already producing,
kept in a second place by hand.
That kind of case is the easiest to miss,
precisely because nothing about it feels like deciding.

This is one principle with two faces, operating on different timescales.
They are not alternatives, and neither supersedes the other.

- **As a constraint**, binding right now, on the task in front of you:
  where a deterministic option exists, use it.
  Do not spend judgment on something a script decides.
- **As a goal**, directional, over time: where none exists, build it, so
  that next time the constraint is cheap to obey.

A session that honours only the constraint does the same manual work
forever, because no tool ever gets built.
A session that pursues only the goal builds tooling while deciding the
thing in front of it by hand.
Both faces, or neither works.

## Distinct from algorithmatize-checks and no-llm-algorithmic-thinking

[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) is the
checks-shaped special case, and most of the argument for correctness and
cost already lives there.
[`no-llm-algorithmic-thinking`](no-llm-algorithmic-thinking.md) is the
computational counterpart, strictly forbidding in-context probabilistic
reasoning for arithmetic, algebra, calculus, sorting, and proof steps.
Read them first; this principle extends them on two axes rather than
restating them.

**Scope.** The check rule governs *verification*: never spend reasoning on a
check an algorithm can decide.
The algorithmic-thinking rule governs *computation*: never spend probabilistic
tokens on an algorithmic result software can compute.
This one governs the *workflow itself*.
Counting, extracting, transforming, resolving a routine merge, composing
a status line, harvesting job output --- each is doing rather than
checking, and each is a candidate.

**Inspectability**, which that fragment never argues for.
A deterministic algorithm can be read before it runs, reviewed by someone
who does not trust its author, diffed across revisions, and re-run to the
same answer.
Model reasoning is none of those: there is nothing to review in advance,
no artifact to diff afterwards, and no guarantee the next run agrees with
the last.
That is a different argument from correctness or cost, and it is why a
hook beats a rule *even when the model would usually follow the rule* ---
the hook can be read, tested, and mutation-tested by someone who trusts
nothing about the model at all.

## It applies to every repo, not only the infrastructure

This is ordinary engineering practice that happens to have agentic
examples, not a rule about how agents should behave.
It governs the analysis and manuscript repos exactly as it governs the
CI and tooling ones.

A hand-run analysis step, a manually refreshed figure, a provenance claim
made from recollection, a validation someone eyeballs, a catalog verified
by reading --- each is the same shape as a hand-composed status line, and
each is a candidate.
"Automate everything" is a **direction**, not a completeness claim.

## The test: after doing it twice, the third time is a tool

The goal needs an observable trigger, or it stays aspirational.
Two occurrences establish that a task recurs rather than being a one-off;
the third is where building repays itself.

The trigger fires on *recurrence*, which is what keeps it from colliding
with YAGNI (see the [catalog](README.md)): a tool for something done once
is speculative generality, and the once-only case is exactly what YAGNI
governs.
The failure this test prevents is the opposite one --- doing the same
mechanical task eight times, each instance too small on its own to
justify a script, and never noticing the total.

Turn it inward from [`dont-reinvent-wheel`](dont-reinvent-wheel.md), too.
That principle says to search for an existing tool before building one.
This one says to leave a tool behind when your search finds nothing, so
the next session's search succeeds where yours failed.

**The count that fires this test is itself a claim about state, so derive it
rather than recalling it.**
Two occurrences and three are different verdicts here, and the whole
difference is whether you build --- so an off-by-one in memory is a wrong
decision, not merely a wrong number.
A tally assembled at the end of a session is exactly the state claim
[`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md) says to
re-query, and it errs upward, because a near-miss caught in a draft is vivid,
feels like the same mistake, and is not one.

An error caught before it was committed is the process working.
Counting it toward the bar licenses an instrument the evidence does not
support, which is worse than not building: the instrument then encodes a
recurrence pattern nobody actually has, and every later reader inherits it as
established.

For a claim about what a past commit said, the deriving query is one command
per commit, and it is not the same as reading the file:

```bash
git show <commit>:<path>
```

- **Do:** derive the occurrence count from the artifacts, and say which query
  produced it.
- **Do:** report shipped occurrences and caught near-misses as two numbers,
  since only the first counts toward the bar.
- **Don't:** let a draft error you caught count as an occurrence --- it is
  evidence the check worked.
- **Don't:** build on a remembered tally, however recent the session that
  produced it.

## A follow-up question gets a hastier instrument than the main task did

The test above fires on recurrence across occasions, which leaves a gap
inside a single one.
An instrument built for the main task, correct and still at hand, routinely
goes unused when a follow-up question arrives minutes later, and the
follow-up gets a throwaway one-liner instead.

Nothing about the two questions justifies the gap.
They run over the same corpus and ask the same kind of thing, so the
instrument would have answered the second one directly.
What differs is only how each felt.
The main task's tool reads as infrastructure, while the follow-up reads as a
quick lookup, and a quick lookup does not feel like something that needs a
tool.

Perceived stakes are therefore doing the work, and they point the wrong way.
A follow-up question is usually asked in order to settle something, so its
answer feeds a recommendation, a disposition, or a report to a human, whereas
the main task's output goes on to be reviewed, tested, and revised.
The artifact built with the least care is thus the one most likely to be
acted on unchecked, and its error arrives dressed as a measurement.

The constraint face at the top of this fragment already forbids this: use the
deterministic option where one exists.
What it lacks is the moment at which to notice, and that moment is
observable.
**A question of the same shape as one an existing instrument already answers
is a second use of that instrument**, not a new problem.
Re-run it with different arguments rather than writing a fresh matcher for
the same corpus.

This is not the reuse
[`check-purpose-before-reusing`](../workflow/check-purpose-before-reusing.md)
warns about, and the boundary is worth stating because the two look alike:
same session, same artifact, built minutes ago.
That fragment governs reuse across a **purpose** boundary, and says a
recently self-authored template gets too little scrutiny.
This one governs reuse within a single purpose, and says a recently built
instrument gets too little **use**.
Run its check first, naming what the original was for and what the new
question is for.
Where those match, reuse is the answer rather than the risk.

**Read the scope an instrument prints, and compare it against the size you
expected.**
A printed denominator nobody checked is worth no more than one that was never
printed.
[`fail-fast`](fail-fast.md) makes the producer's half of this case at length,
in its rule that a check should report what it examined rather than only what
it found.
The consumer's half is the same number one step later: a range that stops
short of the population is right there in the output and gets read past,
because the finding beneath it is what the question was about.

- **Do:** re-run the instrument already built this session when a follow-up
  asks the same kind of question of the same corpus.
- **Do:** compare a printed examined-range or population count against the
  expected size before using the result beneath it.
- **Don't:** write a fresh throwaway matcher because the new question feels
  smaller; perceived stakes are not a property of the corpus.
- **Don't:** publish a scope figure a truncated scan produced as though it
  were the population's real size.

(2026-08-07, `UCD-SERG/serocalculator#635`: a fence-aware Quarto heading
scanner, written for the main task and used to drive a 15-file restructure,
was set aside minutes later for a follow-up question about how much one part
of the document used a concept.
The follow-up's fresh scan matched `^# ` with no fence tracking, so it stopped
at the first R comment inside a code chunk, covering 194 of the part's 538
lines.
It printed that truncated range, and the range went unread.
On that evidence the part was reported to hold a single passing mention of
the concept, and a proposed move was recommended against.
A fence-aware rescan found 5 mentions, one of them a named forward reference
in prose pointing 611 composed lines ahead, so the recommendation was the
opposite of correct.
`UCD-SERG/serocalculator#569` had already diagnosed the same thing, and it
surfaced only during the dupe check before filing a new issue.)

## The third case: a value your toolchain already generates

Two instances of this principle are already well covered.
Model judgment displaced by an algorithm is this fragment's main subject.
Data with an external source of truth is [`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md).

A third sits between them and belongs to neither: **a value the toolchain already derives from the artifact itself**, written out by hand alongside it.
Section numbers a renderer computes from heading depth.
A table of contents a generator emits.
A count, a total, or a cross-reference that some tool resolves.
An index whose entries the build produces.

It is the least visible of the three, for a reason worth naming.
Hard-coded external data has an obvious owner elsewhere, so the question "where does this really come from?" arises naturally.
Model judgment at least feels like work, so it prompts the question of whether it should be.
Typing `## 6.2` prompts nothing.
It is not a decision, it is not a lookup, and it looks like authorship.

**The failure mode is silent divergence, and it is worse than being wrong.**
Two generators now exist for one value: yours and the tool's.
While nobody enables the tool's, the hand-written copy looks authoritative and stays correct.
The moment anything turns the real one on --- a format option, a config inherited from a parent directory, a downstream consumer with different defaults --- both run, and the artifact carries two answers at once.

Measured 2026-08-22 on `ucdavis/matt.contracts#2`:
a Quarto document whose 30 headings carried hand-typed numbers
while a directory `_metadata.yml` set `number-sections: true`.
Every heading rendered doubly numbered --- `2 1. Objectives and estimands`,
`2.3 1.3 Estimand framework` --- and the eight `@sec-` cross-references
resolved to the generated scheme, so a reference to the estimand section read
"Section 2.3" while its heading offered the reader both `2.3` and `1.3` with
nothing to say which was the section number.
Neither number was wrong on its own.
What the document lost was the ability to answer what a section is called,
which is the only thing a cross-reference is for.
None of it was visible in the source, and nine review rounds over a day did
not catch it, because every one of them read the `.qmd`.

**The check is one question, asked before typing a value into an artifact:** does anything in this toolchain already compute this?
If yes, let it, and delete the copy.
If the tool's version is turned off, prefer turning it on over maintaining the manual one --- an inert generator is a latent conflict, not an absent one.

**And where the value is generated, verify the generated artifact.**
Source inspection cannot see this class of defect by construction: the hand-typed number and the generated one are both correct in the file, and only the render shows them colliding.
That is [`verify-the-right-artifact`](../workflow/verify-the-right-artifact.md) applied here --- checking the `.qmd` is checking an adjacent object.

- **Do:** ask what the toolchain already derives before writing a value by hand.
- **Do:** enable the generator and delete the hand-maintained copy, rather than leaving the generator off.
- **Do:** read the rendered output when a value is generated, since the source cannot show the collision.
- **Don't:** treat "it is not a judgment call" as putting something outside this principle --- the clearest cases involve no judgment at all.
- **Don't:** assume an unused generator is harmless;
  it runs the moment a config elsewhere turns it on.

## An enumeration is still a parse, and a name list is the disguise it wears

This file's argument is that a deterministic instrument beats model judgment.
It does not follow that every deterministic instrument is sound, and the failure worth naming is the one that looks like having *removed* a parse.

Deciding whether a span of untrusted text belongs to the harness or to the user is delimiter-matching, and it does not converge: a non-greedy match stops at the first close, a repeated opener leaks the remainder, injected content containing a literal closing tag terminates the wrong span.
Replacing that with a **list of tag names** feels like a different kind of thing --- there is no grammar left, only membership --- and the code said so outright: *"nothing is parsed"*.

It was still parsing.
The parse had moved from **grammar** to **vocabulary**, and the vocabulary belonged to the format's author rather than to the checker.
The shipped harness emitted or stripped fifteen tag names inside user content;
the list held four, and intersected them in two.
A teammate agent's message and an editor selection appended to the user's own prompt both certified clean.

The tell is that the new instrument's correctness now depends on a set **someone else maintains** and does not publish to you.
An enumeration over your own domain is fine --- the keys of a dispatch table you wrote are complete by construction.
An enumeration over someone else's is a snapshot, and it decays silently, because nothing about a missing name looks like an error.

So ask which side owns the set.
Where the answer is *not you*, the sound move is structural rather than enumerated: match the **shape** the format uses rather than the instances you have seen, so an instance added later is covered without a code change.
Then measure what the structural form costs on real data before adopting it, because over-matching is a real price and is worth paying only when you know its size.

The same question settles the coverage direction, which is the half that took its own round to surface.
Reading the shapes you know a payload arrives in is the same snapshot pointed inward: reading one meant reporting "no record contains it" over text the user had typed.
Recursing into nested payloads is the structural answer there --- a shape nested inside one already read is reached with no code change.

- **Do:** ask whether you or the format's author owns the set your instrument enumerates.
- **Do:** match the shape rather than the instances when the answer is the author, and measure the over-matching on real data before adopting it.
- **Do:** apply it to coverage as well as exclusion --- an enumerated list of shapes to read decays exactly as an enumerated list of shapes to reject does.
- **Don't:** read "there is no grammar left" as "there is no parse left";
  a membership test over a foreign vocabulary is a parse whose failure mode is silence.
- **Don't:** count a shortened enumeration as a fix.
  Four names against fifteen is the same defect as one, with better odds.

(Measured 2026-08-28 on [ai-config#2539](https://github.com/Morrison-Lab/ai-config/pull/2539), rounds 8 and 9 of twelve.
Rounds 3 through 8 were grammar;
round 9 was the vocabulary;
round 11 established that neither works, because the harness delivers control tags entity-escaped --- `&lt;system-reminder&gt;` is what it writes when it neutralizes them --- namespaced, split across blocks, or with no angle bracket at all.
The tool was inverted to report records and their provenance rather than classify authorship, which ends the sequence by removing the claim rather than narrowing it.
Round 12 then found the coverage half.)

## Limits

Design, genuine judgment, and semantic work stay with a human or a model:
deciding what to build, weighing a tradeoff, reading whether prose is
clear.
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md)'s own
"Limits" section states the standard and should be read rather than
restated here, including its warning that an instrument with a mushy
threshold trains everyone to ignore it --- a bad tool is worse than the
judgment it replaced.

The difference this principle makes is in how that residue is framed.
It is the part **not yet** automated, shrinking as tools accumulate ---
not a fixed reserve that model reasoning owns by right.
That framing is the whole content of "write ourselves out of a job".

- **Do:** use the instrument that exists, rather than deciding by hand
  what it would decide.
- **Do:** build the instrument that does not exist, once the same
  judgment task has come up twice.
- **Do:** prefer the mechanism that can be reviewed before it runs, even
  where a rule would usually be followed.
- **Don't:** fall back to judgment merely because no tool is at hand ---
  that is the moment the goal fires.
- **Don't:** treat repeated manual work as acceptable because each single
  instance is small.
- **Don't:** automate a genuine judgment badly to satisfy the rule; a
  misfiring instrument is worse than none.

## Fix the class, not the site: route every call through one checked helper

When a review finds a defect that a *second* call site could reintroduce,
patching the sites the reviewer named leaves every future site free to
repeat it.
Routing all of them through one helper that performs the check narrows the
class, and the difference is observable: the raw primitive should appear
once, inside the helper, and nowhere else.
Read "one place the mistake could live" as the helper itself, never as a
tolerance for one stray call --- a stray call is a site the fix missed.

Two counts hide behind that sentence, and only the second is mechanical.
"How many call sites could still commit this defect" is a judgment about
reachability, and this file's own review list rejects an instrument
standing in for a judgment it cannot make.
What a script can count is the raw primitive the helper was built to
monopolize --- occurrences of `subprocess.run` in a file, of a bare
`open(`, of the unguarded API.
Ask the judgment question to decide whether the fix is structural, and
derive the primitive count to say where it stands.
If the primitive appears anywhere outside the helper, the fix went to a
site: one stray call is already an unguarded call site, not a margin.

A helper forbids only what its signature makes unavailable.
Routing every call through one function does nothing if the function still
accepts an unguarded call, and an OPTIONAL parameter is a shape a call site
forgets --- the caller reads as complete without that argument, and nothing
at the call site says otherwise.
So put the input the guarded step is derived FROM in a REQUIRED argument,
and derive the step itself inside.
That forbids OMISSION and nothing else: a call passing an empty or wrong
value still reaches the unguarded behaviour, so report that you closed the
skipping spelling rather than reporting the unsafe call impossible.

Measured 2026-08-22 on
[ai-config#1911](https://github.com/Morrison-Lab/ai-config/pull/1911), at
commit `cf6c47ce`; at the time of writing that PR's branch carries it and
`main` does not.
One commit threaded an optional `overrides=` through the config reads it
knew about and left one pre-existing read without it, which was a live
bypass.
Making the raw `argv` a required argument in place of `overrides=`, and
deriving the overrides from `argv` inside the helper, removed the spelling
rather than the instance --- twice over, since the same helper takes the
pushing command's environment as a second required argument for the same
reason.

State the residue in those terms rather than as an impossibility.
A caller passing `argv=[]` derives no overrides and gets the unguarded read
back, and two end-to-end rows in that guard's own regression suite fail when
an existing call site passes one --- so the value is asserted everywhere the
helper is called today, and nothing stops a NEW call site from spelling it.

A choke point narrows the class without closing it, so say which you
achieved.
The next author can still bypass the helper unless something asserts they
did not --- a test counting the raw primitive, a lint rule, or a
behavioural test that fails when an unguarded call is added.
Absent one of those, "one place the mistake could live" describes the
current revision and not an invariant, and the two claims are worth
different amounts.

This is the same instinct as the rest of this file, one scale down.
An instrument beats a rule because a rule can be forgotten.
A single choke point beats a repeated check for exactly that reason.

Two neighbouring rules cover what this one does not.
[`learn-from-review-findings`](../workflow/learn-from-review-findings.md)'s
recurrence section fires when the same finding class returns to a
*detector* that keeps almost working, and answers by replacing the kind of
evidence.
[`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s "safe
because X never happens" section fires when a second counter-example
refutes one ambiguity, and answers by searching for the general class of
counter-example instead of patching the instance.
The first asks whether the instrument is the right kind of thing; the
second asks how wide the defect is.
Both wait on a recurrence to tell them.
[`learn-from-review-findings`](../workflow/learn-from-review-findings.md)'s
"A fix for a defect class is where a fresh instance of that class hides"
is the closest relative of all, and the complement to this one: it asks where the next instance will be and answers "the fix", where
this asks how many places could host one at all.
This one asks how many places can commit the defect, which a single diff
can answer before any recurrence --- though answerable is not answered,
and a class that reopens after a first fix is evidence that nobody asked.

Measured 2026-08-22 on
[ai-config#1932](https://github.com/Morrison-Lab/ai-config/pull/1932).
That PR added a `PreToolUse` guard and its test suite --- at the time of
writing they sit on its own branch rather than on `main` --- and every
function named below came from one or the other.
A timeout budget was enforced in `_rev_parse`.
Two helpers added later, `_git_config` and `_rev_parse_ref`, each ran
`git` on its own hardcoded timeout and read no deadline, so one path could
spend six unbudgeted subprocess calls --- eighteen seconds against a
ten-second `PreToolUse` timeout that fails **open**.
Patching those two would have left the next helper free to repeat it.
Every call was routed through one budgeted `_run_git`, leaving the guard
with a single `subprocess.run`, inside that helper.

How firmly that is held is worth stating, because the two counts land
differently.
`budget_cases()` asserts the budget behaviourally: it runs the bare push
--- the path with the most calls --- against a `git` shim sleeping a
second per call, and fails on any of four conditions: the hook
exiting non-zero, not denying, denying for a reason other than running out
of time, or elapsed passing 6.0 seconds against a 2-second budget.
The deadline is absolute, set once, so an unguarded call consumes the
budget instead of extending the run: elapsed tracks the larger of the
budget and the number of calls, and about six unguarded calls are needed
to pass 6.0.
Six is exactly the pre-fix shape, which the fixing commit's own
message recorded failing at 6.1 seconds.
So the test catches a wholesale reopening of the class and not one new
unguarded call, which is weaker than "the budget is enforced".
The structural count is asserted by nothing at all.

- **Do:** ask which call sites could still commit the defect to decide
  whether the fix is structural, and derive the primitive's count to say
  where it stands.
- **Do:** treat any occurrence of the primitive outside the helper as an
  unfinished fix, instead of counting to two.
- **Do:** prefer a choke point the next author must go out of their way to
  bypass over a check the next author must remember.
- **Do:** make the input a required argument and derive the guarded step
  inside, so the call that SKIPS it cannot be spelled.
- **Do:** say whether the count is enforced or merely current, and name
  the assertion that would enforce it.
- **Don't:** patch the sites a reviewer happened to name --- they found
  the instances, not the boundary.
- **Don't:** take the un-skippable input as an OPTIONAL parameter --- that
  routes the callers you remembered and leaves the spelling that skips it.
- **Don't:** claim a bypass is impossible when nothing tests for one.
- **Don't:** reach for a choke point when the defect genuinely has one
  site.
  `## Limits` above already says a bad tool is worse than the judgment it
  replaced.

## In review

Flag these with the same weight as the other principle-level findings:

- A hand-performed step that recurs in the same diff, or that the commit
  message says was done repeatedly, with no script proposed.
- A claim reported from reading or recollection where a one-line query
  settles it.
- A new rule written into prose where a hook, a CI step, or an assertion
  could decide the same thing mechanically.
- Two hand-written checks in one diff that ask the same question of the same
  corpus, where the second could have re-run the first.
- Conversely, a new instrument standing in for a judgment it cannot make,
  or built for a task with exactly one occurrence.
- A fix applied to the two or three call sites a reviewer named, where
  routing them through one checked helper would drop the unguarded count
  to zero.
- A guarding input threaded through call sites as an optional parameter,
  where making it required would leave the skipping call unspellable.

(Directives from the user, 2026-07-30: "cai: minimize use of generative
ai in agentic work; maximize use of deterministic, inspectable algorithms
(like hooks)", then "cai: our goal in developing tools, like in all
programming work, is to write ourselves out of a job", "that goes for the
ai-tools repo and everything else we do"
(quoted as said; no repo of that name exists under any of our owners,
so read it as our AI tooling broadly, this corpus included),
"automate everything", and ---
correcting a framing that had set the two halves against each other ---
"it's both a constraint and a goal".
From a session with three judgment tasks done repeatedly by hand: a
`DESCRIPTION` version conflict resolved at least eight times with
identical logic, a PR status line composed from `gh pr checks` output and
once reported from a reading that predated its own pushes, and an ad-hoc
pre-push sweep run in a different order each time, which is why two of
its checks missed things.)
