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

**When a reviewer calls a citation hallucinated, test it before conceding ---
the alleged correction can be the hallucination.** A reviewer asserting what
the "known" URL patterns or the source's "typical" phrasing are is making a
factual claim from memory,
and it deserves the same verification as the citation it challenges.
Both of these are decidable in one command,
so decide them rather than arguing (or capitulating) from recollection:

- **A docs URL's canonicality: check the target page's own `redirect_from`
  frontmatter.**
  This one is specific to `github/docs` (and other sites using the
  Jekyll-inherited `redirect_from` convention),
  not a general property of docs sites with public source ---
  other generators use their own redirect mechanisms, so find the site's
  before assuming this shape.
  In `github/docs`, fetch the content file and read its frontmatter:
  every path listed under `redirect_from` is by definition one that
  redirects *to* that page,
  so if the reviewer's proposed "correct" URL appears in that list,
  it is a superseded path and the cited one is current.
  A `github/docs` content file's path also maps directly to its URL
  (`content/<path>.md` -> `/en/<path>`),
  so a successful raw fetch of the source is itself evidence the URL resolves.
- **A quotation's fidelity: exact-substring grep, not a read-and-judge.**
  `grep -c "<the quoted sentence>" <fetched source>` settles
  verbatim-or-not outright,
  and grepping the reviewer's proposed alternative wording in the same file
  often shows it appears zero times.

**Then fix what the challenge was really pointing at.**
A wrong finding can still mark a genuine weakness.
One case worth checking: the quoted sentence lives in a
**version-conditional fragment**,
so a reader who finds the other branch first sees different wording
and reasonably concludes the quote was misremembered.
Name the exact source file and the branch the quote comes from,
and say whether the claim survives the other branch's wording.
That converts a citation a reader has to trust into one they can check.
(`ai-config#697`, 2026-07-24: a review flagged a `docs.github.com` URL as
"likely fabricated" and a quote as "likely a paraphrase".
The frontmatter listed both of the reviewer's proposed URLs as
`redirect_from` entries for the cited page,
and the quote grepped as verbatim while the reviewer's suggested phrasing
appeared zero times ---
but the quote did sit in a `{% ifversion %}` branch,
so naming the fragment and branch was a real improvement.
The reviewer retracted both findings.)

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

**Verifying a source's TITLE PAGE verifies its metadata, not its findings.**
A distinct instance of the same mismatch, and an easy one to miss because the
verification genuinely happened: checking a PDF's first page confirms authors,
year, journal, and title --- everything a bibliography entry needs.
It confirms nothing about what the paper *found*.
So a bibliography swept clean by a
title-page pass can sit under prose making confident, wrong claims about those
same papers' results, and the sweep's success is what makes the prose feel
checked.

Classify each citation-backed claim before deciding what to read:

- **Metadata claim** ("Smith et al. (2020) studied X") --- title page suffices.
- **Findings claim** ("Smith et al. found X dominates Y", "the effect was 22
  percentage points") --- requires the results section, and a numeric claim
  requires the sentence containing the number.

Quote the supporting sentence in the PR or a comment when a findings claim
lands.
That makes it checkable by reading, which matters doubly where the reviewer
cannot open the PDF at all.

(ucdavis/bcs#422: a manuscript claimed a scoping review "found IP weighting
with pooled logistic regression to be the dominant estimation strategy".
The paper reports the hazard ratio as the most common effect measure,
estimated by Cox in 61% of studies against pooled logistic regression's 35%,
with confounding handled predominantly by conditioning --- roughly the opposite.
It survived three review rounds.
An earlier pass had verified that same
`references.bib` against the PDFs' title pages and corrected two wrong author
lists, so the citations *were* checked --- just not for this.
The reviewer that flagged it named the reason precisely:
"this claim is about the paper's findings, not its metadata".)

## A permalink that resolves can still cite the wrong content

The same metadata-versus-content split has a link-checking form, and there
the false signal is stronger: an HTTP `200` feels like verification.
It is not.
`200` proves only that *something* is served at that URL, never that what is
served supports the claim the citation makes.

This bites hardest when pinning a commit for provenance ("derived from
`<repo>` at `<sha>`").
The instinct is to pick a commit near the change that removed the file, and
that is exactly the wrong neighbourhood: a removal is often the *second* step
of a migration whose first step already gutted the file.
Pin to the last commit whose **content** matches, and confirm by reading the
file at that SHA, not by checking that the URL loads.

The generalization, for any automated link sweep: a status code answers
"reachable", and reachability is not accuracy.
Anything asserting provenance, a quotation, or a specific claim needs the
target opened.

(UCD-SERG/serocalculator#619, 2026-07-28: a workflow comment was repinned from
a deleted-on-`main` file to `5d1efae04f`, verified `200`, and shipped.
Review fetched the file at that SHA and found it had already been reduced to a
one-line delegator by the first half of the same migration, hours before the
deletion --- so the citation resolved while pointing at nothing resembling
what the file was derived from.
`1865ad02a6`, the last commit carrying the standalone workflow, was the right
pin.
The PR's whole purpose was citation accuracy.)
