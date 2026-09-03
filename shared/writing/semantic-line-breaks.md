Break lines in prose at major phrase and sentence boundaries — one clause
per line, roughly 60 to 80 characters — rather than wrapping at a fixed
column or writing one long line per paragraph. This matters most in files
under version control (Quarto `.qmd`, Markdown docs, and similar), since a
semantic break keeps a diff to the changed sentence instead of a whole
reflowed paragraph.

**When editing existing prose**, preserve the file's current line breaks
exactly — don't reflow to a single long line or a different wrap width.
**When writing new prose**, add breaks at phrase/sentence boundaries as you
go.

**When a review flags a semantic-line-break violation, fix every
over-length line in the touched section in one pass** — not just the
specifically-flagged ones. Review bots (`@claude` / Copilot) re-scan on
each push and flag the next batch of adjacent borderline lines the prior
round left alone, so fixing only what was named drags the PR through round
after round of the same finding (UCD-SERG/lab-manual#297 took five review
rounds this way). Doing the whole section in one pass is how you spend
fewer rounds --- not a reason to stop iterating, which is never on the
table (see [`ardi`](../../skills/ardi/SKILL.md)'s "Stopping conditions").

**URL-inflation exception:** a line that runs long *only* because of an
embedded `[text](long-url)` link — where the visible prose before the link
is well under 40 characters — is fine as-is. Don't force an awkward
mid-clause break just to shorten the raw line; review bots themselves
classify these as borderline / acceptable.

**When reviewing prose, suggest semantic-line-break fixes — don't insist on
them.** Flag lines that ignore clause/sentence boundaries as a style
suggestion, the same weight as a word-choice nit: worth raising, not worth
blocking approval over, and not worth re-raising if the author declines.
This is distinct from the rule above: that one governs how thoroughly to
fix violations once a review has flagged them; this one governs the
weight to give the finding when you are the reviewer in the first place.

**What CI actually enforces is one sentence per line, not a character
count -- don't reflow to 80 columns thinking the check demands it.**
The 60-to-80 range above is guidance for a human writing prose.
The automated check backing it (`check-new-line-breaks`, a reusable
workflow in [`Morrison-Lab/gha`](https://github.com/Morrison-Lab/gha); formerly
ai-config's own `scripts/check-new-line-breaks.py`, retired in ai-config#703)
tests something narrower, against each **newly added** prose line in the diff.
Its primary rule flags a line holding more than one sentence.
Since gha#336 it also carries a **clause** rule, on by default: a line whose
markup-stripped text reaches 80 characters and carries a mid-line semicolon.
Neither rule is a character count, and the clause rule is the only one that
looks at length at all.

Two consequences.
A single long line carrying exactly one sentence and no mid-line semicolon
passes, so the URL-inflation exception above still needs no special casing in
the check.
And a line that packs two short sentences fails even at 50 characters, which
is the violation to actually look for before pushing.
Fix a flagged line by breaking at the sentence boundary, not by rewrapping
the paragraph to a narrower column.
(ai-config#712: assuming an 80-character limit sent me measuring line lengths
against the wrong criterion; reading the retired script's own source settled
it, and the real check then found 7 multi-sentence lines a length check had
passed over.)

**The reformatter consumes the gate; it is still not the job CI runs.**
`scripts/semantic-line-breaks.py` is the in-repo tool named for this
convention, so it is the obvious thing to reach for when a line-break warning
needs clearing.
As of 2026-08-26 (ai-config#2085) it loads
`scripts/vendor/gha-check-new-line-breaks.py`, which is the script at the SHA
`.github/workflows/validate.yml` pins for
`Morrison-Lab/gha/check-new-line-breaks`.
Sentence splits and the mid-line-semicolon clause rule both come from that
module's `split_sentences` and `classify_line`.
A pin file next to the vendored copy must match the `uses:` SHA, so bumping
the action without refreshing the vendor is a loud failure rather than a
silent second implementation.

Nothing runs the reformatter in CI.
`grep -rn "semantic-line-breaks.py" --include=*.yml .` returns no workflow;
the `new-line-breaks` job still calls the composite action directly.
`--write` is now a preview of what that job will accept on the lines it
reflows, not a second opinion.

It still **joins** a hand-wrapped sentence that the gate would leave whole ---
a comma-clause chain with no semicolon, the #2081 case, is one line after a
reformat however long it is.
Corpus practice is the clause-wrapped 60-to-80 range this file opens with.
The construction #2085 closed is the pair of predicates the gate actually
enforces (multi-sentence lines, and a line whose stripped text is at least 80
characters with a mid-line semicolon), not every wrap a human would make.
The tool stays narrower by design (ai-config#2586): natural language clause
detection at comma and conjunction boundaries requires a syntactic parser;
regex heuristics over-split clean prose (>50% false positive rate on commas),
and whole-file `--all` reflow collapses ~31,000 hand-broken clause lines across
375 files (measured 2026-08-31 over 458 Markdown files).
Diff-scoping (the default under `--write`) isolates touched sentences and leaves
untouched multi-line clause breaks intact (ai-config#1599).

`MD013` is off repo-wide in `.markdownlint-cli2.jsonc`, so no width gate
exists either.

Measured 2026-08-15, before #2085, by copying two fragments out of
`origin/main`, reformatting each copy with `--all`, and classifying both
versions with the gate's own `classify_line`:

| fragment (at `origin/main`) | longest line | lines over 80 | clause-flagged |
| --- | --- | --- | --- |
| `semantic-line-breaks.md` before | 80 | 0 | 0 |
| `semantic-line-breaks.md` after | 387 | 97 | 10 |
| `grep-is-not-coverage.md` before | 79 | 0 | 0 |
| `grep-is-not-coverage.md` after | 411 | 59 | 5 |

So the pre-#2085 reformatter cleared the sentence rule and manufactured clause
violations the gate then reported, on files that had none.
The classifier was pinned in both directions first, per
[`fail-fast`](../principles/fail-fast.md)'s negative-control rule: it returns
`clause` on a padded semicolon line, `sentence` on a two-sentence line, and
`None` on a short clean one.

It still found real violations, which is what made a preview worth reading ---
the same two fragments carry 5 and 0 genuine multi-sentence lines at
`origin/main`.
`--write` of that vintage was the defect; the default preview was the detector.
Take the sentence splits it proposes.
Clause splits now come from the same `classify_line` CI runs, so a semicolon
join that would fail the gate is split rather than written.

- **Do:** run `scripts/semantic-line-breaks.py` on new prose and read the
  preview; `--write` applies splits the gate's `classify_line` accepts.
- **Do:** re-run the gate after any reformat, since the joined or split lines
  are added lines and the gate is diff-scoped.
- **Don't:** treat a green reformatter run as a substitute for the
  `pull_request`-triggered `new-line-breaks` job --- that job is still
  diff-scoped to added lines, and this script is not invoked by any workflow.
- **Don't:** expect `--write` to wrap comma-clause chains to 80 columns.
  That is #2081, not the gate, and this construction does not close it.
- **Do:** after any `--write` reflow,
  print the longest added line's length with
  `git diff | grep '^+[^+]' | awk '{ if (length > m) m = length } END { print m }'`
  and re-break by hand when that number is past about 120,
  since the gate does not flag a long comma-joined line with no mid-line semicolon.
- **Don't:** ship a `--write` reflow on the gate's clean verdict alone.
  Recurred 2026-09-02 in a `/gia` session:
  `--write` rewrapped three clause-broken prose additions into single lines up to 398 characters long,
  and the fix was `git checkout <prior-commit> -- <files>` and re-breaking by hand.

(Morrison-Lab/ai-config, 2026-08-15, measured on this machine with the gate at
`Morrison-Lab/gha@da46419`, whose `_DEFAULT_CLAUSE_BREAKS` is `True` and
`_DEFAULT_CLAUSE_MIN_LENGTH` is 80.
The construction that retired the manufactured-clause half landed 2026-08-26
as ai-config#2085.
The narrower-by-design disposition and corpus measurement were confirmed
2026-08-31 for ai-config#2586.)

**Third dated recurrence, 2026-08-21, and the tell is the tool's name.**
An `ardia` sweep drove three PRs whose prose it had edited, ran
`scripts/semantic-line-breaks.py` on each, read its silence as the gate being
satisfied, and pushed.
The gate then failed on `memories/preferences.md:151` --- a 197-character line
with a mid-line semicolon, which the reformatter itself had produced by joining
two hand-wrapped lines.
A detector for the two documented rules, run afterwards across every branch that
sweep had pushed, found the same violation on two more of them.

Nothing about that sequence felt like skipping a step, which is why the existing
Don't pair above did not fire.
The reformatter is named for the convention, lives in this repo's own `scripts/`,
and its silence is a positive-sounding all-clear --- so reaching for it reads as
having checked rather than as having substituted one tool for another.
That is [`verify-the-right-artifact`](../workflow/verify-the-right-artifact.md)'s
adjacent-artifact substitution, arriving through a tool whose name matches the
check it is not.

The laundering step is worth naming separately, because it is what let the error
reach a reviewer.
The sweep reported "`semantic-line-breaks.py` scoped to the added lines
(canonical)" in a PR comment, which reads as a gate result and is not one.
A verification sentence naming a tool is only as good as that tool's relationship
to the check being claimed, and here there is none.

**The same run corrected a false cause claim.**
The sweep had already diagnosed a different PR's failure on this gate as the
added line opening with `(`, and "fixed" it by joining the new text onto an
existing case record --- deleting 8 lines to add 1, and leaving the semicolon in
place, so the fix could not have worked.
The real cause was the clause rule both times.
Per [`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)'s
**cause** claim type, the question that would have caught it is what else
produces a red gate on a one-line diff --- and the rule is documented directly
above, so the answer was one read away.

- **Do:** name the check you actually ran when reporting a line-break result,
  and say whether it was the gate or the reformatter.
- **Don't:** keep teaching the pre-#2085 reformatter's silence as a gate pass.
  That vintage had no semicolon rule, so it was silent about the violation
  it created.
  After #2085 the reformatter splits those lines.
  A clean run still is not the `pull_request`-triggered job.

**Fourth dated recurrence, 2026-08-24, the same day as #2085.**
PR #2071 carried a memory entry whose added lines passed a deliberate scoped
run of the reformatter ("0 would change") and then failed the gate on three
lines, each flagged as a long line with a mid-line semicolon.
The fix wrapped two clauses at their semicolons and reworded a third
parenthetical so it needed none (heads `456a6c87` -> `57116043`).
[Issue #2085](https://github.com/Morrison-Lab/ai-config/issues/2085) records
the same root cause from PR #2073 hours earlier.

What this instance adds to the pairs above is that diligence did not help.
The author ran the local script on purpose, scoped to the added lines, and
read its clean result as clearance --- the substitution happened inside a real
check, not in place of one.
The second slip came at banking time: the failure was first written up as a
new `memories/github-actions.md` section forking a third record of this
lesson, until review consolidated it here instead.

- **Do:** search this fragment and the open issues for the root cause before
  banking a SemBr failure as a new memory entry.
- **Don't:** treat a 2026-08-24 clean scoped reformatter run as covering the
  clause rule --- that vintage had no semicolon split, which is why #2085
  exists.
  After #2085, `--write` splits what `classify_line` flags.
  It still is not the diff-scoped CI job.

**Fifth dated recurrence, 2026-09-02: the gap costs review rounds, not only
CI, since a reviewer applies the wider convention the script does not.**
Four PRs pushed the same day
([#3004](https://github.com/Morrison-Lab/ai-config/pull/3004),
[#3007](https://github.com/Morrison-Lab/ai-config/pull/3007),
[#3016](https://github.com/Morrison-Lab/ai-config/pull/3016),
[#3036](https://github.com/Morrison-Lab/ai-config/pull/3036), all merged)
each carried a scoped `semantic-line-breaks.py` run reporting clean, and
**three of the four** still drew a Copilot finding citing this convention on
a line the script had approved.
Two of those are the clause-density case this entry is about:
`shared/workflow/metacognitive-monitoring.md:1057` in #3007
("uses compound sentences as physical lines ... contrary to this corpus's
semantic-line-break convention of one clause per line"), and, in #3036,
`skills/daytb/SKILL.md:86`
("diverges from this repo's semantic line break convention (one clause per
line)") alongside `shared/workflow/pr-on-claim.md:275`, which asks for the
same reflow in different words
("currently written as a few very long lines ... reflow this new block into
clause/sentence-level line breaks").

The third is a **different mechanism** and is counted separately for that
reason rather than omitted:
`memories/r-quarto.md:1053` in #3016 flagged two *sentences* sharing one
physical line, which is the digit/parenthesis-opener case already recorded
at [ai-config#2127](https://github.com/Morrison-Lab/ai-config/pull/2127)
below, not a comma-or-conjunction clause join.
Naming that split matters because the merged commit message for
[#3036](https://github.com/Morrison-Lab/ai-config/pull/3036) (`52d6fa57`)
gets it wrong in the other direction, calling the findings on
[#3016](https://github.com/Morrison-Lab/ai-config/pull/3016) and
[#3007](https://github.com/Morrison-Lab/ai-config/pull/3007)
"the same finding" raised "twice".
They are not, and a tally that silently drops one of them is how the
conflation survives.
Every line flagged for *clause* density joined its clauses with a comma or a
coordinating conjunction and carried no mid-line semicolon, so the gate's
own clause rule --- the semicolon predicate documented above --- had nothing
to catch either.
This is the narrower-by-design gap arriving as a review comment instead of
a CI failure, which the script's own docstring already predicts but no
prior recurrence here had measured.

**Applying this convention can itself break `lint-markdown`, and it did so
in the commit that recorded the paragraph above.**
Putting one sentence on its own line is exactly what puts a bare `#NNNN` at
column 1, and markdownlint reads a line-initial `#` followed by a non-space
character as a malformed ATX heading:

```
MD018/no-missing-space-atx No space after hash on atx style heading
  [Context: "#3004 drew none."]
```

Two such lines went red on
[#3044](https://github.com/Morrison-Lab/ai-config/pull/3044), both created
by splitting a sentence out onto its own line during the fix for the
finding above.
So the convention and the markdown linter interact: a PR or issue reference
is safe mid-sentence and unsafe as the first characters of a line.

The remedy costs nothing and is already required elsewhere: link the
reference.
`[#3004](https://github.com/Morrison-Lab/ai-config/pull/3004)` opens with
`[`, so MD018 cannot fire, and `AGENTS.md` asks for the linked form anyway.
A bare reference that must stay bare can instead be moved off the line
opening.

- **Do:** link a PR or issue reference that lands at the start of a line, or
  reword so the line does not open with it.
- **Don't:** assume a sentence-per-line split is lint-neutral --- it changes
  which token sits at column 1, which is the only thing MD018 looks at.

The reformatter also worked against the fix once found, in both directions
already named above.
On #3007, splitting a comma-and-conjunction line at the conjunction still
left `scripts/semantic-line-breaks.py` wanting to rejoin the halves,
because a comma-clause split creates no sentence-ending punctuation for it
to preserve.
On #3016 the split fell into this file's own digit/parenthesis-opener case,
first recorded at
[ai-config#2127](https://github.com/Morrison-Lab/ai-config/pull/2127): a
hand-split second sentence there opened with
`(Verified 2026-09-02, ...)`.
Not a new mechanism, but confirmation that it still fires more than a week
after #2085's rewrite, on a fresh instance neither tool sees.
Both times, and in the pre-emptive fourth split on #3036, the fix was the
same: rewrite the pair as one full sentence split into two, rather than a
single sentence with a hand-inserted clause break, which satisfies the
script and the gate at once instead of trading one off against the other.

- **Do:** when the script and the convention disagree, restructure the
  sentence --- usually splitting one long sentence into two --- so both
  pass, rather than picking a side.
- **Do:** read a clean scoped run of `scripts/semantic-line-breaks.py` as
  "no multi-sentence or semicolon-clause lines," not as "this section
  satisfies the one-clause-per-line convention" --- the two claims differ
  in kind, not only in degree.
- **Don't:** treat the reformatter's silence on a comma-or-conjunction-joined
  line as clearance; a reviewer applying the convention by eye still flags
  it, and did, twice, the same day.
- **Don't:** fight the reformatter's rejoin by reinstating the same
  hand-break; convert the clause pair into two genuine sentences instead.

(Morrison-Lab/ai-config, 2026-09-02.
Copilot findings read one endpoint at a time, since `gh api` takes a single
endpoint per invocation:
`for n in 3007 3016 3036; do gh api "repos/Morrison-Lab/ai-config/pulls/$n/comments"; done`
--- all three that drew one, since a query over only the two clause-density PRs
would have produced the undercount this entry now warns about.
No such comment appeared on
[#3004](https://github.com/Morrison-Lab/ai-config/pull/3004).
The rejoin and restructure account is from the PRs' own commit messages, not
inferred.
Whether the reformatter should learn comma/conjunction clause boundaries
was considered and declined: that is the
[ai-config#2586](https://github.com/Morrison-Lab/ai-config/issues/2586)
measurement above, over-splitting more than half of comma boundaries in
clean prose, and nothing in this recurrence changes that trade-off.)

**Until [ai-config#1730](https://github.com/Morrison-Lab/ai-config/issues/1730) gated the job,
a green check run named for this gate might not have run it,
and both runs carried the same name.**
The reformatter trap above is about the wrong *tool*.
This is about the right tool reporting success without measuring anything, and
it is harder to catch because there is nothing to notice: the check run is
green, its name is correct, and it sits in the same list as the real one.

Until [ai-config#1730](https://github.com/Morrison-Lab/ai-config/issues/1730) was fixed, the workflow's base-ref input was
`github.event.pull_request.base.sha` on a pull request and empty otherwise,
which made a push to `main` skip cleanly instead of scanning the whole tree.
The consequence for a *branch* push was the part worth stating: that run had no
base ref either, so it skipped the diff scan and concluded `success` having
examined nothing.

A PR therefore showed **two** check runs called
`new-line-breaks / check-new-line-breaks`.
Only the `pull_request`-triggered one was a verdict.
The `push`-triggered one was green unconditionally, so reading either one, or
reading "the check is green", answered a question it was never asked.

The `new-line-breaks` job in `.github/workflows/validate.yml` now carries
`if: github.event_name == 'pull_request'`, so the push-triggered run reports
`skipped` rather than `success`.
That closes the missing-base push case only: a `pull_request` run can still
skip with the action's warning when the diff cannot be computed, so treat a
green run as a verdict only when its log shows lines were examined.
The rule below still applies to any other workflow of this shape, and to any
repository whose copy of the job predates that guard.

The asymmetry that makes this dangerous: the vacuous run can only ever say
success, so it never disagrees with a real failure loudly enough to notice ---
a red PR-triggered run and a green push-triggered run coexist in the same list,
and the green one is not evidence of anything.
Distinguish them by the triggering event rather than by the name, and prefer
the run whose `event` is `pull_request`.

- **Do:** read the triggering event of a base-diffing run before treating it
  as a verdict wherever the job is not gated on `pull_request`, since such a PR
  carries one real run and one vacuous one under the same name.
- **Don't:** conclude the gate passed from a green check run alone --- confirm
  it was the `pull_request`-triggered one, or that the job is gated so the
  push run reports `skipped`.

**The disagreement had a second, sharper form: the gate split a boundary the
reformatter left whole.**
Closed as to the reformatter by #2085: `split_sentences` is now the gate's
function, including `_SENT_BREAK_LOWER_RE`.
The case record below is the 2026-08-21 measurement that showed the gap, kept
because the durable-opener advice still applies to a boundary *neither* tool
sees (a digit or an opening parenthesis after the period).

The clause case above was the reformatter doing too much, joining wrapped lines
the gate then flagged.
This lowercase-follower case was the reformatter doing too little, leaving two
sentences on one line that the gate then flagged as
`Line packs more than one sentence`.
Before #2085 the two tools carried different sentence-boundary rules.
`scripts/semantic-line-breaks.py` had one break regex, `_SENT_BREAK_RE`, whose
lookahead demanded an uppercase letter or markup after the period, so a sentence
ending in `.` before a lowercase word was no boundary to it.
The gate carries that same branch plus a second one,
`_SENT_BREAK_LOWER_RE` (reported in `Morrison-Lab/gha` #389, added by gha#425), matching
`(?<=[a-z][a-z])([.!?])\s+(?=[a-z])` --- a period after two lowercase letters,
then a space, then a lowercase word.
So `...rules, or agents. opencode instead reads...` was one line to the
reformatter and two sentences to the gate, because the lowercased brand name
`opencode` follows the period after `agents`.
The reformatter did worse than fail to propose the split.
It **undid** the split once you had made it.
`split_sentences()` collapses whitespace before applying the break regex, so a
hand-break at a lowercase-follower boundary was joined back onto one line ---
the reformatter reverted the very fix the gate was asking for.

That made this case an exception to the pre-#2085 remedy.
"Read the reformatter's preview and apply its sentence splits by hand" was sound
for every boundary the reformatter could see, and silently destructive here,
because re-running it after a correct hand-break restored the violation.

- **Do:** treat a `.` before a lowercased package or brand name (`opencode`,
  `renv`) opening a sentence as a boundary the gate will split; the
  reformatter now splits it the same way.
- **Do:** still reword an opener that is a digit or an opening parenthesis,
  which neither the gate nor the reformatter treats as a sentence start.
- **Don't:** hand-reimplement `_SENT_BREAK_LOWER_RE` in the reformatter ---
  that is the second-implementation drift #2085 retired.
- **Don't:** read a historical rejoin of a lowercase-follower break as current
  behaviour; `reformat()` on that input now keeps the two lines.

(Both mechanisms verified by source, read on 2026-08-21:
the reformatter's then-single `_SENT_BREAK_RE` in `scripts/semantic-line-breaks.py`,
and the gate's `_SENT_BREAK_LOWER_RE` at `check-new-line-breaks.py:140` in a
fresh clone of `Morrison-Lab/gha`, whose own `CLAUDE.md` records that gha#425
closed gha#389 by adding that branch.
The rejoin was reproduced directly rather than inferred: calling `reformat()`
on `"...or agents.\nopencode instead reads..."` returned the two lines joined
into one.
Re-verified 2026-08-26 after #2085: the same `reformat()` call keeps the
break.)

**The durable fix at a boundary neither tool sees is to break the line AND
give the opener a form the gate recognizes.**
Choosing the opener retires a prohibition that would otherwise depend on
habit.

The gate's sentence regexes --- which the reformatter now imports --- accept
an opener in ``[A-Z"'`*\[]`` on the uppercase branch and a lowercase letter
on `_SENT_BREAK_LOWER_RE`.
A digit or an opening parenthesis is in neither class.
That third case is the one worth naming, because both instruments go quiet
at once.
Nothing reports the violation and nothing preserves a hand-break there, so
a line packing two sentences survives every check this section describes.
Choose an opener from the first class rather than leaving the gate to catch
the mistake.

Bold and a bracketed link both qualify and are ordinary in this corpus, so the
edit is often free.
`gha's README names ...` can become `` `gha`'s README names ... ``, which keeps
the possessive, or `The gha README names ...`, which drops it.

- **Do:** break at the period, then start the next line with a capital letter or
  with markup --- a backtick, bold, or a link --- when the natural opener is a
  digit or a parenthesis.
- **Do:** confirm the break survived by re-running the reformatter and checking
  that the two sentences still land on separate output lines, since its preview
  is non-empty either way.
- **Don't:** rely on the gate to catch an unbroken two-sentence line --- it is
  silent when the second sentence opens with a digit or a parenthesis.
- **Don't:** expect a lowercase opener to rejoin under `--write` any longer;
  that was the pre-#2085 trap, and the reformatter now uses the gate's lower
  branch.

(Measured 2026-08-24 against `Morrison-Lab/gha` at `9ad1cde` and this repo's
then-local `scripts/semantic-line-breaks.py`.
`classify_line` returns `sentence` for the unbroken line under a lowercase
opener and under all six forms in the lookahead class, and `None` under a digit
or an opening parenthesis.
Calling `reformat()` on the broken pair rejoined it under a lowercase, digit, or
parenthesis opener, and left it alone under all six of the class's forms.
After #2085, the lowercase rejoin is gone; the digit and parenthesis rejoins
remain, because the gate itself does not split those.
The case is
[ai-config#2127](https://github.com/Morrison-Lab/ai-config/pull/2127), where
`shared/workflow/upgrade-to-gha.md:64` at `7f352648` was flagged
`Line packs more than one sentence`, and the fix at `7f352648` -> `d70465f5`
both broke the line and reworded the opener to `The gha README names`.
That file has since moved on, so read both line numbers against `7f352648`
rather than against the current tree.)

**That check WAS advisory --- it warned and exited 0 --- and stopped being so
on 2026-08-18.**
`Morrison-Lab/gha@e91b8bf` ("fail by default when violations are found",
gha#508/#509) flipped `_DEFAULT_FAIL` to `True`, and this repo's `validate.yml`
passes `NLB_FAIL: true` besides, so a violation now reddens the check rather
than annotating a green one.
Read this as a caution about the *file* as much as about the check: the
advisory claim was measured on 2026-08-15 and was wrong three days later,
which is the decay [`timestamp-volatile-claims`](timestamp-volatile-claims.md)
exists for.

The old advice --- read its output rather than its color --- is still worth
keeping, because it now points the other way.
A green **`pull_request`-triggered** job means the added lines passed.
Two other green results mean nothing was examined, and both come from the same
cause --- the script is diff-scoped, so a run against the wrong base, or against
no base at all, reports a clean exit over a diff it never looked at.
The local run does this when pointed at the wrong base ref.
The push-triggered CI job does it unconditionally, as the section above
records.

**Reading that output means reading its summary count, because one failure's
findings mix both rules.**
A failing job prints one `##[error]` per finding and then a total, and the two
rules interleave freely in that list.
So a count of the annotations carrying one rule's wording under-reads the
failure, and the shortfall invites a hunt for a finding the log never withheld.
Take the size of the failure from the summary line, which states the total the
job actually found, and read the findings under both wordings.

Two details make the annotations easy to miscount.
A finding's quoted line is elided only past 80 characters of the raw line, so a
long line ends in a trailing `...` while a short one is quoted whole.
The runner then adds an `##[error]` of its own reading
`Process completed with exit code 1.`, so the annotation count sits one above
the finding count.

[`github-actions`](../../memories/github-actions.md) records a second way to
under-read the same list, from the other end: a `grep -v` on `##[` strips the
annotation lines, leaving the summary total with no findings beneath it.
Both leave a reader reasoning about findings they never read.

- **Do:** take a line-break failure's size from its `N line(s) need a semantic
  break` summary line rather than from a count of matching annotations.
- **Do:** search the annotations for both `mid-line semicolon` and
  `packs more than one sentence`.
- **Don't:** read a trailing `...` as a truncated list --- it elides one
  finding's quoted line, and a short finding carries no ellipsis at all.
- **Don't:** treat a count of one rule's annotations as the failure's total.

(Measured 2026-08-24 on run
[32751350901](https://github.com/Morrison-Lab/ai-config/actions/runs/32751350901),
which printed 9 findings under a summary reading
`9 line(s) need a semantic break`, 7 from the clause rule and 2 from the
sentence rule, plus the runner's own tenth annotation.
A hand-rolled sweep of the same diff for a long line carrying a semicolon
returned 8 rather than 7, and the extra one was its own false positive:
`shared/workflow/upgrade-to-gha.md:62` at `7f352648` is 144 characters raw and
73 once
`strip_inline_markup` removes its code spans and link targets, so it sits below
`NLB_CLAUSE_MIN_LENGTH` and `classify_line` returns `None`.
The two thresholds are separate measurements that happen to share a number: the
elision above counts the raw line, while `NLB_CLAUSE_MIN_LENGTH` counts the
stripped text and is inclusive at 80.
Measuring the raw line rather than the stripped one is one way a hand-rolled
matcher disagrees with the gate.)

**An ellipsis is a sentence boundary to the gate, so a quotation or an elision
splits the line it sits on.**
The lowercase-follower case above used to be a boundary the reformatter
missed and the gate found.
After #2085 they share that branch.
This ellipsis case is a boundary neither tool is *named* for --- the regex
matches characters, not a writer's intent --- but both now split it, because
they share `_SENT_BREAK_RE`.
It arrives in the prose this corpus writes constantly: a quoted fragment
trailing off, or a `[...]` elision inside a citation.

`_SENT_BREAK_RE` matches `[.!?]` followed by any run of closing punctuation
`` [`"')\]*_] `` and then whitespace and an uppercase letter or markup.
A `.` is the first character of `...`, and `]` and `"` are both in that closing
class, so `[...] Text` and `... " And` each match --- the line is then read as
packing two sentences and flagged, however short it is.
A lowercase follower does not match, which is why the same construct passes
mid-clause and fails only when the next word is capitalized.

Verified 2026-08-24 by running the gate's own `_SENT_BREAK_RE` from
`check-new-line-breaks.py` at the pinned SHA over four inputs:
`... " And`, `[...] Everything`, and an ordinary `one. Two` each split into two
segments, while `... continues` stayed one.

- **Do:** break after a `[...]` elision or a trailing-off quotation whenever
  the next word is capitalized, exactly as after a full stop.
- **Do:** treat a flagged line whose only `.` is inside an ellipsis as a real
  finding rather than a false positive.
- **Don't:** assume an ellipsis is inert because it is not a sentence end in
  ordinary reading --- the gate matches characters, not intent.
- **Don't:** skip `--write` on an ellipsis hit thinking the reformatter cannot
  see it.
  It shares `_SENT_BREAK_RE`, so `--write` proposes the same split the
  gate flags.

**The sentence rule has no minimum line length; only the CLAUSE rule does.**
`NLB_CLAUSE_MIN_LENGTH` (80) gates the mid-line-semicolon check alone, so a
SHORT line carrying two sentences is flagged all the same.
That asymmetry is the one worth remembering, because a hand-rolled pre-push
scan naturally applies one length floor to both and then passes a line the
gate rejects --- which is the specific way this was rediscovered, on the PR
that added this very paragraph.
Run it locally before pushing and fix what it names.
This repo vendors that script at the SHA `validate.yml` pins, so a
gha checkout is not required:

```bash
NLB_BASE_REF=origin/main \
NLB_PATHS_IGNORE='codex-skills/**,docs/**,_site/**,.quarto/**' \
  python3 scripts/vendor/gha-check-new-line-breaks.py
```

That path is the file `scripts/lib/nlb_gate.py` loads.
Refreshing it after an action-pin bump is `python3 scripts/sync-nlb-checker.py`.

**That script takes no arguments and runs the sync on any invocation, including `--help`.**
It has no `argparse` or usage guard,
so `--help` is not special-cased and runs the full fetch-and-write path at whatever SHA `validate.yml` currently pins.
Measured 2026-09-02: `python3 scripts/sync-nlb-checker.py --help` fetched the vendored checker at the pinned SHA and rewrote `scripts/vendor/gha-check-new-line-breaks.py` plus its `.pin`.
The run was a no-op only because the pin had not moved yet.
- **Do:** bump the `uses:` SHA in `.github/workflows/validate.yml` first, run the script with no arguments, then commit the workflow, the vendored script, and the `.pin` together.
  `scripts/lib/nlb_gate.py`'s `assert_pin_matches_ci` refuses to load if the three disagree.
- **Don't:** run the script with `--help` to learn its usage.
  Read its module docstring instead.
(Measured 2026-09-02 on [Morrison-Lab/gha#826](https://github.com/Morrison-Lab/gha/pull/826)
and [ai-config#3089](https://github.com/Morrison-Lab/ai-config/pull/3089);
tracked as [ai-config#3095](https://github.com/Morrison-Lab/ai-config/issues/3095).)

**`NLB_PATHS_IGNORE` is the one input the local run needs and does not
default to**, so a command without it over-reports on generated files this
repo's workflow excludes --- the `codex-skills/` wrappers most of all, since
they are machine-written and nobody is going to line-break them.
Everything else the workflow passes is already the script's own default, so
setting it changes nothing: `NLB_GLOBS` defaults to `*.md`, `NLB_FAIL` and
`NLB_CLAUSE_BREAKS` to true, and `NLB_CLAUSE_MIN_LENGTH` to 80 (read off
`check-new-line-breaks.py` at `Morrison-Lab/gha` `430393d`, and confirmed
against a passing job's own log, which prints every `NLB_*` value it used).
The practical consequence is worth stating in the safe direction: the clause
check that catches a long line with a mid-line semicolon **is** on by default
locally, so a local run **of `check-new-line-breaks.py`** cannot silently
under-report that case.
Naming the script matters only when this sentence is read out of its
subsection, where "a local run" could otherwise be taken for
`scripts/semantic-line-breaks.py`.
That script now consumes this same checker (ai-config#2085), but it is a
reformatter of named files, not the diff-scoped job.
It does not apply `NLB_PATHS_IGNORE`, and it does not restrict itself to
lines added since `NLB_BASE_REF`.
(ai-config#725: a round of review fixes introduced 7 multi-sentence lines; the
check flagged all 7 while `validate` stayed green, and the review bot did not
catch them either --- they were found only by reading the check's own output.)

**Run it AFTER committing, not before: it diffs `<base>...HEAD`, so
uncommitted work is invisible to it and a pre-commit run reports clean
vacuously.**
This is a nastier version of the advisory-exit-0 trap above, because here
the output is a positive all-clear rather than a warning nobody reads.
With nothing committed yet, `HEAD` still equals the base ref, so the diff is
empty and the script says `No lines missing semantic breaks` --- a true
statement about an empty diff, easily misread as a verdict on the work in
the tree.
The tell is that it passes instantly on a diff you know is large.
So commit first, then run it, then amend or add a fixup for whatever it
names.
And when quoting the result as evidence (a PR body's verification section),
re-run it against the pushed head rather than reusing an earlier run's
output.
(ai-config#752, 2026-07-27: the pre-commit run reported clean and that claim
went into the PR body; the same content flagged 7 lines the moment it was
run again after committing.)

(A fourth pre-commit false clean, counting `memories/git-diffing.md`'s two:
ai-config#2381, 2026-08-27.
A pre-commit run passed over new uncommitted lines,
and the identical post-commit invocation flagged one of them.
The session then nearly recorded this rule a third time, in
`memories/tools.md`, because its dupe grep was phrase-keyed ---
`nlb|NLB_BASE_REF|gha-check-new-line-breaks` over `memories/` ---
a population that never included this fragment at all,
and `memories/git-diffing.md`'s entry contained none of those strings;
a mechanism-keyed grep (`unified=0`) found both at once, per
[`grep-is-not-coverage`](../workflow/grep-is-not-coverage.md).
That recurrence count meets
[`deterministic-tools`](../principles/deterministic-tools.md)'s bar for an
instrument rather than more prose:
a dirty-tree warning in the checker itself is tracked as ai-config#2382.
[Morrison-Lab/gha#826](https://github.com/Morrison-Lab/gha/pull/826) shipped that dirty-tree warning as `NLB_SCOPE=auto`, which widens the check to the working tree exactly when it is dirty.
[`warn-new-line-breaks-on-push.py`](../../hooks/warn-new-line-breaks-on-push.py) now pins `NLB_SCOPE=committed`,
so the pre-push hook keeps predicting CI on the pushed commits
rather than also warning on uncommitted edits CI will never see.
That pin closes the "hook over-warns" question [ai-config#3027](https://github.com/Morrison-Lab/ai-config/issues/3027) raised.
(measured 2026-09-02 on [ai-config#3089](https://github.com/Morrison-Lab/ai-config/pull/3089).)

**A third dirty-tree symptom, and the only one that flags a line you never
touched: the line NUMBERS come from the commit and the line CONTENT comes
from the tree.**
Both cases around this one describe the check reporting the *committed*
state --- vacuously clean, or stale.
This one reports a line that is unchanged in both states and appears in
neither's diff, which is why it reads as a checker bug rather than as the
run-after-committing rule firing again.

The mechanism is one function boundary.
`_added_line_numbers()` derives its line numbers from
`git diff --unified=0 <base>...HEAD`, so they are numbered against **HEAD**.
`find_violations()` then does `path.read_text()` and indexes
`lines[line_no - 1]`, which is the **working tree**.
An uncommitted insertion above shifts every later line, so the two
snapshots disagree by exactly that many lines and the check classifies a
neighbour it was never pointed at.

That is [`verify-the-right-artifact`](../workflow/verify-the-right-artifact.md)
inside a single instrument: an index from one artifact, content from
another.
It also explains why the flagged line is often a long pre-existing one ---
the corpus has many, and any of them can drift under the cursor.

- **Do:** commit, then re-run, before believing a flag on a line your diff
  does not contain.
- **Do:** check whether the reported line appears in `git diff -U0` at all;
  absent means the numbering is off, not that the checker is wrong about
  the line's contents.
- **Don't:** hand-edit the flagged line --- it is someone else's line, and
  editing it makes a pre-existing violation yours.
- **Don't:** file it as a checker bug; the check is documented to diff
  `<base>...HEAD` and never claimed to read the tree consistently.

(Measured 2026-08-21 on
[ai-config#1787](https://github.com/Morrison-Lab/ai-config/pull/1787).
A dirty-tree run flagged `skills/post-merge/SKILL.md:916`, an anti-pattern
bullet about force-pulling a diverged checkout, roughly 140 lines from the
nearest edit.
`git diff origin/main -- <path>` did not contain it and `git diff -U0` put
it outside every added hunk;
the merge base carried it verbatim.
Committing and re-running cleared it with no edit to that line.)

**On a branch that already has commits, the same mistake reports the opposite
symptom: the violations you just fixed, quoted in their pre-edit form.**
The case above assumes nothing is committed yet, so `HEAD` equals the base
and the diff is empty.
Fixing a *review* finding is the other situation, and the more common one:
the branch already carries commits, so the diff is not empty --- it is simply
the committed state, which still holds the long lines whose replacements sit
uncommitted in the tree.
The check duly reports them.

That inverts the misreading, and the inverted one is worse.
A vacuous all-clear at least invites suspicion, whereas this output looks
like a fix that did not work --- which invites re-editing prose that is
already correct, or doubting where the reviewer's finding actually pointed.
The tell from the case above, passing instantly on a large diff, does not
fire here, because the check runs normally and reports real lines.
The tell for this one is that the flagged text is the *old* wording of lines
you know you changed: if the report quotes a string no longer in the file, it
is describing `HEAD` rather than your tree.
One `grep` for a quoted fragment settles it.

So the rule is unchanged and only the failure looks different: commit first,
then measure.

- **Do:** re-run the check after committing whenever it flags lines you
  believe you already fixed, before touching the prose again.
- **Don't:** conclude a reflow failed because a pre-commit run still reports
  the old lines.

(Morrison-Lab/ai-config#835, 2026-07-30: a round-2 reflow was checked before
committing, and the scan returned the original 154- and 175-character lines
verbatim.
Re-running after the commit reported 0 multi-sentence lines and 1 over-80
line out of 38 added.)

**A rebase or cherry-pick expires the result, so re-run it after moving the
commit to a new base.**
The rule above covers a check that ran too early, against an empty diff.
This is its mirror: a check that ran correctly, and whose answer has since
stopped applying.
A diff-scoped check answers a question about `<base>...HEAD`, so changing the
base asks a different question, and the previous answer is about a diff that
no longer exists.

Cherry-picking onto a fresh `main` is the usual way this happens, and it is
the worst moment for it, because attention is on whether the *content*
survived the move.
The checks feel like settled history rather than like something the move
invalidated, so nothing re-runs them, and the PR opens carrying an all-clear
that was true of a different diff.

Treat any change of base as invalidating every diff-scoped result at once:
this check, the banned-punctuation scan in
[`ascii-punctuation-in-source`](../coding/ascii-punctuation-in-source.md),
and a repo's own `lint-changed-lines`.
The re-run is seconds; the alternative is a reviewer finding what your own
instrument already knew how to find.
(Morrison-Lab/ai-config#833 -> #836, 2026-07-29: #833 merged while a
follow-up commit was mid-push, so that commit was cherry-picked onto a fresh
branch off the new `main`.
The check had passed on the old branch and was not re-run against the new
head; review then flagged a two-sentence line, which the re-run reproduced on
the first try.)

**A reflow pass of your own expires it too, because the range has two ends and
a rebase only moves one of them.**
The section above states the mechanism generally --- a diff-scoped check
answers a question about `<base>...HEAD` --- and then narrows its conclusion to
the base.
The narrowing is what lets this through.
`HEAD` moves far more often than the base does, and it moves because of your
own edits, so a reformatting pass expires every line-scoped result taken before
it even when nothing rebased and every check ran at the right moment.

The mechanism is that a reformat changes **which lines are added**.
Splitting a long line at a sentence boundary retires one added line and creates
two, and neither of the new ones was in the set an earlier scan examined.
So the earlier answer is not merely old.
It is an answer about lines that no longer exist.

A reflow is the worst of the diff-mutating passes to run late, and the one a
pre-push sweep most encourages running late, because its findings arrive as
warnings to clear rather than as content to write.
Regenerating a generated tree and merging `main` do the same thing on a larger
scale.

The failure is silent and reads as verified, which is what separates it from an
ordinary stale result.
The earlier check genuinely passed, so its output is a true measurement --- and
a true measurement is exactly the kind of thing that gets quoted into a commit
message and a PR body's verification section, where a reviewer meets a specific
numeric claim with nothing in the diff to contradict it.

The remedy is ordering rather than vigilance: run every diff-mutating pass
first, and every line-scoped check afterwards, as one block at the end.
Ordering is checkable, and a resolution to remember is not.

- **Do:** run every diff-mutating pass --- a reflow, a rewrap, a re-sort, a
  generator re-run, a `main` merge --- before any line-scoped check, and run
  the checks last as one block.
- **Do:** re-run a line-scoped check after any pass that edited the diff,
  including one whose whole purpose was to satisfy a different check.
- **Don't:** treat a check's result as durable because it was taken after
  committing and with the three-dot range --- that range's `HEAD` end moves
  with every edit you make.
- **Don't:** quote a check's output in a commit message or PR body without
  re-running it at the head you are about to push.

**Re-run markdownlint in that block too, even though it is not line-scoped ---
it is the only one of these that actually reddens `validate`.**
The rule above enumerates line-scoped checks, and a reader takes the
enumeration as the list: this check, the banned-punctuation scan,
`lint-changed-lines`.
Markdownlint is not on it, because it is whole-file rather than diff-scoped,
so nothing about the phrase "line-scoped check" reaches it.

Its scope and its severity run opposite to everything else in the block, which
is what makes the omission expensive.
`validate.yml` runs both `npx --yes markdownlint-cli2` and
`check-new-line-breaks` as blocking checks (each fails the job on a non-zero
exit).
Markdownlint is the one the ordering rule above leaves out, and a reflow can
introduce a rule violation none of the enumerated line-scoped scans can see ---
MD018 when a split lands an issue reference in column 1 (the section further
down owns that collision), and MD022 when it disturbs the blank line around a
heading.

- **Do:** run markdownlint last, alongside the line-scoped checks, after every
  diff-mutating pass.
- **Don't:** read "line-scoped checks" as the whole re-run list --- the
  whole-file one is the only one that can fail the build.

(Morrison-Lab/ai-config#1259, 2026-08-07: `3c2cd225` moved 38 case records out
of `CLAUDE.md`, then converted em-dashes on the diff's added lines, verified
with `git diff | grep -c` for banned glyphs at 0, then reflowed long lines to
clear `check-new-line-breaks`, verified at 0 warnings, then pushed quoting the
punctuation result.
The reflow split a list item, so the line carrying an em-dash was not in the
set the punctuation pass had scanned, and that pass was never re-run.
Review found the surviving glyph at `CLAUDE.md:420` --- the only one left in
the whole diff --- and noted that it contradicted the commit message's own
claim.
Fixed in `a06aa88f`.
Both passes ran after committing and with the three-dot range, so every remedy
this file offered was already being followed.)

**Relocating prose makes its multi-sentence lines yours, for the same
diff-scoped reason.**
Moving a section between files edits none of its lines and still puts every one
of them in the diff as an added line, so a file split or extraction hands you
the whole moved body to reformat.
[`ascii-punctuation-in-source`](../coding/ascii-punctuation-in-source.md) owns
the full statement of this, including why the scope-creep caution does not apply
and why deferring to a corpus-wide sweep does not either --- read it there
rather than re-deriving it.

Two mechanics specific to this check when you do the pass.
Use the real `check-new-line-breaks` rather than a hand-rolled matcher: a local
heuristic disagrees with it in both directions, over-reporting on ordered-list
markers and under-reporting a boundary like `.)` where the period is not the
last character before the space.
And prove the reflow changed nothing else, by comparing whitespace- and
markup-normalized word lists against the pre-move version --- a mechanical
reflow is exactly the operation that can silently drop a marker or a clause.

**When hand-reformatting a line the check flagged, copy the raw line rather
than the check's own report of it.**
The script strips a bullet marker or blockquote prefix before handing the
text to its sentence splitter, which is right for counting sentences and
wrong for reproducing the line.
So a reformat built from that output quietly loses the `- ` or `> ` the
original carried: a changelog entry stops being a list item while every
sentence inside it stays intact.

Nothing catches that on its own.
Re-running the check passes, because it re-strips a marker that is no longer
there to strip, and the reformatted prose reads correctly to a human.
The one instrument that decides it is a word-level diff of the two texts with
whitespace normalized away --- a dropped marker shows up as a missing token,
and so does any punctuation the reformat rewrote in passing.
Treat both as real findings rather than noise, since the whole premise of a
reformat is that only line wrapping changed.

Run that diff in **both** directions, though, and not only in the
did-anything-go-missing direction its wording invites.
A token the move *added* is as much a violation of that premise as one it
dropped, and a one-sided comparison passes over it --- which is how a
`grep '^+'` extraction's own `++ b/<path>` diff header rode into merged prose
in ai-config#1290.
Note also what the normalization costs: a dropped blank line contributes no
words, so this instrument cannot see a paragraph boundary the move collapsed
either.
[`fail-fast`](../principles/fail-fast.md)'s third pattern direction owns both
halves.
(ai-config#779, 2026-07-28: a demo reformat of one of gha's changelog
fragments dropped its leading `- ` and rewrote an em dash as `---`.
The check reported the result clean; the word diff found both.)

**A third blind spot, and the one that survives running the diff both ways: a
defect BOTH sides share.**
The two above are differences the normalization cannot represent.
This one is a defect the normalization deliberately ERASES, so the comparison is
not merely silent about it --- it is silent in both directions at once, and the
both-ways rule just above buys nothing against it.

The reasoning is short.
A both-sides comparison validates the TRANSFORMATION, never the INPUT.
Whatever class of difference the normalization exists to ignore, whitespace and
inline markup here, is exactly the class it cannot report --- and a flaw already
present in the ORIGINAL text falls in that class as readily as one the reflow
would have introduced.
The check then passes with a reassuringly specific word count, and the defect
ships untouched.

The worked shape is a hyphenated compound the author split across a line break,
`close-` ending one line and `order foot.` opening the next.
Collapsing `\s+` to a single space turns the pre-reflow and the post-reflow text
alike into `close- order foot.`, so the word lists match exactly and the check
reports nothing lost and nothing added, while both versions render that stray
space.

So pair the transformation check with one aimed at the INPUT.
For a reflow the cheap one is a scan for a line ending in a hyphen, anchored on
an alphanumeric so this corpus's own `---` convention does not flood it:

```bash
grep -rnE '[[:alnum:]]-$' shared/
```

Run it against the PRE-reflow text as well, since its whole point is to judge
text the comparison has already agreed with itself about.
Do not answer this by widening the normalization instead, per
[`address-every-comment`](../workflow/address-every-comment.md)'s rule that
extending a normalizer can break a term the previous version matched.

- **Do:** name the class of difference a normalization erases, and add a check
  aimed at that class over the input.
- **Do:** run the input-side check on the pre-reflow text too --- a defect the
  comparison cannot see is one it never had an opinion about.
- **Don't:** read "identical, N words, nothing lost or added" as a statement
  about the text; it is a statement about the edit.
- **Don't:** widen the normalization to swallow such a defect --- that degrades
  the comparison it exists to make.

(2026-08-16: a design-doc reflow was verified this way and reported "identical,
6498 words, nothing lost or added", while `close-` / `order foot.` sat split
across a line break in both versions; it was caught by eye, reading the
reflowed output.
The detector above, run over `shared/` at `41d82611`, returns exactly four
pre-existing instances and no false positives from the `---` convention, so the
class is live in this corpus and the scan is precise enough to act on.)

**Breaking a line just before an issue reference turns it into a malformed
heading.**
This corpus writes `#NNNN` references constantly and mandates one clause per
line, so the two conventions eventually collide: a clause beginning with an
issue number puts `#` in column 1, markdownlint reads it as an ATX heading with
no space after the hash, and `validate` fails MD018.

It is worth knowing because of *where* it surfaces.
The banned-punctuation and multi-sentence scans both pass, since neither looks
at column 1, and the line reads perfectly as prose --- so the first report comes
from CI, on a file whose content is entirely correct.
Nothing about writing the sentence suggests a formatting problem.

Reword so the clause opens with a word rather than the reference:
prefer "Round 2 on #1287 sharpens why" over the possessive form that leads with
the number.
Note that quoting the bad form in prose reproduces the fault whenever the quote
wraps onto a fresh line, which is how this very paragraph first failed.
Derive the class rather than fixing the reported line, since one collision
usually means others: `git diff <base>...HEAD | grep '^+' | tail -n +2 |
sed 's/^+//' | grep -nE '^#[^ #]'` returns every added line that opens with a
bare `#`.
The `tail -n +2` is load-bearing whenever such a pipeline's output is *kept*
rather than filtered again --- the diff's own `+++ b/<path>` header starts with
`+` too, so it survives the first grep and the `sed` mangles it into
`++ b/<path>` instead of removing it.
Dropping it by position rather than by pattern is deliberate: no prefix
separates the header from an added line that itself begins with `++`, per
[`fail-fast`](../principles/fail-fast.md)'s third direction.
It is harmless in this particular pipeline only because the trailing `^#`
filter discards the mangled header anyway.

**`tail -n +2` strips exactly one header, so on a multi-file diff the
position trick under-corrects.**
A diff carries one `+++ b/<path>` header per file, all of them surviving the
`grep '^+'`, and `tail -n +2` removes only the first --- so a two-file diff
leaves one mangled `++ b/<path>` line in the stream, and an N-file diff
leaves N-1.
A trailing filter (the `^#` grep above) still discards them, but a pipeline
whose output is *counted* or *kept* silently inflates by N-1: an added-lines
count reads one high per extra file, and the phantom line reads as content.
For a count, skip the extraction entirely and sum
`git diff --numstat <base>...HEAD`'s first column, which has no headers to
strip.
For kept content, drop headers per file rather than by global position ---
`grep '^+' | grep -v '^+++ '` --- which is safe exactly when every `+++ `
line in the stream is a real header.
The dangerous class is an added source line beginning `++ ` (two pluses
then a space): git's own `+` prefix turns it into a raw `+++ ` line, which
no pattern can tell from a header, per the fail-fast caveat above.
So the precondition check is a per-line membership test, not a pattern and
not an aggregate: each `+++ ` line's target must be a changed file's
`b/<path>` or `/dev/null`, and any other target is a phantom.

```bash
git diff --name-only <base>...HEAD | sed 's|^|b/|' > /tmp/known
git diff -U0 <base>...HEAD | grep '^+++ ' | sed 's/^+++ //' |
  while read -r t; do
    [ "$t" = /dev/null ] && continue
    grep -qxF "$t" /tmp/known || echo "phantom: +++ $t"
  done
```

Any `phantom:` line means fall back to parsing the diff's hunk structure
instead of prefix-filtering.
An aggregate comparison --- the stream's `^+++ ` line count against
`--numstat`'s file count --- cannot serve here: a header-deflating file (a
binary, a mode-only change) and a `++ ` source line elsewhere in the same
diff cancel, leaving the totals equal over a stream that still carries a
phantom, while a per-item test has nothing to cancel.
Note the deflating files are irrelevant to the filter's own safety --- a
missing header drops nothing --- so the aggregate was also counting a
quantity the question never depended on.
The residual limit: a phantom whose text coincidentally names a changed
file's own `b/<path>` --- or is literally `/dev/null`, colliding with the
deletion-header sentinel the test skips --- is indistinguishable from a
real header by any stream inspection, so certainty past that point is
hunk-structure parsing.

- **Do:** count added lines from `--numstat`, not from a header-stripped
  extraction.
- **Do:** verify every `+++ ` line's target is a changed file's `b/<path>`
  or `/dev/null` before trusting a `^+++ ` header filter on kept content,
  and fall back to hunk-structure parsing on any phantom.
- **Don't:** reuse the single-`tail` pipeline on a multi-file diff when its
  output is counted or kept --- it was written for a one-file diff, and each
  extra file adds one phantom line.
- **Don't:** guard the header filter with a single-line pattern or an
  aggregate count --- a raw `+++ ` line matches every header pattern, and
  totals can cancel; only the per-line membership test decides it, up to
  the coincidental-path and `/dev/null`-sentinel limits above.

(Morrison-Lab/ai-config#1476, 2026-08-15, review round 1, finding 2: a PR
body claimed "13 added lines" over a two-file diff whose true count was 12
--- the extraction pipeline above had left the second file's `+++` header in
the stream, and the header was counted as an added line.
The reviewer derived 12 from the PR's own `additions` field; `--numstat`
confirms it.)

- **Do:** scan added lines for a column-1 `#` before pushing, with the same
  after-committing, three-dot discipline the other diff-scoped scans use.
- **Do:** reword the clause to open with a word, keeping the reference inline.
- **Don't:** rely on the punctuation or sentence-count scans to catch it ---
  neither reads column 1.
- **Don't:** fix only the line CI named; the same phrasing habit produces the
  collision wherever a clause happens to start with a reference.

**Repointing a citation to a longer filename can push an untouched
`memories/` file over its hard-gated size ceiling, with zero content added.**
The "Relocating prose" section above is about the *moved* content's own
lines growing.
The citing side has its own version, and it fires on a file you never meant
to touch beyond a one-word swap.
`memories/` files sit under a hard-gated ceiling --- the checker script
calls itself advisory, but `test_check_memory_file_size.py`'s own
regression test asserts the *live corpus* stays under it, which is a
different, non-advisory guarantee --- so a file already sitting exactly at
1250 lines has zero headroom.
Repointing one citation inside it to a longer replacement name rewraps the
sentence carrying it, and in this semantic-line-break corpus that rewrap can
add a whole line, pushing the file to 1251 and failing CI though not one
word of content changed.

- **Do:** after repointing a citation, `wc -l` any touched `memories/` file
  that was near 1250 lines, and re-wrap the sentence to recover the line if
  it crossed.
- **Do:** read `test_check_memory_file_size.py` itself, not just the
  checker script's docstring --- the docstring calls the check advisory,
  and the test suite hard-gates the live corpus anyway.
- **Don't:** assume a citation swap with no other content change cannot
  move a file's line count.

(Morrison-Lab/ai-config#1291, 2026-08-08: repointing citations from
`fully-clean.md` to the longer `review-verdict-pitfalls.md` inside
`memories/claude-bot-workflows.md` and `memories/github-actions.md` tipped
each from exactly 1200 to 1201 lines, failing `validate` with no content
change; fixed by re-wrapping the same sentences at a different clause
boundary, restoring both to 1200.)

**Neither the gate nor markdownlint can tell a column wrap from a clause reflow, so a green run from both is weak evidence that a reflow was done right.**

Both instruments are described at length above --- the gate's two predicates, and `MD013` being off repo-wide --- and what matters here is what neither of them asks.
Neither asks **where** a break fell.
That is the whole content of the difference between a clause reflow and a hard wrap at column 80, and the width rule that would notice a column boundary directly is the one this repo disables.

Measured on [ai-config#3103](https://github.com/Morrison-Lab/ai-config/pull/3103), over the added prose lines of one fragment at three states, all diffed against base `2cde8d0bf` and classified with the gate's own `classify_line`: the unreflowed original at `02cbf00d8`, a fill-to-80 wrap of that same commit's added lines, and the clause-boundary reflow at `ba265b546`.
The gate reported zero flagged lines at each of the three.
The original scored zero because it was already sentence-conformant --- it was clause-broken prose awaiting a better reflow, not a paragraph blob --- which is the state this comparison needs it to be in.
Three trees, one verdict, and only one of the three is the wanted outcome.
Citing either instrument in that situation is the vacuous verification
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md)'s
"A checker that returns the same verdict on the broken tree is not evidence the fix worked" section describes.

**A column wrap is not guaranteed to pass, which is why the gate's silence has to be read as silence rather than as approval.**
Filling to a column merges as well as splits, so a wrap that packs two short sentences onto one line trips the sentence rule and turns the gate red.
The measurement above came back clean because that fragment's prose happened not to produce such a line.
So the gate can catch a column wrap by accident and cannot catch one on purpose.
Its silence therefore rules out one narrow subclass --- a wrap that merged two sentences --- and says nothing about where any other break fell, which is why it is weak evidence rather than none.

Two measurements do discriminate, each one command over the diff.

Print the added lines' lengths and look for a hard cliff at exactly 80, which is the signature of a column wrap.
Clause-broken prose has no such edge, because clauses do not end on a column.

```bash
git diff origin/main -- '*.md' | grep '^+[^+]' | cut -c2- |
  awk 'length > 0 { print length }' | sort -n | uniq -c | tail -20
```

Then count added prose lines that end mid-phrase --- on an article, a preposition, a conjunction, or an open bracket --- before and after.
A column wrap leaves many, and a clause reflow leaves approximately none, so the pair is the number worth reporting.

```bash
git diff origin/main -- '*.md' | grep '^+[^+]' | cut -c2- |
  grep -cE '\b(a|an|the|of|to|in|on|for|and|or|is|that|with|by|as|at)$|[[(]$'
```

Report the base and the line definition alongside either figure, per
[`grep-is-not-coverage`](../workflow/grep-is-not-coverage.md)'s
"A published count needs the ref and the flags it was measured with".
The second command counts every added line rather than only prose lines, and the gate's own `prose_line_numbers` gives a stricter population, so the two disagree by a margin that depends on how much of the diff is fenced or tabular.

- **Do:** measure the length distribution and the mid-phrase count before reporting a reflow verified.
- **Do:** publish the base and the definition with either figure, since neither is defined by the gate.
- **Don't:** cite the `new-line-breaks` gate or markdownlint as evidence a reflow was done at clause boundaries --- neither looks at where a break fell.
- **Don't:** read a green gate on the reflowed tree as discriminating.
  Confirm it goes red on the unreflowed one first, and on this property it may not.
