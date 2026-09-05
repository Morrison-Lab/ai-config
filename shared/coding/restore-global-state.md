When a function has to change global state, restore it on the way out ---
on every exit path, including the ones that throw.
State a function changes and does not restore is a side effect its caller
never asked for and cannot see, which is what
[purity](../principles/README.md) exists to bound.

The usual targets: the working directory, `options()`, environment
variables, graphics parameters (`par()`), the RNG seed, open connections,
locale, and search-path attachments.

## Register the cleanup next to the change

`on.exit()` runs its expression however the function exits --- normal
return, error, or interrupt:

```r
with_dir <- function(dir, code) {
  old <- setwd(dir)
  on.exit(setwd(old), add = TRUE)

  force(code)
}
```

The value of the pattern is adjacency.
The cleanup sits on the line after the change rather than at the bottom of
the function, so the two cannot drift apart as the body grows, and no
early `return()` can skip it.

## Always pass `add = TRUE`

[Advanced R, "Exit handlers"](https://adv-r.hadley.nz/functions.html#on-exit)
puts this in a sidebar:

> Always set `add = TRUE` when using `on.exit()`.
> If you don't, each call to `on.exit()` will overwrite the previous exit
> handler.
> Even when only registering a single handler, it's good practice to set
> `add = TRUE` so that you won't get any unpleasant surprises if you later
> add more exit handlers.

The default silently discards earlier handlers, so the first cleanup
registered is the one lost:

```r
f <- function() {
  on.exit(cat("first\n"))              # silently dropped
  on.exit(cat("second\n"))
}
f()
#> second
```

Write `add = TRUE` even on a lone handler.
The bug it prevents is not introduced when the handler is written --- it is
introduced months later by whoever adds the second one, and it leaves no
trace at the point of the change.

## Prefer `withr` to hand-rolling the pair

[withr](https://withr.r-lib.org/) already packages the save-change-restore
pattern for every common target, so reach for it before writing the
`on.exit()` by hand --- the same
[`prefer-packaged-functions`](prefer-packaged-functions.md) call as anywhere
else:

```r
withr::local_dir(dir)                 # for the rest of this function
withr::local_options(digits = 3)
withr::local_seed(42)

withr::with_dir(dir, { ... })         # for one block
```

`local_*()` restores when the calling function exits; `with_*()` restores
when its block does.
Both handle the error path, and `local_seed()` restores the RNG *stream*
rather than merely re-seeding it, which a hand-rolled version usually gets
wrong.

In tests, `local_*()` in a `testthat` test restores at the end of that test,
which is what keeps one test's `options()` change out of the next.

## The cost lands on someone else's tests, in file-name order

The rule above is easy to read as tidiness, because nothing fails in the
function that does the mutating.
The bill arrives in a test suite, and it arrives in a form that points at
the wrong file.

`testthat` runs test files in **alphabetical order**, in one R session.
So a package function that switches the RNG kind and does not restore it ---
`rngtools::RNGseq()` moves the session to `L'Ecuyer-CMRG` --- leaves every
*later* file running under a different generator than it was written against.
Add a new test file, and whether it breaks four unrelated snapshot tests
depends on **what you named it**: sort before the existing files and they now
run downstream of your mutation, sort after and nothing moves.

That is what makes it expensive to attribute.
The failures are in files your diff never touched, they are snapshot diffs
rather than errors, and the one variable that actually explains them ---
filename collation --- is invisible in the diff and appears in no error
message.
Renaming your file makes them disappear, which reads as evidence the failures
were flaky rather than as the diagnosis it actually is.

Two fixes, and they are not alternatives:

- **In the package**, restore the kind, per the rule above.
  This is the real fix, and it is the caller's protection as much as the test
  suite's.
- **In the test**, `withr::local_preserve_seed()` around a call that mutates
  RNG state you do not control.
  It restores the **kind**, not just the stream, which is the part `set.seed()`
  in a `setup.R` cannot give you.
  Verified on withr 3.0.2: `.Random.seed[1]` encodes the kind, and it read
  `10403` both before and after a block that switched to `L'Ecuyer-CMRG`
  inside the guard.

- **Do:** suspect a global-state mutation when adding a test file breaks tests
  in files it does not touch, and check whether the new file's name sorts
  before them.
- **Do:** file the missing restore against the package, rather than only
  guarding the test --- a test guard protects the suite and leaves every other
  caller exposed.
- **Don't:** read "renaming my file fixed it" as flakiness; that is the
  ordering dependency reporting itself.
- **Don't:** reach for `set.seed()` in a setup file to stabilize this --- it
  resets the stream while leaving the changed generator in place.

(`UCD-SERG/serocalculator` #634, 2026-08: `sim_pop_data_multi()` switches the
session to `L'Ecuyer-CMRG` via `rngtools::RNGseq()` and never restores it; a
new alphabetically-earlier test file broke four unrelated snapshot tests.)

## The fix for the kind has a NULL case, and it is silent

The rule above says restore the kind, not just the stream.
The fix that lands still has one gap left, because `rngtools::RNGseed()` ---
the getter a save/restore pair naturally reaches for --- returns `NULL` when
no `.Random.seed` exists yet in the session.
A fresh session, or one where nothing has drawn a random number, is exactly
that state, so a save/restore pair built around `old <- rngtools::RNGseed()`
followed by `rngtools::RNGseed(old)` captures nothing on a fresh session and
restores nothing on exit.

The restore side fails in a specific and non-obvious way.
`rngtools::RNGseed(NULL)` does not error and does not leave the kind alone
--- it **removes** `.Random.seed` from the session, which un-sets the seed
without touching `RNGkind()`.
So a function that changed the generator kind, then tried to restore a NULL
baseline by calling `RNGseed(NULL)`, exits with `.Random.seed` gone but the
changed kind still in effect --- the exact leak the section above describes,
reintroduced by the fix meant to close it.

The remedy is to capture the kind separately, since reading `RNGkind()` does
not materialize a seed the way drawing a random number does:

```r
old_kind <- RNGkind()
old_seed <- rngtools::RNGseed()   # may be NULL
# ... code that may change the kind or the seed ...
if (is.null(old_seed)) {
  do.call(RNGkind, as.list(old_kind))
  rngtools::RNGseed(NULL)
} else {
  rngtools::RNGseed(old_seed)
}
```

`withr::local_preserve_seed()`, named in the "Two fixes" list above, does not
have this gap --- it is the reason to prefer it over a hand-rolled pair even
when the pair already restores the kind, since the NULL case is exactly the
kind of branch a hand-rolled version omits.

- **Do:** treat `rngtools::RNGseed()` returning `NULL` as a real state to
  restore, not as "nothing to do".
- **Do:** capture `RNGkind()` separately from the seed, and restore it
  explicitly when the saved seed is `NULL`.
- **Don't:** assume `RNGseed(old)` round-trips the kind when `old` can be
  `NULL` --- `RNGseed(NULL)` removes `.Random.seed` and leaves the kind
  wherever it currently is.
- **Don't:** treat a save/restore pair that does not error on a fresh
  session as evidence it restored the kind --- absence of an error is not
  presence of the restored state (see
  [`verify-the-right-artifact`](../workflow/verify-the-right-artifact.md)'s
  sixth shape).

(`UCD-SERG/serocalculator` #668, 2026-09-01, fixing #634 above: the first
save/restore pair passed a pre-push check because the no-`.Random.seed` case
did not error, which was read as coverage.
It did not restore the kind.
Caught by an adversarial reviewer, not by the check.)

## The better option is not to need it

Restoring state is the fallback, not the goal.
A function that takes what it needs as arguments and returns what it
computed has no state to restore, is testable without a fixture, and is
safe to call concurrently.
Reach for this rule when a boundary genuinely requires the mutation --- a
file written, a directory entered, a plotting device configured --- not as
a license to mutate freely and tidy up after.

## In review

Flag these with the same weight as the other coding rules:

- `setwd()`, `options()`, `par()`, `Sys.setenv()`, or `set.seed()` in a
  function body with no matching restore.
- `on.exit()` without `add = TRUE`, including where only one handler exists
  today.
- A hand-rolled save-and-restore pair where a `withr::local_*()` call would
  do.
- Cleanup written at the bottom of a function rather than registered beside
  the change, where an early `return()` or an error would skip it.
- `set.seed()` in package code or a test, where `withr::local_seed()` would
  leave the caller's RNG stream intact.
- A call that changes the RNG **kind** (`RNGkind()`, `rngtools::RNGseq()`,
  anything setting up parallel streams) with no restore --- the
  file-ordering section above is why this one is worth flagging even when the
  package's own tests are green.
- A hand-rolled `RNGseed()` save/restore pair that never branches on the
  saved value being `NULL` --- the fix-for-the-kind section above is where
  that branch matters, and a passing pre-push check that only confirms the
  no-seed case does not error is not evidence the branch is correct.
