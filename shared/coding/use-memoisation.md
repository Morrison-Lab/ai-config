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

## When not to memoise

- The function is cheap: hashing the arguments can cost more than calling it (KISS).
- It is called once, or its arguments never repeat (YAGNI).
- The caching wanted is pipeline-scale --- skip steps whose inputs have not changed, across sessions.
  That is [`{targets}`](https://docs.ropensci.org/targets/)' job, not `{memoise}`'s, which caches one function's results within one process or one cache directory.

## In review

Flag these with the same weight as the other coding rules:

- A hand-rolled cache environment where `memoise::memoise()` would do.
- A **memoised impure function** --- the serious one, since it yields wrong answers rather than slow ones.
- A package that memoises at the top level instead of in `.onLoad()`.
- An unbounded-by-construction cache with no `max_size` or `max_age`.

A missed memoisation is a finding too, but a mild one: raise it when the function is demonstrably hot, not on suspicion.
The [`measure-performance`](../../skills/measure-performance/SKILL.md) skill is what demonstrates it, and its `mem_alloc` column prices the memory half of the trade.
Premature memoisation is premature optimization, and it costs memory and a purity obligation to boot.
