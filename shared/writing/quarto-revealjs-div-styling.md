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
