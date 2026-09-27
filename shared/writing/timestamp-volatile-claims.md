When you state a factual claim about a **condition that can change over
time**, attach the time the claim was true --- "as of 2026-07-24", or the
abbreviated "(checked 2026-07)". This applies everywhere a reader may
revisit the text later: chat replies, PR/issue/commit prose, docs, READMEs,
code comments, and memory files.

A timestamp makes staleness self-evident. A later reader --- including future
you --- can see the claim's vintage and know to re-verify it, instead of
trusting a bare present-tense assertion that has silently gone stale. An
undated volatile claim reads as a standing, timeless fact, so it gets
repackaged into fresh present-tense assertions without anyone re-checking the
underlying condition.

## What counts as volatile

A claim is volatile if updating the world could falsify the sentence without
touching the sentence itself:

- Software, tools, APIs, harnesses, and platforms --- "package X is on CRAN",
  "feature Y is supported", "the API doesn't expose Z", "the flag default is N".
  All facts about third-party software behavior,
  configuration options, runtime thresholds,
  and architecture are empirical observations,
  not timeless definitions.
- "Current", "latest", "now", "recently", "still" claims --- a version number,
  a default, a "the newest model is ...".
- Counts, prices, dates, and roster facts --- "there are N consumers", "it
  costs $M", "A maintains it", "the pin is K commits behind".
- Anything you verified by looking it up just now --- if you had to check it,
  its answer can change, so record when you checked.

Prefer an **absolute** date over a relative word: "as of July 2026", not
"currently" / "now" / "recently" --- the same reason the memory rule converts
relative dates to absolute ones. A relative word is itself a claim that goes
stale the moment the text is read later.

## What does not need a timestamp

Timeless facts whose truth value can't flip --- a mathematical identity, a
definition, a language's fixed semantics ("R uses 1-based indexing"), a
historical event's date. Don't clutter these with an "as of"; the target is
specifically claims that a future change could falsify.

## A product's distinction between two mechanisms is not one of those definitions

The exemption above is the one that gets misapplied, because a vendor's own
taxonomy reads exactly like a definition.
"A command is user-invoked and a skill is model-invoked" says what each thing
*is*, which feels like a language's fixed semantics rather than a claim a
future change could falsify.
It is a design decision someone at that vendor can revisit, and revisiting it
is ordinary product work.

So before writing down a dichotomy between two mechanisms of a third-party
tool, check in that tool's current docs that the dichotomy still exists.
Then date it, per the absolute-date rule above.
Two file types can collapse into one mechanism with a frontmatter switch, and
the sentence you learned a year ago will not have changed to tell you.

What makes this decay invisible is that the retired form usually keeps working.
A vendor merging two mechanisms leaves the older spelling supported, so nothing
in your own repo errors, no check goes red, and nothing prompts a reader to
look anything up.
The distinction has stopped being true while every artifact built on it goes on
behaving exactly as before.
That is sharper than an ordinary stale claim, because the usual evidence for a
claim's currency --- everything still works --- is precisely what a
compatibility shim manufactures.

The tell is a corpus that still contains **both** forms, plus a mental model
explaining why each one is there.
That state is equally consistent with two live mechanisms and with one
mechanism plus a legacy spelling, so it cannot itself tell them apart, and the
presence of both is what keeps the retired distinction feeling current.

- **Do:** re-read the vendor's own current docs before teaching a distinction
  between two of its mechanisms, and date what you find.
- **Do:** treat a corpus holding both forms as a prompt to re-check, since that
  is the state a merge leaves behind.
- **Don't:** file a vendor's taxonomy under the definitions exemption above ---
  a definition cannot flip, and a product decision can.
- **Don't:** read "everything still works" as evidence the distinction holds;
  backward compatibility is what hides the collapse.

(Morrison-Lab/ai-config, 2026-08-04: this corpus ships 177 skill directories
and one `commands/` file, and a session explained that split to the user as two
mechanisms told apart by file type.
Claude Code had merged custom commands into skills: both spellings create the
same `/name`, the skill wins a name collision, and invocation is carried by
frontmatter rather than by directory.
Nothing in the corpus was broken by the merge, which is why the belief survived
unexamined.
The product facts are in
[`memories/claude-code.md`](../../memories/claude-code.md).)

## The failure mode it prevents

Repo docs stated "snapr is not on CRAN or P3M." That was true when written,
but undated, so it read as a standing fact --- and it was restated as a fresh
present-tense assertion ("snapr isn't on CRAN at all") without re-checking,
even though snapr had since been published to CRAN (0.1.0, 2026-05-22). A
timestamp on the original --- "not on CRAN as of <date>" --- would have marked
it as a fact with a vintage, worth re-verifying before repeating.

## A claim inside a PR is read at merge time, and a shipped one outlives that

The failure above decays slowly, over however long an undated claim sits
unchallenged.
The interval that matters inside a PR is far shorter, and the claim can be
true, freshly verified, and correctly written and still be false by the time
anyone reads it.

A PR body, a review comment, a commit message, and a **source-file comment**
added by the change are each composed once and read later --- at review, at
merge, and afterwards in the log or the file.
That fourth class is the one to watch, and the easiest to leave out of the
list, because the other three are review artifacts that scroll away while a
YAML or code comment ships and stays.
So a claim about mutable state inside any of them carries an implicit "as of
when I wrote this" that a reader has no reason to look for, and a PR's own
lifetime is long enough for the state to move.
Anything a human can change while the PR is open qualifies: a repository
secret, a branch protection rule, an org setting, a dependency's version, a
sibling PR's status.

The increment over the re-derivation rules is the **trigger**, and it is worth
stating precisely.
[`ardi`](../workflow/ardi.md)'s verification-table rules already require
re-deriving a PR body's figures, and every one of them keys on a **push** ---
a round that changes the diff expires the figures that round was about.
A PR sitting open while *external* state moves trips none of them.
Nobody pushed, the diff did not change, and the claim went stale anyway,
because a repository secret is not an artifact your commits control.
So this widens both the trigger, from a push to the merge itself, and the
claim class, from figures you derived to state somebody else owns.

So a timestamp is necessary and not sufficient.
Marking the vintage tells a later reader to re-verify, which is the right
remedy for docs nobody is about to act on.
A PR **is** acted on, so a mutable-state claim inside one owes a re-check
before merge as well --- re-run the query, and correct the text when the answer
has moved.

- **Do:** re-derive any mutable-state claim in a PR body or comment before the
  PR merges, not only before writing it.
- **Do:** timestamp it as well, so it stays checkable in the log afterwards.
- **Don't:** treat "I verified this when I wrote it" as covering a claim a
  reader will meet days later.

(The incident is measured; the re-check-before-merge remedy is inferred from
it, on a single occurrence.
Measured 2026-08-24 on the `UCD-SERG/ucd-serg.github.io` gha migration.
`WORKFLOW_TOKEN` was measured absent from the repo, and "Not set in this repo"
went into a comment in `.github/workflows/claude.yml` --- a shipped source
file, not a review artifact, which is what makes it the fourth class above.
The user added the secret org-wide while the work was still in flight, so the
comment was false before it merged and would have stayed in the tree.
Commit `a4589dec`, whose subject begins "Correct the WORKFLOW_TOKEN comment",
touches only that file.
Reported by the agent that made it.
Tracked as ai-config#2149.)

## The corpus prose a PR adds is the same class, and a sibling PR is a third trigger

The section above names four surfaces --- a PR body, a review comment, a commit message, and a source-file comment --- and calls the fourth the one to watch, because it ships and stays where the other three scroll away.
A fifth is easier to miss than any of them: the **corpus prose the PR is adding**.
A memory entry or a shared fragment describing how a hook, a script, or a workflow behaves is not a comment riding alongside the change.
It is the deliverable, so nothing about writing it feels like asserting mutable state --- and it ships and stays exactly as the fourth class does.

The trigger widens too, and the new one is neither of the two already named.
That section moved the trigger from a push to this PR out to this PR's own merge, keying on state **somebody else owns** --- a repository secret, an org setting, a dependency version.
A sibling PR in the same repository is a third case, and it is nearer than either: it changes the very file the prose describes, in the tree this PR will merge into, while this PR sits open.
No push happened here, the diff did not change, and the merge has not arrived, so neither existing trigger fires.

The remedy is the same query aimed one step later: re-read the artifact the prose describes at its current state on the default branch, rather than trusting the reading that produced the sentence.
A measurement is a statement about a moment, and the moment passes whether or not anything you did made it pass.

- **Do:** re-read the file a corpus entry describes, on the current default branch, before the entry merges.
- **Do:** write a preserved reading in the past tense ("the regex was then"), and state the present state separately.
- **Don't:** treat corpus prose as exempt because it is the deliverable rather than a comment attached to one.
- **Don't:** read "no push since I measured" as "nothing changed" --- a sibling PR merging is the commonest way the artifact moves underneath you.

(Measured 2026-09-18 on ai-config#3778.
A `memories/claude-code-hooks.md` entry quoted `hooks/no-push-without-self-review.py`'s `tid_match` regex as lacking `agentId`, which was true when it was measured.
ai-config#3737 added `agentId` to that regex and to `TASK_ID_KEYS_SPECIFIC`, merging at 2026-09-18T07:15:19Z --- before #3778 was opened, and while its branch was being written.
The reviewer caught it; the session had not re-read the file.
That entry's own subject is trusting a measured artifact over a recollection.)

## A date is coarser than the artifact it dates, when the artifact changes same-day

Everything above treats a date or "as of" stamp as the fix for a volatile
claim.
That assumes the date resolves to one state of the artifact being measured.
It does not when the artifact is edited more than once on the day the
measurement is dated --- a hook, a script, a regex --- and a corpus-scale
figure is quoted against it with no commit named.

A date and a chunk size are not enough to make such a figure reproducible,
because they under-determine the one thing a reader would need to re-run it:
which revision of the code that produced the classification the figure
counts.
Two commits made hours apart on the same calendar day can each change what
"fires" means, so "2026-09-17" resolves to several different true answers
depending on which of that day's commits is meant.

(Measured 2026-09-17 on `ai-config#3737`,
`hooks/warn-unmeasured-capability-claim.py`'s docstring, which reports
"2000-character chunks: 81 of 1992 fire, 4.1%, down from 5.7% before the
branches below were trimmed" and dates the whole measurement to
2026-09-17 with no commit named.
Reproducing the sweep independently, over the same `shared/**/*.md` chunking
at 2000 characters against the code as it stands on this branch, gives 83
hits over 2004 chunks when every trailing partial chunk is kept, or 81 hits
over 1849 chunks when partial trailing chunks are dropped --- neither
matches the docstring's own 81/1992 exactly, because "how a chunk is formed"
is a second undocumented parameter the date does nothing to pin.
A parallel review round on the same PR reproduced 81 of 1994 against the
committed tree and 80 of 1992 against the pre-PR base tree: the numerator
the docstring quotes and the denominator it quotes came from two different
tree states that never coexisted, which a same-day timestamp cannot reveal
because both states share that timestamp.)

- **Do:** name the commit SHA a corpus-scale figure was measured against,
  not only the calendar date, whenever the code producing the classification
  can plausibly change more than once that day.
- **Do:** state the chunking, windowing, or sampling method precisely enough
  that a reader's re-run and the original run count the same population ---
  "2000-character chunks" is under-specified without saying whether a
  trailing partial chunk counts.
- **Don't:** treat a date as pinning a measurement once the measured
  artifact is itself under active edit; pin the commit instead.
- **Don't:** quote a numerator and a denominator as a pair without
  confirming both came from one run against one tree --- a pair assembled
  from two different revisions can be individually accurate and jointly
  impossible.

### Adding the provenance is not taking the measurement

The rule above is easy to satisfy in appearance and miss in substance,
because everything it asks for is *text you write* rather than a command
you run.
A revision that attaches the date, the command, and the expression to a
figure reads as the corrected version of an undated one --- and that is
exactly the reading the next reviewer gives it, since the apparatus is what
they were told to look for.

The near-miss is a revision that carries all three and leaves the NUMBER
where it was.
Nothing about the sentence says so: a stale figure is indistinguishable from
a re-derived one once the command sits beside it, and a reviewer who re-runs
the command is the only detector.

(Morrison-Lab/ai-config#3928, round 20, finding 4.
`hooks/flag-self-authored-verdict-echo.py`'s dotted-code-span figure was
corrected once, from an undated 11017 to a dated 12739 carrying its command
and citing this fragment by name.
Re-running that command gives 12783 at the branch's merge base, 12798 at
171efa1a and 12805 at f6e6d242 --- 12739 reproduces at no commit on the
branch, so the revision that added the provenance had not re-measured.
The same revision also asserted the file count had "moved 744 -> 745 within
this branch" while `git log --diff-filter=AD -- '*.md'` returns nothing over
that range and the denominator was 746 throughout --- a movement invented in
the course of explaining the correction, and the most persuasive sentence in
the passage, since a figure shown to be moving reads as one somebody watched.
The figure now names a commit rather than a date, because the total moves
with every prose commit and 2026-09-25 alone holds two of the three totals
above.)

- **Do:** re-run the command in the same edit that attaches it, and paste
  what it returned.
- **Do:** name the commit when the figure moves faster than the calendar
  --- a per-commit corpus count is dated by a SHA, not by a day.
- **Don't:** treat adding a date, a command, or a cited convention as
  having re-derived the figure it now sits beside.
- **Don't:** narrate a figure's history from memory while correcting it ---
  "it has since moved X -> Y" is a second claim, derivable by one `git log`,
  and asserting it unverified is how a correction adds an error.

## Relationship to other rules

- [`fact-check-prose.md`](fact-check-prose.md) checks that a claim is *true*
  now. This rule is complementary: even a true claim needs a timestamp when
  its truth is time-dependent, so it stays checkable later instead of
  decaying into a confident falsehood.
- The `check-info-quality` skill is the **detector** that finds
  already-stale claims after the fact; this rule prevents them at authoring
  time by making each volatile claim's vintage explicit.
- `CLAUDE.md`'s "Timestamp recaps in local time" and the
  convert-relative-dates-to-absolute memory rule timestamp *when you acted or
  spoke*; this rule timestamps *when a volatile fact was true* --- a different
  quantity that happens to share the "prefer absolute dates" mechanics.
- [`ardi.md`](../workflow/ardi.md)'s verification-table rules re-derive a PR
  body's figures, keyed on a **push**.
  "A claim inside a PR is read at merge time" above is the complement:
  it keys on the **merge**, and covers state somebody else owns, which no
  push of yours disturbs.

## In review

An undated volatile claim is a review finding, the same weight as an uncited
one: ask for a timestamp, or a rephrase to something timeless. Apply it to
your **own** PR descriptions, comments, and commit messages too, not just
when reviewing someone else's prose.

Where the claim is about mutable state, ask for the re-check as well as the
timestamp, per "A claim inside a PR is read at merge time" above --- a vintage
tells a later reader to re-verify, and does not stop the claim shipping false.

## The prior question: does the sentence need the figure at all

Everything above assumes the volatile fact earns its place and asks how to
keep it honest once it's there.
That assumption is worth checking first, because a figure that keeps
decaying despite careful pinning is sometimes not a timestamping problem at
all --- it's a sign the figure was never load-bearing.

The tell is a single number taking several drafting rounds to state
correctly, each round adding a qualifier the last round lacked: which
population it counts, which commit it was read on, whether writing the
sentence itself changes the count.
Every fix is locally correct and the volatility never stops, because each
round is solving the stated problem (make this figure accurate) rather than
the prior one (does the rule need this figure to hold).
When the surrounding rule reads identically with the number removed, the
number was never carrying the argument, and removing it dissolves the
volatility that further pinning could not.

The worked incident is in
[`reorganize-prose.cases.md`](reorganize-prose.cases.md), "A sweep's count
moves while you write the sentence about it", which carries the four drafts,
the collision table, and the measurements.
It is not restated here: that record is the incident, and this section is the
question it prompts.

This is the question to ask **before** reaching for a vintage stamp, not
instead of it: a figure the argument genuinely depends on --- a threshold, a
count a reader will act on --- still needs the timestamp-and-re-check
treatment above.
The check only rules out the figures that were decorative all along.

- **Do:** before pinning a decaying figure with a timestamp, check whether
  the sentence it lives in argues the same thing with the figure removed.
- **Do:** delete a figure once removing it changes nothing about the rule's
  force, rather than pinning a fourth, more careful version of it.
- **Don't:** spend a second or third drafting round making a figure more
  precise when the real defect is that the figure was never necessary.
- **Don't:** treat "the figure is now more carefully qualified" as progress
  when the qualifying itself is the symptom.

(Measured 2026-09-09, ai-config#3499: a single figure ("N hits across M
files") took four drafts.
The first mixed two populations; the second omitted the commit it was read
against; the third asserted a tip-of-branch figure that the sentence
containing it falsified on its own, since writing the sentence added a
literal occurrence of the very string being counted.
Three rounds of increasingly careful pinning were solving the wrong
problem: the rule containing the figure worked identically whether it read
94 or 98, so the figure was never load-bearing, and removing it dissolved
the volatility rather than requiring a fourth round of qualification.)

**Second occurrence, 2026-09-21, same mechanism, a different surface: a source-code comment, not prose.**
`Morrison-Lab/ai-config` PR [#3826](https://github.com/Morrison-Lab/ai-config/pull/3826), commit `8f0a0d28`, replaced an invented count ("fifteen-odd hooks") with a derived one and quoted the deriving query beside it so a reader could re-run it: `` `grep -rln '"tool_calls"' hooks/*.py` returns 33 files, 24 of them not tests ``, written into a comment in `hooks/no-unread-issue-claim.py`. Quoting the grep pattern verbatim put the literal string `"tool_calls"` into that same file's comment, so the file joined its own result set the instant the comment was committed --- re-running the quoted command afterward returns 34, not 33. The number was wrong by one at the moment of the commit that derived it, which is the same self-invalidation ai-config#3499 records ("writing the sentence added a literal occurrence of the very string being counted"), confirming the mechanism is not specific to prose: quoting a search pattern beside its own result count is unsafe wherever the quoting itself is greppable text, source comments included. The next commit, `da240cf2`, fixed it by deleting the number and describing the query instead of quoting it verbatim --- the same remedy this section already prescribes (delete rather than re-pin).

**The same commit (`8f0a0d28`) had an adjacent, structurally identical figure and applied a THIRD remedy shape to it, distinct from both re-pinning and deriving-and-quoting.**
A second invented figure, "nine lines from the end," named where a special case sat in the file.
The commit's own working notes located it precisely ("the ANTIGRAVITY_AGENT check is at line 644 of 656"), but that derived line number never reached the source: the comment instead reads "in `main` below," pointing at the code by its role rather than by any number at all.
Dissolving the reference beats deriving and pinning it, for the reason this section already argues about deleting a decorative figure: a derived number is accurate only until the file moves again, and a reader who trusts it without re-deriving inherits the same staleness risk a hand-typed figure carries --- while a reference by role survives the file changing shape entirely.
The self-invalidating count above and this dissolved one are the same commit's two responses to "a number decorates this claim," and only one of them chose not to have a number at all.

- **Do:** before quoting a search pattern beside a derived count, check whether writing that quotation into the destination file changes what the pattern matches there.
- **Do:** prefer describing a location by its role ("the check below," "the function this hook borrows from") over citing a derived line number or count, when the reference does not need to be that precise --- a role survives edits a number does not.
- **Don't:** assume applying the right general fix (derive, cite the query) once in a commit means every instance of the same figure-writing pattern in that commit is now safe --- check each one for the self-reference hazard separately.
- **Don't:** treat "derive it and quote the query" as the only safe remedy for a decorative figure --- dissolving the figure into a role-based description is available whenever the number's only job was to locate something, and it needs no future re-derivation at all.
