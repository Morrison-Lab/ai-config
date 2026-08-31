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
