# Lecture and slide authoring conventions

Rules for writing lecture notes, slides and teaching pages in any Morrison-Lab course repository.
They come from Ezra's directions for DATA 571, recorded in the private `Morrison-Lab/lds` repository's `AUTHORING.md`, and apply to every course site.
The prose wording of each rule is canonical in [psw's "Writing for teaching" chapter](https://github.com/Morrison-Lab/psw/blob/main/chapters/teaching.qmd), which also carries the examples.
This fragment is the agent-facing copy: follow the rules, and link to psw instead of restating its text.

## Structure

- **Build the lecture from exercise and solution pairs.**
  Pose each data manipulation, analysis, calculation, derivation or proof in an `#exr-` div, and put the worked answer in the repository's solution div (`::: solution` or the `.sol` class), with a `#sol-` id sharing the exercise's slug.
  [`quarto-divs-for-typed-content`](quarto-divs-for-typed-content.md) defines the solution div, and a repository uses the syntax its own `student-qmd` setup expects.
- **Put a slide break between an exercise and its solution** (`{{< slidebreak >}}`, never `---`), so the prompt is on screen alone while students work.
- **Ask before defining.**
  Precede a `#def-` or `#thm-` div with an exercise that asks the question it answers.
  The solution answers informally, and the formal div follows the solution div, never inside it.
  [`informal-definitions`](informal-definitions.md) states the underlying rule.
- **One bottom-level prompt per exercise.**
  Do not write one exercise with parts (a) through (e).
- **Subfiles hold one unit each and start with no heading.**
  The chapter file is a spine of headings, slide breaks and `{{< include >}}` calls.
  Name each unit's file for its div type (`_def-`, `_exr-`, `_sol-`, `_thm-`, `_exm-`, `_fig-`), and decompose further when it is a judgment call.
- **Never nest one theorem-type div inside another.**
  A special case gets its own div after the general one and links to it.
- **Keep body text off section and title slides.**
  Reveal.js does not scroll them, so put a slide break after the heading.

## Content

- **State the notation, and name the alternatives** a reader will meet in other sources, in the definition div or a callout beside it.
- **Name synonyms and near-synonyms** where a term is defined, and say which one the notes use.
- **Use real data and compute every number.**
  Never type or paste output.
  See [`hypothetical-examples`](hypothetical-examples.md).
- **Put media links beside the content they support.**
  See [`media-links-beside-content`](media-links-beside-content.md).
- **Place each topic in the earliest course site whose readers need it.**
  See [`course-sequence`](course-sequence.md).
- **Do not answer graded work in student-facing notes.**
  Check the grading repository before writing a solution, and use a different example when an exercise is graded.

## Prose

Write plain, literal sentences with one idea each.
State the claim instead of using an idiom, name the referent instead of using a bare "this" or "there", and never write "thing".
Cut AI clichés: straw objections, personified abstractions, colon reveals, answered rhetorical questions and closing aphorisms.
The detailed rules are in [`plain-prose`](plain-prose.md), [`ai-tells`](ai-tells.md) and [`ambiguous-reference`](ambiguous-reference.md), and psw's [Writing for teaching](https://github.com/Morrison-Lab/psw/blob/main/chapters/teaching.qmd) chapter.

## Related

- [`definition-crossrefs`](definition-crossrefs.md), [`informal-definitions`](informal-definitions.md), [`forward-references`](forward-references.md), [`semantic-line-breaks`](semantic-line-breaks.md)
- [`quarto-divs-for-typed-content`](quarto-divs-for-typed-content.md): which div type holds which content.
- [`quarto-revealjs-div-styling`](quarto-revealjs-div-styling.md): style div boxes on slides as on the web page.
