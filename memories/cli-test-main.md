# CLI tests that import helpers miss `main()` skip wiring

Satellite of [`debugging.md`](debugging.md), split at the 1200-line
gate when recording Morrison-Lab/ai-config#2292.

Importing a CLI script and calling its helpers is not a test of how
`main()` classifies leftover state.
A skip-reason gate that lives only in `main()` (plugin live versus a
Claude skill catalog, leftover-as-stacked versus leftover-as-ok) can
be inverted while every helper-level assertion still passes.

The miss is the wiring, not the helper.
`catalog_leftovers()` can label a leftover symlink `stacked` correctly
and still never run, if `main()` gates that rewrite on the skill-catalog
skip instead of the plugin-live skip.
A Claude-only install then reports leftover Cursor rules as plugin
leftovers, or a plugin-live install leaves them `ok`, and the helper
tests stay green.

- **Do:** invoke `main()` for any classification that `main()` itself
  decides, especially a skip-reason split (subprocess or in-process).
- **Do:** pair helper tests with at least one assertion on `main()`'s
  result so a wrong gate cannot stay green.
- **Don't:** treat an imported-helper check as coverage of the CLI's
  leftover or skip path.
- **Don't:** key leftover classification on a skip that is true for more
  than the install path that actually serves that catalog.

Prior occurrences in this repo already encode the same shape.
`scripts/test_check_context_closure.py` still calls `positive_int()`
directly for the happy path, and its argparse-rejection tests invoke
`ccc.main(...)` in-process rather than only the helper, because a
direct helper call stayed green against a `type=int` argparse
regression.
`hooks/test-no-whole-file-punct-replace.py` smokes through `main()`.
3rd occurrence, 2026-08-26, Morrison-Lab/ai-config#2292: the first
adversarial pass on leftover Cursor-rule gating caught helper-only
tests in `scripts/test_check_harness_installs.py`; the follow-up drives
`check-harness-installs.py` through a subprocess of `main()` so gating
rule leftovers on the skill-catalog skip cannot pass.
Not a new hook: the decidable condition is "this CLI's skip-reason
wiring", not a lexical pattern a pre-push scanner can see.
