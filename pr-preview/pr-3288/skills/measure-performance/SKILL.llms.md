# measure-performance – profile first, then microbenchmark (perf, benchmark)

Find out what is actually slow before changing anything, then prove the change helped. The method is [Advanced R, ch. 23 “Measuring performance”](https://adv-r.hadley.nz/perf-measure.html): [profvis](https://rstudio.github.io/profvis/) to locate the bottleneck, [bench](https://bench.r-lib.org/) to compare alternatives for it.

**Why this exists.** Intuition about what is slow is unreliable, even for experienced programmers, so the chapter opens with Knuth’s warning that time spent worrying about the speed of noncritical code has a strong negative effect on debugging and maintenance. Two failure modes follow from skipping measurement. Optimizing the wrong line makes code harder to read and no faster. Winning a microbenchmark and reporting it as a speedup makes a claim the real workload does not support: a 2x win on an operation that takes 2 microseconds of a 30-second job is not a win. This skill is [`algorithmatize-checks`](../../shared/workflow/algorithmatize-checks.md) applied to performance claims, and it operationalizes the “performance tuning beyond that needs a demonstrated hot spot, not speculation” clause of the Efficient goal in [the principles catalog](../../shared/principles/README.md).

## When this fires

- “measure performance”, “perf”, “benchmark”, “benchmark this”, “microbenchmark”, “profile this”, “run profvis”, “use `bench::mark()`”
- “why is this slow”, “what is the bottleneck”, “find the hot spot”
- “which version is faster”, “is this actually faster”, “time these two approaches”, “how much did that speed things up”
- Reviewing or writing a diff that asserts a speedup without numbers, or that proposes a micro-optimization with no profile behind it.

## Procedure

### 1. Check the measurement is worth taking

Answer these before installing anything:

- **Is something actually slow?** Name the workload and roughly how long it takes now. A script nobody waits on does not need a profile.
- **Is it slow on a realistic input?** A profile of a toy input measures the toy.
- **What would “fast enough” be?** Without a target there is no way to stop, and the loop runs until the code is unreadable.

If the answer to the first question is “no”, say so and stop. That is a complete, correct result for this skill, not a failure to deliver.

### 2. Fix the input and a correctness baseline

Put the code under measurement in its own file and `source()` it, so the profiler can link its samples back to source lines.

Record what the current code returns on the realistic input. Every alternative gets checked against it later:

``` r
source("<script>.R")
baseline <- <call-under-test>
saveRDS(baseline, "baseline.rds")
```

Speed is only interesting among alternatives that agree. `bench::mark()` enforces that in step 5, but a saved baseline also catches an alternative that changes results in a way the benchmark never evaluates.

### 3. Profile: locate the bottleneck, do not guess

R’s profiler is a sampling profiler: it stops execution every few milliseconds and records the call stack. That keeps overhead low at the cost of being stochastic, so successive profiles differ slightly. The variability mostly affects functions that take very little time, which are the ones you care least about.

The interactive route, which links the profile back to source lines:

``` r
source("<script>.R")
p <- profvis::profvis(<call-under-test>)
```

If the call finishes before any sample lands, profvis aborts with `No parsing data available. Maybe your function was too fast?`. That is the profiler telling you the input is not realistic enough to profile, so go back to step 1 rather than shrinking the sampling interval.

In a headless session, save the widget and open it later:

``` r
htmlwidgets::saveWidget(p, "profile.html", selfcontained = TRUE)
```

`selfcontained = TRUE` needs pandoc, and htmlwidgets discovers it through `{rmarkdown}`: as of htmlwidgets 1.6.0 that path “now uses the `{rmarkdown}` package to discover and call pandoc” ([NEWS](https://github.com/ramnathv/htmlwidgets/blob/master/NEWS.md)). `rmarkdown::pandoc_available()` is therefore the gate that matches what htmlwidgets itself consults, rather than a proxy for it. Without pandoc the call aborts rather than degrading quietly, with `Saving a widget with selfcontained = TRUE requires pandoc.` (verified on htmlwidgets 1.6.4). Drop the argument to `FALSE` in that case, which writes a sidecar dependencies directory next to the HTML instead.

When there is no way to view HTML at all, take the text summary instead:

``` r
source("<script>.R")
tmp <- tempfile()
Rprof(tmp, interval = 0.01, memory.profiling = TRUE)
<call-under-test>
Rprof(NULL)
summaryRprof(tmp, memory = "both")$by.self
```

`by.self` ranks functions by time spent in the function itself rather than in its callees, which is what points at the line to change.

Use `profvis::pause()`, never `Sys.sleep()`, when building a synthetic example to reason about: as far as R can tell, `Sys.sleep()` uses no computing time, so it never appears in the profile.

### 4. Read the profile

The flame graph shows the full call stack, so a function called from two places is visible as two stacks rather than one aggregate. Watch for two things in particular.

**A function high in the self-time ranking because it is called often, not because it is slow.** The fix is the call count, not the function.

**`<GC>`.** This entry is the garbage collector, not your code. A lot of time in `<GC>` almost always means many short-lived objects, and the usual cause is copy-on-modify in a loop that grows an object one element at a time:

``` r
x <- integer()
for (i in 1:1e4) x <- c(x, i)     # every iteration copies all of x
```

Confirm it from the memory column: a line that allocates and frees large amounts on every pass is the one to fix, and the fix is preallocation, not a faster arithmetic operator.

### 5. Microbenchmark only the bottleneck

`bench::mark()` uses a high-precision timer, so it can separate operations that take microseconds. Benchmark the one expression the profile implicated, with the realistic input from step 2, not the whole pipeline:

``` r
x <- runif(100)
lb <- bench::mark(
  sqrt(x),
  x^0.5
)
lb[c("expression", "min", "median", "itr/sec", "n_gc", "mem_alloc")]
```

By default each expression runs at least once (`min_iterations = 1`) and then as many times as fit in half a second (`min_time = 0.5`).

`bench::mark()` checks that every expression returns the same value and aborts if they differ:

``` text
Error : Each result must equal the first result:
`sum(x)` does not equal `mean(x)`
```

That error is usually the benchmark catching a real bug in the alternative. Set `check = FALSE` only when the expressions are *meant* to return different things, and say in the report why.

Use `bench::press()` when the answer depends on input size, so the comparison runs across a grid of sizes rather than at one arbitrary point.

### 6. Interpret the numbers

**Read `min` and `median`, not the mean.** The timing distribution is heavily right-skewed, and often multimodal because the machine is doing other things. `min` is the best achievable time and `median` the typical one; `plot(lb)` shows the distribution on a log x-axis. The returned tibble carries `expression`, `min`, `median`, `itr/sec`, `mem_alloc`, `gc/sec`, `n_itr`, `n_gc`, `total_time`, and the list-columns `result`, `memory`, `time`, and `gc` (verified against bench 1.1.4).

**Report absolute units, not just a ratio.** “2.1x faster” is not actionable on its own. Calibrate with how many calls it takes to reach one second:

| Per call | Calls per second of run time |
|----------|------------------------------|
| 1 ms     | one thousand                 |
| 1 us     | one million                  |
| 1 ns     | one billion                  |

So an expression at 1.4 us that the real workload calls a few hundred times cannot account for a slow job, however large its ratio, and swapping it is churn.

**Check `mem_alloc` and `n_gc` alongside the times.** When step 4 flagged `<GC>`, these are the columns that show whether the alternative actually allocates less.

### 7. Re-profile at real scale

A microbenchmark measures a snippet in isolation. Real code is dominated by higher-order effects, so a microbenchmark win is a hypothesis about the real workload, not a result about it. Apply the change, re-run step 3 on the full realistic workload, and compare against the original wall-clock time from step 1.

If the end-to-end time did not move, revert the change. A faster expression that leaves the job the same length has bought nothing and cost readability.

### 8. Report

State, in this order:

1.  The workload, its input, and its before/after wall-clock time.
2.  The bottleneck the profile identified, and how much of total time it held.
3.  The `bench::mark()` table for the alternatives, with units.
4.  Whether the end-to-end re-profile confirmed the win.
5.  Which limitations below apply, if any.

Attach the numbers to the PR when the change ships, so the next reviewer does not have to re-derive them.

## Limitations to state in the report

The profiler cannot see everything, and each gap silently misattributes time:

- **Compiled code.** Profiling shows that R called into C/C++ but not what happened inside. Say so rather than reporting the C call as a leaf.
- **Anonymous functions.** Heavy functional-programming code is hard to attribute call by call. Name the functions before profiling.
- **Lazy evaluation.** An argument is evaluated where it is first used, so in `j(i())` the profile attributes `i()`’s cost to `j()`. Use `force()` to pull evaluation forward when the attribution matters.

## Outside R

The tools are R-specific; the order is not. Profile before optimizing, microbenchmark only the bottleneck the profile found, read medians rather than means, and confirm the win end to end. In Python the stdlib equivalents of the two measurement steps are `cProfile` and `timeit`.

## Relationship to other skills

- [`algorithmatize-checks`](../../shared/workflow/algorithmatize-checks.md) – the general rule this skill instruments: a performance claim is decidable by measurement, so never settle it by reasoning.
- [`dont-reinvent-wheel`](../../shared/principles/dont-reinvent-wheel.md) and [`prefer-packaged-functions`](../../shared/coding/prefer-packaged-functions.md) – check for an existing, usually C-backed, packaged implementation before hand-optimizing. A found package beats a won benchmark.
- [`use-memoisation`](../../shared/coding/use-memoisation.md) – one of the fixes this skill’s profile can point at, and the fragment that says to raise a missed memoisation only when the function is “demonstrably hot”. Step 3 is what demonstrates it, and step 6’s `mem_alloc` column is where the memory half of the trade shows up.
- [`reprexes`](../../skills/reprexes/SKILL.llms.md) – reduces a slow workload to the minimal self-contained snippet step 5 benchmarks.
- [`test`](../../skills/test/SKILL.llms.md) and [`r-pkg-check`](../../skills/r-pkg-check/SKILL.llms.md) – the correctness gates an optimization still has to pass. `bench::mark()`’s equality check compares the benchmarked expressions to each other, not the package to its test suite.
- [`simplify`](../../skills/simplify/SKILL.llms.md) and [`tidy`](../../skills/tidy/SKILL.llms.md) – an optimization step 7 could not confirm is complexity debt; hand the cleanup to these.
- [`ardi`](../../skills/ardi/SKILL.llms.md) – the loop that carries step 8’s numbers into a review round, whether the finding is yours or a reviewer’s.

## Anti-patterns

- Optimizing a line because it looks slow, with no profile.
- Profiling a toy input, then acting on the result as if it described the real workload.
- Microbenchmarking the whole pipeline instead of the bottleneck the profile named.
- Comparing means, or reporting a ratio with no absolute units behind it.
- Passing `check = FALSE` to silence a genuine difference in results, rather than because the expressions are meant to differ.
- Shipping a microbenchmark win without the end-to-end re-profile of step 7.
- Reading `<GC>` as slow code rather than as an allocation problem.
- Using `Sys.sleep()` in a synthetic profiling example, where it is invisible to the profiler.
- Asserting a speedup in a PR body with no numbers attached.

Back to top
