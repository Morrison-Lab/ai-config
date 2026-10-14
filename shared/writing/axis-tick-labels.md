# Axis tick labels: no scientific notation

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
