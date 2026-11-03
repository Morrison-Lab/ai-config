# Explain every arbitrary analysis choice in the prose

Ezra's rule (2026-11-03, ai-config#4905): every time you make an arbitrary analysis choice, explain the decision in detail in the prose next to it.

An analysis choice is arbitrary when the data do not force it and another defensible value exists.
Examples:

- Bin edges and widths.
- Smoothing bandwidths and spans.
- Thresholds and cutoffs.
- Random seeds.
- Train and test splits.
- Subsets, exclusions and transformations.
- Tuning-parameter grids.

State three things:

- What you chose.
- What the alternatives were.
- Why this one, with numbers from the data where they bear on it.

If you cannot give a reason, remove the choice.
On Morrison-Lab/lds `fig-logistic-regression`, age was grouped into three-year bins with no stated reason.
Each age had 17 to 144 men per behavior pattern, so nothing forced the bins, and the figure now plots one proportion per age.

The hook `hooks/flag-unexplained-analysis-choice.py` warns when an edit to a `.qmd` page adds such a choice in code and no prose with a reason word.
