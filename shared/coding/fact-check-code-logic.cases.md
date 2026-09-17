# Case records: fact-check-code-logic

Worked-example case records for the rules in
[`fact-check-code-logic.md`](fact-check-code-logic.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Check tests the same way --- a vacuous ordering-constraint assertion

(d-morrison/altdoc#43: an ordering-constraint test
asserted `expect_false(any(grepl("_GITHUB", out)))` while also expecting
`out` to be `character(0)`, so it could never fail; fixed by adding an
input line that survives substitution, then verified by swapping the two
source lines into the wrong order and watching both assertions fail on the
resulting `"* [GitHub](_GITHUB)"` residue.)

## Mutate the fix, not only the test

(Morrison-Lab/ai-config#1029,
seven Copilot review rounds on `scripts/check-context-closure.py`,
produced six tests that passed against a reverted fix.
One called `positive_int()` directly and missed the parser's `type=int` crash;
one lost-import test used an anchored import already caught by an earlier guard;
one indented-fence fixture lacked the blank line needed to avoid a neighbouring
code-span rule;
one span-boundary fixture was line-initial
and therefore a legitimate fence opener;
one expected CommonMark multi-line code spans not to be spans,
contradicting the spec;
and one `positive_int` label said "rejects zero"
while asserting acceptance of `"4"`.
Each was caught by mutating the fix,
not by reading the test.)

## When the runtime is available, run the claim instead of reasoning about it

(ai-config#774, 2026-07-28: a fragment stated that R's `[[` errors on a
missing name in a list, offered as the strict counterpart to `[`.
The book's own out-of-bounds table contradicted it, and one call settled it
--- on R 4.6.1, `list(a = 1)[["b"]]` returns `NULL`, and only an
out-of-bounds *integer* index errors.
Stamping the version here is the habit this section asks for, not a hedge
about base R: `[[` is about as stable as R gets, and recording what you ran
it on costs a parenthetical either way.
The stamp is worth least exactly where you are most sure, which is why it
is easiest to skip there.
The claim had been written precisely because it felt obvious.
The same pass executed the other five behavioural claims in the diff, all of
which held, and the reviewer independently confirmed each one --- so the
cost of being wrong here was one wrong sentence caught before review rather
than a finding.)

## Matching values is not matching roles

(2026-07-31, `ucdavis/bcs#539`: R constants of 18 and 30 months were reported
as following the SAS, on the strength of finding both numbers in the SAS
source.
The SAS comment one line up reads "ignore a diagnostic exam if the difference
between this diagnostic examdate and the previous examdate is outside the
annual screening window 11-18 months" --- exam eligibility, not an estimation
horizon.
Both quantities derive from the same screening schedule, which is why they
coincide.
Withdrawn the following round, when review also found the R constants live in
simulation-validation code the real pipeline never calls.)

## Mutate the fix, not only the test --- a payload rejected before it arrived

(Morrison-Lab/ai-config#1902, 2026-08-21: a ReDoS regression guard for a
`PreToolUse` hook fed it a command built to trigger catastrophic
backtracking --- an opening quote deliberately left unbalanced, followed by a
long run of backslashes.
The hook parses commands with `shlex`, which refuses an unbalanced quote, so
the function returned before the regex ever ran.
The guard passed in 0.03s with the vulnerable pattern fully in place, and was
caught only by mutating the fix out and noticing it stayed green.
Every other part of the test was right.
The mutation applied to the intended line, the assertion was the right
assertion, and the timing threshold was calibrated.
Balancing the quotes delivered the payload to the matcher, after which the
guard behaved --- exit 0 with the fix at 0.045s, exit 1 without it at 7.22s.
One line confirming that the parse step returned a value rather than `None`
would have exposed the gap.
Note which way the coupling runs.
The payload had to be malformed to reach the defect, and malformed is
precisely what `shlex` rejected it for, so the more layers a guard sits
behind, the likelier this is.)

## Mutate the fix, not only the test --- one suite total pinned only one of two parallel paths

(Morrison-Lab/ai-config#3707, commits `6ed5807` and `0a125ec`, 2026-09-17: a subagent-dispatch guard (`hooks/no-push-without-self-review.py`) parses two transcript shapes for the same provenance question --- Claude's native `message.content` blocks and OpenCode/OMO's flat, call-id-less records.
A provenance fix (excluding task-output-retrieval tools from being treated as reviewer dispatches) was applied to both parsers in the same commit, whose message claimed "`TASK_OUTPUT_TOOLS` is now tested first on both the native and the OMO path...
Twelve cases pin it."
Reverting the native path's fix does fail twelve cases.
Reverting the OMO path's identical exclusion left the entire 345-case suite passing, because the one case built to catch this exact bypass constructs nested `message.content` blocks and can never reach the flat-record branch at all.
The independent confirmation of that came with a lesson of its own, recorded here because it is the same error one level up.
The first attempt ran the suite against a copy of the hook placed OUTSIDE the checkout, and reported a baseline of "6 pre-existing failures, unchanged by the mutant" --- a plausible-looking number that is an artifact of the copy's location, since this suite resolves paths relative to the hook it is given.
Re-run in the checkout, `origin/main`'s hook against `origin/main`'s own test file passes 310 of 310, and the mutant applied in the checkout passes 345 of 345.
Both runs support the finding;
only one of them was evidence about the repository.
A same-shaped case for the flat-record path, added the following review round, fails 12 under that path's own reversion.
The "345/345 pass" and "twelve cases pin it" claims were both true and together implied a claim about coverage that was false: a total combining both paths cannot say which path a given case reached.)

## Mutate the fix, not only the test --- a fixture ordered like the table

(ucdavis/bcs#913, 2026-09-03: a refactor replaced three inline
`dplyr::recode_values()` blocks with a named-character-vector lookup,
`labels[outcome]`.
That silently broke factor input, because indexing a named vector by a factor
uses the integer level codes rather than the values --- so a factor whose
levels are ordered differently from `labels` reads the wrong label out, and one
whose levels happen to match reads the right one.
The fix was `labels[as.character(outcome)]`, and a regression test was written
alongside it.
The test was vacuous: its factor's `levels` were in the same order as
`labels`, so level-code indexing and value indexing returned identical
results, and it passed with the fix removed.
Nothing about the fixture looked like a shortcut --- it was an ordinary,
representative factor, and its order was the order anyone thinking about the
label table would have written.
An adversarial reviewer caught it.
Reversing the level order made the test discriminate, and the mutation ---
delete the `as.character()` call, confirm the suite goes red, restore, confirm
green --- settled it in one command.
Note which direction is cheap: reading the test a second time would not have
found this, because the test was correct in every respect except the one that
cannot be read off it.)
