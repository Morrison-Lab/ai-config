# Hyperlink liberally

Make it easy for readers to find more information by hyperlinking liberally.
When writing documentation, guides, READMEs, rules, skills, memories, PR descriptions, issue comments, commit explanations, or agent replies, connect named concepts, tools, artifacts, and references to clickable URLs.

A plain-text mention --- "use Quarto", "per the strict merge policy", "filed issue 4066", "tested with testthat" --- forces the reader to leave the document, switch to a search engine or terminal, formulate a query, and guess whether the search result they found is what the author actually intended.
A hyperlink provides 1-click access directly to the authoritative documentation, repository, definition, or artifact, preserving reader momentum and eliminating ambiguity.

## What to hyperlink

- **External tools, packages, and frameworks.**
  When citing an external tool, library, package, standard, or service, link to its official documentation or upstream repository on first or key mention (e.g. [Quarto](https://quarto.org), [testthat](https://testthat.r-lib.org), [CommonMark](https://commonmark.org)).
- **Internal rules, skills, fragments, and memories.**
  When citing a policy, operating rule, skill, memory file, or repository script, provide a clickable relative markdown link to the file (e.g. [`strict-merge-policy`](../workflow/strict-merge-policy.md), [`use-preferred-style`](../../skills/use-preferred-style/SKILL.md), [`check-context-closure.py`](../../scripts/check-context-closure.py)).
- **Forge artifacts.**
  Always format issues, pull requests, commits, discussions, workflow runs, and review comments as clickable hyperlinks to their forge URLs (e.g. [issue #4066](https://github.com/Morrison-Lab/ai-config/issues/4066), [PR #4152](https://github.com/Morrison-Lab/ai-config/pull/4152)), never as bare numbers, review ids, or SHAs.
  See [`link-forge-artifacts`](link-forge-artifacts.md).
- **Technical terms and formal concepts.**
  Hyperlink technical terms and named concepts on first mention to their defining section, glossary anchor, or canonical specification.
  See [`definition-crossrefs`](definition-crossrefs.md).
- **Error messages, diagnostic codes, and flags.**
  When discussing a compiler warning, linter rule, or CLI flag, link directly to the manual page or rule documentation explaining its behavior and remediation.

## Best practices

- **Use informative anchor text.**
  Wrap the name of the subject or entity in the link (e.g. [`strict-merge-policy.md`](../workflow/strict-merge-policy.md) or [Quarto documentation](https://quarto.org)).
  Avoid vague link labels such as "here", "click here", "link", or pasting bare URLs.
- **Link on first or key mention.**
  Link when a concept, tool, or document is first introduced or when it serves as the central reference for an argument or step.
  Avoid linking the exact same common term in every single sentence of a paragraph, which creates visual noise without adding information.
- **Use relative markdown links for repository files.**
  Keep links to files within the repository portable by using relative paths rather than absolute filesystem paths or forge URLs.
- **Preserve semantic line breaks and ASCII punctuation.**
  Write one sentence per line (SemBr) and use ASCII punctuation (`---` for em-dashes).

- **Do:** hyperlink tools, libraries, internal rules, forge artifacts, and technical terms to make finding more information effortless.
- **Do:** use informative anchor text naming the referenced entity.
- **Don't:** leave references to external packages, internal policies, or forge items as plain unlinked text.
- **Don't:** use bare URLs or uninformative labels like "here" as anchor text.

## A request to link one thing is a request to sweep the page

When someone asks for one missing link on a page, the missing link is a sample of a gap, not the whole gap.
Read the whole page for every other named organization, person, tool, book, or concept that has no link, and add those in the same change.
Check each target URL before adding it.

Observed on [Morrison-Lab/morrison-lab.github.io#7](https://github.com/Morrison-Lab/morrison-lab.github.io/pull/7) (2026-10-13).
When asked to link "SeRG", the first pass searched only for other SeRG mentions.
It missed UC Davis, Kristen Aiemjoy, two cited books, Quarto, GitHub Actions, and R packages, all on the same short page, and the user had to ask twice more.

- **Do:** after adding the requested link, reread the whole page and link every other unlinked name it carries.
- **Do:** open each new target URL and confirm it names the entity before linking it.
- **Don't:** search only for other mentions of the term the user named and report the page done.

## Link a term where the sentence names it, not in a trailing parenthetical

A list of definition links after the sentence --- "(definitions: bias, variance, irreducible error)" --- makes the reader find each term twice, once in the sentence and once in the list.
Put each link on the word the sentence already uses, once per passage as in [`definition-crossrefs`](definition-crossrefs.md).
A single crossref attached to the term it defines, such as "(@def-hessian)", is a different construction and stays;
a parenthetical list of them does not.

The test is observable: does a sentence in the passage use the term as a word?
If so, link it there, rewriting the sentence in prose when the term sat only in a formula.
If the term occurs only as a math label (for example an underbrace in a displayed equation), keep a "Hint: see the definitions of ..." line.

Observed on a private `Morrison-Lab/mlg` exercise and exam question (issue 203, merged in pull request 204 for `Exams/2026-fall-morrison/midterm1.qmd` and `midterm1-practice.qmd` and drafted in pull request 205 for `exercises/generalization/_exr-kfold-cv-feature-count.qmd`, 2026-10-26;
no link is given because the repository is private, per [`media-links-beside-content`](media-links-beside-content.md)).
Midterm 1 question 3(c) wrote the decomposition as a formula and listed the three terms in a parenthetical after it, and Ezra asked for the links in the sentence itself:

- **Before:** `Each model's expected squared error on a new point decomposes into $\text{bias}^2 + \text{variance} + \text{irreducible error}$ (definitions: [bias](https://morrison-lab.github.io/lds/chapters/big-ideas.html#def-bias), [variance](https://morrison-lab.github.io/lds/chapters/big-ideas.html#def-variance), [irreducible error](https://morrison-lab.github.io/lds/chapters/big-ideas.html#def-irreducible-error)).`
- **After:** `Each model's expected squared error on a new point is the sum of three terms: its squared [bias](https://morrison-lab.github.io/lds/chapters/big-ideas.html#def-bias), its [variance](https://morrison-lab.github.io/lds/chapters/big-ideas.html#def-variance), and the [irreducible error](https://morrison-lab.github.io/lds/chapters/big-ideas.html#def-irreducible-error).`

In general practice, place the link on the term where the sentence uses it and sweep the document for remaining parenthetical link lists:

- **Do:** link each term at its mention, and find other instances with `grep -n -E '\((definitions?|see)[: ]' <files>` over the document you are editing.
- **Don't:** append a parenthetical list of links after a sentence whose words could carry them.
