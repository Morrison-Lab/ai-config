# Graph and display equation defaults

Defaults for analysis figures, visuals and display math: `ggplot2`, worded axes and plain-number ticks, a visual wherever one helps, one equation per display line, labelled display equations, and the shared semantic macros.

When authoring analysis figures, prefer `ggplot2` over base graphics wherever the dependency is available or appropriate to add.
Title axes in words, not symbols; print ticks as plain numbers ([details](axis-tick-labels.md)).
One equation per display line unless a reason favors more;
one `=` per math line ([details](math-derivation-steps.md)).
Include a visual wherever one helps a reader, in new work and in existing content you touch, as plotly where feasible with a static fallback.
Give every `#exm-` div a figure, or a `<!-- no-figure: reason -->` comment, unasked ([details](visuals-everywhere.md)).
Label every display equation so it receives an equation number and a stable URL.
Write all LaTeX math, in any repo or format, with the shared semantic macros: [`use-math-macros`](../../skills/use-math-macros/SKILL.md).

These rules moved verbatim from `AGENTS.md`'s section of the same name (ai-config#5310), which keeps a one-sentence summary and links here.
