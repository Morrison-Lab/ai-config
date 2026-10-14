Complex code belongs in named functions, not inline in a Quarto `.qmd`'s R
chunks. An analysis `.qmd` should read as narrative plus orchestration: each
chunk calls documented functions and shows their results. When a chunk grows
into substantial logic (multi-step data manipulation, a function defined
inline, a non-trivial transformation, or the same block copied across
chunks), extract that logic into a package function and have the chunk call
it.

Extract to one function per file under `R/` (see
[`one-function-per-file`](one-function-per-file.md)), with full roxygen, the
same way any other package function is written. The chunk then shrinks to a
call plus whatever narrative or display wraps it.

**Why.** A function can be unit-tested, reused across chunks and analyses,
documented, and linted; a `.qmd` code chunk can be none of these. Keeping
logic inline also buries the analysis narrative under implementation detail
and duplicates code that should have one home. This is the `.qmd`
counterpart to the standing rule that function definitions live in `R/`.
[`lms::function_location_linter()`](https://github.com/Morrison-Lab/psc/tree/main/lms)
(added in the lab manual's copy of `lms` by [UCD-SERG/lab-manual#403](https://github.com/UCD-SERG/lab-manual/pull/403), before `lms` moved to psc)
catches a function *defined* in a `.qmd`; this rule also covers loose chunk
logic that was never wrapped in a function at all, which no linter flags.

Apply it when writing an analysis and when reviewing one: a `.qmd` chunk
carrying substantial logic is a decomposition finding, the same weight as the
other modularity checks. The fix is to move the logic into `R/` and leave the
chunk calling it.
