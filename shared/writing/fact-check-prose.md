When reviewing prose in a PR/MR --- documentation, lecture notes, a README, any
non-code narrative content --- assess it for **accuracy and clarity**, not just
style. This is broader than the terminology check in
[`challenge-ambiguous-terminology.md`](../workflow/challenge-ambiguous-terminology.md):
that guide catches phrasing whose meaning is unresolved; this one catches
claims and reasoning that are resolved but wrong.

One class of source needs naming before the checks below, because it defeats
the premise they rest on.
A **test fixture** looks like a source --- it lives in the repo, it is named
after real output, and its comment often claims to be verbatim --- so a claim
checked against one feels checked rather than guessed.
It is not a source: see
[`fixtures-are-not-evidence.md`](../workflow/fixtures-are-not-evidence.md).

## What to check

- **Factual claims.** Check each claim against the AI's own domain knowledge
  and, where the claim is checkable against an external source (a paper, a
  spec, a package's documentation, a dataset), fetch and check it there too.
  Don't accept a plausible-sounding claim without checking it.
- **Claims inherited from the tracking issue or upstream discussion.** Prose
  copied or paraphrased from the issue body, review thread, or proposal that
  motivated the change is unverified input, not established fact --- the
  author wrote it while proposing, usually without checking the mechanism.
  Before restating such a claim in a code comment, changelog entry, or doc,
  verify it against the mechanism's own documentation the same way you would
  a fresh claim; inheriting it verbatim launders it into text reviewers
  trust. (gha#259/#260: the issue body claimed an untrusted `@claude` mention
  "burns runner minutes"; the implementing session propagated that phrase
  into two workflow comments and a changelog fragment, and it survived two
  review rounds before a fact-check pass caught that a job whose
  [job-level `if:`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idif)
  is unmet never runs (it's marked *skipped*), and GitHub Actions
  [bills only minutes actually used on a runner](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
  --- so the pre-fix gap cost zero minutes.)
- **Undefended claims.** Separately from accuracy, check that each factual
  claim is *defended* --- either by reasoning laid out in the surrounding
  text, or by a citation to an external source. Flag a bare assertion that
  has neither, even when it turns out to be true: a reader has no way to
  verify an undefended claim without redoing the checking work themselves.
  This is distinct from `check-info-quality`'s citation-mismatch check
  (does an existing citation actually back its claim) --- this check is
  about claims that carry **no** citation or reasoning at all.
- **Tool/library behavior claims.** When prose describes how a specific tool
  or library behaves (a git merge driver, a shell built-in, a regex engine, a
  function's edge-case handling) and that behavior is deterministic and cheap
  to reproduce, run a small live test rather than relying on memory or a
  half-remembered doc. A plausible-sounding mechanism description ("union
  merge de-duplicates identical lines") can be wrong in a specific,
  checkable way; a two-minute constructed repro settles it definitively where
  recall alone can't.
- **Document-internal reasoning.** Work through the logic of any argument the
  document makes, not just its individual factual claims --- this includes
  **formal mathematical reasoning** (derivations, proofs, algebraic steps ---
  verify each step follows from the last, check dimensions/units, check
  edge cases and boundary conditions) and **informal reasoning** (an argument
  that X implies Y, a causal claim, a justification for a design choice).
  Flag steps that don't follow, unstated assumptions load-bearing enough that
  the conclusion breaks without them, and conclusions the stated reasoning
  doesn't actually support. This checks whether each *stated* step is valid ---
  for the complementary check (a step missing entirely, where the derivation
  jumps from one line to a non-adjacent one), see
  [`math-derivation-steps.md`](math-derivation-steps.md).
- **Rendered/computed artifacts.** When the document references a computed
  value, a figure, or a numeric result (a fitted coefficient, a plotted
  curve, a table entry), don't take the source prose's word for it --- check it
  against the rendered output. If the project has a rendered preview site
  (a PR-preview deploy, a `gh-pages` branch, a built docs site), fetch the
  live preview and/or the underlying built files on that branch to confirm
  the value or figure the prose describes actually matches what was computed.
  Prefer the live preview when the PR is far enough along to have one; fall
  back to the `gh-pages`/built-output branch's raw files when the preview
  isn't deployed yet or doesn't cover the changed page. Many PR-preview
  setups (e.g. `rossjrw/pr-preview-action`, used by this lab's Quarto repos)
  deploy each PR's rendered site to a `gh-pages` branch under
  `pr-preview/pr-<N>/`, with the direct URL posted in a sticky PR comment ---
  check that comment or the repo's own CLAUDE.md for the exact convention
  rather than assuming a layout.

## What to report

For every claim or reasoning step checked, state:

1. **Which claims are inaccurate**, if any --- quote or point to the specific
   sentence, and say what's wrong with it.
2. **The basis for each judgment** --- cite the specific source checked (a URL,
   a file path and line, a rendered page, a computed value pulled from the
   preview/`gh-pages` branch) so the author can verify the check without
   re-deriving it.
3. **Additional citations or references that would help**, proactively ---
   not just where a claim is already flagged as uncited, but anywhere a
   reader would benefit from a pointer to a source (a foundational
   result, a dataset's documentation, a package's reference page) even if
   the prose isn't currently wrong without it.
4. **Which claims are undefended** --- identify factual claims that carry no
   citation and no internal reasoning, even when the claim itself turns out
   to be accurate.

Silence on a checkable claim reads as "verified" --- don't leave one unchecked
because it sounded right on a first pass.

## Applies to your own PR descriptions and comments too

This checklist isn't just for reviewing someone else's prose --- run it on
your **own** PR description, commit message, and code comments before
posting them, especially any "design choice" claim (a justification for why
the code does X instead of Y, or a claim that it *excludes* / *handles* a
specific case). A design-choice claim is exactly the "informal reasoning"
category above, and it's checkable against the same code you just wrote: did
you actually implement the exclusion/handling you're describing, or does the
claim just describe your *intent*? (gha#201's PR description and code
comments asserted a retry mechanism "excludes" a known bad pattern via a
`stub_review` flag --- but the flag was set purely from "no verdict," with no
check on the signal (`permission_denials_count`) that actually distinguished
the excluded pattern from the retried one. A `claude[bot]` review caught the
gap: the code didn't implement what the prose claimed. Re-reading the claim
against the actual `if` conditions before posting would have caught it
without needing a review round.)

## Prose that distills code is a code claim, checked like code

When prose restates a code formula, invariant, or gate condition -- a UMS pass
distilling a hook into English, a doc summarizing a function's logic -- that
prose is a claim about what the code computes, and it earns the logic
fact-check in [`fact-check-code-logic`](../coding/fact-check-code-logic.md), not
the lighter reading prose usually gets.
A dropped negation or a renamed variable is invisible in the restated form the
way it never is in the code: the right-hand side matches term for term while
only the gate's sense inverts, so the formula computes the exact opposite of
the invariant the surrounding prose defines, with every word around it arguing
for the original.
The restatement gets less scrutiny than the code it came from, not more,
because restating something already verified feels like transcription rather
than a fresh claim.

So evaluate a distilled formula the way you would the code: name what each
variable means, run the gate against a case whose answer you know, and confirm
every negation kept its sense across the rewrite.

- **Do:** fact-check a prose formula, invariant, or gate against the code it
  distills, checking that each negation and comparison kept its sense.
- **Don't:** treat a restatement of already-verified code as transcription
  exempt from the logic check -- the inverted copy reads as authoritative.

(Morrison-Lab/ai-config#1096, 2026-08-03: a UMS pass distilled a hook's
`req_failed = (not last) or err or failure_pattern(body)`, gated by
`if not req_failed:`, into prose that renamed the variable to `released`, kept
the right-hand side, and dropped the negation on the gate -- so the prose
computed the exact inverse of the invariant the section defined, and a reader
copying it would have built the very bug the section warns against.
The reviewer caught it; the fix restored `req_failed`/`if not req_failed` and
turned the mistake into an in-text warning.)

## The general case: any condensation of a verified source is a fresh claim

The section above is scoped to code, and the psychology it names is not.
Its reason --- that a restatement gets less scrutiny than its source
"because restating something already verified feels like transcription rather
than a fresh claim" --- holds for every source, so the same exemption applies
whenever prose condenses **prose**: a paragraph into a bullet, a section into
a heading, a measurement into the sentence that reports what it showed.

The condensed copy is where the falsehood enters, because condensing chooses
the claim's *scope* again, and a shorter sentence is under pressure to choose
it wider.
The source says "the one line", meaning one specific hook; the bullet says
"the one place", and a true narrow claim has become a false general one with
no measurement having changed.

Two things make this survive the checks that should catch it.

**Re-checking the source catches nothing**, which is the whole difficulty.
A pre-push pass that re-verifies your measurements re-verifies the half that
was already right, and never reaches the sentence, because the sentence is
not what you measured.
The gap is not diligence; it is that the verified artifact and the false one
are different artifacts and only one of them gets checked.

**Adjacency launders the claim.**
The false sentence usually sits directly beside the real measurement, so the
measurement's credibility transfers to it while the verification does not.
`fail-fast`'s
["The narration can be the unfalsifiable part, while the check is
fine"](../principles/fail-fast.md) is this exact mechanism in a shell script,
and its explanation carries over unchanged: the label "is the part a reader
believes, because it is phrased as a conclusion while the lines above it are
raw data", and it "survives review of the command" because nothing is wrong
with the command.
Here the raw data is a measurement in the paragraph above rather than a
command's stdout, and the reader who believes the conclusion is the author.

Note that two neighbouring rules read as covering this and do not.
[`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md) supplies
the right claim types -- a widened summary is a **scope** claim -- but its
Do-bullet says to "re-measure any that is not from this turn", and a
condensation and its source are both from this turn, so that bullet reads as
already satisfied at exactly the moment it is needed.
The same file's "a summary of settled conclusions cannot fail, so it cannot
test anything" is true of a summary as an **instrument** and false of a
summary as an **artifact**, which is the intuition this section exists to
contradict.

So check a condensation against its source before pushing, the way the
section above checks prose against code: confirm the scope did not widen, and
that any quantity, count, or uniqueness claim in the short copy is one the
long copy actually supports.

- **Do:** re-read a bullet, heading, or summary sentence against the passage
  it condenses, treating the short copy as an unverified claim.
- **Do:** treat a sentence adjacent to a measurement as unverified unless the
  measurement is about *that sentence*, not merely nearby.
- **Don't:** count re-checking your measurements as having checked what you
  wrote about them -- that pass cannot reach the condensed copy.
- **Don't:** read "both are from this turn" as exempting a restatement from
  re-verification; the source's freshness says nothing about the copy.

(Morrison-Lab/ai-config#1110, 2026-08-03, **seven** findings on one added
section, every one of them a sound observation with an unsound sentence
written about it.
Two were uniqueness claims.
A Do/Don't bullet read "that is the one place it is switched off" in a file
whose own enumeration lists four suppression contexts and closes "All four
were confirmed directly rather than recalled"; the prose it condensed had
said "the one line", scoped to a single hook.
And "capturing the status is the only way to reach the branch that handles
it" was followed immediately by "Measured on bash 5.1.16", a measurement of
return codes that says nothing about whether other forms reach the branch --
three do.
Two were fidelity losses, covered by
[`citations`](citations.md) and by the **cause** claim type respectively: a
quotation with a clause silently dropped from its middle, and a `PATH`
shadowing explanation for a divergence actually caused by a shell function.
Two more were dropped hedges.
One flattened `command -v` and `type -aP` into equivalents in a Do bullet,
when the prose four lines above it had drawn the distinction correctly.
The other shortened "reaches a child shell only if it was exported with
`export -f`" into "a function is not exported", in a prose paragraph rather
than a bullet.
The seventh was a claim about what a *check* returns, asserted rather than
run.

**This record's own sentences kept committing the defect they describe**,
which is the sharpest evidence the section has, and each one was caught by a
reviewer rather than by re-reading.
It read "four findings" because four was true when the sentence was written,
and #1110 went on to seven.
The attribution beside it said the author found the second of each pair by
re-running the reviewer's check, which is true of the uniqueness pair and
false of the fidelity pair, whose second finding records a different origin.
The sentence *directly above this paragraph* then put both dropped hedges "in
a bullet", which is true of one and false of the other -- a detail belonging
to one finding, generalized to its neighbour.
None of those was a bad measurement.
All were sentences *about* measurements, written once and not re-read.

The instances are named rather than counted on purpose.
An earlier draft said "twice over", which a third instance falsified within
one review round -- a running total in a record about stale totals is the one
figure guaranteed to go stale.

ai-config#1101 is the same class arriving independently: an unquantified
superlative in a script comment, false on measurement, in an issue whose own
note records that it was "Corrected 2026-08-03, twice, after filing ... both
the same errors it reports".)

## Check a general claim against the concrete numbers in the same document

The checks above compare prose against an external referent --- the code,
the source, the tool.
The cheapest referent is usually closer than that: a document that reports
a measurement and then generalizes from it carries its own test case, and
the two can contradict each other with nothing external consulted at all.

The shape is a sentence of the form "X behaves like this" sitting near a
figure that only makes sense if X behaves the other way.
Both read fine alone.
The generalization sounds authoritative because it is stated as background
rather than as a finding, and the number reads as a detail of the example
rather than as evidence about the claim.

So when a passage states a rule *and* reports a number the rule governs,
run the rule against the number before publishing.
A mismatch means one of them is wrong, and the number is usually the
trustworthy one, since it was observed while the rule was recalled.
This is the same missing-input-variety tell as elsewhere, inverted: here
the disconfirming case is already present in the text, unexamined.

- **Do:** re-read each general claim against every figure in the same
  passage, and reconcile the two before pushing.
- **Do:** prefer the measured number over the remembered rule when they
  disagree, then re-verify the rule directly.
- **Don't:** treat a number as illustration rather than as evidence about
  the claim it sits next to.

(Morrison-Lab/ai-config#813, 2026-07-29: a memory entry stated that `du`
reports logical size for dataless placeholder files, three paragraphs after
reporting that a placeholder-only OneDrive folder occupied 2.1 MB.
That figure is only possible if `du` reports physical blocks, which is what
it does.
The review caught it by citing the entry's own number back at it; a direct
test then showed `du` = `0B` against `ls -l` = 276 MB on one placeholder.)


**When a disputed figure cannot be recounted, say so and fall back to internal
consistency.**
The section above trusts the measured number over the remembered rule because
the measurement is available.
This is the case where the source measurement is not available anymore, or not
available from the machine making the fix.
A recount that cannot reach the original population is not a stronger
replacement for the disputed number.
It is a new unverifiable number, and publishing it upgrades the claim beyond
what the evidence supports.

Use the part the reader can check without trusting your local data, but do not
pretend the mismatch identifies its own source.
An itemized breakdown and its total are an internal-consistency test: when the
rows sum to one value and the total prints another, one side is wrong.
Prefer the rows only when their completeness is itself inspectable or stated as
a remaining premise; otherwise report the discrepancy without selecting a side.
Then bound the downstream effect rather than leaving the correction open-ended:
check whether derived percentages or labels still hold, and say when they do
not.
This composes with
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md)'s enumeration
rule and
[`fail-fast`](../principles/fail-fast.md)'s count-what-you-examined rule, but it
adds the escape hatch those rules need when the enumeration's scope does not
match the cited source.

- **Do:** report the attempted recount's scope and result, including why it does
  not reproduce the cited source.
- **Do:** use the itemized breakdown over a disagreeing total only when the
  rows' completeness is checkable, and state which derived claims survive the
  correction.
- **Don't:** assert a fresh recounted number when the source population rotated,
  lived on another machine, or otherwise cannot be reached.
- **Don't:** replace one unverifiable figure with another merely because the new
  one came from a command you just ran.

(Morrison-Lab/ai-config#981, 2026-08-01: docstrings claimed a fixture came from
122 real `Agent` launches, while their own rows summed
`48 + 33 + 27 + 9 + 3 + 1 = 121`.
A recount over local `~/.claude/projects/**/*.jsonl` transcripts before
2026-08-01 returned 8 `Agent` `tool_use` records in one key shape, not 121
records spread over the six rows, so the original sample had rotated or lived
on another machine.
The fix therefore used the internally checkable row sum, 121, while naming the
remaining assumption that the rows were complete.
It also corrected the derived label: under whole-percent rounding, 60/122 is
49%, while 60/121 is 50%.)


**An entry's case record is its own test case, and the numbers check above does
not fire on one, because the record reads as the reason the claim is true.**
That check governs a passage that happens to report a figure.
An entry written to this corpus's conventions always reports one, in the
parenthetical case record that closes it, and that record is attached to
*support* the generalization above it.
So it is read as corroboration rather than as evidence the claim is measured
against, and the check goes unrun on the one document guaranteed to hold the
material for it.

Run the rule against its own record before shipping the entry, and again on any
round that edits the rule.
A round addressing a finding about the claim is a likely place for the
contradiction to enter, since attention is on the reviewer's wording rather than
on the evidence below it.
A mismatch means one of the two is wrong, and the numbers check above already
says which is usually which, and that the rule still needs verifying directly
afterwards.
Both halves hold here, with one addition: a case record is authored prose too,
so its own figures are recalled until checked.
A record that contradicts a rule is therefore a counterexample to verify, not a
source to copy from.
Check each side against its referent before re-deriving, and expect the
correction to sharpen the rule rather than only delete a clause: the record is
the concrete thing the generalization was abstracted from, so what it refutes
is usually the step where the abstraction went wrong.

- **Do:** read a case record back against the rule it supports, before shipping
  and after every edit to the rule.
- **Do:** verify both sides against their referents when they disagree, then
  re-derive the rule rather than striking the contradicted clause and leaving
  the rest.
- **Don't:** read a case record as corroboration, which is the stance its
  placement invites and the reason nothing tests the rule against it.
- **Don't:** exempt a bullet you have just rewritten to satisfy a review
  finding, since that rewrite is an edit to the rule like any other.

(Morrison-Lab/ai-config#1073, 2026-08-02: an entry added to
[`address-every-comment`](../workflow/address-every-comment.md) asserted that an
escalation's claimed scope is "by construction wider than the finding, and so
wider than whatever instrument produced the finding".
Its own case record, fifteen lines below that bullet in the same block, reports
that the reviewer's instrument showed five fields while the escalation named
three, which is the reverse.
The five-field figure was present from the entry's first commit, `6b066ec1`.
The clause it refutes was not: that entered at `6bdd4148`, a commit addressing a
Copilot finding about this very bullet, whose message reasons explicitly about
the record's other figures, a two-field probe behind a one-field finding widened
to three.
Round 2 dropped it at `8b0291ae`, and the retraction produced a sharper rule:
the defect was truncating a full-scope instrument, not choosing a narrow one.
The numbers check above had been on the books since 2026-07-29, via
[#816](https://github.com/Morrison-Lab/ai-config/pull/816), and did not fire.
The escalation itself concerned
[#1056](https://github.com/Morrison-Lab/ai-config/pull/1056), merged as
`e1875ff7`.
This entry's own first draft put that distance at eight lines, and measuring it
against the branch gave fifteen, which is why the rule above checks the record
against its referent rather than preferring it outright.)


## Check that a stated trigger actually fired

A justification for why a file was split, a check was added, or a workflow was
changed is a factual claim.
It often reads as background rather than as the change itself, which makes it
less likely to be checked than the mechanics it justifies.
That is exactly why it needs the same fact-check as any other claim.
If the sentence says a threshold, gate, or rule caused the action, read that
gate's source and compare it with the measured state before publishing.
This is an [`algorithmatize-checks`](../workflow/algorithmatize-checks.md)
case: one comparison against the threshold decides it.

Duplicating the justification makes the problem worse, not safer.
Two independently authored copies can share the same false reason when both
sessions inferred the motivation from the same visible action.
A reviewer then sees agreement across files and reads it as corroboration,
although neither copy was ever measured.

- **Do:** verify a stated motivation against the source of the gate or threshold
  it names, and quote the command or value that settles it.
- **Do:** re-check every duplicate copy of the justification, because agreement
  between copies is not evidence that either one was checked.
- **Don't:** treat a sentence about why work was done as less factual than a
  sentence about what changed.
- **Don't:** infer that a threshold fired from the fact that someone took the
  action the threshold would have suggested.

(Morrison-Lab/ai-config#966 and #973 both wrote that
`memories/github-mcp-tools.md` was split out of `memories/github.md` when that
file crossed the 1200-line gate in `scripts/check-memory-file-size.py`.
The gate is `if len(lines) > max_lines` with `DEFAULT_MAX_LINES = 1200`, so it
fires only above 1200 lines.
Walking `memories/github.md` on `main` found a peak of 1199 lines at
`3eb15a4c`, so the gate never fired and the split was pre-emptive.
The same false justification appeared in the new file's header and in
`memories/MEMORY.md`'s index row.)


## A superlative you inherited is one you are now asserting

The **claims inherited from the tracking issue** bullet above covers the
general case.
This is the shape it takes most often and catches least, and two things narrow
it.

The inheritance source need not be the issue.
A sibling repo's code comment is the same unverified input, and porting a fix
between repos is precisely when you reach for one --- the phrase arrives
carrying the authority of having already shipped somewhere else, which the
original never earned either.
And the claim is a **superlative** --- "the most common", "the usual", "almost
always" --- which is the class where measuring is cheapest and the answer is
most often no.

Copying such a phrase does not feel like asserting it.
It feels like carrying context over faithfully, which is a virtue, so nothing
about the moment prompts a check.
It is an assertion, and it inherits none of the verification the original never
had.

A superlative is a quantitative claim wearing prose, so it is decidable by one
command rather than by judgment, per
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md).
Run that command before copying the phrase, rather than after a reviewer asks
for it.

Two notes for when you do measure it.
Fix the wrong claim at every site it reached, deriving that list by grepping
rather than by recollection --- see
[`address-every-comment`](../workflow/address-every-comment.md)'s rule on
deriving a finding's site list, since a superlative that got copied once tends
to have been copied more than once.
And name the denominator of whatever figure replaces it: a percentage
**increase** and a **share of total** answer different questions, and the two
are easy to swap without noticing.

- **Do:** measure a superlative before restating it, whatever its source.
- **Do:** treat a sibling repo's code comment as unverified input, exactly as
  you would an issue body.
- **Do:** name the denominator when a figure replaces a superlative.
- **Don't:** read faithful porting as an exemption, since the copy is your
  assertion now.
- **Don't:** ship a superlative you have not counted even where it turns out to
  be true --- an undefended claim is a finding on its own, per the bullet above.

(`Morrison-Lab/gha#398`, 2026-08-03: a sentence-splitting regex fix was ported
from `Morrison-Lab/ai-config`, and the claim that `**Claim.** Explanation.` is
"the corpus's most common paragraph opener" came across with it --- out of
gha#397's issue body, and out of ai-config's own
`scripts/semantic-line-breaks.py` comment, added by ai-config#1098.
It was restated in four places before review flagged it as an unquantified
superlative.
Measured 2026-08-03, it is false: the construction accounts for 561 of 3398
multi-sentence lines in ai-config's Markdown, 16.5%, about one in six --- so
common, and not most common.
The upstream instance is filed as
[ai-config#1101](https://github.com/Morrison-Lab/ai-config/issues/1101).
The denominator note above comes from a separate finding on the same PR, which
caught 561/2837 = 19.8% --- the increase over the old count --- being reported
where 561/3398 = 16.5% was meant; only the second answers how much the old
regex had been hiding.)
