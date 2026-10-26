# Axis titles and tick labels: plain words, original units, no scientific notation

## Axis titles name the quantity in plain words

Name the quantity on each axis in plain words, and add its symbol only as an option (Ezra, 2026-10-26).
Write "Probability, p" and "Log-odds, η", not a bare symbol or expression such as "p", "η", "x1" or "f(x)".
A reader should not have to look up a symbol to know what an axis shows.
The gha check `check-axis-titles` ([Morrison-Lab/gha#1240](https://github.com/Morrison-Lab/gha/pull/1240))
flags a title with no plain word in it once that PR merges,
in ggplot2 `labs()`, `xlab()` and `ylab()`, in matplotlib `set_xlabel()` and `set_ylabel()`,
and in plotly axis titles.

- **Do:** label the axes of a logistic curve "Log-odds, η" and "Probability, p".
- **Don't:** label them "η" and "p".

## Ticks are in the variable's original measurement scale

Every axis carries ticks in the original measurement scale of its variable, so a reader can read it without help (Ezra, 2026-10-15).
This holds however the model is parametrized and however the axis is spaced.
If a fit runs on scaled, standardized or log-transformed values, draw the data where the fit needs it, but put ticks at the positions of round original values and label them with those values.
Report numbers beside the figure, such as an RMSE, in the response's units too.
Say in the text that the fit uses the transformed values, and why, rather than leaving the transformed scale on the axis.

- **Do:** label a horsepower axis 50, 100, 150, 200, with the scaled value 0 to 1 only under the hood.
- **Don't:** label an axis "mpg (standardized)" or "horsepower (scaled to 0 to 1)" when the reader needs to read miles per gallon and horsepower.

How, by tool:

- ggplot2, when the plotted column is transformed (scaled, standardized):
  plot the back-transformed values (`aes(x * sd + mean)`),
  or give `breaks` at the transformed positions and `labels` with the original-value text.
  Bare `breaks` in original units against a scaled column draws an empty axis.
- ggplot2, when the axis uses a `scale_*(transform = ...)` such as `"log10"`: set `breaks` in the original units.
- Observable Plot: pass `ticks` at the scaled positions and a `tickFormat` that maps back, as the lds Big Ideas helpers `biHpAxis` and `biMpgAxis` do.

A log axis is fine: label it with the original values.

## No scientific notation

Avoid scientific notation in axis tick labels where feasible (Ezra, 2026-10-13).
Print plain or comma-separated numbers, such as 0.001, 1, 10 and 1,000, not 1e-03 or 1e+03.
Logarithmic spacing is fine.
The rule is about the label format only.

When the numbers are huge or tiny, rescale the units and say so in the axis title, such as "dollars (millions)".

Ways to format the labels:

- ggplot2: `scales::label_comma()` or `scales::label_number()` in the `labels` argument of the scale.
- matplotlib: `ax.xaxis.set_major_formatter("{x:,.0f}")`, and `set_minor_formatter` for a log axis, whose minor ticks also carry labels.
- plotly: `tickformat`.
- Observable Plot: a `tickFormat` that calls `toLocaleString`, or `d3.format(",~f")`.

A log axis with a small range prints a few unlabelled minor ticks by default.
Check the render, since a formatter can crowd or clip the labels (widen the margin if so).
