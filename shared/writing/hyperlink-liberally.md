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
  Always format issues, pull requests, commits, discussions, workflow runs, and review comments as clickable hyperlinks to their forge URLs (e.g. [PR #4066](https://github.com/Morrison-Lab/ai-config/issues/4066)), never as bare numbers, review ids, or SHAs.
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
