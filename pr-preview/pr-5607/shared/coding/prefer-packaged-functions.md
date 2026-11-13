Before writing a function, **perform a research step to look for an existing packaged one that already
does the job** --- and prefer it over rolling your own:

- Check, roughly in this order: base R and the **tidyverse / r-lib** packages,
  then a focused, well-maintained CRAN package, then **our own lab packages**
  (e.g. `{bcs}`, `{ettbc}`, `{gha}`, and the shared workflows there). Packages
  can depend on each other, so reuse across our repos is fine.
- Reach for the packaged version unless it is genuinely unfit --- the wrong
  API, a heavy dependency for a one-liner, or it doesn't quite do what you
  need.

Packaged functions are tested, documented, and maintained by other people;
hand-rolling an equivalent duplicates that work, adds surface area to maintain,
and risks subtle bugs the package already fixed. For example, use
`withr::with_seed()` to set a seed and restore the RNG stream, rather than
hand-rolling a `.Random.seed` save/restore.

This is a default, not an absolute rule. A tiny, dependency-free helper can
beat pulling in a package, and sometimes nothing fits --- but look first, and
prefer the standard, well-known way over a bespoke one.

One reason to skip a packaged function does not count: an environment your
own change chose.
"The script runs on a bare R, so `rlang` is unreachable" is not evidence that
`rlang` does not fit when this change is what decided the script would run
that way.
Install the package, fix the CI job, and re-run the comparison.
See the DRW fragment's "A constraint your own change authored is not evidence
against an upstream".

- **Do:** say whether a constraint ruling out a package is external or one of
  ours, before letting it decide.
- **Don't:** verify a self-imposed constraint and report that as having
  justified the hand-rolled version.

This is the R-function special case of the broader don't-reinvent-the-wheel
principle --- see [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)
for the general statement, which also covers whole features, the
fork-or-contribute preference for close-but-not-exact matches, and the
review-side application.

## Adding a dependency and replacing existing helpers are both in scope

The default above covers new code.
It applies equally to a hand-rolled helper already in the codebase that a CRAN package function makes redundant.
A new dependency is an acceptable price for deleting such a helper:
the aim is a lean codebase,
meaning less code we maintain ourselves,
even when the dependency list grows.
"Heavy dependency" is a reason to skip a package only when the package is heavy relative to the job;
the mere fact that it is not yet in `DESCRIPTION` is not.
The tiny-helper exception above still holds for a true one-liner when the package is heavy relative to it.

Check behavioural equivalence before swapping, on the inputs the code actually sees.
A similar name or purpose is not equivalence.
Measured 2026-09-30 with R 4.6.0 and gtsummary 2.4.0.9001 and 2.6.1, which agreed (re-check against current versions):
`gtsummary::style_sigfig(0.0065, digits = 3)` returns `"0.007"`, capping decimals,
so it is not a drop-in for 3-significant-figure formatting.
`formatC(signif(x, 3), digits = 3, format = "fg", flag = "#")` keeps `"0.00650"`
but leaves a trailing `"."` on whole numbers with three or more integer digits (`100` gives `"100."`).
Neither replaces the other without a check, and a candidate that fails the check is a reason to keep the helper, not to bend the call sites.

When swapping validators to `{checkmate}`, keep `cli::cli_abort(class = ...)` wrappers around `checkmate::test_*()`.
Tests that assert a condition class then keep passing,
which `checkmate::assert_*()` alone would break
(measured 2026-09-30 with checkmate 2.3.4: `assert_number("a")` signals a plain `simpleError` with no custom class).

- **Do:** replace a redundant hand-rolled helper with the package function, and add the dependency to do so.
- **Do:** compare outputs of the candidate and the helper before swapping,
  on representative and edge inputs (small, whole-number, `NA`),
  and keep the helper when they differ.
- **Do:** preserve the condition class of existing errors when changing the validator underneath.
- **Don't:** leave a helper in place because it already works,
  or because the package is a new dependency,
  when an equivalent package function passes the equivalence check.
- **Don't:** swap on name or description alone,
  or swap without having compared the candidate's and the helper's outputs and error classes on the same inputs.

(Directive from the user, 2026-09-30:
always DRW, prefer packaged functions even at the cost of added dependencies,
replace redundant hand-rolled functions with CRAN package functions,
and keep the codebase lean.)
