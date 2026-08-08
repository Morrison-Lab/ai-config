Fail fast; no silent failures.
Detect bad state as early as possible and stop with a clear error,
rather than proceeding and letting the failure surface later — or
never — as silently wrong output.

Worked-example case records for the rules below live in
[`fail-fast.cases.md`](fail-fast.cases.md), moved out of the auto-loaded context.

## In code

- Validate inputs and assumptions at the top of a function —
  `stopifnot()`, or `rlang::abort()` with a clear message — instead of
  letting a bad value flow into a confusing downstream error or, worse,
  a plausible-looking wrong result.
- Don't swallow errors.
  A bare `except:` in Python, an R
  `tryCatch(..., error = function(e) NULL)`, or a shell `|| true` hides
  the failure without fixing it.
  R's `try()`, `suppressWarnings()`, and `suppressMessages()` belong in
  the same category: each mutes a whole class of condition rather than
  the one you know about.
- When a fallback is genuinely wanted — graceful degradation at a
  system boundary, a retry for a known-transient failure — make it
  explicit and observable: message the degradation, bound the retries,
  and document why the fallback is safe.
- In CI, a step that can fail should fail the job, not
  `continue-on-error` its way to a green check.
  The exception is a deliberate pattern that re-checks the outcome
  downstream (e.g. `d-morrison/gha`'s `continue-on-error` review
  attempts feeding a single resolve-outcome step that still fails the
  job when neither attempt succeeded) — the failure is deferred and
  handled, not ignored.

## Catch conditions by class, never by message text

The rule above bans swallowing every error.
Its natural consequence is that code sometimes needs to handle exactly
*one* failure and let the rest through --- and the way that is reached for
in R, matching on the error's message, quietly reintroduces the problem.

[Advanced R, "Custom
conditions"](https://adv-r.hadley.nz/conditions.html#custom-conditions):

> if you want to detect a specific type of error, you can only work with the
> text of the error message.
> This is error prone, not only because the message might change over time,
> but also because messages can be translated into other languages.

A message-matching handler fails in the direction that hurts.
When the wording drifts or the session runs under another locale, the match
stops firing and the error escapes the handler that was supposed to own it
--- or, worse, a substring match starts catching an unrelated error and
routing it into recovery meant for something else.

Signal a classed condition instead, and put the machine-readable detail in
fields rather than in the sentence:

```r
rlang::abort(
  "Path `blah.csv` not found",
  class = "error_not_found",
  path  = "blah.csv"
)

tryCatch(
  read_thing(p),
  error_not_found = function(cnd) use_default(cnd$path)
)
```

The handler now keys on `error_not_found`, which is part of the interface,
while the sentence stays free to be rewritten or translated.
Unrelated errors are unaffected and keep propagating, which is the property
message matching cannot offer.
(Verified on rlang 1.3.0: the condition's class chain is
`error_not_found` / `rlang_error` / `error` / `condition`.
Note the book shows an older calling convention, passing the class as the
first argument; current `rlang::abort()` takes `message` first and `class`
as a named argument.)

This is also why `try()`, `suppressWarnings()`, and `suppressMessages()`
are listed above as swallowing rather than handling.
The book's own objection is precisely their lack of a class to aim at:

> These functions are heavy handed as you can't use them to suppress a
> single type of condition that you know about, while allowing everything
> else to pass through.

When a specific condition genuinely should be ignored, name it ---
`withCallingHandlers()` plus `rlang::cnd_muffle()` on that class, or
`tryCatch()` on that class --- rather than muting the whole category.
See [Ignoring
conditions](https://adv-r.hadley.nz/conditions.html#ignoring-conditions).

## In a check you run by hand

The rule is easiest to break in the throwaway one-liner you write to
verify your own work, because there the swallowed failure does not
produce a wrong result -- it produces a **clean bill of health**, which
is worse.

The shape to watch for is a verification command whose failure path and
whose pass path print the same thing:

```bash
# Wrong -- "none" means "no matches" OR "grep never ran"
grep -P '[\x{2014}]' file || echo "none"
```

`grep` exits non-zero both when it finds nothing and when it errors out,
so a bad pattern, an unreadable file, or an unsupported flag reports
exactly like a clean file.
Nothing looks wrong, and the check is now worse than not having run one,
since it converts an unknown into a confident "verified".

Make the two outcomes distinguishable.
Test the exit status explicitly (`rc=$?`, treating 0 as found, 1 as clean,
anything else as an error), or write the check in a language that raises on
a bad pattern and print an explicit count -- a check reporting `0 hits` out
of a stated number of lines examined cannot silently mean "examined
nothing".

This is [`algorithmatize-checks`](../workflow/algorithmatize-checks.md)'s
partner: that rule says build the instrument instead of eyeballing, and
this one says an instrument that cannot fail loudly is not yet an
instrument.

Note what actually triggered that "code point value ... too large" error,
because it is the reason the pattern is worth keeping as the example.
U+2014 is an unremarkable code point, well inside Unicode's range; the
rejection came from the **locale**.
With `LANG`/`LC_ALL` unset, PCRE runs in non-UTF mode, where any `\x{...}`
above `0xFF` is "too large" -- so the identical command fails bare and
succeeds under `LC_ALL=C.UTF-8`:

```bash
$ grep -P '[\x{2014}]' file                 # LANG unset
grep: character code point value in \x{} or \o{} is too large   # rc=2
$ LC_ALL=C.UTF-8 grep -P '[\x{2014}]' file
file:1:<the matching line>                                      # rc=0
```

That environment-dependence is what makes the `||` so dangerous rather
than merely sloppy: the check can pass on a laptop and silently examine
nothing in a container, with no output difference to notice.
So set the locale explicitly in any check that matches non-ASCII, and
still make the error path distinguishable from the clean one.

**Setting it explicitly is not the same as setting it on the right command,
and a pipeline is where those two come apart.**
An environment-variable prefix binds to the single command it precedes, so in
a pipeline it never reaches the later stages:

```bash
LC_ALL=C.UTF-8 git diff | grep -P '[\x{2014}]'   # prefix reaches git diff only
```

`grep` still runs in the ambient locale, so this fails exactly as the bare
form does while *looking* like the fixed version above.
The correct string is present, one process to the left of where it was needed.

Put the assignment on the command that reads it, or export it around the whole
pipeline:

```bash
git diff | LC_ALL=C.UTF-8 grep -P '[\x{2014}]'                # on the consumer
( export LC_ALL=C.UTF-8; git diff | grep -P '[\x{2014}]' )    # whole subshell
```

This variant is more survivable than the `|| true` above, and worth recording
for the opposite reason: `grep` exits 2 with "code point value ... too large",
so it fails **loudly** and the fix is a one-token move.
The hazard is that a reader who has already internalized "set the locale" sees
the variable on the line and stops looking.

- **Do:** put the locale assignment on the process that interprets the
  pattern, or export it around the whole pipeline.
- **Don't:** treat the presence of `LC_ALL=` somewhere in a command line as
  evidence that the matching stage received it.

### The same vacuous zero has a second cause: an empty input

Everything above assumes the check **broke** --- a rejected pattern, a wrong
locale, a swallowed non-zero exit --- and prints its failure as a pass.
The identical zero arrives with nothing broken at all, when a perfectly sound
command runs over an input that is empty.
A diff-scoped scan run before anything is committed compares committed history
against itself, so it examines no lines and truthfully reports no findings.

That defeats the guards this section prescribes, which is why it needs
separating rather than folding in.
No command failed, so an `rc=$?` test passes; the exit status is 1, which here
is the *clean* answer rather than an error; and the locale was never involved.
A reader who has internalized "make the error path distinguishable" is still
caught, because there was no error path to distinguish.

The denominator is the one remedy above that covers both causes, and this is
the case that argues for it hardest: `0 findings in 0 lines examined` is
unmistakable where a bare `0` is not.
Report what a check *examined*, not only what it *found*.

Deciding **when** to run such a check, as opposed to how to write it, belongs
to [`skill-checklists`](../workflow/skill-checklists.md)'s pause-point rule ---
a correctly written check still reports on the wrong thing if it runs at the
wrong moment.

- **Do:** print the examined count beside the finding count, so an empty input
  is visible rather than silent.
- **Don't:** treat an exit-status or locale guard as covering this --- both
  pass cleanly while the check examines nothing.

### The narration can be the unfalsifiable part, while the check is fine

Everything above concerns a command whose *output* cannot distinguish pass
from fail.
The adjacent failure leaves the command correct and puts the ambiguity in the
sentence printed next to it:

```bash
git log --oneline HEAD..origin/main -- <files>
echo "(empty above = none of them touch my files)"
```

The `git log` is right, and the `echo` runs unconditionally.
So when the range is non-empty, the output says one thing and the label
beneath it asserts the opposite --- and the label is the part a reader
believes, because it is phrased as a conclusion while the lines above it are
raw data.

It is worse than an ambiguous check for two reasons.
It reads as *more* rigorous, since narrating what a command proves is what a
careful person does.
And it survives review of the command: someone checking your `git log`
invocation finds nothing wrong with it, because nothing is.

The fix is to compute the label or omit it.
Anything that makes the sentence depend on the data will do:

```bash
out="$(git log --oneline HEAD..origin/main -- <files>)"
[ -z "$out" ] && echo "none touch my files" || printf '%s\n' "$out"
```

This is the [`deterministic-tools`](deterministic-tools.md) rule applied to a
status line, which that fragment names outright as a thing to stop composing
by hand.

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
A parallel sweep swallows every worker's, and the aggregate then reads as a
finding rather than as an error: not "the check broke" but "nothing was
found", across the whole corpus at once.

The shape is a scan whose per-item worker writes only on a hit, run under
`xargs`/`parallel` with stderr discarded:

```bash
xargs -P 12 -n 1 ./scan.sh < "$OUT/repos.txt" >/dev/null 2>&1   # every failure discarded
```

Any per-worker failure now produces an empty results file, which is exactly
what a clean corpus produces.
The specific trap worth naming: a `chmod +x` that lived in an earlier command
which never ran --- denied by a permission prompt, edited out, lost to a
failed compound --- leaves the script non-executable, so all N invocations
die with "permission denied" into `/dev/null`.
Nothing in the output distinguishes that from success.

Count what you examined, not only what you found.
A worker that appends its own identifier unconditionally, before any
early-exit path, turns the ambiguity into arithmetic:

```bash
echo "$item" >> "$OUT/scanned.txt"     # first line of the worker, not the last
...
echo "scanned $(wc -l < "$OUT/scanned.txt") of $(wc -l < "$OUT/repos.txt")"
```

`scanned 0 of 947` is unmistakable; a bare "no hits" is not.
Place that line **before** the worker's early exits, or the items that failed
their first lookup go unrecorded and the shortfall silently shrinks --- which
converts this instrument back into the thing it was built to replace.

Distrust a sweep that reports zero, and distrust one whose scanned count you
never printed.
(2026-07-28: a 947-repo scan reported `scanned: 0`, caught only because the
count was printed; the `chmod +x` had been in a command the permission
classifier denied minutes earlier.
A later run of the fixed script reported 910 of 947, which is how the
rate-limit truncation above was found.)

#### A zero-shaped summary can be sound, and the scope line is what decides it

The rule above has a false-positive direction, and it lands on exactly the
tools that already comply with it.

A well-behaved instrument prints its scope --- which is the remedy this
section asks for --- but it prints it on a **different line** from its
summary, and the summary can be phrased so that it reads as the vacuous-scan
signature:

```
Linting: 439 files
Summary: 0 issues in 0 files
```

That is `markdownlint-cli2`.
`0 files` counts **files with issues**, not files scanned.
So the line that looks like "this examined nothing" is the line reporting
that nothing was wrong, and the evidence against that reading is sitting two
lines up.

The failure this produces is not a swallowed error but a needless
retraction: you report your own check as having verified nothing, withdraw a
true claim, and spend a round re-running an instrument that was fine.
That is the same cost the fragment warns about elsewhere --- a check nobody
trusts stops being run --- arriving from over-application rather than from
under-application.

So read for the scope line before concluding a zero is vacuous, and quote it
alongside the result rather than quoting the summary alone.
Where a tool prints no scope at all, the original rule stands unchanged: that
zero is not yet evidence.

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
A watcher is one you deliberately stop reading, which is its whole purpose ---
so its output channel is a *notification*, and the absence of one is
indistinguishable from the thing still running.

That inverts the usual economics of this bug.
A silent `|| echo "none"` at least sits in front of you.
A watcher's silence is what you asked for: quiet means nothing to report,
which is exactly what a healthy long-running job looks like.
So the failure is not merely unnoticed, it is *reassuring*.

The shape is a poll loop that emits only on the happy path:

```sh
for i in $(seq 1 25); do
  pending=$(...)
  if [ "$pending" = 0 ]; then echo "settled: ..."; break; fi
  sleep 60
done                       # <- falls out silently when it never settles
```

Every iteration finds work still pending, the loop exhausts its range, and the
script exits 0 having printed nothing.
Nothing failed, so nothing is reported, and the watcher's silence gets read as
"not finished yet" indefinitely.

Two fixes, and take both.
Give the loop a **terminal else**, so exhausting the range says so out loud and
names what it was waiting for.
And emit on **every** state you would act on, not just the one you hope for ---
a failed check, a blocking verdict, a job that vanished.

Note the second is the same instruction the Monitor tool's own documentation
gives ("if this process crashed right now, would my filter emit anything?"),
which is worth saying because reading that guidance is evidently not sufficient
to follow it.

- **Do:** end a bounded poll loop with an explicit timeout message naming the
  condition that never arrived.
- **Do:** widen the filter to every terminal state, then confirm by asking what
  the watcher would have printed had the job died at the start.
- **Don't:** read a watcher's quiet as evidence the work is still in flight.
- **Don't:** treat "I read the tool's guidance about coverage" as having applied
  it.

A second route to the same silence, with a different cause, is recorded in
[`memories/claude-code.md`](../../memories/claude-code.md): a pipe stage that
consumes the content a later stage was meant to read (`grep -q`, `-l`, or `-c`
upstream of something that greps stdout) starves the loop of anything to emit.
That one is about what reaches the filter and this one is about what the filter
is written to match, so the fixes differ --- but the symptom is identical, and
in both cases the discrepancy surfaced only by running the underlying query by
hand.

### The pattern itself is the other half, and it fails without erroring

Everything above is about a check that *cannot report* its own failure.
The sibling case is a check that runs perfectly, exits 0, and answers the
wrong question, because the pattern was looser or narrower than intended.
There is no error to swallow here and no exit status to inspect -- the
instrument works, and its verdict is simply false.

Two directions, both seen in one session:

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

The fix is not "be careful with regexes".
It is to **test the instrument against a known positive before trusting a
negative**.
A grep that should find something, run against a case you know contains it,
either matches or exposes the assumption that was wrong.
Where the thing being matched has structure -- a YAML key, a Markdown
heading -- anchor to that structure (`^[[:space:]]*(- )?uses:`) rather than
to a substring that happens to appear inside it, and search the source text
rather than a re-serialization of it, since dumping and reformatting can
move or wrap the very string being looked for.

State the scope with the result, too.
"No matches" and "no matches **under these three paths**" are different
claims, and the second is the honest one when the search was scoped.

- **Do:** run the pattern against a case you know contains the thing, before
  reporting that it contains nothing.
- **Do:** anchor to the structure being matched, and state the paths the
  search actually covered alongside its result.
- **Don't:** treat a zero-hit result as a fact about the corpus when the
  pattern has never been seen to match anything.
- **Don't:** grep a re-serialization -- a YAML dump, a rendered page -- for a
  string whose formatting that step may have changed.

Distinct from
[`grep-is-not-coverage`](../workflow/grep-is-not-coverage.md), and the pair is
worth keeping apart.
That fragment governs a **sound** command whose conclusion overreaches --- the
null result is a real fact about the pattern, and only the step to "the corpus
lacks this" is wrong.
Here the command itself is unsound, so the result is not a fact about anything.

**A third direction, and the one the remedy above passes: the pattern is right
about the data and admits the stream's own metadata, because that metadata is
written in the data's alphabet.**
Both directions above are a pattern matching the wrong *things*.
Here it matches the right things and one more, because the stream it reads is
not pure data.
A unified diff marks added content with `+` and names the file that content
came from with `+++ b/<path>`, so a filter for added lines cannot separate the
two by prefix:

```bash
git diff <base> <head> -- <path> | grep '^+' | sed 's/^+//'   # leaks the header
```

`sed` then strips one character rather than the whole marker, so the header
does not leave --- it is *disguised*, arriving in the output as `++ b/<path>`.
The deletion side does the same, leaving `-- a/<path>`.
Neither `--no-prefix` nor `-U0` helps: the first shortens the header to
`+++ <path>` and the second changes only the context, so both still open with
the marker character.

Note that this defeats the remedy this section prescribes.
Testing the instrument against a known positive **passes**, since the pattern
does match the content, correctly, and merely takes one line more.
Anchoring to structure does not help either, because here the header *is* the
structure.
What separates them is length rather than prefix, so exclude the delimiter by
its full length:

```bash
git diff <base> <head> -- <path> | grep '^+' | grep -v '^+++' | sed 's/^+//'
```

**What the pattern feeds decides how much this costs.**
A too-loose pattern in a **detector** surfaces as a phantom finding, which is
the first direction above: somebody investigates it and finds nothing.
The same looseness in an **extractor** turns the extra match into *content*,
and nothing investigates content.
So one flaw is self-reporting in the first role and silent in the second.

**The tighter guard over-corrects, and what it loses is invisible to the check
that would look for it.**
`grep '^+[^+]'` drops the header in a single pass, and
[`memories/git.md`](../../memories/git.md)'s stash-supersession bullet uses it
correctly --- there each added line is grepped for in `main`, so a blank line is
noise.
Reuse it on prose and it silently drops every added **blank** line, collapsing
paragraph boundaries.
Measured on git 2.50.1 against a two-paragraph addition: `^+[^+]` returned the
two lines of text and not the blank between them, while
`grep '^+' | grep -v '^+++'` returned all three.

Carry that pair together, because a whitespace-normalizing word-level
comparison --- the content-preservation check
[`semantic-line-breaks`](../writing/semantic-line-breaks.md) prescribes for
exactly this kind of move --- cannot see either failure.
The leaked header is an **addition**, and a check phrased as "did anything go
missing" is one-sided.
The dropped blank line contributes no words, and the check normalizes
whitespace away before comparing.
So the two candidate guards fail in precisely the two directions that check is
blind in.

- **Do:** exclude a delimiter by its full length (`grep -v '^+++'`) when it is
  prefix-compatible with the data's own marker.
- **Do:** ask what a pattern *feeds* --- a detector's extra match gets
  investigated, an extractor's becomes content.
- **Do:** compare a moved block in both directions, so an added line is as
  visible as a dropped one.
- **Don't:** read a passing known-positive test as clearing this; the pattern
  matches the content correctly and takes one line more.
- **Don't:** reuse `^+[^+]` on prose --- it eats added blank lines, and the
  whitespace-normalized check will not report that either.

The class is wider than diffs.
Any delimiter carried **in band**, in the data's own alphabet, has this
property: a fence marker inside fenced content, a heredoc terminator the
heredoc's own text can contain, a comment character that also opens a
directive.
[`batch-merge-and-resolve`](../workflow/batch-merge-and-resolve.md) records the
mirror failure, where `grep -c '^<<<<<<<'` returns 0 on a real conflict because
`merge-tree` indents every line by the diff's own leading character.
There the collision hides a true positive; here it manufactures a false one.
Read that one before concluding a concept is absent; read this one before
trusting any grep as an instrument.

### The third one arrives in the repair, and only on the empty input

The two cases above are checks written wrong the first time.
This is the one written wrong the second time, inside the fix for the first,
which is the version that ships.

The standard repair for a check that read the wrong thing is to split its one
question across two commands: record a baseline, do the work, read again, and
compare the two.
That is sound while both reads encode their answers the same way.
It stops being sound when one read supplies a chosen sentinel and the other
supplies a default, because the two then agree on every input carrying data
and differ on the input carrying none.
Emptiness is usually the case such a check exists to catch, so it reports
success on the one input it was built for.

Two things keep this out of view.
A repair carries credibility the original had just lost, since it is visibly a
response to a real finding, so it reads as the hardened version rather than as
new and untested code.
And a check exercised against real data never meets the empty case at all, so
re-running it on more real data cannot surface the gap.

The control is therefore a question of **which input**, not of which stage.
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) already
requires a negative control to enter at the instrument's real input.
For a comparison check whose inputs can be empty, that control is an input
holding nothing, and it costs one run.

That qualifier is doing real work, so decide it rather than assuming it.
One question settles it: can any input this check will actually meet make
either side's read return nothing?
A PR that has never been reviewed is such an input, so the check below owes
the control.
A comparison over two fields a schema guarantees to be present is not, and
demanding an empty run there asks for a case nobody can construct.
Answer the question explicitly, because "absence cannot happen here" is itself
a claim about the input domain, and it is the claim that excuses the control.

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
Making that failure invisible takes two things at once: the loser's error is
suppressed, and the winner's output does not name itself.

```bash
ls "$A" 2>/dev/null || ls "$B" 2>/dev/null || { echo "searching..."; find ...; }
```

The first is this fragment's own opening principle rather than anything new ---
no silent failures, the same discarded stderr the fan-out section above marks
`>/dev/null 2>&1   # every failure discarded` --- and dropping that one token
makes the loser announce itself by name.
Be exact about which half is lost, though, because the "In code" bullets ban a
different mechanism: `|| true` and a bare `except:` swallow the **failure**,
while `2>/dev/null` suppresses only the **message** and leaves the exit status
intact, which is precisely what `||` then reads.
The second is the increment, and it is a property of the commands rather than
of `||`: `ls DIR/` prints the directory's **contents**, so its stdout never
names the directory it read.
`ls -d DIR/` prints the path, and `command -v` prints the resolved binary, so a
chain over those forms identifies its own winner and leaves only the
suppression to fix.

What makes the misreading survive a re-read is that the output is genuine
evidence.
Two files really were listed; nothing in the transcript says they were listed
from the path you had in mind, so looking again confirms the reading you
already had rather than exposing it.

Drop the suppression first.
Where the resolved value is what you actually want, take it from a variable and
fail loudly when nothing matched, per the canonical form at
[`use-mcp-servers`](../workflow/use-mcp-servers.md):

```bash
for p in "$A" "$B"; do
  [ -e "$p" ] && { GODOT="$p"; break; }
done
if [ -z "${GODOT:-}" ]; then
  echo "no Godot binary at $A or $B" >&2      # loud, and it names both candidates
  exit 1
fi
printf 'resolved: %s\n' "$GODOT"
```

A `||` chain is also one of the errexit-suppression contexts in
[`errexit-is-not-uniform`](../coding/errexit-is-not-uniform.md), so one chain
can be silent in two independent ways at once.
That fragment governs the exit status such a chain suppresses; this one governs
an output that does not name its source.

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
This one asks what asking it **cost**, which is a property the answer never
reports: the check can return the right result and still have destroyed the
state you were checking against.

The shape is a diagnostic whose question is plainly read-only --- "does this
also fail on `main`?", "what did this file look like before?" --- answered by a
command that puts the working tree into the state being asked about.
Chained into one call it reads as a single act of looking:

```sh
# looks like one lookup; is a lookup plus two mutations
<run the failing check>; git stash -q; git checkout -q origin/main -- hooks/
```

Nothing in that line is wrong as a command.
`git stash` and `git checkout <ref> -- <path>` both do exactly what they say,
which is why the composition passes a read-through: the scrutiny lands on
whether each piece is correct rather than on whether a diagnostic should be
doing this at all.
The result is that uncommitted work is stashed and a whole directory in the
working tree **and index** is replaced by another ref's version, discarding the
branch's own committed changes from the tree, in service of a question that
only ever needed to read.

Materialize the other ref somewhere else instead.
Extraction to a scratch directory touches neither the tree nor the index:

```sh
scratch="$(mktemp -d)"
git archive <ref> <path> | tar -x -C "$scratch"   # nothing in the tree moves
```

A throwaway `git worktree add --detach <ref>` does the same for a whole tree,
and both leave `git status` unchanged --- which is the property to check after
running a diagnostic, not before.

The generalizable test is a sentence, not a command list: **say what the
question needs to read, and confirm the answer writes nothing outside a scratch
path.** A diagnostic that fails that test is not a diagnostic, whatever it
returns.

- **Do:** materialize another ref with `git archive | tar -x` into a scratch
  directory, or a detached throwaway worktree, when a question spans refs.
- **Do:** run `git status` after a diagnostic you composed on the spot, and
  treat any change as the diagnostic having done something it was not asked to.
- **Don't:** chain a mutating command onto a read-only question because the
  mutation is the shortest route to the answer.
- **Don't:** let each command being individually correct stand in for the
  composition being appropriate --- that check passes on every instance of
  this.

## In a guard you ship: partial is worse than absent

Everything above concerns a check whose failure is invisible **at runtime**,
because its failure path prints what its pass path prints.
A guard applied to only some of the paths that need it fails one level earlier,
and in the opposite medium: it is perfectly loud wherever it runs, and it
simply does not run on the paths that were left out.
What goes wrong is what a **reader** infers from the source.

An absent guard is discoverable.
Someone reading the file sees an unguarded write and asks about it.
A guard present once answers that question before it is asked --- the reader
finds the guard, recognizes the hazard as handled, and stops looking for the
two places it is not.
So the partial version does not merely leave the bug in place; it spends the
one signal that would have surfaced it, which is the same trade
[`fact-check-code-logic`](../coding/fact-check-code-logic.md) prices for a
vacuous assertion: "worse than no test, because it reads as coverage".

The shape is a hazard handled at one site out of several, where the sites are
siblings rather than a sequence: three emitters, four entry points, both
directions of a conversion.
It is the author-side, no-reviewer sibling of
[`address-every-comment`](../workflow/address-every-comment.md)'s rule that a
reviewer-flagged pattern must be fixed everywhere it recurs.
That rule needs a finding to convert into N fixes; here nobody flagged
anything, so nothing fires, and the cost is a shipped bug rather than an extra
review round.

Enumerate the sites before writing the guard, and make the enumeration
mechanical where it can be --- grep for the operation being guarded, not for
the guard, since grepping for the guard finds the site you already fixed.
Where the sites genuinely differ, say in a comment why an unguarded one is
safe, so the next reader inherits a decision instead of an apparent oversight.

- **Do:** list every site that performs the guarded operation, then check the
  guard against that list rather than against the site that prompted it.
- **Do:** grep for the operation, not for the guard.
- **Don't:** ship a guard on one of several sibling paths without a comment
  saying why the others need none.
- **Don't:** read a guard's presence in a file as evidence the file is guarded
  --- that inference is precisely what a partial guard supplies for free.

**A review lifecycle can play this failure out one path at a time, which is
the same defect stretched across rounds rather than shipped at once.**
When the sibling paths are parallel *discharge* conditions rather than
emitters, a guard added to one and not the others does not read as a bug ---
it reads as a fix --- so each review round finds the one path still unguarded,
the next round adds it, and the loop repeats until every sibling is covered.
The remedy is unchanged: enumerate the sibling paths and guard them together in
the change that guards the first, rather than letting review drive the
enumeration one round at a time.

**When the siblings are members of one pattern rather than sites in one file,
the remedy above has nothing to grep.**
Both cases so far spread the guard across *locations* --- three emitters, four
discharge paths --- which is what makes "grep for the operation being guarded"
work: the operation occurs somewhere the guard does not.
An alternation, an allowlist, or a set of accepted tokens has no such spread.
The member you fixed and the member you missed are in the same expression, on
the same screen, so there is no second site to find and the enumeration step
silently does not fire.
The unit to enumerate is the pattern's own members, and nothing about editing a
pattern prompts you to list them.

What makes it worse than an ordinary miss is that the fix usually arrives with
a **comment explaining itself**, and the comment records a *removal*: which
members were taken out, and why they were unsafe.
That is the inverse of the guidance above, which asks you to say why an
unguarded site is safe.
A note saying why something is safe invites the reader to check the claim.
A note saying why something was *removed* reads as the hazard having been
surveyed and settled, so it discharges the reader's suspicion about the members
still in the pattern --- the same "spends the one signal that would have
surfaced it" trade this section already prices, arriving through the artifact
written to demonstrate diligence.

The remedy is cheap because that comment has already done the hard part.
A stated reason for removing some members is a **predicate**, so run it over
the members that remain.
The reason is the strongest evidence available that the survivors are defective,
since it was derived from the same hazard they sit in.
It just has to be applied rather than read.
That turns a prose rationale into a check, per
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md), and it is the
step to take at the moment you write the comment, not at review.

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

**Widen that last bullet's trigger: any sentence naming a hazard is a
predicate, and the first code it applies to is the code directly beneath it.**
The block above needs a *removal* note --- members taken out of an alternation,
with a stated reason that can be re-run over the survivors.
The commoner artifact states the hazard and removes nothing, so there is no
survivor set to sweep and that remedy has nothing to operate on.
It still supplies a predicate.
A comment reading "an over-broad pattern here would let X through" names the
exact test the lines under it have to pass, and applying it to them costs one
reading.

The reason it goes unapplied is that describing the hazard has already
discharged the feeling of having handled it.
Naming a risk in prose is the part that *feels* like diligence, and it is
finished the moment the sentence is, so nothing prompts the second step.
That is why same-author and same-commit are the diagnostic rather than a
mitigating detail: this is not a stale note somebody else left behind, and the
comment and the violation are minutes apart in one edit.

It is worse than silence, on the terms this section already prices.
An unguarded pattern with no comment invites the next reader to ask.
The same pattern under a sentence explaining why over-broad matching would be
dangerous reads as surveyed, so the comment spends the one signal that would
have surfaced it, and keeps spending it for every later reader.

Distinguish this from a comment that asserts a property of the code beneath it
("only matches at the start of a command"), which
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) already covers
under treating a comment claiming the matcher's scope as an untested assertion.
There the comment and the code agree and are both wrong, so only a test
separates them.
Here they disagree, and a reading separates them.

- **Do:** re-read the lines under a hazard comment against the hazard it names,
  in the edit that writes the comment.
- **Don't:** count naming a risk as handling it --- the sentence is a
  specification, and nothing has yet met it.

**When the hazard is a phrase a qualifier can reverse, enumerate the qualifier
classes by which SIDE of the phrase they sit on.**
The "members of one pattern" block above enumerates along the alternation's own
members, and a reader who applies it correctly still ships this bug, because
these classes are not members of the pattern at all --- they are positions
relative to it.

A negation sits **before** ("this is not ready for merge").
A condition sits **after** ("ready for merge once the findings are fixed").
"Add a negation guard" is the natural reading of the problem, it produces a
lookbehind, and a lookbehind closes only the first of those.
The after-side form is the likelier one in practice, since it is how a reviewer
signs off on work that is nearly done, so the guard that feels complete misses
the commoner case.

Enumerate the positions before writing the guard: a prefix that negates, a
suffix that conditions, and a mid-phrase qualifier that narrows scope.
Then write a case per side and confirm each fails without its own half of the
guard, per the mutation discipline in
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md).

- **Do:** list the qualifier classes by position --- before, after, within ---
  and cover each with its own case.
- **Do:** treat the after-side conditional as the likely form when the guarded
  phrase is an approval, not as the exotic one.
- **Don't:** read "add a negation guard" as the whole requirement; negation is
  one side, and it is the side that comes to mind first.
- **Don't:** reach for the members-of-one-pattern rule here --- enumerating an
  alternation's members leaves both sides of every member unguarded.

**One level up from a partial guard: editing state that two consumers share
regresses the consumer you were not looking at.**
Every case above spreads a guard across *sites* --- emitters, discharge paths,
members of one pattern.
This is the inverse: a single object read by two consumers, where the edit that
satisfies one silently breaks the other, because the two place *conflicting*
demands on it and you only had one in view.
An allowlist, a shared regex fragment, a config map, a lookup table are all this
shape.

It is nastier than the "members of one pattern" case above, because there the
fix is still to edit the members correctly.
Here no single edit to the shared object can satisfy both consumers at once, so
each round of editing it trades one regression for another --- and that is the
tell: a fix that *moves* the failure to the other consumer rather than removing
it.
When that happens, stop editing the shared object and **un-share it**: give the
second consumer its own separately-scoped copy or pass, applied after the first
consumer has run.

The discipline that avoids the whole loop is the enumerate-the-sites rule one
level up: before editing shared state, enumerate every consumer that reads it
and check the edit against each, not only against the one whose bug you are
fixing.

- **Do:** enumerate every consumer of a shared object before editing it, and
  check the edit against each.
- **Do:** un-share the state --- a separately-scoped second pass --- when two
  consumers place conflicting demands on it, rather than re-editing it round
  after round.
- **Don't:** read a fix as done when it moves the failure to a different
  consumer of the same object; that is the shared-state loop, not progress.
- **Don't:** assume an edit that fixes one reader of shared state leaves the
  others intact.

(Morrison-Lab/gha#425, 2026-08-05: one abbreviation list (`_ABBREV_RE`) fed two
regex branches --- a lowercase-sentence branch and an uppercase one.
Dropping `No` from the list fixed the lowercase branch and un-protected `No.` on
the uppercase branch; registering every lowercase form then fixed the lowercase
branch and leaked protection onto the uppercase one.
Each edit traded one regression for the other until the fix became
architectural: a second, separately-scoped pass applied only after the first
branch ran.)

## A guard's discharge fires on positive success, not the absence of failure

The section above is about a guard that runs on too few sites.
This is about a guard that runs everywhere and **stops guarding too early** ---
it clears its own obligation on evidence that only *looks* like the hazard was
resolved.
A guard exists to catch a condition, so every state change that *releases* the
guard --- a discharge, a clear, a "this one is handled now" --- is an assertion
that the condition is gone.
An assertion of absence must rest on **positive evidence the thing succeeded**,
never on the mere non-appearance of a failure.

The failure mode is a **silent discharge**: the guard forgets a live obligation
and reports clean, which is strictly worse than an over-warn, because an
over-warn is visible and annoying while a silent discharge is invisible and
defeats the guard's whole purpose.
The two directions are not symmetric, and treating them as symmetric is the
root error:

- **Over-warn** (guard fires when it needn't) is the **safe** direction.
- **Silent discharge** (guard clears when it shouldn't) is the **dangerous**
  one.

So when a reviewer or your own instinct pushes to *reduce* an over-warn ---
"stop nagging on this case" --- weigh it as a request to move toward the
dangerous direction, and prefer keeping the over-warn (and rebutting the
request with this reasoning) over trading the fail-safe away.
Reducing a safe-direction over-block is exactly how a fail-safe guard grows a
dangerous hole.

**Once the safe direction is known, it is a property to build the guard around,
not only one to defend it in.**
The paragraph above is defensive: it says which way *not* to be pushed.
The constructive form is to ask which way an **unforeseen** case falls, because
that is decided by the guard's shape rather than by its contents.

A guard that **enumerates what may act** fails open on anything the enumeration
misses, and the miss is silent, so each new construct is a fresh fail-open found
only by whoever goes looking.
A guard that instead **removes what cannot act** and then treats everything
remaining as live fails the other way: an unforeseen construct is caught by the
default rather than missed by the list, so the cost of being wrong is a loud
over-block that a documented override clears.
Same information, inverted, and the residual risk moves from the dangerous
direction to the safe one.

Do not read this as licence to drop the narrow pass.
"What cannot act" is a real claim about the world and it can be false --- a
quoted span is inert until something defers execution of it, so an evaluator
that runs its own quoted operand makes the exclusion wrong.
Keep the narrow, raw-text pass and add the inverted one as strictly additive,
so the two disagree only where the exclusion is unsound.

- **Do:** ask which direction an unforeseen case falls, and prefer the guard
  shape that sends it to the safe one.
- **Do:** pair an inverted pass with the original narrow pass, additively,
  rather than replacing it.
- **Don't:** keep extending an enumeration whose every gap is a silent
  fail-open, when inverting it makes the same gaps loud.
- **Don't:** treat an exclusion set as self-evidently safe --- "this text cannot
  execute" is a claim, and a deferred evaluator falsifies it.

The worked instance is
[`address-every-comment`](../workflow/address-every-comment.cases.md)'s
"Deriving the class is necessary and not sufficient", where two rounds of
extending an enumeration of shell constructs kept producing fresh silent
fail-opens until the guard was inverted to blank inert quoted spans and treat
every remaining position as live.

(Distinct from
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md)'s "A reminder
guard's discharge condition is a second matcher": that governs a discharge
*condition* too broad to begin with, this governs a correct condition *firing*
on evidence it cannot attribute.)

### A combined result cannot attribute a per-step outcome

The commonest way a discharge fires on false evidence: the guard reads a
**combined result** --- a shell `tool_result` covering several chained
commands, a batched response, any blob spanning more than one action --- and
attributes success to the specific step it cares about.
It cannot.
A whole-call exit status (`is_error`, `$?`) belongs to the **last** command in a
`;`-sequence or a `pipefail`-less pipeline, not to an earlier one.
So a failed request followed by a trailing `echo` reads as success, and --- in
any chaining form, `&&` included --- a successful request followed by a failing
command reads as failure.
(An `&&`-chain short-circuits, so it alone surfaces a failed *leading* request;
the trailing-failure ambiguity holds regardless.)
Attributing a per-step outcome from an opaque combined blob is fundamentally
ambiguous; no amount of body-scanning recovers it.

The invariant that survives this: **defer every releasing state change to a
result you can attribute, and fail toward keeping the guard armed when you
cannot.**
Concretely:

- A releasing change (discharge / clear) fires only on positive success of a
  step whose result is unambiguously its own --- the **last** simple command
  in a call, or a single **atomic** structured tool.
  Key it by the action's own `tool_use_id`, not by position.
- A step chained **ahead** of anything else is ambiguous, so it **never**
  releases the guard --- a deliberate over-warn, per the safe/dangerous
  asymmetry above.
- Any state change made at the *tool_use* moment, before its result is known,
  can be wrong if that result fails --- so route it through a pending map and
  apply it only on the non-failed result.
  This holds for **every** releasing path, not just the obvious one: an
  obligation-drop, a draft-clear, and a discharge are all the same class, and
  fixing one while leaving its siblings is the "partial guard" failure of the
  section above.

The discipline that makes each such fix trustworthy is **mutation-testing the
invariant term by term**: revert each clause of the condition independently and
confirm exactly its own regression case fails.
Name the condition for what it computes --- *failure*, not release --- so the
guard reads `if not req_failed: discharge`, with
`req_failed = (not last) or err or failure_pattern(body)`.
Its three terms say the request is unattributable, errored, or matched a failure
pattern; a test suite that does not fail when any one is dropped is not yet
testing the invariant.
Labelling that same right-hand side `released` inverts it --- the guard would
then discharge in exactly the three cases it must not, which is the
silent-discharge bug this section exists to prevent.

- **Do:** release a guard only on positive, attributable success; treat every
  releasing path as one class and gate them all on a confirmed result.
- **Do:** mutation-test each term of a release condition, and keep the
  over-warn on any genuinely ambiguous input.
- **Don't:** infer a per-step outcome from a combined result's whole-call
  status.
- **Don't:** trade a safe-direction over-warn for fewer nags --- that is the
  move that grows a silent-discharge hole.

## In review

Flag error handling that hides failure — swallowed exceptions, silent
defaults substituted on failure, unbounded retries, `continue-on-error`
without a downstream outcome check — the same weight as any other
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
