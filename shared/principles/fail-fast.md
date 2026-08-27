Fail fast; no silent failures.
Detect bad state as early as possible and stop with a clear error,
rather than proceeding and letting the failure surface later --- or
never --- as silently wrong output.

Extended rationale --- the mechanism, evidence, and argument behind
each rule below --- lives in
[`fail-fast.rationale.md`](fail-fast.rationale.md),
moved out of the auto-loaded context.
Each rule here keeps its statement and its Do/Don't pair;
read the companion when the reasoning or the evidence is the question.

Worked-example case records for the rules below live in
[`fail-fast.cases.md`](fail-fast.cases.md), moved out of the auto-loaded context.

## In code

- Validate inputs and assumptions at the top of a function ---
  `stopifnot()`, or `rlang::abort()` with a clear message --- instead of
  letting a bad value flow into a confusing downstream error or, worse,
  a plausible-looking wrong result.
- Don't swallow errors.
  A bare `except:` in Python, an R
  `tryCatch(..., error = function(e) NULL)`, or a shell `|| true` hides
  the failure without fixing it.
  R's `try()`, `suppressWarnings()`, and `suppressMessages()` belong in
  the same category: each mutes a whole class of condition rather than
  the one you know about.
- When a fallback is genuinely wanted --- graceful degradation at a
  system boundary, a retry for a known-transient failure --- make it
  explicit and observable: message the degradation, bound the retries,
  and document why the fallback is safe.
- In CI, a step that can fail should fail the job, not
  `continue-on-error` its way to a green check.
  The exception is a deliberate pattern that re-checks the outcome
  downstream (e.g. `Morrison-Lab/gha`'s `continue-on-error` review
  attempts feeding a single resolve-outcome step that still fails the
  job when neither attempt succeeded) --- the failure is deferred and
  handled, not ignored.

## Catch conditions by class, never by message text

The rule above bans swallowing every error.

[`fail-fast.rationale.md`](fail-fast.rationale.md) carries the argument.

What follows for a **change** to that class lives in
[`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s "Changing which
exception a function RAISES is a signature change that fails silently":
swapping the type can route an error into a handler written for something else,
making it quieter rather than louder, with nothing red to show for it.

## When exit codes carry meaning, an error path must set its own

The "In code" bullets say to stop with a clear error rather than proceed on bad
state.

- **Do:** reserve a distinct status for usage and internal errors whenever any
  other status carries a verdict, and set it explicitly.
- **Do:** assert the exit code in the test, not merely that `SystemExit` was
  raised.
- **Don't:** pass a string to `SystemExit`/`sys.exit` in such a program ---
  the message is free and the status is not.
- **Don't:** read "it exits and prints an error" as the error path being
  correct; the status is the part a caller acts on.

See [`fail-fast.cases.md`](fail-fast.cases.md), "A usage error that would have
been read as a verdict".

## In a check you run by hand

The rule is easiest to break in the throwaway one-liner you write to
verify your own work, because there the swallowed failure does not
produce a wrong result -- it produces a **clean bill of health**, which
is worse.

**The failure path and the pass path print the same thing, because `||` fires
on any non-zero status.**
`grep` exits 1 when it searched and found nothing, and 2 or higher when it
never ran, so `<check> || echo "clean"` reports a tool error as a pass.
A `\x{...}` pattern above `U+00FF` is the usual way to reach that error, since
PCRE rejects it outright under a non-UTF-8 locale.

- **Do:** branch on the exit status explicitly, treating 0 as found, 1 as
  clean, and anything else as the check having failed to run.
- **Do:** set `LC_ALL=C.UTF-8` on a glyph scan, or write the scan in a
  language that raises on a bad pattern.
- **Don't:** `||`-chain a check whose success message you would act on ---
  that spelling cannot distinguish "found nothing" from "never ran".
- **Don't:** substitute a literal-glyph bracket for the locale fix, since
  under a byte-wise locale `grep -P` reads it as a set of bytes and
  over-matches.

**Setting it explicitly is not the same as setting it on the right command,
and a pipeline is where those two come apart.**

- **Do:** put the locale assignment on the process that interprets the
  pattern, or export it around the whole pipeline.
- **Don't:** treat the presence of `LC_ALL=` somewhere in a command line as
  evidence that the matching stage received it.

### The same vacuous zero has a second cause: an empty input

Everything above assumes the check **broke** --- a rejected pattern, a wrong
locale, a swallowed non-zero exit --- and prints its failure as a pass.

- **Do:** print the examined count beside the finding count, so an empty input
  is visible rather than silent.
- **Don't:** treat an exit-status or locale guard as covering this --- both
  pass cleanly while the check examines nothing.

### A sound command can still examine almost nothing, when the selection stage collapses

The two cases above are the check **breaking** and the input being **empty**.

**The existing awk-range caution does not cover this, and its check passes
here.**

- **Do:** print how much the selection stage returned, not only what the matcher
  found in it.
- **Do:** run a range or extraction on its own once, and read what it selected,
  before piping it anywhere.
- **Don't:** treat a well-formed command over a non-empty file as evidence that
  anything was examined.
- **Don't:** rely on the anchors-match-once check to catch a collapsed range ---
  it is aimed at the widening case and passes cleanly on this one.

See [`fail-fast.cases.md`](fail-fast.cases.md), "Five instruments in one session
reporting a vacuous zero".

### A fourth cause: the check is sound, and the subject is wrong

The three above all leave the instrument examining too little --- it broke, its
input was empty, or a selection stage collapsed.

- **Do:** print or state the subject an instrument examined --- the repository,
  tree, or path --- alongside its finding count.
- **Do:** pass the subject explicitly (`git -C`, an explicit path argument)
  rather than inheriting it from the working directory.
- **Don't:** read a clean verdict as being about the repository you have in
  mind; a sound check reports truthfully about whatever it was pointed at.
- **Don't:** treat a printed scope line as covering this --- naming the base ref
  says nothing about which tree that ref was resolved in.

See [`fail-fast.cases.md`](fail-fast.cases.md), "A sound checker pointed at the
wrong repository".

**Both remedies above assume the subject is chosen by an argument, and a
drifted working tree chooses it silently.**
A checkout can hold `HEAD` on one commit while its index and working tree carry
another commit's content.
The repository is right, the path is right, and `git -C` changes nothing --- so
every bullet above passes while a whole-tree instrument measures a tree nobody
asked for.

What hides it is that such an instrument names no ref at all.
It reads the working tree, so there is no argument to get wrong and nothing
informative to print: a scope line naming the repository and the paths examined
is accurate, and still says nothing about which commit's content sat in them.

The tell is a disagreement between two reads of the same file, one scoped to a
git object and one to the working tree.
A `grep -n` for a heading returning one line number while
`git show HEAD:<path> | grep -n` returns another for that same heading means the
working tree is the thing to suspect, rather than either instrument.

The remedy is the one "A read-only question does not license a state-mutating
answer" gives, reached from a different direction: materialize the ref into a
scratch directory, rather than mutating the checkout to make the question
answerable.

```bash
scratch=$(mktemp -d)
git archive HEAD | tar -x -C "$scratch"
(cd "$scratch" && <run the instruments>)
```

Expect the figures to survive that, and do not read their survival as evidence
the first run was sound.
Re-running this way reproduced identical numbers, so the published counts stood
--- but they had rested on the wrong subject until something checked, which is a
correct conclusion drawn from a premise nobody had tested.

- **Do:** compare a `git show <ref>:<path>` read against a working-tree read of
  the same file when an instrument's numbers are load-bearing.
- **Do:** run a whole-tree instrument over `git archive <ref> | tar -x` into a
  scratch directory, so its subject is the ref rather than whatever the checkout
  currently holds.
- **Don't:** read `git -C` or an explicit path argument as settling the subject
  --- each names a location, and a drifted working tree is wrong about the
  content at that location.
- **Don't:** treat matching numbers on re-measurement as retroactive evidence
  that the first measurement was pointed at the right tree.

### The narration can be the unfalsifiable part, while the check is fine

Everything above concerns a command whose *output* cannot distinguish pass
from fail.

- **Do:** derive any conclusion you print from the output you just captured.
- **Do:** print the raw result alone when computing the label is not worth it
  --- no label beats a wrong one.
- **Don't:** write a parenthetical asserting what an upcoming command's output
  will mean; you are describing the expected case, and the unexpected one is
  why you ran it.
- **Don't:** trust your own label on a re-read --- it carries the authority of
  a conclusion and none of the evidence.

### A fan-out makes this worse, because every worker fails identically

The one-liner above swallows one command's failure.

See [`fail-fast.cases.md`](fail-fast.cases.md), "A 947-repo sweep that scanned
nothing".

#### A zero-shaped summary can be sound, and the scope line is what decides it

The rule above has a false-positive direction, and it lands on exactly the
tools that already comply with it.

- **Do:** look for a scanned/examined count on its own line before calling a
  zero-hit result vacuous.
- **Do:** report the scope and the finding together --- "439 files linted, 0
  issues" cannot be misread in either direction.
- **Don't:** read a summary's "0 files" as the number examined without
  checking what that tool counts.
- **Don't:** retract a check as vacuous on the strength of one line of its
  output.

### A background watcher reports failure as silence by default

The cases above are all checks you read the output of.

- **Do:** end a bounded poll loop with an explicit timeout message naming the
  condition that never arrived.
- **Do:** widen the filter to every terminal state, then confirm by asking what
  the watcher would have printed had the job died at the start.
- **Don't:** read a watcher's quiet as evidence the work is still in flight.
- **Don't:** treat "I read the tool's guidance about coverage" as having applied
  it.

### The pattern itself is the other half, and it fails without erroring

Everything above is about a check that *cannot report* its own failure.

- **Too loose -> phantom finding.**
  `grep "uses: [a-z]"`, written to find unpinned GitHub Actions, also
  matches the tail of `statuses: write`.
  It reported a pinning regression in a repo that had none.
- **Too narrow -> false all-clear, which is the dangerous direction.**
  A detector that serialized each CI job to YAML and searched the dump for
  `git push` cleared a job that runs `git push --force`, because the dump
  had line-wrapped the string.
  Acting on that would have stripped the push credential from a job that
  pushes.
  Separately, grepping a Markdown file for a section title returned nothing
  although the title was there, because the phrase spanned two source lines
  and was interrupted by backticks.

- **Do:** run the pattern against a case you know contains the thing, before
  reporting that it contains nothing.
- **Do:** anchor to the structure being matched, and state the paths the
  search actually covered alongside its result.
- **Don't:** treat a zero-hit result as a fact about the corpus when the
  pattern has never been seen to match anything.
- **Don't:** grep a re-serialization -- a YAML dump, a rendered page -- for a
  string whose formatting that step may have changed.

**A third direction, and the one the remedy above passes: the pattern is right
about the data and admits the stream's own metadata, because that metadata is
written in the data's alphabet.**

See [`fail-fast.cases.md`](fail-fast.cases.md),
"Why no prefix pattern separates a diff header from its data".

**Mind the precondition, because it is easy to lose.**

See [`fail-fast.cases.md`](fail-fast.cases.md),
"The per-file precondition, caught by dogfooding the guard".

**The precondition does not travel with the command, so knowing it is not
enough.**

See [`fail-fast.cases.md`](fail-fast.cases.md), "A denominator three too high,
from the documented remedy".

**What the pattern feeds decides how much this costs.**

**The tighter guard over-corrects, and what it loses is invisible to the check
that would look for it.**

See [`fail-fast.cases.md`](fail-fast.cases.md), "What the tighter `^+[^+]` guard
drops".

- **Do:** separate a prefix-compatible delimiter by **position**
  (`grep '^+' | tail -n +2`) rather than by a longer prefix, since a longer
  prefix is still a prefix and still collides.
- **Don't:** read a narrowed pattern as a fixed one --- `^+++ ` collides with
  an added `++ foo` exactly as `^+++` collides with an added `++i;`.
- **Do:** ask what a pattern *feeds* --- a detector's extra match gets
  investigated, an extractor's becomes content.
- **Do:** compare a moved block in both directions, so an added line is as
  visible as a dropped one.
- **Don't:** read a passing known-positive test as clearing this; the pattern
  matches the content correctly and takes one line more.
- **Don't:** reuse `^+[^+]` on prose --- it eats added blank lines, and the
  whitespace-normalized check will not report that either.

**The positional remedy does not generalize to a TWO-sided filter, and the obvious substitute for it is the same mistake with a longer prefix.**
`grep '^+' | tail -n +2` works because one file contributes exactly one added header.
A filter wanting both sides --- `git diff -U0 | grep -E '^[+-]' | grep -v '^[+-][+-]'` --- has no such position to skip to, so the reach for a two-marker prefix is natural and wrong in exactly the way the paragraphs above describe.
Markdown is where it bites hardest, since every list item begins with the data marker: a removed `- item` renders as `-- item` and an added one as `+- item`, both matching `^[+-][+-]` precisely as a header does.

Excluding the **real** header patterns is better and still not a fix, because `^--- ` and `^+++ ` are prefixes too.
Measured on git 2.53.0, against a commit replacing `-- legacy flag` with `++ new flag` alongside two ordinary lines:

| filter | reported | actual |
|---|---|---|
| `^[+-]` minus `^[+-][+-]` | 4 | 6 |
| minus `^(diff \|index \|--- \|\+\+\+ \|@@)` | 4 | 6 |
| `--output-indicator-old/new` | 6 | 6 |

`git diff --output-indicator-old=< --output-indicator-new=> --output-indicator-context=' '` re-marks the **data** lines while the file headers stay `---`/`+++`, so the collision cannot arise rather than being narrowed.
That dissolves the class the rest of this block works around, so prefer it where it is available --- measured present on git 2.53.0; check `git diff --help` before relying on it under an older git, since the version that introduced `--output-indicator-*` was not verified here.

Note the failure direction, which is the opposite of the extractor case above: this filter **under**-reports, so the diff looks smaller and cleaner than it is, and a reviewer trusting it approves lines nobody displayed.
Cross-check against `git diff --stat`'s own counts, which are a second instrument keyed on a different surface --- that disagreement is the only thing that surfaced this.

- **Do:** re-mark the data with `--output-indicator-old/new/context` when a filter needs both sides, rather than excluding markers from the data's own alphabet.
- **Do:** reconcile any hand-rolled diff filter's line count against `git diff --stat` before trusting what it printed.
- **Don't:** answer a header collision with a longer prefix --- `^--- ` and `^+++ ` collide with the data lines `-- legacy flag` and `++ new flag` exactly as `^[+-][+-]` collides with a markdown bullet.
- **Don't:** read a plausible-looking filter output as complete; under-reporting produces a clean-looking diff and no error.

(2026-08-17: the two-sided filter above reported 4 changed lines where `git diff --stat` said 8 insertions and 8 deletions, the missing lines being markdown bullets.
Re-measured here on a synthetic three-line case, so the arithmetic is checkable without that branch.)

**A fourth direction, and the one that answers a question you never asked:
`grep -o` reports the MATCH, so it cannot describe the VALUE.**

See [`fail-fast.cases.md`](fail-fast.cases.md),
"How far a `grep -o` pattern's own alphabet reaches into a value".

- **Do:** match the value's delimiters when the question is what the values look
  like, and mask the contents rather than quoting the match.
- **Do:** pick mask characters outside every class being collapsed, and check
  the mask against a value you already know.
- **Don't:** read a `grep -o` distribution as a fact about the data --- it is a
  fact about where each value first leaves the pattern's alphabet.
- **Don't:** promote a pattern written to locate something into the description
  of what it located.

### An anchor that forbids indentation is a narrowing nobody decided

The too-narrow direction above is a pattern that misses a **wrapped** or
**re-serialized** occurrence.
A leading `^` misses an **indented** one, and that deserves separating because
the narrowing is invisible in the pattern's own text: `^\| ` reads as "a table
row", and what it means is "a table row starting in column 1".

Markdown is where this bites hardest, since a table, a fence, or a nested list
is indented by the structure around it rather than by anyone's choice.
So a pattern anchored for a top-level occurrence returns a confident zero over
a file full of the thing it is looking for --- and unlike the wrapped-phrase
case, nothing about the source text looks unusual enough to prompt a re-check.

The failure direction is the expensive one, and it is the one the
known-positive rule above exists for: a zero reads as **absent**, which
licenses a claim about the corpus rather than about the query.

Allow the indentation rather than dropping the anchor.
An unanchored pattern matches mid-line occurrences the anchor was there to
exclude, so `^\s*` is the fix and bare removal is not:

```bash
grep -cE '^\|'    file.md   # 0  --- top-level rows only
grep -cE '^\s*\|' file.md   # 23 --- what is actually in the file
```

- **Do:** write `^\s*` rather than `^` whenever the thing matched can sit
  inside a list, a blockquote, or another block.
- **Do:** re-check a zero whose conclusion surprises you, since surprise is
  the only signal this failure emits.
- **Don't:** read a zero from a column-anchored pattern as a fact about the
  file --- it is a fact about column 1.
- **Don't:** answer it by deleting the anchor; that trades a false negative
  for the false positives the anchor was preventing.

(`Morrison-Lab/ai-config#1583`, 2026-08-17: checking whether a positional
reference "the table above" had a referent, `grep -n '^| '` over
`memories/github-mcp-tools.md` returned nothing, and the conclusion drawn was
that the file contained no table at all --- which would have made the
reference dangling rather than merely fragile.
`grep -nE '^\s*\|'` finds 23 table lines across four blocks, the nearest at
lines 991-1000, so the reference resolved correctly.
The tables are indented because they sit inside bullets.
Caught only because "this file has no table" was surprising enough to re-run,
which is not a mechanism.)

### Guarding an unsound pattern with a second pattern, rather than replacing it

Every direction above ends by naming a pattern that cannot separate what it is
asked to separate.
The natural next move, once you know a filter is unsound, is to keep it and add
a **precondition** that detects the case it gets wrong.
That move is wrong twice over, and it feels like diligence, which is why it
survives the reading that produced it.

It is wrong because the precondition is a pattern over the same stream, so it
inherits the ambiguity that made the first one unsound.
And it is wrong because nobody tests a guard: the filter has visible output that
gets eyeballed, while the guard's whole contract is to stay silent, so a
precondition that can never fire is indistinguishable from one that fires
correctly and finds nothing.
It therefore fails **open**, and it publishes a clean number while doing so.

The tell is a diff whose prose cites a rule saying no pattern works, in support
of a second pattern.
When the corpus already establishes that a class of instrument cannot decide a
question, the response is to **replace the instrument** --- with position, with
an independently computed quantity, with the tool's own structured output ---
never to add a detector for its failures.

Where a cross-check is genuinely wanted, take it from something that is not the
pipeline under test: a count from `--numstat`, a total the tool itself reports,
a figure derived by a different command.
A second reading of the same stream is not a second opinion.

- **Do:** replace an instrument a rule has already called unsound, rather than
  guarding it.
- **Do:** cross-check against a quantity computed outside the pipeline being
  checked.
- **Do:** test any guard you do write against the exact case it names, before
  trusting a zero from it.
- **Don't:** add a precondition over the same stream that made the first
  pattern ambiguous --- it inherits the ambiguity and hides it behind silence.
- **Don't:** read a guard's `0` as evidence of anything until you have seen it
  produce a non-zero **on the case it names**.
  A non-zero on some other case is the same false comfort one step along ---
  the guard has demonstrated it can count, and not that it can see.

See [`fail-fast.cases.md`](fail-fast.cases.md),
"A precondition that could not fire on the case it named".

### The third one arrives in the repair, and only on the empty input

The two cases above are checks written wrong the first time.

- **Do:** produce both sides of a comparison with the same command and the
  same filter, or show that they encode absence identically.
- **Do:** run a repaired comparison check once against an empty input before
  trusting the repair, whenever absence is reachable in its input domain.
- **Don't:** compare a chosen sentinel against a default emptiness shape.
- **Don't:** let a fix inherit the scrutiny that produced it, since the repair
  is the least-reviewed code in the round.

### A fallback chain flattens which alternative won

A `||` chain advances **only** on failure, so a later branch running is proof
an earlier one failed.

- **Do:** drop `2>/dev/null` before anything else --- the loser's own error
  message is the cheapest thing that names it.
- **Do:** check whether the winning branch's stdout identifies itself, and
  prefer a form that does (`ls -d` over `ls`) or print the resolved value.
- **Don't:** read a later branch running as evidence that nothing failed; `||`
  advances only on failure.
- **Don't:** assume the first branch won because it is the one you expected to
  win.

### A read-only question does not license a state-mutating answer

Every subsection above asks whether a hand-run check's **answer** can be
trusted.

- **Do:** materialize another ref with `git archive | tar -x` into a scratch
  directory, or a detached throwaway worktree, when a question spans refs.
- **Do:** run `git status` after a diagnostic you composed on the spot, and
  treat any change as the diagnostic having done something it was not asked to.
- **Don't:** chain a mutating command onto a read-only question because the
  mutation is the shortest route to the answer.
- **Don't:** let each command being individually correct stand in for the
  composition being appropriate --- that check passes on every instance of
  this.

**The undo step is the other half, and it can finish the destruction the
diagnostic started.**
Everything above concerns the mutation a diagnostic performs on the way in.
A control that writes into your working tree has a second mutating step
nobody plans for: the revert that puts the file back.
The natural undo is path-scoped --- `git checkout <path>` or
`git restore <path>` --- and that reverts **everything** uncommitted in that
path, not only the line the control injected.

So a control that was itself harmless destroys uncommitted work, in the step
whose whole purpose was to leave no trace.

Two properties keep it hidden.
The revert reports paths rather than lines, so nothing in its output
distinguishes reverting one injected line from reverting a file's entire
uncommitted diff.
`git restore FILE` prints nothing at all, and `git checkout FILE` prints only
`Updated 1 path from the index` --- measured on git 2.43.0 --- which is
equally true either way.
And `git status` afterwards still looks plausible whenever sibling files
carry their own uncommitted changes: the tree is still dirty, the list is
still non-empty, and only the one file has been emptied.

Three remedies, in order of preference.
Commit or stash before running a control that writes into the tree, so the
revert has a real baseline to return to.
Inject into a copy outside the tree, so no revert is needed at all.
Or undo the injection surgically, deleting the line you added, rather than
reverting the path.

- **Do:** commit or stash uncommitted work before a control writes into a
  tracked file.
- **Do:** undo an injection by removing what you injected, rather than by
  reverting the path it lives in.
- **Don't:** reach for `git checkout <path>` or `git restore <path>` to clean
  up after a diagnostic --- it reverts every uncommitted change in that path.
- **Don't:** read a still-dirty `git status` as evidence the revert was
  scoped; sibling files' changes keep the list non-empty either way.
- **Don't:** read `Updated 1 path from the index` as confirmation the revert
  was narrow --- it counts paths, never lines.

(2026-08-15: testing whether a repo's `chars` check detected U+00D7 meant
appending a literal multiplication sign to a tracked `.qmd`, re-running the
check --- which reported PASS, a real finding --- and then reverting the file.
The revert discarded an uncommitted fix made to that same file minutes
earlier.
Three sibling files kept their fixes, so `git status` still listed
modifications and looked plausible; only re-counting the specific file caught
it.)

## In a guard you ship: partial is worse than absent

Everything above concerns a check whose failure is invisible **at runtime**,
because its failure path prints what its pass path prints.

- **Do:** list every site that performs the guarded operation, then check the
  guard against that list rather than against the site that prompted it.
- **Do:** grep for the operation, not for the guard.
- **Don't:** ship a guard on one of several sibling paths without a comment
  saying why the others need none.
- **Don't:** read a guard's presence in a file as evidence the file is guarded
  --- that inference is precisely what a partial guard supplies for free.

**A review lifecycle can play this failure out one path at a time, which is
the same defect stretched across rounds rather than shipped at once.**

**When the siblings are members of one pattern rather than sites in one file,
the remedy above has nothing to grep.**

- **Do:** treat an alternation, allowlist, or token set as a list of sites, and
  check the fix against every member before committing it.
- **Do:** apply a comment's stated exclusion reason as a predicate to the
  members still present, in the same edit that writes the comment.
- **Don't:** read "grep for the operation" as covering this --- when the
  siblings share one expression, that grep returns the line you are already
  looking at.
- **Don't:** treat a considered comment about a hazard as evidence the hazard
  was handled everywhere it applies; a removal note is the artifact most likely
  to stop the search early.

**The same defect arrives with the members in a LIST and the branch inside the
loop, which this block's "same expression, on the same screen" tell misses.**

- **Do:** grep a guarded loop for `== <literal>`, and turn each hit into a
  whole-collection rule or a named subset.
- **Don't:** read a per-member equality branch as a special case; it is an
  enumeration of one, and the collection it enumerates can grow.

**Widen that last bullet's trigger: any sentence naming a hazard is a
predicate, and the first code it applies to is the code directly beneath it.**

- **Do:** re-read the lines under a hazard comment against the hazard it names,
  in the edit that writes the comment.
- **Don't:** count naming a risk as handling it --- the sentence is a
  specification, and nothing has yet met it.

**When the hazard is a phrase a qualifier can reverse, enumerate the qualifier
classes by which SIDE of the phrase they sit on.**

- **Do:** list the qualifier classes by position --- before, after, within ---
  and cover each with its own case.
- **Do:** treat the after-side conditional as the likely form when the guarded
  phrase is an approval, not as the exotic one.
- **Don't:** read "add a negation guard" as the whole requirement; negation is
  one side, and it is the side that comes to mind first.
- **Don't:** reach for the members-of-one-pattern rule here --- enumerating an
  alternation's members leaves both sides of every member unguarded.

**Getting both sides covered is not the end of it: one side's own BOUNDARY can
encode the negation of the assumption the other side rests on.**

- **Do:** name the corpus property a guard depends on, and check the same diff
  for a boundary assuming its mirror.
- **Do:** distinguish a paragraph break from a wrapped line when defining a
  terminator, since only one of them ends a statement.
- **Don't:** treat a property you argued for two rounds ago as settled for the
  whole guard --- it was settled for the side you were writing then.
- **Don't:** let a boundary definition ride in as an implementation detail; it
  is a claim about the corpus, and it can contradict one you already made.

**A narrowing you argued for on one axis can be undone by an independent clause
on a DIFFERENT axis of the same predicate.**

- **Do:** list every independently-sufficient clause of a predicate you are
  narrowing, and apply the stated reason to each.
- **Do:** mutation-check clause by clause, and read a clause whose removal
  changes no test as a claim about redundancy rather than about correctness.
- **Don't:** treat a narrowing as implemented once the clause on the axis you
  argued about carries it --- a sibling clause on another axis can restore the
  breadth in the same function.
- **Don't:** excuse an over-broad guard as the safe direction when the inputs
  it over-reports are the tool's main use case.

**A rule you write down for one axis does not fire on the sibling axis in the
same function, and having written it is what makes the sibling invisible.**

- **Do:** treat an argument against a first-match reading as a predicate over
  every first-match reading in the same function and module, not only the one
  it was written beside.
- **Do:** re-derive the full set and require the whole set to qualify, which is
  the same ambiguity test the argument already prescribes for its own axis.
- **Do:** check the call site that supplies an argument, since a first-match
  derivation upstream reaches the guard as an ordinary parameter.
- **Don't:** count having written the reasoning as having applied it --- the
  argument is a specification, and only the axis you were thinking about has
  met it.
- **Don't:** reach for the disjunction rule above here; enumerating
  independently-sufficient clauses finds nothing when both conditions are
  necessary and the defect is in how each one's input was computed.
- **Don't:** read the hazard-comment rule as covering it either --- that rule
  sweeps the lines beneath the comment, and those are the lines that already
  comply.

See [`fail-fast.cases.md`](fail-fast.cases.md), "A rule written for one axis
does not fire on the sibling axis".

**One level up from a partial guard: editing state that two consumers share
regresses the consumer you were not looking at.**

- **Do:** enumerate every consumer of a shared object before editing it, and
  check the edit against each.
- **Do:** un-share the state --- a separately-scoped second pass --- when two
  consumers place conflicting demands on it, rather than re-editing it round
  after round.
- **Don't:** read a fix as done when it moves the failure to a different
  consumer of the same object; that is the shared-state loop, not progress.
- **Don't:** assume an edit that fixes one reader of shared state leaves the
  others intact.

See [`fail-fast.cases.md`](fail-fast.cases.md), "One shared abbreviation list
feeding two regex branches".

**The same shape governs an INSTRUCTION, and there the missing half is a step
rather than a site.**

- **Do:** derive a documented procedure's steps from the gate's own conditions,
  and state each as required.
- **Do:** re-read the docs of a fix that removes a silent failure, asking
  whether following them literally reproduces it.
- **Don't:** rely on an adjacent sentence to carry a precondition -- a reader
  who does not want that adjacent path will not read it as applying to theirs.
- **Don't:** treat "the docs mention the trigger somewhere in this file" as the
  precondition being stated.

See [`fail-fast.cases.md`](fail-fast.cases.md), "A documented enabling procedure
naming one of two required steps".

**A protective list and the test that proves it works are one artifact, so
adding a member to the list without adding its probe leaves the new member
outside the very net the list exists to be part of.**

The two lists look nothing alike from the inside, which is why this slips.
Adding the member is the task, and it is complete and correct on its own
terms: the entry is right, the thing is protected, the check passes.
The test file is somewhere else, usually in another directory, and nothing
about the edit points at it.
So the protection appears to be in place, and only the *proof* that it is in
place has a hole -- which is exactly the state a partial guard supplies for
free, one level up.

It is worse than a plain missing test.
A list of this kind is added to precisely when something newly needs
protecting, so the untested member is always the newest and least-understood
one, and a passing suite now reports on every member except the one whose
protection nobody has ever confirmed.

The shape is not specific to any one file.
A `.gitignore` guarding restricted data, a secret-scanner rule set, a
`CODEOWNERS` entry, a lint exclusion, an ignore list in CI: each has, or
should have, a test that asserts the list actually does its job, and each
grows one member at a time.

- **Do:** extend the list's own test in the same commit that extends the list,
  with a probe naming the new member.
- **Do:** confirm the probe fails when the list entry is removed, so it proves
  the protection rather than the file's existence.
- **Don't:** treat adding the member as the whole edit -- the member is
  protected and unproven until its probe exists.
- **Don't:** read a green suite as covering a member added after the suite was
  written; the suite enumerates, and an enumeration cannot grow by itself.

(`ucdavis/bcs#679`, 2026-08-20: `hong/` was added to `inst/extdata/.gitignore`
with no matching probe in `tests/testthat/test-restricted-paths-ignored.R`.
That test is layer 2 of a five-layer protection scheme bcs's `CLAUDE.md`
documents as having been built after a real PHI-and-credential incident on
2026-07-30, and its whole purpose is that a restricted path added without a
matching ignore rule fails CI rather than waiting to be noticed.
The new path sat outside it.
An AI reviewer caught the gap.)

## A guard's discharge fires on positive success, not the absence of failure

The section above is about a guard that runs on too few sites.

- **Over-warn** (guard fires when it needn't) is the **safe** direction.
- **Silent discharge** (guard clears when it shouldn't) is the **dangerous**
  one.

**Once the safe direction is known, it is a property to build the guard around,
not only one to defend it in.**

- **Do:** ask which direction an unforeseen case falls, and prefer the guard
  shape that sends it to the safe one.
- **Do:** pair an inverted pass with the original narrow pass, additively,
  rather than replacing it.
- **Don't:** keep extending an enumeration whose every gap is a silent
  fail-open, when inverting it makes the same gaps loud.
- **Don't:** treat an exclusion set as self-evidently safe --- "this text cannot
  execute" is a claim, and a deferred evaluator falsifies it.

### Measure how each wrong answer decays, and check what the status quo already pays

The two bullets above rank the directions by what each error costs **at the
moment it occurs**: an over-warn is visible, a silent discharge is not.

**Check the counterfactual in the same pass, because the decay you fear may
already be running.**

- **Do:** run each candidate direction forward one extra event, against both the
  changed and the unchanged code, and report all four results.
- **Do:** state what the status quo already pays before offering a cost as an
  argument against a change.
- **Don't:** settle a direction on a persistence argument you have not run ---
  a well-formed mechanism claim about future events is a prediction, not a
  measurement.
- **Don't:** credit a suppression with protection it does not supply; measure
  whether it prevents the recurrence or only postpones one event of it.

### A combined result cannot attribute a per-step outcome

The commonest way a discharge fires on false evidence: the guard reads a
**combined result** --- a shell `tool_result` covering several chained
commands, a batched response, any blob spanning more than one action --- and
attributes success to the specific step it cares about.

- **Do:** release a guard only on positive, attributable success; treat every
  releasing path as one class and gate them all on a confirmed result.
- **Do:** mutation-test each term of a release condition, and keep the
  over-warn on any genuinely ambiguous input.
- **Don't:** infer a per-step outcome from a combined result's whole-call
  status.
- **Don't:** trade a safe-direction over-warn for fewer nags --- that is the
  move that grows a silent-discharge hole.

### The FIRE condition is the mirror, and it wants corroboration rather than an absence

Everything above governs what RELEASES a guard.
A guard keyed on something being MISSING owes the same standard one step
earlier, at what makes it fire, since a fire condition satisfied by a null
result inherits
[`grep-is-not-coverage`](../workflow/grep-is-not-coverage.md)'s overreach
wholesale.

**This does not contradict the Don't directly above, and the two look
identical, which is why the distinction is worth stating.**
That one governs the RELEASE, where weaker evidence opens a silent fail-open.
Narrowing a FIRE condition spends false negatives instead, which for a
reminder guard is the cheap direction.

- **Do:** require a positive corroborating finding before a guard keyed on an
  absence fires, and put that finding in the message it emits.
- **Do:** measure the false-positive count both ways against the corpus the
  guard will actually run on, rather than arguing the direction.
- **Don't:** fire on a null result alone --- that is a claim about the query,
  not about the world.
- **Don't:** read the release rule above as forbidding a narrowed fire
  condition; it governs discharging on weak evidence, not triggering on
  strong.

## An empty substitution changes what the command operates on

Every case in "In a check you run by hand" above is a check whose failure
path and pass path print the **same** thing.

### `$?` belongs to the last thing evaluated, not the interesting thing

Two attribution traps in the same family, both of which make a status line
describe a command other than the one under judgment:

```bash
grep -q PATTERN file | head                  # rc is head's
echo "hits: $(wc -l < out.txt) (rc=$?)"      # $? is wc's, not the earlier grep's
```

- **Do:** assign a substitution to a variable, check it for emptiness, and
  quote it at the point of use.
- **Do:** treat "no output" from a query command as a **result** to report,
  since it is frequently the informative answer rather than a failure.
- **Don't:** read a command's output as an answer about an argument that came
  from an unchecked substitution.
- **Don't:** write `$?` after a pipeline or a substitution and label it with
  the name of an earlier command.

### A proxy that answers a narrower question passes the same way

The same session hit the pattern one level up, in a **recovery procedure**
rather than a single command.

See [`fail-fast.cases.md`](fail-fast.cases.md), "A proxy check that could not
discriminate the case it was run for".

- **Do:** ask what a proxy check would report in the case you are worried
  about, not only in the case you expect.
- **Don't:** accept a check that is right for a reason it never tested, when
  the deciding question is one command away.

See [`fail-fast.cases.md`](fail-fast.cases.md),
"An empty merge-base substitution reporting HEAD as the merge base".

**A history rewrite is the exotic cause of that zero; a squash merge is the routine one, and it makes the subject test fail by construction.**

See [`fail-fast.cases.md`](fail-fast.cases.md),
"A published bullet count that was stale before anyone read it".

**That content check is itself line-oriented, so in a semantic-line-break
corpus it produces the same alarming-direction false negative it was
introduced to cure.**

**Normalizing repairs the instrument and not the needle, so a probe you
invented returns the same confident zero.**

**The known-positive rule earlier in this file does not discharge it as
written, and the reason is what points at the fix.**

- **Do:** decide "did this land?" by grepping the content at the ref, naming a string only that change introduced.
- **Do:** prove a merge landed with `--numstat` where you can, since a check carrying no invented input cannot false-negative on its needle.
- **Do:** take the probe from the diff's own added lines whenever a specific string must be confirmed.
- **Do:** normalize whitespace and markup on both sides before concluding a merged phrase is absent, and name the search that settled it.
- **Do:** run the content check as its own command, so a zero count cannot also truncate the rest of the verification.
- **Do:** treat a zero from a subject match in a squash-merging repo as carrying no information, rather than as evidence of orphaned work.
- **Don't:** read a zero from a line-oriented `grep` for your own merged prose as evidence the merge did not land --- in this corpus that is the search failing, until a normalized one agrees.
- **Don't:** chain that grep with `&&` --- a zero count is also a non-zero exit, so it kills the steps behind it.
- **Don't:** read `--is-ancestor` returning non-ancestor as "not merged" in a repo that squash-merges --- it returns that for every merged branch.
- **Don't:** substitute a message-scoped `--grep` for the content check; it depends on whether the squash body was rewritten, which is nobody's invariant.
- **Don't:** build a probe from the PR title, the commit message, or the issue body --- that prose paraphrases the change by design, so it is the least likely text to appear in it.
- **Don't:** read a normalized search's zero as settled --- normalization repairs the matcher, and an invented needle is a different fault it cannot touch.

See [`fail-fast.cases.md`](fail-fast.cases.md), "Normalizing repairs the
instrument and not the needle".

## In review

Flag error handling that hides failure --- swallowed exceptions, silent
defaults substituted on failure, unbounded retries, `continue-on-error`
without a downstream outcome check --- the same weight as any other
standing review check.
Flag a handler that identifies a condition by matching its message text,
too, and ask for a class.
Ask for the explicit form: an early validation, a loud error, or a
documented, observable fallback.

Flag a guard applied to one of several sibling paths as well, and ask either
for the remaining ones or for a comment saying why they are safe.
This is the finding most likely to be missed by reading, since the diff shows
the guard being added rather than the sites it skipped --- so check it against
a grep for the guarded operation, not against the diff.

Flag a guard that **releases** (discharges, clears, marks handled) on the
absence of a failure rather than on positive, attributable success --- and one
that infers a per-step outcome from a combined result's whole-call status.
Ask whether every releasing path is gated on a confirmed result, and whether a
change that reduces an over-warn is quietly opening a silent-discharge hole in
the dangerous direction.

This serves the Reliable goal in the
[principles catalog](README.md): a loud failure is easier to catch than
a silent one.
