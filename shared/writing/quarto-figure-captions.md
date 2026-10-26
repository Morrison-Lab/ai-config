# Quarto figure and table captions

In Quarto `.qmd` files, label and caption figures and tables with **div syntax**,
not chunk-option syntax.
Wrap the code chunk in a `::: {#fig-...}` / `::: {#tbl-...}` fenced div and put
the caption as the last line before the closing `:::`:

````
::: {#fig-stage-at-dx}

```{r}
#| label: stage-at-dx-fig
#| code-fold: true

plot_stage_at_dx(pt_data)
```

Stage at diagnosis by screening frequency
:::
````

Do not use the chunk options `#| label: fig-...` / `#| fig-cap: "..."` for the
cross-reference id and caption.
The div id (`#fig-`/`#tbl-`) carries the cross-reference; the chunk `label` stays
a plain code label.
This keeps figures consistent with tables, which already use div syntax.

For where floats go in a journal-submission manuscript,
the page breaks around them,
and keeping each caption on its float's page,
see [`manuscript-float-layout`](manuscript-float-layout.md).

## Figure defaults in notes

These come from Ezra's reviews of the lab's notes repositories (2026-10-14 to 2026-10-15).

- **Legends go at the bottom by default.**
  Use `theme(legend.position = "bottom")` in ggplot2 and `legend = list(orientation = "h", y = -0.2)` in plotly.
  Keep an inside or right legend only with a stated reason.
- **Put the alt text in the figure div.**
  Write `::: {#fig-x fig-alt="..."}` around the chunk, with the caption as the last paragraph, instead of the `fig-cap` and `fig-alt` chunk options.
  A caption paragraph can hold inline R, so its numbers stay computed.
  An attribute value cannot, so keep computed numbers out of the alt text.
  Break a long `fig-alt` over lines, one sentence per line.
- **Draw with ggplot2 and plotly, not base graphics.**
  Make one ggplot2 figure per subfile and let `plotly::ggplotly()` supply the interactive HTML version.
  Use plotly directly only for 3D.
  Add a package to the render workflows' `r-packages` in its own PR before a page relies on it.
- **A caption states what the float shows.**
  Open the caption with a sentence that says what the figure or table displays, so the float stands alone.
  A cross-reference to the example that the float illustrates may follow that sentence, but must never replace it
  ("The symmetry of @exm-x." is a pointer, not a caption).
  That opening-sentence rule is in psw `chapters/slides-posters-figures.qmd`
  ([psw#357](https://github.com/Morrison-Lab/psw/pull/357)),
  and gha `check-self-contained-captions` is the check for it
  ([gha#1241](https://github.com/Morrison-Lab/gha/pull/1241), open as of 2026-10-26).
  The remaining three rules in this bullet are ai-config guidance only, with no psw rule or gha check behind them as of 2026-10-26.
  Describe what the reader sees (lines, points, panels), not a property of the objects drawn ("linear functions are linear in $x$" describes nothing visible).
  Word the panels of a multi-panel float in parallel
  ("On the left, ...; on the right, ...").
  Link each cross-reference or hyperlink target once per caption.
- **Show confidence intervals on estimates**, and put axis ticks in the original scale ([`axis-tick-labels`](axis-tick-labels.md)).
