# Visuals everywhere

Include a visual (graph, diagram, figure) wherever one helps a reader, in new work and in existing content (Ezra, 2026-10-14: "going forward, we want to include visuals (graphs, etc) everywhere relevant (including backfilling the existing content)").

Where a visual helps:

- a definition that describes a shape or a relationship (a loss function, a decision boundary, a distribution);
- a worked example that fits a model to data (plot the data and the fit);
- a result whose statement a picture makes obvious (a bound, a convergence rate, a bias-variance tradeoff);
- a procedure with steps or a structure (a flowchart or a network diagram).

A visual follows the figure rules already in force:

- figures that show estimates carry confidence intervals (error bars or ribbons);
- axis ticks print plain numbers, not scientific notation ([details](axis-tick-labels.md));
- every figure has alt text ([`alt-text`](../../skills/alt-text/SKILL.md)) and a numbered caption;
- the code chunk comments what it does and why;
- colors are colorblind-safe.

Backfilling existing content:

1. Audit the chapters for definitions, examples and results that lack a visual, and save the audit list where other sessions can find it.
2. Open one PR per chapter with the figures, so each is reviewable alone.
3. Check the open PRs and issues first, so a figure another PR is adding is not duplicated.

- **Do:** ask of every definition, example and result whether a picture would help, and draw it in the same PR.
- **Don't:** leave a visual for a later pass, or add a decorative figure that shows nothing the text does not.

The human-facing version is in the psw chapter [Slides, posters, and figures](https://morrison-lab.github.io/psw/chapters/slides-posters-figures.html#sec-scientific-figures).
