When writing code, **don't nest function calls**, and avoid nested function definitions where feasible:

- Don't pass one function call's result straight into another call, as in `f(g(h(x)))`.
  Give each intermediate result a name, or chain the steps with a pipe (`|>` / `%>%` in R);
  pipes are fine.
  Naming each step makes the data flow read top-to-bottom and leaves intermediate values inspectable in a debugger (Ezra Morrison, 2026-10-09: "a policy of no nested function calls (pipes are fine)").
- Prefer standalone, top-level function definitions over functions defined
  inside other functions. Nested definitions hide reusable logic, complicate
  unit testing, and obscure scope.
  Define a function inside another only for a specific efficiency or
  simplicity reason, and say which in a comment beside it
  (Ezra Morrison, 2026-09-25: "I don't like function definitions inside
  other functions unless there's a specific efficiency or simplicity reason").
  - **Do:** define helpers at top level, one per file, and pass them what
    they need as arguments.
  - **Don't:** define a helper inside its caller merely because only that
    caller uses it today.

The nested-call rule is a policy, not a default: a nested call is a review finding.
It covers a call whose result is a value handed to the outer call.
It does not cover an argument the outer function captures and interprets itself: tidyselect helpers (`all_of()`, `any_of()`, `starts_with()`), data-masked expressions inside data-masking verbs such as `mutate()` / `filter()` / `summarise()`, `aes()` mappings, and formulas.
Those are part of the outer call's own syntax, and pulling them out would break or obscure it.

The nested-definition rule is a readability/maintainability default, not an absolute rule --- keep the nesting when flattening it would be more convoluted (a trivial one-argument wrapper, or a closure that genuinely needs the enclosing scope).

## Name `if()` conditions before testing them

Pre-compute every `if()` and `while()` condition: assign it to a named logical variable first, then test that name, so the condition inside the parentheses is always a bare name (or a literal, as in `while (TRUE)`).
This holds even for a condition with no nested call, such as `is.na(strat)`, because the name is what documents the test:

```r
# Preferred --- the name states what the test means
n_plots <- trace_strat_list |> lengths() |> sum()
single_plot <- n_plots == 1
if (single_plot) {

# Avoid --- the inline expression hides a misplaced parenthesis
if (sum(lengths(trace_strat_list) == 1)) {
```

For a `while()` loop, compute the named condition before the loop and recompute it at the end of the loop body.

The inline form above was a real bug, fixed in [UCD-SERG/serodynamics#326](https://github.com/UCD-SERG/serodynamics/pull/326).
`sum(lengths(x) == 1)` counts the strata that hold exactly one plot, so the single-plot branch ran whenever any stratum held one plot, not only when the whole result was one plot.
Naming the condition makes the author say what it should mean (`single_plot`), which makes a misplaced parenthesis visible in review, and the named value can be inspected in a debugger before the branch runs (Ezra Morrison, 2026-10-09: "a policy that if conditions have to be pre-calculated, so that mistakes like the one fixed in [serodynamics#326] are harder to make").

## Prefer more, simpler steps over fewer, denser ones

The named-intermediate rule above operates within one expression.
The same trade runs one level up, across a pipeline: given a choice, do less
per step and take more steps.

Advanced R makes the observation while comparing a purrr pipeline against
the base-R and `for`-loop versions of the same task, in
[Purrr style](https://adv-r.hadley.nz/functionals.html#purrr-style):

> It's interesting to note that as you move from purrr to base apply
> functions to for loops you tend to do more and more in each iteration.
> In purrr we iterate 3 times (`map()`, `map()`, `map_dbl()`), with apply
> functions we iterate twice (`lapply()`, `vapply()`), and with a for loop
> we iterate once.
> I prefer more, but simpler, steps because I think it makes the code easier
> to understand and later modify.

The gain is the same one named intermediates buy: each step is separately
readable, separately testable, and separately replaceable, and a change
lands in one step rather than in the middle of a compound one.
Cost only shows up when a step is traversed enough times for the extra
passes to matter --- which is a claim to settle with
[`measure-performance`](../../skills/measure-performance/SKILL.md), not by
assumption.

## Lambdas in map()/apply-family calls

The nested-definition rule applies to `purrr::map*()` / `pmap*()` /
`lapply()`-family call sites too: don't wrap a named function in an anonymous
function (lambda) just to fix constant arguments. Pass the mapped elements
positionally and the constants through the mapping function's `...`:

```r
# Preferred --- hr/power match schoenfeld_events()'s leading parameters
# positionally; the constant fractions ride along via map2's `...`
purrr::map2_dbl(
  df$hr, df$power, schoenfeld_events,
  p1 = frac_op, p2 = frac_nonop
)

# Avoid --- a lambda that only fixes constant arguments
purrr::map2_dbl(df$hr, df$power, function(h, p) {
  schoenfeld_events(hr = h, power = p, p1 = frac_op, p2 = frac_nonop)
})
```

purrr's own documentation (since 1.0; see the "Extra arguments" note in
[`?map`](https://purrr.tidyverse.org/reference/map.html)) mildly recommends
the opposite --- shorthand lambdas over `...`-passing. This preference
deliberately overrides that: when the mapped elements line up with the
callee's leading parameters, use `...` and skip the wrapper. Don't relitigate
this in review rounds; cite this fragment instead.

When a wrapper genuinely is necessary --- the mapped element isn't the
callee's leading argument, is used more than once in the body, or the body is
a real expression rather than a single call --- define a **named wrapper
function in its own file** (see
[`one-function-per-file`](one-function-per-file.md)) rather than a lambda.
The one exception is a demonstrated performance reason to define the wrapper
nested inside the calling function (e.g. it must close over a large
enclosing-scope object that would otherwise be passed repeatedly); that is
the same closure escape hatch as the nested-definition rule above.

Apply this when writing code and when reviewing it: a map-site lambda that
only fixes constants is a review finding, the same weight as the other
nesting findings. (Encoded from review feedback on `ucdavis/rampp#137`,
where two power-table builders wrapped `schoenfeld_events()` and
`total_n_for_power_unequal()` in lambdas that `...`-passing replaced.)
