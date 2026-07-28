Prefer calls whose output type you can predict from the call itself, and
declare the type when the language lets you.
A type-unstable call is a silent-failure hazard: it does not error on the
input that breaks it, it returns a plausible object of the wrong shape, and
the failure surfaces somewhere else entirely.

That makes this [`fail-fast`](../principles/fail-fast.md) applied to
**shape** rather than to errors.
The usual fail-fast finding is a swallowed error; this one is a call that
never raised an error at all, and still returned something wrong.

## Never `sapply()` outside interactive use

From [Advanced R, "Producing atomic
vectors"](https://adv-r.hadley.nz/functionals.html#map-atomic):

> I recommend that you avoid `sapply()` because it tries to simplify the
> result, so it can return a list, a vector, or a matrix.
> This makes it difficult to program with, and it should be avoided in
> non-interactive settings.
> `vapply()` is safer because it allows you to provide a template,
> `FUN.VALUE`, that describes the output shape.

The failure is input-dependent, which is what makes it survive testing.
The same `sapply()` call returns three different classes depending only on
the data it is handed:

```r
sapply(list(1, 2), function(i) i)      |> class()   # "numeric"
sapply(list(),     function(i) i)      |> class()   # "list"
sapply(list(1, 2), function(i) c(i, i))|> class()   # "matrix" "array"
```

A test fixture usually exercises exactly one of those three, so the other
two reach production unexamined.
The empty-input case is the one that bites most often, because "no rows
matched" is a normal state rather than an error.

Use a call that names its own output type:

```r
# Preferred --- the suffix is the return type, enforced
purrr::map_dbl(x, mean)

# Acceptable in a base-R file --- FUN.VALUE is the declared template
vapply(x, mean, FUN.VALUE = double(1))

# Avoid --- returns a list, a vector, or a matrix depending on the input
sapply(x, mean)
```

Between the first two, [`tidy-code`](tidy-code.md) already sets the
preference (purrr over the base apply family); this fragment is only about
ruling out the third.
`mapply()` inherits `sapply()`'s problem and `pmap_*()` is its type-stable
counterpart.

## `ifelse()` only when both branches share a type

From [Advanced R, "Vectorised
if"](https://adv-r.hadley.nz/control-flow.html#vectorised-if):

> I recommend using `ifelse()` only when the `yes` and `no` vectors are the
> same type as it is otherwise hard to predict the output type.

`ifelse()` also takes its output length and attributes from `test`, not from
the branches, so a scalar branch is recycled silently.
When the branches differ in type, or when there are more than two, use
`dplyr::case_when()`, which enforces a common type across every arm and
errors when they cannot be reconciled.

## The general rule

Beyond these two, prefer the strict member of any pair:

- `purrr::chuck()` over `[[` when a missing element should stop the run.
  `[[` is only half-strict on lists: an out-of-bounds *integer* index errors,
  but an out-of-bounds *character* index returns `NULL`, so a mistyped name
  propagates a `NULL` rather than failing.
  [Advanced R's table](https://adv-r.hadley.nz/subsetting.html#subsetting-oob)
  gives the full matrix, and names this inconsistency as the reason
  `pluck()`/`chuck()` exist --- `pluck()` always returns `NULL`, `chuck()`
  always throws.
- `vctrs::vec_c()` over `c()` where the combination must not silently coerce.
- An explicit `FUN.VALUE`, `.ptype`, or output-typed suffix wherever the API
  offers one.

The cost is a few characters at the call site; the return is that a wrong
input fails where it is written rather than three functions later.

## In review

Flag these with the same weight as the other coding rules:

- `sapply()` or `mapply()` anywhere in package code, a script, or a `.qmd`
  chunk --- interactive console use is the only exemption.
- `vapply()` without `FUN.VALUE`, or `map()` followed by `unlist()` where a
  `map_*()` variant would declare the type directly.
- `ifelse()` whose `yes` and `no` differ in type, or which is nested more
  than once where `case_when()` would be flat.
- Any call whose return type depends on the *values* of its input rather
  than only on its arguments, where a type-declaring alternative exists.
