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

## In review

Flag error handling that hides failure — swallowed exceptions, silent
defaults substituted on failure, unbounded retries, `continue-on-error`
without a downstream outcome check — the same weight as any other
standing review check.
Flag a handler that identifies a condition by matching its message text,
too, and ask for a class.
Ask for the explicit form: an early validation, a loud error, or a
documented, observable fallback.

This serves the Reliable goal in the
[principles catalog](README.md): a loud failure is easier to catch than
a silent one.
