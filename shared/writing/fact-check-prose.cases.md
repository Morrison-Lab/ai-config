# Case records: fact-check-prose

Worked-example case records for the rules in
[`fact-check-prose.md`](fact-check-prose.md),
moved here verbatim to keep them out of the auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Prose that distills code is a code claim, checked like code

(Morrison-Lab/ai-config#1096, 2026-08-03: a UMS pass distilled a hook's
`req_failed = (not last) or err or failure_pattern(body)`, gated by
`if not req_failed:`, into prose that renamed the variable to `released`, kept
the right-hand side, and dropped the negation on the gate -- so the prose
computed the exact inverse of the invariant the section defined, and a reader
copying it would have built the very bug the section warns against.
The reviewer caught it; the fix restored `req_failed`/`if not req_failed` and
turned the mistake into an in-text warning.)

## Any condensation of a verified source is a fresh claim

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
And in [`citations`](citations.md), the sibling entry this same PR added, a
`Do` bullet went on prescribing "with whitespace normalized" after the prose
five lines above it had been corrected to require markup normalization too --
so the bullet recommended a test that the section's own worked example
demonstrates failing.
That one is worth separating, because its timing is the reverse of the
others: the bullet was not condensed *from* stale prose, it was written
first and never revisited when the prose it summarized was corrected.
A bullet is the natural place for this to hide, since it reads as the
settled form of whatever sits above it.

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

## An edit made for precision can assert what the loose version never did

(`UCD-SERG/serocalculator`
[#654](https://github.com/UCD-SERG/serocalculator/pull/654), 2026-08-09,
`vignettes/methodology/_cluster-robust-se.qmd`.
Commit `4a202f49` wrote, loosely and correctly:

> Summing `\llik_i` over every observation recovers the full-sample
> log-likelihood of `@prp-full-sample-likelihood`, which is what makes these
> per-observation pieces the right thing to accumulate by cluster.

Commit `50c2d808`, tightening that prose, replaced it with:

> The sandwich accumulates by cluster exactly the per-observation pieces that
> `@prp-full-sample-likelihood` sums over the whole sample.

The sharper sentence carried two false claims the looser one had not made.
`U_i` is the **gradient** of `\llik_i` rather than `\llik_i` itself, so
"exactly the per-observation pieces" asserts an identity that does not hold.
And `@prp-full-sample-likelihood` states a **product**,
`\Lik(\lambda) = \prod_{i=1}^n \Lik_i(\lambda)` at `methodology.qmd:787`, while
the summing of `\llik_i` happens under "Finding the MLE numerically" at line
822 --- so the sentence also credited the wrong operation to the wrong place.
The automated review flagged the first, calling it a "prose precision
regression" and "a small step back in precision from the immediately-preceding
commit".
It did not flag the second, which surfaced while fixing the first.
Fixed in `43bd40d5`.

The overclaim sweep was `06f381c5b`, twelve minutes and three commits earlier
on the same chapter, replacing "will be" with "are usually" and "appropriately
widen" with "widen correspondingly".
A first draft of this record said the regression landed one commit after that
sweep; `git log` says three, and the corrected figure is the stronger one ---
the file stayed swept across two intervening commits before the third
reintroduced the defect.)

## Check a general claim against the concrete numbers in the same document

(Morrison-Lab/ai-config#813, 2026-07-29: a memory entry stated that `du`
reports logical size for dataless placeholder files, three paragraphs after
reporting that a placeholder-only OneDrive folder occupied 2.1 MB.
That figure is only possible if `du` reports physical blocks, which is what
it does.
The review caught it by citing the entry's own number back at it; a direct
test then showed `du` = `0B` against `ls -l` = 276 MB on one placeholder.)

## When a disputed figure cannot be recounted, fall back to internal consistency

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

## An entry's case record is its own test case

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

## A definition can resolve, render, and still say nothing

(`UCD-SERG/serocalculator`
[#654](https://github.com/UCD-SERG/serocalculator/pull/654), 2026-08-08/09: a
methodology vignette formalized the score and Hessian as
`$$\score(\lambda) \eqdef \llik'(\lambda)$$` and
`$$\hess(\lambda) \eqdef \llik''(\lambda)$$`.
The vendored `Morrison-Lab/macros` submodule defines `\def\llik{\ell}` at
`macros.qmd:143`, `\def\score{\ell'}` at 165, and `\def\hess{\llik''}` at 170,
so both lines rendered as a symbol defined as itself.
Two automated review rounds passed over them, and so did I --- having verified
that the crossrefs resolved, which is the check described above as answering a
different question.
The same file defines the concepts properly at `macros.qmd:511-512`, as
`\def\defScore{\score \eqdef \deriv{\th} \lik(\vx|\th)}` and
`\def\defHess{\hess \eqdef \deriv{\vth}\deriv{\vth\'} \llik(\vx | \vth)}`, so
the alias-only form was the deviation from house style.
Fixed by spelling the operator out with `\deriv` and `\dderiv`.)

## Confirm a rendered page carries your commit before reading anything off it

(`UCD-SERG/serocalculator`
[#654](https://github.com/UCD-SERG/serocalculator/pull/654), 2026-08-09: the
docs workflow took 11 to 14 minutes per run on that branch while pushes arrived
3 to 9 minutes apart, so the deployed preview trailed `HEAD` for most of the
session.
Derived with
`gh run list -R UCD-SERG/serocalculator --workflow 223280926 --branch
claude/cluster-robust-variance-formalize-4004b8 --json
headSha,createdAt,updatedAt,conclusion`:
the run for `6a2f4cb9` started at 17:10:19Z and finished at 17:24:35Z, by which
time `06f381c5` (17:18:59Z) and `35acf3dc` (17:24:32Z) had both been pushed, so
the page that had just deployed was two commits old the moment it appeared.
The build-versus-push intervals above are measured; that a marker check caught
this three times in the session is reported from that session rather than
derived here.)

## An availability claim about a repository is a state claim, not a safe default

(`ucdavis/bcs`, 2026-08-20: reviewing a manuscript PR that reworded the
abstract and introduction, I added a Code and Data Availability section and an
Introduction rewrite that both asserted the `bcs` R package was "open-source"
and gave a live, clickable `https://github.com/ucdavis/bcs` link.
The `@claude` review bot caught it: the repository is private, confirmed by an
unauthenticated fetch returning 404, so a reader following the link in the
published manuscript would hit a dead end.
The claim did not feel like something to verify, because most R packages under
active development eventually go public, and "open-source" read as a plausible
default rather than as an assertion about the repository's state that day.
Fixed by rewording to state the repository is private during development and
dropping "open-source".)
