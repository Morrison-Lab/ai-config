When writing or reviewing a function that wraps or closely relates to another
function, prefer **reusing** that other function's documentation and argument
list over retyping them.

## Documentation reuse

In R, use [roxygen2's tag-reuse system](https://roxygen2.r-lib.org/reference/tags-reuse.html)
instead of copy-pasting a `@param` description or an explanatory section
between functions:

- **`@inheritParams other_fn`** — pull in `other_fn`'s `@param` documentation
  for any parameter this function shares with it, instead of retyping the
  description.
- **`@inheritDotParams other_fn`** — document a `...` argument by pointing at
  the function it's forwarded to (see "`...` passthrough" below), rather than
  writing out each forwarded parameter by hand.
- **`@inheritSection other_fn Section Title`** — reuse a full prose section
  (e.g. a shared "Details" block) instead of duplicating it.

Reused docs stay in sync automatically when the source function's docs
change; copy-pasted docs silently drift. In other languages, use the
equivalent inheritance mechanism instead of copying prose by hand — e.g.
JSDoc's `@inheritdoc` or Doxygen's `@copydoc`. Python/Sphinx has no direct
equivalent; cross-reference the wrapped function in the docstring (e.g.
`See :func:\`other_fn\` for parameter descriptions.`) instead of retyping it.

## `...` passthrough

Favor passing `...` straight through to a subfunction over manually
re-declaring and re-relaying its arguments one by one. See
[Advanced R, "`...` (dot-dot-dot)"](https://adv-r.hadley.nz/functions.html?q=dot-dot#fun-dot-dot-dot):
a wrapper function that doesn't itself use an argument shouldn't name it in
its own signature just to hand it down — declare `...` and forward it
(`inner_fn(...)`), and document it with `@inheritDotParams` as above. This
keeps the wrapper's signature stable when the subfunction's arguments
change, and avoids the wrapper silently going stale (a new argument added to
the subfunction becomes unreachable through the wrapper until someone
remembers to add a matching pass-through parameter).

Apply the same idea in other languages with the analogous mechanism: `**kwargs`
forwarding in Python, spread/rest parameters (`...args`) in JavaScript/TypeScript,
or variadic forwarding in whatever the target language provides.

This is a default, not an absolute rule — name an argument explicitly (instead
of leaving it inside `...`) when the wrapper needs to inspect, validate, or
transform that specific value before forwarding it.

### What `...` costs

Advanced R names two downsides, and they are the reason the escape hatch
above is worth using more often than it first appears
([`...` (dot-dot-dot)](https://adv-r.hadley.nz/functions.html#fun-dot-dot-dot)):

> * When you use it to pass arguments to another function, you have to
>   carefully explain to the user where those arguments go.
>   This makes it hard to understand what you can do with functions like
>   `lapply()` and `plot()`.
>
> * A misspelled argument will not raise an error.
>   This makes it easy for typos to go unnoticed.

The second is the sharp one, because `...` removes a check the language
otherwise performs for free.
A named parameter catches a typo; `...` swallows it:

```r
sum(1, 2, NA, na_rm = TRUE)   #> NA   -- the typo is silently absorbed
sum(1, 2, NA, na.rm = TRUE)   #> 3

f <- function(x, verbose = FALSE) x
f(1, verbse = TRUE)           #> Error: unused argument (verbse = TRUE)

g <- function(x, ...) x
g(1, verbse = TRUE)           #> 1    -- no error
```

`@inheritDotParams` answers the first downside, since the forwarded
arguments then appear in the wrapper's own docs rather than only in the
callee's.
Nothing answers the second, so weigh it: when an argument is one a caller
will plausibly mistype and getting it wrong changes results silently ---
`na.rm` is the archetype --- name it in the signature and forward it
explicitly, even though `...` would carry it.

## In R, never use `@noRd`; use `@keywords internal`

Document **every** function with a generated `.Rd` page, internal ones
included. For a function that shouldn't appear in the manual index or the
rendered reference site, use `@keywords internal` — **never `@noRd`**.

The reasoning: every internal function is reachable through `:::`, so its
documentation should be available to anyone who calls it that way.
`@keywords internal` still generates the `.Rd` page (so `?pkg:::helper`
works and cross-references resolve), it just omits the page from the manual
index and the pkgdown/altdoc reference listing. `@noRd` suppresses the page
entirely, which hides documentation from a reachable function for no benefit.

This also keeps doc-reuse working. When a wrapper's roxygen references a
helper — via `@inheritParams`, `@inheritDotParams`, or a `[helper()]`
cross-reference link — that reference only resolves if the helper has a
generated `.Rd` page. A helper marked `@noRd` has none, so R CMD check fails:
`@inheritParams`/`@inheritDotParams` error that they can't find the target,
and a `[helper()]` link becomes a "missing link in Rd file" WARNING (which
fails CI under `error_on = "note"`). The fix is **not** to strip the doc-reuse
syntax (retyping the `@param` descriptions, spelling out the `...` forwards,
or downgrading the link to plain code font) — that reintroduces exactly the
duplication this fragment exists to prevent. Use `@keywords internal` on the
helper and keep the `@inheritDotParams`/`@inheritParams`/`[helper()]`
references intact.

## In review

Flag all three as review findings, the same weight as other idiomatic-code
findings: a `@param` description or prose section that's copy-pasted from
another function's docs instead of inherited, a wrapper function that
manually re-declares and relays arguments it never touches itself instead of
using `...`/`**kwargs`/rest-parameter passthrough, and an internal function
marked `@noRd` instead of `@keywords internal`.
