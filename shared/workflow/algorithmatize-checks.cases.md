# Case records: algorithmatize-checks

Worked-example case records for the rules in
[`algorithmatize-checks.md`](algorithmatize-checks.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## A holding-constant measurement is a regression test

(Morrison-Lab/ai-config#1029:
`scripts/check-context-closure.py` reported the auto-loaded context closure
as 70 files and 803,950 bytes across review rounds.
A code-span regex regression that crossed newlines dropped the closure to 51 files
by swallowing 19 real imports;
no test failed,
and only the moved number caught it.
The same PR tried CommonMark's rule
that an unclosed fence runs to end of document.
On this corpus that dropped `CLAUDE.md` from 69 anchored imports to 50,
because same-length nested fences,
such as an outer triple-backtick fence wrapping an inner triple-backtick R fence,
made the outer closer look like a fresh unclosed opener.
The fix was to report the ambiguous fence
rather than silently consume the rest of the document.)

## Never predict which case will fail; enumerate the class

(2026-07-31, `ucdavis/bcs#503`: a spelling check could not run locally, and the
status report named `monotonicity` as the only newly-reachable word.
`monotonicity` passed; `unlabelled` failed --- a British spelling in prose
written minutes earlier.
A three-line pattern scan over the diff, needing nothing installed, then found
`unlabelled` **and** `neighbours` in one pass.
The user's correction was "no guessing".)

## Test the instrument against the incident that prompted it, verbatim

(2026-07-31, a guard against running heavy R jobs on a cluster's head node:
the reported command was
`R -e 'Sys.setenv(NOT_CRAN="true"); res <- devtools::test()'`.
Splitting on `;` left a fragment leading with `res` rather than an
interpreter, so the one command the hook existed to stop was the one it let
through.
A second bug in the same file had a comment asserting that a leading anchor
kept bare mentions from matching, which it did not -- `grep -rn
'devtools::test'` was blocked.
Neither surfaced from re-reading the code.
Both surfaced from tests, and the first only from the test that pasted the
reported line in unaltered.)

## A negative control must enter at the real input

(2026-07-31, `ucdavis/bcs#539`: a three-step spelling check --- extract
candidates from the diff, drop those already present on a green `main`, look
the rest up in a dictionary --- reported 52 candidates, 3 unproven, 0 unknown,
and was called trustworthy on the strength of a control fed directly to the
dictionary step.
CI then failed on `SAS's`, a possessive added by the same commit the check had
just cleared.
Its extraction was `grep -oE '\b[a-z]{7,}\b'`: lowercase, seven or more
characters, no apostrophes, so the word was excluded on all three counts and
never became a candidate.
The filtering step was sound --- against green `main` it separated the four
possessives exactly, `arm's` 4 files, `manuscript's` 2, `simulation's` 6, and
`SAS's` 0 --- which is what makes the extraction the whole of the defect.)

## A reminder guard's discharge condition is a second matcher, and its failure is silence

(`Morrison-Lab/ai-config#1075`, 2026-08-03: the review of a new inject-only
`UserPromptSubmit` hook, `remind-learn-from-review.py`, found its
mechanism-discharge branch matched `memories?/`, `CLAUDE.md`, `/skills/`, and
`/shared/` --- roughly half the repo --- so an ordinary Address-fix edit
discharged the reminder by path match alone, with no check that a lesson had
been recorded, silencing the hook in its own home repo.
The fix scoped mechanism-discharge to `hooks/` and CI paths and required an
explicit learning signal.
The same `UMS_PATH` prefix already ships in `remind-ums-after-error.py`
(`memories?/|MEMORY\.md|CLAUDE\.md|/skills/|^skills/|/shared/|^shared/`,
commented "A write to any of these is a recorded learning"), so the proxy is
not hypothetical; whether its looser fire trigger there --- an error admission
rather than a finding whose fix edits those paths --- makes the coarse
discharge acceptable is the backstop-versus-fire-on-event judgment
[`algorithmatize-checks.md`](algorithmatize-checks.md) draws.)

## A review flagging an overclaimed check is a prompt to build it, not to soften the claim

(Morrison-Lab/ai-config#1047 round 5, 2026-08-03: `claude-review` returned
"Ready for merge" with one non-blocking note --- the PR body said "the parser
is fuzzed for the no-throw invariant", but no fuzzing shipped.
The invariant is real: a parser crash prints a traceback into Bash.
Rather than delete the claim, `fuzz()` was shipped --- a `random.Random`-seeded
adversarial corpus driven through `split_segments` and the full predicate,
plus a subprocess smoke through `main()`.
The first non-vacuity probe injected a bug the `BACKSLASH_CONT` case also hit,
so the suite aborted on that case before `fuzz()` ran; a second probe targeting
an unterminated-quote-with-trailing-backslash shape the deterministic cases
never build was caught by `fuzz()` in isolation, while the real parser passed
4000 rounds.)

## A guard whose condition ANDs several clauses masks its own mutation test

(Morrison-Lab/ai-config#1042, 2026-08-03: `hooks/no-unreviewed-pr.py`'s
discharge fired only when structural-identity, "last simple command", and
same-PR-scoping clauses all held, and a single regression case that two of the
three clauses each kept correct made reverting any one of them still pass; each
clause needed its own isolating case before the mutation test meant anything.)
