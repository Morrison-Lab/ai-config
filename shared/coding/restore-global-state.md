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

## The better option is not to need it

Restoring state is the fallback, not the goal.
A function that takes what it needs as arguments and returns what it
computed has no state to restore, is testable without a fixture, and is
safe to call concurrently.
Reach for this rule when a boundary genuinely requires the mutation --- a
file written, a directory entered, a plotting device configured --- not as
a licence to mutate freely and tidy up after.

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
