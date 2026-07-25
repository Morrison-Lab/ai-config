When explaining a concept or writing documentation, **cite claims to their
primary or authoritative source, thoroughly and by default** --- not only
when asked. This applies to chat explanations and to any content added to
docs, READMEs, or manuals (e.g. lab-manual chapters).

- Prefer the primary source: official docs, a spec, a standards body, the
  project's own repository --- over a secondhand summary.
- For well-established general concepts, a solid encyclopedia article (e.g.
  Wikipedia) is an acceptable citation.
- Link the *first* mention of a term or product, not every repetition.
- A "further reading" link is appropriate even for claims that don't strictly
  need a citation, when it would help a reader go deeper.
- Skip a citation when the source would be redundant with one already given
  in the same passage, or when the claim is about this session's own visible
  tool output (nothing external to cite).

This is a default, not an absolute rule: don't let a citation search block a
plain answer to a simple question, and don't cite something so well-known
that a link would look padded.

A citation that resolves but doesn't actually back the claim it's attached
to is still a defect --- the `check-info-quality` (`ciq`) skill's
misleading/out-of-context check catches that case; run it on content with
citations alongside `purge-hallucinations` (which only checks the citation
*exists*).

**The authoring-side counterpart: write citations from a fresh fetch of the
target, not from memory.** A remembered URL-plus-statement pairing goes
stale when the docs reorganize: the citation can be historically correct
(the page once said it) and still be a defect today, because doc sites move
statements between pages while keeping old URLs resolving via redirects ---
so the remembered URL lands on a live page that no longer contains the
claim. Fetch the cited target at writing time and confirm the statement is
actually there (when a docs site is blocked by a network policy, use its
source repo instead --- see the `github/docs` bullet in `memories/claude-code.md`). (gha#272: the
`GITHUB_TOKEN` no-retrigger claim was cited to GitHub's
`automatic-token-authentication` page, whose successor no longer carries the
statement --- it had moved to the "Triggering a workflow" article; caught by
review.)

**Mirroring a precedent's citation style doesn't guarantee the new citation
holds.** When a new section is modeled on an existing one --- same structure,
same "this is a global standing rule from X (see file Y)" closing sentence
--- read the *newly cited* file's own text before reusing that phrasing, not
just the precedent's. The precedent's citation can be self-sufficient (the
cited file's own opening sentence already makes the claim) while the new
file doesn't say what's being attributed to it --- a real gap, not a
copy-paste nitpick. (Caught by `@claude` review on `gha`#209: item 5 mirrored
item 4's "cite the specific `shared/writing/*.md` file" pattern, but
`shared/writing/ai-tells.md` only framed itself as a pre-send self-check,
while `shared/writing/fact-check-prose.md` --- the file item 4 cites --- opens
by stating the review-time claim directly. Fixed at the root in
`ai-config`#445 by adding the missing framing to `ai-tells.md` itself, making
the fragment self-sufficient rather than just softening the downstream
citation.)

**Match the claim's strength to what was actually verified.** Fetching a
file's *current* content only supports a present-tense claim ("X currently
does Y") --- it does not support a comparative or temporal claim ("X predates
Y's migration", "X was written before Z") unless commit history or dates were
also checked. Reaching for a stronger word ("predates", "originally",
"since") than the evidence supports is the same overclaiming failure as a
fabricated citation, just milder --- caught by `@claude` review on gha#180: a
raw-fetch confirming one repo's config still inlines its own rules (unlike
another repo's current shared-package-based one) was accurate, but the added
claim that the first "predates" the second's migration wasn't established by
that fetch alone.
