Memoise a function --- cache its results, keyed by its arguments --- when caching would actually pay off.
Three conditions have to hold together, not just one of them:

- **Pure**: the output depends only on the inputs.
- **Expensive**: one call costs enough to notice, next to the cost of hashing its arguments.
- **Called repeatedly with repeating arguments**: otherwise the cache only grows and never hits.

Use [`memoise::memoise()`](https://memoise.r-lib.org/) rather than hand-rolling a cache environment.
It is an r-lib package, MIT-licensed, importing only `rlang` and `cachem`, and it already handles key hashing, eviction, and swappable cache backends.
A hand-written `cache <- new.env()` plus lookup-or-compute logic is a [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md) finding, like any other hand-rolled equivalent of a packaged function.

```r
fib <- memoise::memoise(function(n) {
  if (n < 2) return(n)
  fib(n - 2) + fib(n - 1)
})
```

## Purity is a precondition, not a nice-to-have

Advanced R, 2nd ed., [11.2.2 "Caching computations with `memoise::memoise()`"](https://adv-r.hadley.nz/function-operators.html#memoise):

> Think carefully before memoising a function.
> If the function is not **pure**, i.e. the output does not depend only on the input, you will get misleading and confusing results.

The same section reports the failure from the inside.
Wickham memoised `available.packages()` in devtools, because it is slow: it downloads a large file from CRAN.
The available packages do not change often, so the staleness only mattered in R processes that had been running for days --- and because it surfaced only there, the bug was "very painful to find."

That is what makes an impure memoisation worse than a missing one.
It does not error; it returns a stale value that looks right, late, in the one setting nobody reproduces.
Treat it as a [`fail-fast`](../principles/fail-fast.md) violation rather than a performance nit.
Anything that reads the clock, the RNG, the filesystem, the network, or a global is not a candidate until that dependency becomes an argument.

## The tradeoff is memory for speed

A memoised function is faster and larger, and the cache is not free just because it is invisible.
`memoise()`'s default is `cachem::cache_mem(max_size = 1024 * 1024^2)`, an in-memory cache that evicts least-recently-used entries once it exceeds 1 GB.
That bound is a backstop, not a plan: when the argument space is unbounded (user-supplied strings, data frames) or the return values are large, set `max_size` deliberately, and `max_age` when a result should expire on its own.

```r
# expire cached results after an hour, and cap the cache at 64 MB
mem_fetch <- memoise::memoise(
  fetch,
  cache = cachem::cache_mem(max_size = 64 * 1024^2, max_age = 3600)
)
```

## R gotchas, from `?memoise`

- **In a package, memoise in `.onLoad()`**, not at the top level, so the memoised copy is created when the package is loaded rather than when it is built.
- **In a script you re-`source()`**, guard the assignment with `if (!is.memoised(f))`; otherwise each `source()` installs a fresh cache.
- **`forget(f)` clears a cache; `drop_cache(f)(x)` drops the single entry for `x`.**
  Call `forget()` between tests, or a result cached by one test leaks into the next.
- **`cachem::cache_disk()`** when the cache should outlive the R session.

## Across sessions, one expression at a time: `xfun::cache_exec()`

`{memoise}` caches within one process.
`{targets}` caches a whole pipeline.
Between them sits the case where a single expensive expression --- a simulation, a fit, a download --- should survive an R session ending, without adopting a pipeline framework.
[`xfun::cache_exec()`](https://cran.r-project.org/package=xfun) is the packaged answer, so reach for it before hand-rolling a `saveRDS()`/`file.exists()` pair, per [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md).

Prefer it over its older sibling `xfun::cache_rds()`, which now says so itself:

> Please consider using `cache_exec()` instead, which is more flexible and intelligent.

(Read off `cache_rds`'s own help page, xfun 0.57.
`cache_exec()` exists from xfun 0.44.)

The signature is `cache_exec(expr, path = "cache/", id = NULL, ...)`.

**`path` needs a trailing slash, or nothing is cached and nothing says so.**
Without one it is read as a file path rather than a directory, and the call silently executes every time.
This is the [`fail-fast`](../principles/fail-fast.md) shape where the failure path and the pass path produce identical output --- the expression still returns the right value, so only a cache that never fills betrays it.
Measured on xfun 0.57: `path = "nosl"` left 0 files after two identical calls, `path = "wsl/"` left 1 and returned an identical object the second time.

What makes it worth the switch is that **it hashes the values of the expression's free variables** (via `xfun::find_globals()`), so inside a function wrapper the wrapper's own arguments become the cache key with no hand-built hash:

```r
sim_cached <- function(n, seed) {
  xfun::cache_exec(simulate(n, seed), path = "cache/", id = "sim")
}
```

Measured: repeating a call hits the cache, and changing an argument invalidates it.

Three refinements from `?cache_exec`:

- **Set `hash = "<varname>"` explicitly when the expression references a function object**, or the closure is hashed too --- and its environment may be an entire package namespace.
- **`extra =`** folds further inputs into the key (a package version, a data file's mtime).
- **`keep = FALSE`** forces re-execution and re-saves, which is how you refresh a cache without deleting it.

The layout is `<path>/<id>/<md5>.rds`, one file per id by default, so **comparing the file list across a call is a reliable cache-hit signal** --- an instrument rather than a guess, per [`algorithmatize-checks`](../workflow/algorithmatize-checks.md).

The purity precondition above is not relaxed here, and it bites harder: a disk cache outlives the session, so an impure expression's stale value can be served days later, in a fresh process, with nothing in scope to explain it.

## When not to memoise

- The function is cheap: hashing the arguments can cost more than calling it (KISS).
- It is called once, or its arguments never repeat (YAGNI).
- The caching wanted is pipeline-scale --- skip steps whose inputs have not changed, across sessions.
  That is [`{targets}`](https://docs.ropensci.org/targets/)' job, not `{memoise}`'s, which caches one function's results within one process or one cache directory.
  For a single expression that merely needs to outlive the session, `xfun::cache_exec()` above is lighter than either.

## In review

Flag these with the same weight as the other coding rules:

- A hand-rolled cache environment where `memoise::memoise()` would do.
- A **memoised impure function** --- the serious one, since it yields wrong answers rather than slow ones.
- A package that memoises at the top level instead of in `.onLoad()`.
- An unbounded-by-construction cache with no `max_size` or `max_age`.
- An `xfun::cache_exec()` call whose `path` lacks a trailing slash --- it caches nothing, silently.
- A hand-rolled `saveRDS()`/`file.exists()` pair where `cache_exec()` would do, or a hand-built hash of arguments it would derive on its own.

A missed memoisation is a finding too, but a mild one: raise it when the function is demonstrably hot, not on suspicion.
The [`measure-performance`](../../skills/measure-performance/SKILL.md) skill is what demonstrates it, and its `mem_alloc` column prices the memory half of the trade.
Premature memoisation is premature optimization, and it costs memory and a purity obligation to boot.
