# Check the renders, not just the source

In a repo that publishes a website or a book, the deliverable is the rendered page.
A `.qmd` or `.md` diff can be entirely correct while the published page is broken, and the source is the artifact you will instinctively read.

This is [`verify-the-right-artifact`](verify-the-right-artifact.md) applied to rendered output: the diff in hand cannot show the claim false, because the claim is about a page the diff does not contain.

## What only the render shows

- A macro that never expanded, because it was never defined.
- A citation key with no bib entry.
  Pandoc renders it as `key?` inside the link text; nothing goes red.
- A crossref that resolved to nothing (`?@fig-...`).
- A list that lost the blank line above it and rendered as a paragraph beginning with a literal `-`.
- A KaTeX error swallowed into a `katex-error` span.
- **The source being fixed while the deployed page is not**, because a stale freeze cache served the previous render.

That last one is the one to internalize, because every other check in this corpus passes on it.
On `d-morrison/rme` #1134 and #1138 (2026-09-07) the source was verifiably correct and the deployed preview still carried the pre-fix content: `_subfiles/` were edited without that repo's `clear freezer` label, so the build restored a freeze cache keyed to the commit before the fix.
Reading the diff passes.
Reading the render does not.

**No pattern scanner detects that case, including the one this fragment ships.**
Staleness is a relation between a page and the commit it should reflect, not a property of the page, so a stale render that happens not to trip one of the five patterns reports clean --- which is most stale renders, since a wording change trips nothing.
The pattern checks caught the rme instances only because the pre-fix content there contained an undefined macro and an unresolved citation.

Check staleness directly instead, and it takes one line: **grep the rendered page for the specific thing your diff changed.**
Search for the new text, confirm it is present;
search for the text you removed, confirm it is gone.
That is a positive and a negative control on the one page that matters, and it is what actually settled #1134 and #1138.

## What already existed

Two pieces of this were already in the corpus, and this fragment adds to them rather than replacing them.

[`fact-check-prose`](../writing/fact-check-prose.md)'s "Confirm a rendered page carries your commit before reading anything off it" section already gives the staleness check described above --- pick a string your commit introduced, search the fetched page for it.

`scripts/check-rendered-references.py`, driven by the [`check-rendered-refs`](../../skills/check-rendered-refs/SKILL.md) skill, already finds unresolved crossrefs and missing citation keys in local rendered artifacts, with fence stripping and footnote handling.
For a local `_site/` tree, prefer it.

What is new here is the other three failure classes --- a list that lost its blank line, a KaTeX error, an unexpanded macro in prose --- and fetching a URL, so one command covers a deployed preview.

## The instrument

```bash
python3 scripts/check-rendered-page.py <url-or-file> [<url-or-file> ...]
```

Exit 0 when every target is clean, 1 when any check fires, 2 on a fetch error.
It takes a PR-preview URL, a published URL, or a local `_site/` file, so the same command covers a local render and a deployed preview.

Run it on the pages your diff can reach, which for an edited subfile means the chapter that includes it, not the subfile.

## Five findings worth carrying, each measured by getting it wrong

**The commonest shape of a bug is rarely the one you first write the detector for.**
The broken-list check began anchored at the start of a paragraph, which catches a list with nothing before it.
Pandoc's actual output for the usual mistake is different: a list normally introduces something, so the lead-in sentence and the items fold into one paragraph with the marker in the middle.
The first detector missed every instance of the commoner form.
Get real output from the renderer before deciding what to match.

**A false-positive rate sinks a checker faster than a gap does.**
A text-level scan for `word?` as an unresolved citation matched ordinary English --- `plausible?`, `measurement?` --- eleven times on a page with no citation problem at all, and a regex strip of KaTeX reported twenty unexpanded macros on the same clean page, because KaTeX nests spans several deep and a non-greedy `<span class=katex>.*?</span>` stops at the first inner close.
Both needed structural answers: a parser for the math, and markup matching for the citation.

**A third instance of the same class, found in review rather than by running the checker.**
The unexpanded-macro detector was `\[a-zA-Z]{2,}` --- any backslash followed by two or more letters --- which matches every segment of a Windows path, so a page whose prose says `C:\Users\Documents\myfile` reported three unexpanded macros.
Structure is no help here, because a path and a control sequence are the same characters;
what separates them is the character BEFORE the backslash.
A macro follows whitespace, `$`, `{` or start-of-text, while a path segment follows a drive letter, a colon, or the previous segment's name, so a negative lookbehind over that class is the discriminator.
It costs one gap on purpose: the second macro of `$\hat\beta$` is preceded by a letter and goes unreported, while the first still fires --- so a count is lost and never a verdict.

**A detector wide enough to match a sibling's defect misclassifies rather than misses.**
The `?@` citation scan had no shape restriction, so `?@fig-missing` was reported as an unresolved CITATION and an unresolved CROSSREF at once.
Nothing is scored falsely clean by that, which is why it reads as cosmetic;
the cost is that it names the wrong defect kind and sends the reader to the bibliography over a crossref problem.
The crossref prefixes now live in one constant that the crossref check matches and the citation check subtracts, since two copies of that list drift silently --- a prefix in one and missing from the other restores the double-report for exactly that type.
The subtraction keys on the prefix plus a hyphen rather than the whole key, so a bibtex key that merely begins with one (`?@defoe1990`) is still reported;
swallowing that would be a false CLEAN, the one direction this checker must not fail in.

**Suppressing noise by excluding a class can silence the defect itself.**
The obvious fix for the citation noise is to skip `class="citation"`.
That is where Quarto puts a literal `?@fig-x`, so the exclusion made the checker report a known-broken preview as clean.
Exclude the bibliography (`csl-entry`) instead.
A `tippy` exclusion for the hover popups was tried and removed: that markup is injected client-side, so it never appears in HTML fetched by curl or read from `_site/`, and the entry could not match anything.

- **Do:** check the rendered page for any change to a repo that publishes a site or book.
- **Do:** check the DEPLOYED preview, not only a local render, when the repo caches renders --- they can disagree.
- **Do:** grep the render for the exact text your diff added and removed, since that, and not the pattern scan, is what detects a stale build.
- **Don't:** treat a correct source diff as evidence the published page is correct.
- **Don't:** read a clean run of the pattern checker as evidence the page is current;
  it answers a different question.
- **Don't:** decide what a detector should match from the source you expect;
  render the broken case and match what the renderer actually emits.
