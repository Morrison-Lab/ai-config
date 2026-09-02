When reviewing prose in a PR/MR --- documentation, lecture notes, a README, any
non-code narrative content --- assess it for **accuracy and clarity**, not just
style. This is broader than the terminology check in
[`challenge-ambiguous-terminology.md`](../workflow/challenge-ambiguous-terminology.md):
that guide catches phrasing whose meaning is unresolved; this one catches
claims and reasoning that are resolved but wrong.

Worked-example case records for the rules below live in
[`fact-check-prose.cases.md`](fact-check-prose.cases.md), moved out of the auto-loaded context.

One class of source needs naming before the checks below, because it defeats
the premise they rest on.
A **test fixture** looks like a source --- it lives in the repo, it is named
after real output, and its comment often claims to be verbatim --- so a claim
checked against one feels checked rather than guessed.
It is not a source: see
[`fixtures-are-not-evidence.md`](../workflow/fixtures-are-not-evidence.md).

A fixture is one instance of a wider substitution: the artifact inspected is
adjacent to the one the claim is about, so the evidence is genuine, the
reasoning from it is sound, and the conclusion is false.
The checks below all assume the object in hand is the object under discussion.
[`verify-the-right-artifact.md`](../workflow/verify-the-right-artifact.md)
covers confirming that, and the shapes the substitution takes when it is not
so.

## What to check

- **Factual claims.** Check each claim against the AI's own domain knowledge
  and, where the claim is checkable against an external source (a paper, a
  spec, a package's documentation, a dataset), fetch and check it against the local `sources/` corpus.
  Do **not** fall back to the open web (`WebFetch`/`WebSearch`) if the local source is missing or incomplete.
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
- **Displayed equations vs the implementation they cite.**
  When the document says an equation is what the Stan, R, or JAGS
  code, the R runner, or the simulator implements,
  read that implementation.
  A derivation that is algebraically fine but is not what those
  programs do is still a finding: the filter, the mixture,
  the defaults that produced the tables, and similar choices,
  not only the algebra on the page.
  (UCD-SERG/shigella#31, 2026-08-25:
  `@eq-lpfilter` used the per-chain max of `lp__`.
  Every R runner used the median.
  `@eq-brt` wrote a truncated exponential.
  The R likelihood mixed a uniform into that density.
  `@eq-joint` and `@eq-shared` wrote `p(y | y_0^{(k)})` for the
  never-infected branch.
  The R likelihood used `y_f = 0` instead.
  The R simulator evaluated a decay-only curve
  while the design said to evaluate `@eq-curve`.)

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
- **Do:** re-read the bullets *after* correcting the prose above them --- a
  bullet written before the correction is not covered by having made it.
- **Do:** treat a sentence adjacent to a measurement as unverified unless the
  measurement is about *that sentence*, not merely nearby.
- **Don't:** count re-checking your measurements as having checked what you
  wrote about them -- that pass cannot reach the condensed copy.
- **Don't:** read "both are from this turn" as exempting a restatement from
  re-verification; the source's freshness says nothing about the copy.

## A command written into documentation is a condensation of the code that builds it

The two sections above cover prose that distills code and prose that distills
prose.
A **command** written into guidance is the same act wearing a disguise: it
reads as an artifact rather than a claim, because it is copy-pasteable and it
runs.
It is still a condensation, and of the least forgiving kind, because what it
condenses is frequently a script that assembles the command
**conditionally** --- so the flat form quietly asserts that those conditions
do not exist.

The carve-outs are what get dropped, and they are the load-bearing part.
A tool that omits a flag in several cases omits it for reasons, and at least
one of those reasons is usually safety rather than convenience.
A reader who follows the documented unconditional form in a carved-out case
does the unsafe thing while believing they followed the docs, which is worse
than there having been no documentation for that case at all.

**Having applied the carve-out yourself is not having written it down.**
That is the part worth naming, because it defeats the remedy the section
above prescribes.
There, re-checking the source catches nothing because the verified artifact
and the false one are different artifacts.
Here the source was not merely verified: it was **obeyed**, minutes earlier,
in the same session, correctly.
Executing a command and documenting one are separate acts, and knowledge that
reached the first does not cross into the second on its own --- so the
feeling of knowing the rule is at its strongest exactly while the sentence
dropping it is being typed.

So when documenting a command that a repo's own tooling constructs, read the
constructing code and port every branch, or say plainly that the form given
covers the common case and name where the tool departs from it.

- **Do:** read the script, action, or function that builds the command, and
  carry each of its conditions into the documented form.
- **Do:** say which case the documented form covers, when you deliberately
  give only one.
- **Don't:** document the unconditional form of a conditionally-constructed
  command --- the flat version asserts the conditions are absent, and says so
  silently.
- **Don't:** treat having just run the command correctly as evidence about
  the sentence describing it; obeying a rule and stating it are different
  acts, and only the second one ships.

(`UCD-SERG/shigella#46`, 2026-08-31.
Guidance was written reading
`gh workflow run claude-code-review.yml --ref <pr-branch> -f pr_number=<N>`,
with no conditions attached.
`Morrison-Lab/gha`'s `.github/workflows/scripts/dispatch-review.sh` omits
`--ref` in four cases, read at `838011e`: a fork PR, a `PR_BRANCH` it cannot
resolve, a PR editing top-level `.github/workflows/*.yml`, and a changed-file
listing it cannot complete.
Its own header comment names the first three, so the fourth is derivable only
from the code --- which is the same lesson one level down, since the header
is itself a condensation of the branches below it.
The workflow-editing case is a trust boundary rather than a convenience: with
`--ref` pointed at the PR branch, GitHub executes the PR head's own
unreviewed caller YAML under the repository's model credentials, which is
what [`Morrison-Lab/gha#598`](https://github.com/Morrison-Lab/gha/issues/598)
exists to prevent.
The same session had applied that carve-out in its own dispatch, choosing the
default branch as the ref precisely because the PR edited workflow YAML, and
then wrote the unconditional form into the guidance anyway.
An [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) subagent
found it.)

## An edit made for precision can assert what the loose version never did

The section above covers a **condensation**, where a shorter restatement widens
scope because a short sentence is under pressure to choose it wider.
This is the neighbouring transformation, and it usually runs the other way.
A **precision** edit adds specificity: which proposition, which operation,
which object.
Each added specific is a new checkable claim, so tightening raises the claim
count, at the moment confidence in the sentence is highest.

The loose original was not vague by accident.
Vagueness is how it avoided committing to anything, so it could be correct
without asserting much.
The sharper replacement commits, and a commitment can be false.
So the point is not that prose can be wrong, which is obvious.
It is that the **tightening pass is itself a source of new false claims**, and
it is the pass least likely to be re-read, because its stated purpose is
accuracy.

**The tell is a word.**
"exactly", "precisely", "just", "identical to", "the same" --- words added
while sharpening, which upgrade a loose relation into an asserted identity.
They are the same word-class an overclaim sweep removes ("will be", "always",
"appropriately"), met from the opposite direction: a sweep deletes them, and a
precision edit installs them.

That yields the part worth keeping, which no amount of care on any single pass
supplies.
**An overclaim sweep is not a one-time pass over a file.**
It is a check on each edit, and most of all on an edit whose purpose is
improving precision.
A file swept clean does not stay clean, and the edit most likely to reintroduce
the defect is the one that feels like it is fixing it.

- **Do:** re-read a sentence you tightened as a fresh claim, checking each
  specific it now names --- the proposition, the operation, the object.
- **Do:** require the identity that "exactly", "precisely", "identical to", or
  "the same" asserts to actually hold, rather than reading the word as
  emphasis.
- **Do:** re-run an overclaim check on the edits that follow one, rather than
  counting the file as swept.
- **Don't:** exempt a precision edit from checking because its purpose was
  accuracy --- that purpose is what suppresses the check.
- **Don't:** read the looser original as the weaker sentence; it may have been
  correct precisely by declining to commit.

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

## A clause you carried through a rewrite is a claim you are now asserting

The section above covers a phrase you bring **in** from somewhere else --- an
issue body, a sibling repo's comment --- where the tell is that copying feels
like faithful porting.
This is the nearer miss and it has no import step at all: the clause was
already in the sentence, and you rewrote the sentence around it.

[`ascii-punctuation-in-source`](../coding/ascii-punctuation-in-source.md) states
the line-level form --- touching a line makes its contents yours, because the
diff cannot tell which words you meant to change.
The content-level form has no check behind it, so nothing reports it at all.

Rewriting a sentence puts every clause in it under your name, including the ones
that rode through unexamined: a locator, a figure, an attribution, a claim about
what some other file says.
Those parts go on feeling like someone else's while you work, precisely because
you were not thinking about them --- and that feeling is the defect rather than
a symptom of it.
Attention went to the clause being changed, and the untouched clause quietly
inherited the confidence of the rewrite around it.

The check has to be deliberate, since nothing prompts it and the sentence reads
as freshly written.
Read the finished sentence back as though you had written it from scratch, and
verify each factual clause against its referent rather than against your memory
of having left it alone.

- **Do:** verify every factual clause in a sentence you rewrote, not only the
  part you rewrote it for.
- **Do:** re-check locators and figures specifically, since those are the
  clauses a rewrite is least likely to touch and most likely to invalidate.
- **Don't:** treat a clause you did not deliberately change as still belonging
  to whoever wrote it --- you shipped the sentence.
- **Don't:** read this as covered by the import rule above; there is no source
  to have been faithful to, which is what removes the moment of doubt.

## A definition can resolve, render, and still say nothing

The "Rendered/computed artifacts" bullet above covers a computed value or a
figure the prose describes.
A **definition** is checkable against the rendered page in the same way, and it
fails in a way the source cannot show.

When a macro corpus contains **aliases**, both sides of a definition can expand
to the same glyph.
A line written as `\score(\lambda) \eqdef \llik'(\lambda)` names a concept on the
left and defines it in terms of the log-likelihood on the right, which is exactly
what a definition should look like.
Expand the aliases and it is `A \eqdef A`.
The rendered page shows a symbol defined as itself.

Two properties make it survive every check short of reading the output.

**The source reads correctly**, because the two names are genuinely different
strings and each is genuinely defined.
Nothing about the line is malformed, so no linter, no render warning, and no
source-reading reviewer has anything to report.
Only expansion collapses the two sides, and expansion happens at render time.

**Checking that the reference resolves answers a different question.**
Confirming that `@def-score` has a matching `::: {#def-score}` target, that no
`?@` marker leaked into the HTML, and that the crossref numbers correctly,
establishes that the definition **exists**.
It establishes nothing about whether the definition **says** anything.
That gap is easy to walk into precisely because the resolve check is real work
and comes back clean.

So the general rule: **a check that a reference resolves is not a check that the
referenced thing has content.**
Read the rendered form of a definition, not its source, and read it for whether
the two sides differ after expansion.

Where a corpus defines the concept canonically, prefer its form over an alias
restatement.
Spelling the operator out (`\deriv{\lambda}\llik(\lambda)`) says something the
alias cannot, and a definition that merely renames is usually a deviation from
the corpus's own house style rather than a shorthand for it.

- **Do:** read a definition's rendered output and confirm the two sides differ
  after macro expansion.
- **Do:** grep the macro corpus for the concept's canonical definition before
  writing your own, since a library that has aliased a symbol has usually
  defined it properly somewhere too.
- **Don't:** treat a resolving crossref, a clean `?@` scan, or a correct
  definition number as evidence that the definition has content.
- **Don't:** define a macro'd concept by restating another macro, which is the
  form that collapses under expansion while reading perfectly in source.

## Confirm a rendered page carries your commit before reading anything off it

The "Rendered/computed artifacts" bullet above sends you to the preview.
The section directly above sends you there again, to read a definition's
expanded form.
Neither says how to tell that the page you fetched is the one your branch
produced.

A published preview is a **build**, not a view of your branch.
Three things put a lag between the two, and they compound: the build has not
started yet, the build is still running while later pushes queue behind it, and
a cache serves whatever was deployed last.
So the page can sit one commit behind, or several, with nothing on it saying
so.

The failure direction is the expensive one.
A stale page still shows the defect you already fixed, so it argues for
re-fixing correct code.
Unlike an ordinary stale reading, the natural response is to **edit**, on top
of a file that was already right.
That reading is also the one that feels diligent, since it looks like catching
your own incomplete work.

The positive test costs one grep.
Pick a string your commit introduced that no earlier build could contain, such
as a renamed symbol, a new sentence, or the corrected side of a definition.
Search the fetched page for it.
Present means you are reading your build.
Absent means you are reading an older one, and the page is silent about your
fix rather than evidence against it.
That is [`fail-fast`](../principles/fail-fast.md)'s denominator move applied to
a page: a check that cannot separate "not fixed" from "not built yet" is not
yet a check.

The mechanics live elsewhere and are not repeated here.
[`memories/github-remote-sessions.md`](../../memories/github-remote-sessions.md)
covers reading the deployed
bytes off `gh-pages` when the served URL is blocked, and reading that branch's
own commit log to see which build is actually deployed.
[`check-rendered-refs`](../../skills/check-rendered-refs/SKILL.md) covers the
local rendered tree, where the fix is a re-render rather than a wait.

- **Do:** grep a fetched page for a string unique to your commit before drawing
  any conclusion from it.
- **Do:** compare the docs build's own duration against your push spacing when
  a preview keeps disagreeing with your source, since pushes that outpace
  builds guarantee a lag.
- **Don't:** read a defect still present on a preview as evidence your fix
  failed; a build predating the fix looks exactly like that.
- **Don't:** treat a preview comment's timestamp, or the mere existence of a
  deployed page, as saying which commit it was built from.

A CDN copy of the deployed site is a further step removed than the build is,
and reading one for the branch's own bytes is the same substitution one layer
out; see
[`verify-the-right-artifact.md`](../workflow/verify-the-right-artifact.md).

## A block presented as program output is a claim, so capture it rather than composing it

A fenced block introduced as what a command prints is a factual claim about
behaviour, and it earns the same check as any other.
The usual way it goes wrong is that it was **composed** from convention rather
than **captured** from a run: you know roughly what the tool says, you know
what error output generally looks like, and you type the block.

The invented element is almost always **added detail shaped like
boilerplate** --- a severity tag, a timestamp field, a leading `$`, an exit
line --- rather than a wrong message.
That is what makes it survive review.
Every part a reader would think to check is correct: the wording is the
wording, the flags are the flags, the advice is the advice.
What is wrong is a decoration nobody reads as a claim, because it looks like
the format rather than like content.

Note this is not the fixture case.
[`fixtures-are-not-evidence`](../workflow/fixtures-are-not-evidence.md) governs
reasoning **from** a repo artifact **back to** the real system, and its remedy
is to consult the real artifact instead.
Here there is no artifact at all --- the block was written from memory of a
genre, and the real output was one command away the whole time.

It also propagates, which raises the cost past one wrong line.
Sample output is written once and pasted into every surface that explains the
feature --- a README, a PR body, an issue, a changelog entry --- so the fix has
to sweep all of them rather than the one a reviewer named, per
[`address-every-comment`](../workflow/address-every-comment.md)'s rule on
deriving a finding's site list.

The remedy costs one command, and it is the same shape
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) prescribes for
publishing a command you ran: run the thing, paste what it printed, and
compare it against what you were about to write.
Where the real output cannot be produced --- an error path you cannot trigger,
a machine you do not have --- read the code that emits it and quote the format
string, rather than reconstructing the line from what such lines usually look
like.

- **Do:** run the command and paste what it actually printed, whenever a block
  is introduced as program output.
- **Do:** read the emitting code's own format string when the output cannot be
  produced, and say that is what you did.
- **Do:** grep every surface carrying the same block once one copy is found
  wrong --- sample output is pasted, so it is rarely wrong in one place.
- **Don't:** add a severity tag, prefix, or field because output of that kind
  usually has one; that decoration is the part most likely to be invented and
  least likely to be checked.
- **Don't:** treat a block as verified because its message text is right ---
  the wording is the half you remembered correctly.

(`Lacaedemon/sparta#1305`, 2026-08-17, review round 1: `tools/README.md` and
the PR body both carried a sample block showing the new Godot version check's
failure output with an `[ERR]` prefix on each line.
`check.sh`'s `err()` is `printf '%s%s%s\n' "$C_RED" "$1" "$C_RESET" >&2` ---
ANSI color only, no text severity tag, and no severity tag anywhere in the
script.
The four message lines were verbatim correct; only the invented prefix was
wrong, and it appeared in two places, so the fix swept both.
This entry's own first draft then quoted that `err()` line as
`printf '%s\n' "$*" >&2`, composed from memory rather than read from the
script --- caught in this fragment's own review, the failure mode illustrating
itself.)

## A contrast sentence imports the neighbouring rule's parameters

[`Check a general claim against the concrete numbers in the same
document`](#check-a-general-claim-against-the-concrete-numbers-in-the-same-document)
above already turns a sentence back on its own document.
This check does too, and differs in **what it compares against**: that one
reads a stated rule against a figure the document reports elsewhere, while this
one reads a contrast sentence's parameters against the rule that sentence is
supposed to be stating.
Not against the neighbour.
The neighbour is where a wrong parameter comes *from*, never what you check
against --- checking against it would flag every asymmetry this section goes on
to sanction.

The construction at risk is the one this corpus is built on: stating a rule by
contrasting it with an adjacent rule.

> That rule says the third time you do a judgment task by hand, build a tool.
> This one says the third time your tool gets the same finding, the tool is wrong.

The second sentence is wrong, and the rule it belongs to says so earlier in
the same section --- its trigger is the **second** occurrence.
The number came from the neighbour, whose bar genuinely is the third.
Parallel structure is the mechanism: writing "That rule says X / This one says
Y" pulls the shape of X into Y, and a parameter rides along inside the shape.

**Three things conspire to hide it**, which is why it needs a named check rather
than ordinary care.
The imported parameter is *correct about the neighbour*, so the sentence
survives a spot-check aimed at the neighbour rather than at your own rule.
The contradiction sits far enough away to be invisible locally, so the paragraph
reads fine on its own.
And the parallelism makes the wrong value look deliberate --- third against
third scans as a designed symmetry rather than as a slip.

**The cost is highest in an auto-loaded instruction fragment**, where the reader
is an agent rather than a person.
A person who notices two thresholds asks which is right.
An agent gets two sanctioned readings and may reasonably take the more permissive
one --- which, in the case behind this entry, was exactly the behaviour the rule
existed to prevent.

So when a sentence contrasts your rule with another, **re-read your own rule's
statement, not the neighbour's**, and confirm every number, threshold, scope, and
disposition in the contrast matches it.
Where the two genuinely differ, say that they differ and why, in the same
breath.
An unexplained asymmetry invites the next reader to "fix" it back into agreement.

- **Do:** verify each parameter in a contrast sentence against your own rule's
  statement, not against the rule you are contrasting with.
- **Do:** state a deliberate asymmetry as deliberate, with its reason, so it is
  not read as an oversight.
- **Don't:** let parallel phrasing carry a neighbour's number, scope, or
  threshold into your rule.
- **Don't:** treat "that number is right for the other rule" as the check
  having passed --- the question is whether it is right for yours.

(Morrison-Lab/ai-config#1742, from the review of
[#1735](https://github.com/Morrison-Lab/ai-config/pull/1735).
The fragment added there stated its trigger as the second recurrence in both its
rule statement and its Do/Don't pair, and as the third in the sentence
contrasting it with
[`deterministic-tools`](../principles/deterministic-tools.md).
The construction is widespread here rather than incidental: `grep -rn "pointed
the other way\|the mirror of\|inverts cleanly" shared/
--exclude=fact-check-prose.md` returned 9 hits when this was written, and that is
one phrasing family among several.
The exclusion is load-bearing rather than tidy: this paragraph quotes the pattern
it searches for, so a run that includes this file counts itself.)

## An availability claim about a repository is a state claim, not a safe default

The **Factual claims** bullet above already covers claims checkable against an
external source.
This is the shape that slips past it: a claim about a repository's or
service's *current status* --- public or private, released or unreleased,
open-source or not --- reads as a safe default rather than as a claim, because
it lines up with intent rather than with anything actually asserted.

Writing "open-source, available at `<URL>`" in a Code and Data Availability
statement, a README, or similar prose feels natural when publication is
planned or eventually expected.
It is a claim about **state** in
[`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)'s
taxonomy, and a claim about state gets re-queried, not recalled from what
seems likely.
A repository actively being developed toward eventual publication is not
automatically public yet, and intent to publish is not evidence of the state
now.

Query the system directly before writing the claim: `gh api
repos/<owner>/<repo> --jq .private`, or an unauthenticated fetch of the given
URL.
Neither a `DESCRIPTION` file's `URL:` field nor "most packages like this
eventually go public" settles it, since both describe intent rather than the
live state.

- **Do:** verify a repository's or service's current visibility live, before
  asserting it in an Availability statement, README, or similar prose.
- **Do:** treat a live-looking URL offered as evidence of accessibility as
  itself a claim needing the same check.
- **Don't:** write an availability or open-source claim as a natural default
  because publication is planned or intended.
- **Don't:** infer current visibility from a config file's URL field, or from
  what similar projects usually do.

This is a first occurrence of this specific pattern, so it does not yet clear
[`deterministic-tools`](../principles/deterministic-tools.md)'s
third-occurrence bar for a dedicated instrument.
Revisit as a check only if the pattern recurs.

## An insertion asserts something about the whole file, not just the added lines

Two earlier sections in this file each turn a sentence back on its own document --- [`Check a general claim against the concrete numbers in the same document`](#check-a-general-claim-against-the-concrete-numbers-in-the-same-document) and [`A contrast sentence imports the neighbouring rule's parameters`](#a-contrast-sentence-imports-the-neighbouring-rules-parameters).
Both compare the new text against something *inside* the passage being written --- a figure the same passage reports, or the rule the contrast sentence is stating.
This one compares it against a sentence it never touched.
Naming them beats counting to them here, deliberately, because the section directly above this one ([`An availability claim about a repository is a state claim, not a safe default`](#an-availability-claim-about-a-repository-is-a-state-claim-not-a-safe-default)) is about verifying against **external** live state and is not one of them.

Inserting a paragraph into an existing fragment publishes a file, not a paragraph.
Whatever the insertion claims, the file now claims, alongside everything the file already said --- so a sentence a dozen lines away that **qualifies, bounds, or hedges the same phenomenon** is part of the assertion you are making, and contradicting it makes the fragment say both things at once.

**Nothing in the normal loop looks there.**
The author reads the insertion, which is coherent on its own.
The reviewer reads the diff, and the contradicted sentence appears in it as context or not at all, so a review can be careful, correct, and still never consider it.
This is the instrument-soundness argument [`sync-with-main`](../workflow/sync-with-main.md) already states for merges --- "when a defect can be introduced by **deleting** a line, any instrument keyed on added lines is unsound" --- borrowed for its *reasoning* rather than for its merge case.
Here the added line is the defective one, and it is only defective **relative to an unchanged line**, which leaves every diff-scoped check equally blind.

**Read the surrounding paragraphs before landing the insertion, not the insertion point.**
Read far enough out to cover the section the insertion joins, and look specifically for a sentence that already limits the claim you are about to state without limits.
A hedge is the likeliest collision, because a hedge and a confident restatement of the same finding are the two natural things to write about one phenomenon.
Duplication is the same read's second finding --- an option list or definition the file already owns elsewhere --- and [`challenge-redundant-content`](../workflow/challenge-redundant-content.md) governs what to do with it.

**This does not license checking your claim against the neighbour.**
[`A contrast sentence imports the neighbouring rule's parameters`](#a-contrast-sentence-imports-the-neighbouring-rules-parameters) above says the neighbour is where a wrong parameter comes *from*, never what you verify against, and that still holds: a deliberate asymmetry between two rules is sanctioned there.
The question here is different --- not whether your parameter matches the neighbour's, but whether the file now states two incompatible things about **one** phenomenon.
Where the difference is deliberate, say so in the insertion, so the next reader does not reconcile them by deleting one.

- **Do:** read the whole section an insertion joins, before pushing it, for a sentence that qualifies or bounds the same phenomenon.
- **Do:** rewrite whichever of the two is wrong, or state the difference as deliberate in the insertion itself.
- **Don't:** treat a clean review as evidence of consistency --- the reviewer read the diff, and the contradicted sentence was not in it.
- **Don't:** confuse this with a deliberate asymmetry between two rules, when the defect is two readings of one phenomenon rather than two rules with different thresholds.

No mechanical check is proposed, and this is not a case where one is being deferred: contradiction between two paragraphs is semantic, so it is not lexically decidable over the artifact, and [`grep-is-not-coverage`](../workflow/grep-is-not-coverage.md)'s point applies to any grep that would stand in for it.
The reviewable action is the read, not an instrument.

(Morrison-Lab/ai-config#1788, 2026-08-20.
Commit `4d1a979b` inserted a paragraph into [`self-review-fallback`](../workflow/self-review-fallback.md) calling a high-denial review stub a "non-recovering" subcase, asserting that "re-running this pattern has repeatedly NOT recovered", and that "two high-denial stubs back to back is conclusive".
Thirteen lines below, untouched by the diff, the file already said that two stubs back to back is "still not conclusive" and that the failure modes behind stubs "don't always repeat".
The automated reviewer read the same diff and reported only a tense problem on a different line.
The insertion additionally re-listed a set of reviewer options the same file defines in another section, which [#1778](https://github.com/Morrison-Lab/ai-config/pull/1778) was concurrently editing.
Tracked as [#1794](https://github.com/Morrison-Lab/ai-config/issues/1794), and corrected on the branch by `0cc398ca`.
This section's own first draft then committed the same error: it opened by describing "the two sections above", carrying that framing over from its neighbour, when the section directly above it argues the opposite of what the sentence attributed to it.
The reviewer on [#1795](https://github.com/Morrison-Lab/ai-config/pull/1795) caught it, which is worth recording as evidence about the remedy rather than about the author --- naming a target beats counting to it, exactly as [`forward-references`](forward-references.md) says, and the count was wrong here because an unrelated section had been inserted between the two being counted.)

## An elapsed-time claim is a computation, not a memory

The section on claims inherited from upstream discussion covers a figure you
took from somewhere.
This covers the figure you took from nowhere: "an hour ago", "earlier today",
"four hours later".

It is the one quantity that feels **observed** rather than derived, because you
were present for the interval.
Nothing about writing it prompts a check, in the way a version number or a file
count does --- those are obviously lookups, and a duration feels like something
you already know.

**You do not know it.**
An agent's sense of elapsed time is anchored to turns and tokens rather than to
a clock, and those run at no fixed rate against wall time.
A stretch of many tool calls reads as long whether it took four minutes or
forty.

**The error has a direction**, which makes it worth more than a general warning.
Both figures measured below were **over**-estimates, by factors of about three
and about sixteen.
The bias runs one way because the felt duration tracks work done, and dense work
compresses into little clock time.
So treat your own elapsed-time estimate as an upper bound at best, and derive
the number.

Both endpoints are almost always recorded --- a commit timestamp, a merge event,
a comment's `created_at`, a run's `started_at`.
Subtract them.

- **Do:** derive a duration from two recorded timestamps, and cite them.
- **Do:** read a duration you are about to write as a claim of the same kind as
  a version number, since both are lookups wearing different clothes.
- **Don't:** report elapsed time from the sense of how much happened --- that
  measures the work, not the interval.
- **Don't:** treat "I was there for it" as evidence; presence is what makes this
  feel exempt.

(Measured twice on 2026-08-21, in one session, after the first had already been
corrected.
On [ai-config#1838](https://github.com/Morrison-Lab/ai-config/pull/1838) a
corpus entry claimed two events were "ninety minutes" apart; review derived the
real gap as about twenty-nine minutes from `17:12:39Z` and `17:41:36Z`.
Two PRs later, on [#1840](https://github.com/Morrison-Lab/ai-config/pull/1840),
the PR body said a dependency had merged "four hours ago"; review derived
**about fifteen minutes** --- 14m49s --- from a merge at `18:14:25Z` and a
commit at `18:29:14Z`.
The second figure was not inherited from anywhere --- unlike the first, which at
least came from an earlier comment, it was generated whole.
Both were wrong in the same direction.

This entry then needed three review rounds to get its own arithmetic right,
which is the strongest evidence it has.
The first draft said "fourteen", having floored the subtraction and reported the
floor as the value.
The second gave the over-estimate factor as eighteen where 240/14.82 is about
sixteen --- a ratio nobody had computed, sitting in the sentence that says to
compute ratios.
Neither was caught by writing carefully about the very discipline they violate;
both were caught by review.
So: deriving a number is not the whole of it.
An integer division is an estimate wearing a computation's clothes, and a figure
derived FROM derived figures needs its own arithmetic run rather than an
eyeball.)
