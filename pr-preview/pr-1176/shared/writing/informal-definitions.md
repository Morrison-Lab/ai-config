An **informal definition** is prose that does the work of defining a
concept --- naming it, giving it a precise meaning, often an equation or an
`\eqdef` --- without using the project's formal definition construct. In a
Quarto book or site, that construct is the theorem-like crossref div
(`{#def-...}`, and its siblings `{#thm-...}`, `{#lem-...}`, `{#cor-...}`);
in other repo types the equivalent might be a docstring, a glossary entry,
or a spec's defined-terms list. Either way, a concept defined only in
running prose never gets a stable id, so nothing downstream can cite it,
and [`definition-crossrefs.md`](definition-crossrefs.md)'s hyperlink-on-
first-mention check has nothing to link to.

This is a **different gap** from what `definition-crossrefs.md` catches.
That check assumes a defining div exists somewhere and verifies mentions
link to it in the right order, flagging a term as "undefined" only when no
div defines it *anywhere*. This check catches the case in between: the
concept **was** defined --- with definition-grade precision --- just not
inside the formal construct, so `definition-crossrefs.md`'s div-position
comparison never sees it as a definition to track in the first place.

## The detection heuristic

Two independent patterns, each catching phrasing the other misses --- run
both:

1. **A bolded or otherwise emphasized term, immediately followed by
   language that states a precise meaning** --- "is", "is defined as",
   `\eqdef`, an equation:

   ```bash
   rg -n '\*\*[A-Za-z][a-zA-Z .-]{2,60}\*\*[^.]*(\\eqdef|is (defined|the)\b|=)' <file>
   ```

2. **A naming sentence ending "is:"/"are:" immediately before a display
   equation** --- catches a concept named in plain prose with no bold at
   all, which pattern 1 misses entirely:

   ```bash
   rg -n '\bis:\s*$|\bare:\s*$' <file>
   ```

   Treat a hit as a real candidate only when the very next non-blank line
   opens a display-math block (`$$`) or contains `\eqdef` --- a line
   ending "is:" that instead introduces a list or a code block isn't a
   definitional naming sentence.

For each hit from either pattern, find its enclosing div (search backward
for the nearest `:::{#...}` opener and forward for the matching closer).
Treat it as a **candidate** if:

- it is **not** inside any `{#def-...}`/`{#thm-...}`/`{#lem-...}`/
  `{#cor-...}` div at all (plain prose), **or**
- it **is** inside such a div, but that div's id and heading name a
  *different* concept than the one this sentence bolds (a second concept
  riding along inside another's definition).

## Confirming a candidate

Not every bolded, precise-sounding sentence is a missing definition. Check
each candidate against these before flagging it:

1. **Is this introducing something new, or just reusing an
   already-defined concept?** Bolding for emphasis when restating a term
   that already has its own `{#def-...}` div elsewhere is fine --- only
   flag a term that has **no** formal div anywhere in the document.
2. **Is this a practical/tool-usage explanation, not a theoretical
   concept?** Describing what a function argument or CLI flag does (e.g.
   "the percentile method (`type = "perc"`)") is instructional prose, not
   a concept this document is building theory on --- don't flag it.
3. **Is this a deliberately informal list, not a formal-definition
   context?** A numbered "practical considerations" or "gotchas" list is
   allowed to state things precisely without a div for each item --- the
   surrounding content already signals "this is not the formal-definitions
   section."
4. **Is it actually used downstream?** A concept that gets cited by name
   elsewhere in the document (in a proof, another definition, an example)
   is a strong signal it needed a stable, cross-referenceable id --- and a
   strong signal you're looking at a real finding, not just informal color
   that happens to sound precise.

Only a candidate that introduces a genuinely new concept, isn't a
practical aside, isn't part of a deliberately informal list, and would
benefit from being citable, is a confirmed finding.

## Fixing a confirmed finding

1. **Wrap it in its own formal-definition div**, with its own id and
   heading, following the same convention every other definition in the
   document already uses.
2. **Give it its own worked example**, immediately after the new
   definition and before any new theoretical claim builds on it --- the
   same "definition, then example, then theorem" ordering this project's
   other content-writing checks already expect.
3. **Update anything that already depended on it informally** to cite the
   new id explicitly (`(@def-<new-id>)`), instead of just reusing the bare
   symbol or term with no traceable source.
4. If the concept was crammed inside a *different* definition's div (the
   "riding along" case above), **split it out** rather than leaving both
   concepts sharing one id --- each gets its own div, its own id, and its
   own example.

## Relationship to other checks

- **[`definition-crossrefs.md`](definition-crossrefs.md)** --- assumes the
  defining div exists and checks that mentions link to it, in the right
  order. This check runs first, conceptually: it catches the case where
  prose reads like a definition but never became a div at all, so there's
  nothing yet for `definition-crossrefs.md` to track.
- **[`forward-references.md`](forward-references.md)** --- a concept
  without its own div can't be crossref'd, which is exactly what forces an
  author into a forward-pointing phrase ("the definition below") instead
  of a working link. Fixing this check's findings often removes a forward
  reference for free.
- **[`fact-check-prose.md`](fact-check-prose.md)** /
  **[`check-info-quality`](../../skills/check-info-quality/SKILL.md)** ---
  sibling prose-rigor checks; run this alongside them on a diff that
  introduces new technical content.
