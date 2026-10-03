# Quarto: give revealjs slides the same div boxes and colors as HTML

Theorem-like and callout divs (`#def-`, `#thm-`, `#exr-`, `#sol-`, custom
callouts) render as boxed, colored blocks in HTML, but the `revealjs` format
renders them as plain text unless the project styles them.
On a slide the reader then cannot see where a formal definition ends and the
commentary begins.

Style those divs for `revealjs` as well, in the deck's theme SCSS or through
the same callout extension the HTML format uses, so each div is visibly boxed
and colored by type in every format.
Check the rendered deck, not only the HTML page.

- **Do:** give every theorem-like and callout div a border and background in
  the `revealjs` output, matching the HTML colors by div type.
- **Don't:** accept a deck where a definition's box is invisible because the
  styling exists only for `html`.

(Directive from the user, 2026-09-25: "can we add the div boxes and colors in
revealjs format? ... it's not clear where the formal definition ends and the
commentary begins", stated as a general principle for every project.)

## A section header gets its own slide

Put a slide break between every section (level 1) header and the content after it,
so the header is a title slide and the content starts on the next slide.
Do this once for the whole project, in a Lua filter listed under `revealjs: filters:`
(lds uses `filters/section-slide-break.lua`),
not by typing a break after each header in every chapter.
The [`slidebreak`](https://github.com/Morrison-Lab/slidebreak) shortcode inserts one break where it is typed,
so it suits a one-off break but not this every-header rule.

- **Do:** check in the rendered deck that each section header stands alone on its slide.
- **Don't:** leave a section header sharing a slide with its first paragraph or box.

(Directive from the user, 2026-10-02: "put a slide break between every section slide header and the following content", stated as a general principle for every project.)
