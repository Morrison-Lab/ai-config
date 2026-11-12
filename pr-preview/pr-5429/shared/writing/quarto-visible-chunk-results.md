# Quarto: every visible code chunk shows a result

In lecture notes and other rendered documents,
a code chunk that readers can see should produce a visible result:
a figure, a table, or console output.
A chunk that only assigns, such as

```r
hers <- rmb::hers |> haven::as_factor()
```

shows code with nothing to connect it to,
so the reader cannot check what it made.

## How to fix a silent chunk

- **Loaded data:** end with its first rows (`hers |> head()`),
  which stays short whether the object is a tibble or a data frame.
- **A computed value:** print it.
- **A defined function:** call it once on a small example.
  If the call draws random numbers,
  check that a later chunk sets its own seed before the next random draw,
  so the call does not change later results.
- **Set-up code:** show what it set up,
  such as a summary of the variables or settings it created.
- **A result the next chunk displays:** merge the two chunks
  rather than printing the result twice.

Chunks hidden with `#| include: false` are exempt.

## Finding silent chunks

Decide this with a parser, not by reading:
parse each visible chunk
and flag it when every top-level expression is an assignment,
a function definition, a loop,
or a call that returns invisibly
(`library()`, `set.seed()`, `options()`, `invisible()`).
