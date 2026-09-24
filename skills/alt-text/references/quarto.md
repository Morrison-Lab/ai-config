# Alt Text in Quarto Documents

This reference covers how to find figures and add alt text in `.qmd` files.
It covers both code-generated figures and static images, since a course-notes or book project often has more of the second kind.

## Finding figures

```bash
# List all figure labels with file and line number
grep -n "#| label: fig-" *.qmd

# Find figures in a specific file
grep -n "#| label: fig-" my-document.qmd

# Find a specific figure
grep -rn "#| label: fig-splines-predictor-outcome" *.qmd

# List static images, with or without a fig-alt attribute
grep -rn '!\[' --include='*.qmd' .
```

## For each figure

1. **Locate** --- use grep to find file and line number
2. **Read context** --- read ~50 lines around the chunk (prose before + code + prose after)
3. **Extract details** --- note `fig-cap`, plotting code, data generation, surrounding explanation
4. **Draft alt text** --- apply the three-part structure from the main skill
5. **Verify** --- check against the quality checklist

## Adding fig-alt to a code chunk

Use the hashpipe syntax inside the code chunk:

```r
#| label: fig-penguin-scatter
#| fig-cap: "Bill length vs. bill depth for 344 penguins."
#| fig-alt: >
#|   Scatter chart of bill length vs. bill depth for 344 penguins
#|   across three species. Gentoo penguins form a distinct cluster
#|   at higher bill depth. Adelie and Chinstrap overlap but separate
#|   along the bill length axis, with Chinstrap skewing higher.
plot_code_here()
```

Note: use `fig-alt` (hyphen) in `.qmd` files.

## Adding fig-alt to a static image

A markdown image has no generating code, so the "source code access" advantage in the main skill does not apply.
Read the image itself (open the file) and the prose around it instead.
The bracketed text is the caption; alt text goes in a `fig-alt` attribute:

```markdown
![Decision boundary of a linear classifier.](images/boundary.svg){#fig-boundary fig-alt="Scatter chart of two classes in the plane. A straight line separates the classes, with a few points of each class on the wrong side."}
```

Without `fig-alt`, a captioned image renders with no `alt` attribute at all: the caption goes only into the `<figcaption>` (checked with Quarto 1.10.18, where `![Caption.](e.png){#fig-e}` rendered as `<img src="e.png" class="img-fluid figure-img">`).
So audit for the attribute itself rather than assuming the caption covers it.
An SVG diagram's alt text should name the diagram type first (flowchart, network diagram, plot of a function) in the same way the main skill names a chart type.

## Auditing existing alt text

When alt text already exists, leave it alone unless it fails one of these checks:

**Placeholder text** --- generated text that names what an image *is* rather than what it *shows* ("Figure from the lecture notes", "Diagram 3") describes nothing, and should be replaced.

**Relative references** --- alt text must be self-contained.
Fix phrases like:

- "A plot identical to the one above..." -> describe the plot fully
- "Much like the first one..." -> stand-alone description

**Missing key information** --- fix if alt text omits:

- Chart type as the first words
- Axis labels and what they represent
- The key pattern or takeaway

**Grammar and spelling errors** --- alt text is read aloud by screen readers.
