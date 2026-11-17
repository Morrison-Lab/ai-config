# Verify changes before pushing

The checks to run before pushing to `ai-config`: the three fast checks and the full test suite when shared tools or scripts change.

At minimum for `ai-config`: `python3 scripts/validate-skills.py`, `python3 scripts/check-links.py`, `python3 scripts/check-ascii-punctuation.py`.
Run the full test suite (`python3 scripts/test_*.py`) when touching shared tools or scripts.

These lines moved verbatim from the "Verify changes before pushing" bullet of `AGENTS.md`'s "Ship work through a verified push and a PR" section ([ai-config#5310](https://github.com/Morrison-Lab/ai-config/issues/5310)), which keeps the rule and the data-file line and points here for the checks.
