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
