Fail fast; no silent failures.
Detect bad state as early as possible and stop with a clear error,
rather than proceeding and letting the failure surface later — or
never — as silently wrong output.

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

(ai-config#754, 2026-07-28: a pre-push scan for banned punctuation used
`grep -P '[\x{2014}...]' || echo "none"`.
PCRE rejected the pattern with "character code point value in \x{} or \o{}
is too large", and the `||` branch printed `none`, which read as a pass.
A rewrite in Python found a real em-dash on an added line.)

Note what actually triggered that error, because it is the reason the
pattern is worth keeping as the example.
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

(ai-config#871, 2026-07-30: a pre-push punctuation scan written as
`LC_ALL=C.UTF-8 git diff -U0 origin/main...HEAD | grep -P '[...]'` aborted with
rc=2.
The fix adopted was rewriting the scan in Python, which also reports how many
added lines it examined --- so a zero-hit result is distinguishable from a run
that examined nothing, per the fan-out section below.)

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

(2026-08-03, one `ucdavis/bcs` session: three instances in about an hour, each
printed beneath output that contradicted it.
`(empty = my files are untouched by those commits)` beneath three filenames,
which was briefly believed and produced a wrong statement before a corrected
query caught it; `(no output above = no auto-review rule)` beneath the
`copilot_code_review` rule it denied; and `(empty above means none)` beneath
the commit it said was absent.
The two later ones were caught immediately, which is the point --- the pattern
recurred after being noticed twice, because nothing about writing the label
feels like making a claim.)

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

(Morrison-Lab/ai-config#974, 2026-07-31: a `markdownlint-cli2` result already
published in a PR body as `0 issues in 0 files` was about to be re-reported as
a check that examined nothing.
Re-running it printed `Linting: 439 files` above the same summary.)

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

(2026-08-01, a `UCD-SERG/ucd-serg.github.io` session: two successive monitors
watching a PR's checks exited silently after 25 minutes, both written to print
only when zero checks were pending.
The first hid a red `validate`; the second hid nothing but was equally
uninformative.
Both were caught by querying the PR directly rather than by anything the
watchers did, and the second was armed *after* writing a status note about the
first --- so knowing the failure mode did not prevent repeating it within the
hour.)

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
Read that one before concluding a concept is absent; read this one before
trusting any grep as an instrument.

(Morrison-Lab/gha#328/#329, 2026-07-31: the unanchored `uses: [a-z]` was
published in an issue and a merged PR body as *the* verification command
for a security invariant, so the phantom it produced was reported as a
regression before the pattern was re-read.)

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

(Morrison-Lab/ai-config#1056, 2026-08-02: review round 1 found that a
verification step read the newest bot comment *after* dispatching a run, so a
pre-existing comment satisfied it and a broken credential read as working.
The repair split that read in two, taking a baseline with
`... | last | .id // "none"` and the later read with
`... | last | "\(.id) \(.createdAt)"`.
On jq 1.7.1 an empty selection yields `none` from the first and `null null`
from the second, so on any PR carrying no prior bot comment the two differ and
the check again reported success whatever the run did.
Round 2 caught it, and the landed fix is a single filter naming all four
outcomes rather than a patched sentinel.
The worked commands live in
[`refresh-claude-token`](../../skills/refresh-claude-token/SKILL.md), which
that PR merged on 2026-08-03.
This entry is the general rule.)

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

(ai-config#950/#951, 2026-07-30/31: `scripts/semantic-line-breaks.py` has three
emitters --- its own docstring lists "prose paragraphs, bullet continuation
text, and blockquote prose" --- and a draft of the scope fix guarded only the
blockquote one, leaving the two that do the bulk of the reflowing unscoped.
The script therefore still rewrote whole files while its source visibly
contained the fix; the unguarded behaviour changed 342 of `CLAUDE.md`'s 1163
lines.
Caught before it was committed, so the landed fix at `39b98c7b` already calls
`_in_scope` at all three sites --- which is why git history shows no trace of
the partial state, and why the enumeration has to happen while the guard is
being written rather than afterwards.)

**A review lifecycle can play this failure out one path at a time, which is
the same defect stretched across rounds rather than shipped at once.**
When the sibling paths are parallel *discharge* conditions rather than
emitters, a guard added to one and not the others does not read as a bug ---
it reads as a fix --- so each review round finds the one path still unguarded,
the next round adds it, and the loop repeats until every sibling is covered.
The remedy is unchanged: enumerate the sibling paths and guard them together in
the change that guards the first, rather than letting review drive the
enumeration one round at a time.
(Morrison-Lab/ai-config#1042, 2026-08-03: `hooks/no-unreviewed-pr.py` has four
parallel open/draft/request/self discharge-and-identity paths, and the
fail-safe guard --- structural identity, "last simple command", same-PR
scoping --- was applied to them one at a time across the review rather than all
at once, and each subsequent round surfaced the one path still unguarded: the
shell-command parser underlying them, then the `open` path (`open_ident`), then
the `self` discharge.
The per-path *discharge* mechanics of that same PR are in the section below.)

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

(Morrison-Lab/ai-config#1042, 2026-08-02/03: the `no-unreviewed-pr.py` Stop
hook took ~12 review rounds, six of them closing the same dangerous class ---
a discharge, an obligation-drop, and a draft-clear each fired on unattributable
or premature evidence.
Its discharge path churned across rounds 8-10, and round 9 is the clean instance
of the trap this section warns about: a fix that *reduced* a safe-direction nag
introduced a non-4xx-failure silent discharge, which round 10 caught and fixed.
They converged only when the ad-hoc patches were replaced by the single
`req_failed = (not last) or err or RX_REQ_FAILED(body)` invariant (discharge iff
`not req_failed`) plus result-gated `pending`/`pending_clear` maps, every term
mutation-checked.)

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
