When a `for` loop really is the right construct --- see
[`least-flexible-tool`](least-flexible-tool.md) for when it is not ---
three checks apply.
Each is mechanical, greppable, and catches a bug that does not announce
itself.

## Preallocate the output; never grow it in the loop

Allocate the container at full size before the loop, with `vector()`:

```r
out <- vector("list", length(means))
for (i in seq_along(means)) {
  out[[i]] <- rnorm(10, means[[i]])
}
```

The alternative --- starting empty and appending --- is quadratic, because
each append reallocates and copies everything already there.
[Advanced R, "Avoiding
copies"](https://adv-r.hadley.nz/perf-improve.html#avoid-copies):

> Whenever you use `c()`, `append()`, `cbind()`, `rbind()`, or `paste()` to
> create a bigger object, R must first allocate space for the new object and
> then copy the old object to its new home.
> If you're repeating this many times, like in a for loop, this can be quite
> expensive.

This is the one item here that is a performance bug rather than a
correctness bug, and it is the rare performance finding worth raising
without a profile, because the cost grows with input size rather than
sitting at a fixed percentage.
Its signature in a profile is time spent in `<GC>`; see
[`measure-performance`](../../skills/measure-performance/SKILL.md) for
reading that, and note the direction of travel --- the profile tells you
*which* loop, this rule tells you not to write it in the first place.

## `seq_along(x)`, never `1:length(x)`

`:` counts down as readily as up, so on an empty input `1:length(x)`
iterates twice over indices that do not exist:

```r
x <- c()
1:length(x)      # [1] 1 0   <- two iterations
seq_along(x)     # integer(0) <- none
```

[Advanced R, "Common
pitfalls"](https://adv-r.hadley.nz/control-flow.html#common-pitfalls) notes
that this "will fail in unhelpful ways" --- the error surfaces inside the
body, pointing at the subscript rather than at the sequence that produced
it.
Empty input is a normal state, not an edge case: a filter that matched
nothing, a group with no rows, a first run against an empty table.

`seq_len(n)` is the equivalent when iterating a count rather than an object.

## Index with `[[i]]` when iterating an S3 vector

`for` strips attributes from the loop variable, so a `Date`, `factor`, or
`difftime` degrades to its underlying base type mid-loop:

```r
xs <- as.Date(c("2020-01-01", "2010-01-01"))
for (x in xs) print(x)              # 18262, 14610 --- bare doubles
for (i in seq_along(xs)) print(xs[[i]])   # the Dates
```

This one is the most dangerous of the three, because nothing fails.
The loop runs, the values are numerically right, and the class is simply
gone --- so formatting, comparison, and dispatch all quietly change
behaviour.

## In review

Flag these with the same weight as the other coding rules:

- A container built by `c()`, `append()`, `rbind()`, `cbind()`, or `paste()`
  inside a loop, where preallocation plus indexed assignment would do.
- `1:length(x)` or `1:nrow(df)` in a loop header, an `if`, or a slice ---
  anywhere the object can legitimately be empty.
- `for (x in xs)` where `xs` carries a class, and the body relies on that
  class.
- A loop that accumulates into a data frame row by row, which is the
  preallocation finding and the type-stability finding at once.
