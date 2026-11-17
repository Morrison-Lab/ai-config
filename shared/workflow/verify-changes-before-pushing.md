# Verify changes before pushing

The checks to run before pushing to `ai-config`: the three fast checks and the full test suite when shared tools or scripts change.

At minimum for `ai-config`: `python3 scripts/validate-skills.py`, `python3 scripts/check-links.py`, `python3 scripts/check-ascii-punctuation.py`.
Run the full test suite (`python3 scripts/test_*.py`) when touching shared tools or scripts.

These lines moved verbatim from the "Verify changes before pushing" bullet of `AGENTS.md`'s "Ship work through a verified push and a PR" section ([ai-config#5310](https://github.com/Morrison-Lab/ai-config/issues/5310)), which keeps the rule and the data-file line and points here for the checks.

## Before pushing a refactor of a hook or `scripts/lib`

Moving or renaming code in a hook or in `scripts/lib` breaks files the touched hook's own suite never runs.
[#5735](https://github.com/Morrison-Lab/ai-config/pull/5735) went red twice that way (2026-11-17, [#5738](https://github.com/Morrison-Lab/ai-config/issues/5738)).
Mutation clauses in the hook's test were anchored on the moved code, and a sibling hook that loads the changed one through `load_sibling` called a helper the refactor removed.

- **Do:** run `python3 scripts/check-mutation-anchors.py`, as [`algorithmatize-checks`](algorithmatize-checks.md) says for an extracted helper ([#5739](https://github.com/Morrison-Lab/ai-config/pull/5739)).
- **Do:** run the full `python3 scripts/test_hooks.py`, not only the touched suites.
- **Do:** grep `hooks/` and `scripts/` for the changed file's name, and check each `load_sibling(` importer for a name the refactor removed.
  In #5735, `grep -rln flag-commit-a-sweeps-submodule hooks/ scripts/` lists `hooks/no-commit-with-conflict-markers.py`, which called the removed `_strip_env`.
- **Don't:** push on a clean review while a slow local suite is still running.
  A review reads the diff, and both breaks were outside it.
