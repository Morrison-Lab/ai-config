When adding a new function to a codebase, give it its own file rather than
bundling it into a file that already holds other functions --- unless the
function is a two-liner (a trivial wrapper or short helper), in which case
grouping it with closely related functions in a shared file is fine.

This applies per-language, following that language's file-naming convention
for the mapping between a function and its file:

- **R**: one file per exported/top-level function under `R/`, file name
  matching the function name (e.g. `simulate_data()` lives in
  `R/simulate_data.R`). A private helper that's genuinely inseparable from a
  single caller (and itself more than a two-liner) still gets its own file,
  named after the helper.
- Other languages: follow the same principle using that ecosystem's own
  convention (e.g. one class/component per file in Java/TypeScript; in
  Python, give a substantial function its own module file rather than
  bundling it into one that already holds unrelated functions).

**Why:** a file with one function per unit of functionality is easier to
find, easier to diff (a change to one function doesn't sit inside an unrelated
grep hit for a different one), and matches how `git blame`/code review tools
attribute changes. Bundling unrelated functions into one file (e.g. because
they were added in the same PR, or because an existing file happened to be
open) accumulates unrelated concerns in one place over time.

**When adding a function to an existing multi-function file** (a common
pattern in older/vendored code that predates this convention): don't feel
obligated to split every pre-existing function out --- that's a separate,
larger refactor with its own cost/benefit call. Do put the **new** function
in its own file, so at least new code follows the convention going forward.

(Corrected on `d-morrison/altdoc#21`, 2026-07-09: two new functions --
`.rewrite_self_links()` and its helper `.rewrite_self_links_one()` -- were
initially added inline to an existing multi-function file,
`R/settings_quarto_website.R`, placed right after the function that calls
them. The user redirected: each should get its own file. Split into
`R/rewrite_self_links.R` and `R/rewrite_self_links_one.R`, leaving the
original file's three pre-existing functions untouched.)
