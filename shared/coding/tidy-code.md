Write clean, tidy code, and hold code under review to the same bar. A change
should read as if it always belonged in the file: no leftover debug prints,
no dead branches, no needlessly long functions doing three things at once.

In R specifically, prefer concise **tidyverse** idioms over more verbose base
R or `{rlang}` paradigms when both do the job:

```r
# Preferred — tidyverse, concise and pipe-friendly
df |> dplyr::filter(x > 0) |> dplyr::pull(y)

# Avoid — base R subsetting/indexing for the same result
df[df$x > 0, "y"]
```

```r
# Preferred — purrr, concise
purrr::map_dbl(x, mean)

# Avoid — base R apply-family equivalent
vapply(x, mean, numeric(1))
```

```r
# Preferred — rlang's {{ }} embrace, when you do need tidy eval
my_fn <- function(data, col) data |> dplyr::summarise(mean({{ col }}))

# Avoid — spelling the same thing out with rlang::enquo()/!!
my_fn <- function(data, col) {
  col <- rlang::enquo(col)
  dplyr::summarise(data, mean(!!col))
}
```

When `lintr`'s `object_usage_linter` flags a data-masked column
(`no visible binding for global variable`), keep the tidyverse call and use the
`.data` pronoun, attached with `library(rlang, include.only = ".data")` so the
linter can see it.
Do not swap in base R subsetting to silence the warning
(Ezra rejected exactly that on lds#793, 2026-10-13).
A `# nolint` comment is the weaker fallback.

```r
# Preferred — the .data pronoun, visible to lintr
library(rlang, include.only = ".data")
df |> dplyr::filter(.data$group == which_group)

# Avoid — base R only to dodge a lint false positive
df[df$group == which_group, ]
```

`rlang::.data$x` written with the prefix instead fails inside `filter()`
(`stop_fake_data_subset`), so attach the pronoun rather than namespace it.

This is a readability default, not an absolute rule: reach for base R when
the tidyverse equivalent pulls in a heavy dependency for a one-liner, when
performance in a hot loop matters, or when base R is already the idiom the
surrounding file uses throughout. `{rlang}`'s lower-level tidy-eval building
blocks (`enquo()`, `eval_tidy()`, `sym()`) are for package authors who need
that control; `{{ }}` and other tidyverse-facing shorthand covers nearly
everything else.

This complements [`prefer-packaged-functions`](prefer-packaged-functions.md)
(look for an existing package before hand-rolling) and
[`per-operation-grouping`](per-operation-grouping.md) (a specific dplyr
instance of the same conciseness preference) — this fragment is the general
statement: write tidy code, and in R lean tidyverse over base R/rlang for it.
