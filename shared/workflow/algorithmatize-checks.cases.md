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

## A metric that cannot discriminate over its whole range may be sharp over part of it

(`Lacaedemon/sparta`#1207, 2026-08-06: a regression guard asserted that a
regiment's facing rotates less than 28 degrees over 700 ticks of melee, pinned
to a single seed.
Measuring it across six seeds showed unmodified `main` itself exceeding the gate
at two of them, 35.89 and 53.39 degrees against a 9.29-to-53.39 range, and the
same commit reading 16.39 locally against 39.88 on CI.
From that the issue concluded that no bound could work at all --- a wider
absolute bound would have to clear 53 and so would stop catching the roughly
46-degree bug the guard existed for, per-seed baselines die on the platform
split, and a loose sanity bound has the first option's problem --- and #1211
quarantined the assertion on that reasoning.

That diagnosis was right about the 700-tick window and wrong about the metric,
and #1211 was closed as superseded by someone else's fix in #1212, merged as
`d8cc635b`.
That PR first established the negative result properly, which the issue had
asserted rather than measured: disabling the fix the guard protects made the
700-tick number *worse* at three seeds and *better* at three, so there the
metric carries no signal about the fix at any bound.
Inside the first 300 ticks it separates cleanly --- a healthy build holds
2.84 to 3.44 degrees across eight seeds while a regressed one ranges 1.94 to
14.45 --- so the fix bounds that window instead.
Two regressed seeds land under the healthy band, which is why the per-seed
ceiling cannot be the discriminator: the gate is on the seed mean, 2.98 healthy
against 6.52 regressed, with a looser per-seed backstop so one blown seed cannot
hide behind seven good ones.
It also declines to bound the late window at all and says why, since clean
`main` genuinely reaches 58 degrees by tick 700 at seed 777 and pretending to
bound that would restore the original silent pass.)

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

## Widening an instrument invalidates every figure it produced, not only the one that exposed it

(`ucdavis/bcs#599`, 2026-08-06: sanitizing 11 SAS programs before committing
them, removing a credential and real participant identifiers.
A bash pipeline found identifiers on context lines matching
`studyid_c *(=|in) *["'(]` --- note ` *`, spaces only, not `\s*` --- and
reported 52 occurrences and 18 distinct IDs across 3 files.
An independent subagent sweep run in parallel also reported 18 distinct, and
72 total, that figure being 52 quoted plus 20 identifiers in two pasted
`proc print` output blocks.
Two methods agreeing at 18 read as strong confirmation; both keyed on quoted
tokens near a context word, so their agreement measured the shared blind spot.

The sanitizing script written afterwards used `\s*` and asserted the expected
count, aborting before writing anything with "expected 18 distinct IDs, found
19".
The 19th was a 10-digit numeric token on a tab-adjacent line that ` *` cannot
match.
The distinct count was corrected to 19; the **occurrence** count and the
**file** count were not re-derived, and were carried forward from the narrow
detector into the PR body, the `NEWS.md` entry, and a README table shipped in
the repo, as "72 occurrences of 19 real participant StudyID_c values, across 8
files".

`claude-review` recounted against the diff and reported 9 files rather than 8
and 64 sites rather than 72.
The finding went unaddressed through two further commits and was re-raised in
a later round.
A third figure was wrong the same way: `<REDACTED-USERID>` appears 6 times,
3 per file --- the `%let nuid` line plus **both** `%include` path forms --- not
4.
Derived independently from the committed files rather than accepted on trust:
`grep -o 'STUDYID[0-9][0-9]'` over the 11 files gives 9 files, 64 occurrences,
19 distinct, and `grep -o 'REDACTED-USERID'` gives 6.
The reviewer was right on all three.

72 was wrong twice over.
It was 52 + 20, and the 20 pasted identifiers were **deleted**, not
pseudonymized, so they were never placeholders --- two populations summed and
labelled as one of them.
And the 52 was itself the narrow detector's output, missing all six
`model*.sas` programs, which use a tab-separated form.
The correct accounting is 84 identifier sites redacted: 64 pseudonymized in
place across 9 files, plus 20 deleted with the two pasted blocks.)

## A reference frame chosen from the initial condition expires as the system moves

(`Lacaedemon/sparta#1222`, merged 2026-08-07 as `320fe3b2`: an instrument
attributing a two-regiment rotation projected each candidate's per-tick
contribution onto world X, on the stated grounds that the separation between
the two regiments starts along +Y.
It does, at tick 0, where world X is exactly tangential and the projection
measures precisely what it was built to measure.
By tick 700 the pair had rotated 56 degrees, so world X had become 83% radial
--- `cos(90 - 56) = 0.829`, computed here rather than recalled --- and the
radial channel is dominated by `Unit._press_into`, the one candidate that is
purely central away from a field edge and therefore contributes essentially no
rotation there --- 0.002 degrees, measured.
The instrument accordingly reported `_press_into` at +/-152 wu of exactly
anti-symmetric world-X displacement and read it as the driver, where
attributing the bearing directly via `cross(r_hat, dr) / |r|` puts it at 0.002
degrees against `SoldierBodies.couple`'s -59.163 of the -59.16 total.
The projection never failed, never went empty, and never returned anything but
a large stable number; only its meaning changed.)

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

## The harness that performs those mutations needs the same scrutiny

(`Morrison-Lab/ai-config#1293`, 2026-08-08, measured while drafting the rule:
the first harness dropped one alternative from a regex alternation by deleting
the token `<alt>|`, which is present for every interior member and absent at the
end of the list.
Run against this corpus's own negation-prefix guard,
`\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't)\s+`, that form mutated
seven of eight and silently no-opped on `can't`, which is followed by `)` rather
than `|`.
The mirror form `|<alt>` mutated seven of eight and no-opped on `not`, preceded
by `(?:`.
So each single-sided token leaves exactly one end unreachable, and a harness
scoring "no failure observed" as a pass would have reported that end verified.
The brief this was recorded from asserted that one form was vacuous at BOTH
ends; running it is what showed each form fails at one, which changes the fix ---
adding the opposite delimiter does not help, because substring overlap between
alternatives makes string replacement the wrong instrument regardless.)

## A component that stops failing under mutation is a question

(`Morrison-Lab/ai-config#1278`, 2026-08-08: after a positional guard replaced two
word lists as the primary classifier, mutation testing showed the negation and
hedge lists had gone dead --- removing either failed nothing, because position
already caught every case the suite held for them, a negation never being markup.
Searching for where they remained load-bearing rather than deleting them found a
case the corpus guarantees: this repository writes semantic line breaks, so a
qualifier routinely sits at the end of the PREVIOUS line, as in "The PR is not"
followed by "ready for merge until the findings are fixed."
The phrase is then line-initial, so the positional guard calls it marked, and
only the prefix scan sees across the break.
Two cases now pin it, and the suite went to 44 from 34 with every component
failing only its own cases when mutated.
Adding the position guard is what made the two older components look redundant,
so the moment their score dropped to zero was the moment the missing case was
findable.)

## Scale that from one reported input to a corpus of real ones

(`Morrison-Lab/ai-config#1278`, 2026-08-08, rounds 4 to 6: `classify_verdict()`
in `scripts/check-pr-fully-clean.py` had taken four rounds of authored cases,
each round's reviewer supplying counter-examples the previous fix missed.
Instead of inventing more, the author ran the classifier over the real verdict
bodies on the six PRs open that night, where ground truth was known
independently.
Two findings followed that no synthetic case had produced.

The first is an under-block on the side nobody was editing.
Three rounds of "Needs **minor** work" on `Morrison-Lab/ai-config#1293`
classified as no verdict at all, because the not-clean pattern required
`Needs\s+work` adjacency --- a genuine not-clean verdict that neither blocked
nor superseded anything, which is the mirror of the bug the PR existed to fix.
The author's note is the argument for the method: "no synthetic case would have
produced the phrasing", and the corpus "is now better evidence than the unit
suite, because I did not choose its wording".

The second is the over-block, and it appeared only on re-running the corpus
after a later widening.
With `\n` no longer terminating a sentence, that same PR's genuinely clean
verdict began classifying as not clean, on an ordinary `but` roughly 120
characters downstream in one long sentence.
That direction makes criterion 4 unsatisfiable for a clean PR, which is worse
than the under-block being fixed, so the scan was bounded to 60 characters as
well as to the sentence --- a qualifier retracts only when it sits close.
Post-fix the classifier reproduced ground truth across 20 verdict bodies on six
PRs.

The harness itself is the third instrument failure recorded that session, after
a mutation harness that silently no-opped and a `grep`-based keyword count that
returned 8 for 7.
The first comparison run reported all six PRs as MISMATCH.
The classifier was right; the harness derived the PR number with `split('c12')`,
turning `c1257.json` into `57`, so every ground-truth lookup missed.
A uniform verdict across a corpus whose members vary is the tell --- and the
author's own framing of why it still deserved recording is that failing loudly
is the safe direction for a broken instrument, not a correct one.)
