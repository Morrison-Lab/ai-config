# Visuals everywhere

Include a visual (graph, diagram, figure) wherever one helps a reader, in new work and in existing content (Ezra, 2026-10-14: "going forward, we want to include visuals (graphs, etc) everywhere relevant (including backfilling the existing content)").

Where a visual helps:

- a definition that describes a shape or a relationship (a loss function, a decision boundary, a distribution);
- a worked example that fits a model to data (plot the data and the fit);
- a result whose statement a picture makes obvious (a bound, a convergence rate, a bias-variance tradeoff);
- a procedure with steps or a structure (a flowchart or a network diagram).

Draw graphs with plotly where feasible (Ezra, 2026-10-14: "use plotly graphs where feasible, including 3d graphs where relevant"):
an interactive widget on the website and slides, and a 3D plotly surface or scatter where a third dimension shows the idea, such as a risk surface over two parameters.
Keep a static fallback for PDF and Word, which cannot show a widget;
lds#642 (`chapters/_subfiles/big-ideas/_fig-risk-surface.qmd`) is the worked pattern: a plotly chunk for HTML output and a static image for the other formats.
Use plain `ggplot2` or an SVG only where plotly is not feasible, such as a diagram.

A visual follows these figure rules:

- figures that show estimates carry confidence intervals (error bars or ribbons);
- axis ticks are in the variable's original measurement scale and print plain numbers, not scientific notation ([details](axis-tick-labels.md));
- an axis is extended to show important reference values when they matter, such as the null value 1 for a ratio;
- the value axis includes zero whenever readers judge size from a bar's length or from the distance between marks, as for counts, rates and proportions ([details](#axis-at-zero-in-every-format));
- every figure has alt text ([`alt-text`](../../skills/alt-text/SKILL.md)) and a numbered caption;
- the code chunk comments what it does and why;
- colors are colorblind-safe.

Every example gets one (Ezra, 2026-10-23, [psw rule](https://morrison-lab.github.io/psw/chapters/teaching.html)):
give each `#exm-` div a figure of its data, model or results in the same PR that writes or edits it, without being asked.
Put the figure in the div or in a `_fig` subfile it includes.
When there is nothing to plot, such as a single number, put `<!-- no-figure: reason -->` in the div.
Each notes repo enforces this by calling the gha `check-exm-figures` workflow (warn-only, diff-scoped),
so an example without a figure is flagged at review once that repo's caller has merged.

Backfilling existing content (an explicit ask, so an exception to [`no-sweeps-by-default`](../workflow/no-sweeps-by-default.md);
other rules are not backfilled unless Ezra says to):

1. Audit the chapters for definitions, examples and results that lack a visual, and save the audit list where other sessions can find it.
2. Open one PR per chapter with the figures, so each is reviewable alone.
3. Check the open PRs and issues first, so a figure another PR is adding is not duplicated.

- **Do:** ask of every definition, example and result whether a picture would help, and draw it in the same PR.
- **Don't:** leave a visual for a later pass, or add a decorative figure that shows nothing the text does not.

The human-facing version is in the psw chapter [Slides, posters, and figures](https://morrison-lab.github.io/psw/chapters/slides-posters-figures.html#sec-scientific-figures).

## Axis at zero in every format

The figure rules apply to every figure in every output format: a Quarto chunk, a matplotlib or plotly figure saved for a `.pptx` or Word file, a native PowerPoint chart, a Shiny app.
A rule written while drafting notes still binds a slide built from a Python script (ai-config#5614: a slide session read this page as covering Quarto and R chunks only).

Zero matters whenever a reader judges size from a bar's length or from the distance between marks.
That covers counts, rates and proportions.
A bar chart's value axis always starts at zero, because the bar's length is the value it shows.
A dot or line plot of a rate or proportion that readers compare across groups also starts at zero, unless the quantity has no meaningful zero (a temperature in Celsius, a calendar year, an index).
To show a small difference clearly, plot the difference itself, or use dots with intervals, rather than cutting the axis.

A distortion you notice gets fixed, never captioned.
A speaker note or caption warning that the axis does not start at zero leaves the misleading picture in place for every reader who skips the note.

`hooks/no-truncated-bar-axis.py` denies the decidable case: a bar chart (matplotlib, ggplot2, plotly, python-pptx) whose value axis gets a literal lower limit above zero.
A comment `axis-zero: allow <reason>` exempts the rare bar chart of a quantity with no meaningful zero.
The dot and line cases stay prose, because whether zero matters there depends on what the quantity means, which no pattern in the code can decide.
The reviewer's checklist item is in [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md#figures-with-a-cut-value-axis).

- **Do:** start the value axis at zero, and if the difference then looks small, show the difference directly.
- **Don't:** keep a cut axis and add a caution in a caption or speaker note.
