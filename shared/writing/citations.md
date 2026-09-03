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

**Second occurrence, 2026-09-02 on `Morrison-Lab/gha#811`, where the citations
were never fetched at all rather than remembered from an earlier fetch.**
Two `github/community` discussions were cited for a GitHub Actions deadlock
message, and neither carries it: #30708 reports
`Canceling since a higher priority waiting request ... exists`, whose cause is
a `github.workflow` naming collision, and #43510 is about the default two-run
concurrency limit.
[rhysd/actionlint#538](https://github.com/rhysd/actionlint/issues/538) does
carry it, verbatim:
`Canceling since a deadlock for concurrency group 'ci-939eda80...' was detected
between 'top level workflow' and 'build-image'`.
The rule above already prescribes the remedy.

What is new is the **tell**, because this section states its cause as staleness
--- a pairing that was once right --- and a citation that was never checked
matches none of that wording.
The cause here is that the message was *known to be real*, so the URLs were
selected to support a claim already believed rather than read to establish one,
which feels like sourcing rather than like asserting.
The round-two commit that retracted them, `385d4f43`, states it plainly: "I
cited two community discussions for the deadlock message without opening
either."

- **Do:** fetch a citation you are adding to support a claim you already
  believe, on the same terms as one you are adding to establish a claim.
- **Don't:** treat confidence in the underlying claim as evidence about the
  URL --- a real message can be cited to two pages that do not carry it.

**The other authoring-side counterpart: run the exact-substring check on your
own quotation, not only on one a reviewer disputes.**
The bullet further down
this file gives the deciding instrument --- `grep -c "<the quoted sentence>"
<fetched source>` --- but offers it *defensively*, for testing a citation
someone has called hallucinated.
It decides the authoring case just as exactly, and costs one command at the
moment you paste the quote.

**Run it on normalized text, not on the raw files, or it returns a false
negative on the very quotes you most need to check.**
That bullet does not say so, and this section originally attributed the
qualifier to it, which was wrong twice: the bullet is silent, and whitespace
alone is not enough.
`grep` is line-oriented, so a quotation spanning two source lines never
matches.
Source formatting adds more: a `man` page justifies with double spaces, and
your own copy usually adds Markdown code spans the source has no idea about.
Normalize whitespace **and** inline markup on both sides, per
[`address-every-comment`](../workflow/address-every-comment.md)'s rule that
the same normalizer must run over the needle and the haystack:

```python
norm = lambda s: re.sub(r"[\s`*_]+", " ", s).strip()
norm(quote) in norm(source)
```

The defect it catches there is a **silent elision**: a clause dropped from the
middle of a quoted sentence with no ellipsis marking the cut, so the result
reads as contiguous verbatim text while never having appeared in the source in
that form.
This is not cherry-picking, which selects a genuinely contiguous span and is
honest about its boundaries; here the contiguity itself is fabricated, and the
substring test is what separates the two.
The remaining words can each be the source's own and the sentence still be one
the source never wrote.

Reading the two side by side is what fails, because a spliced quote is
*designed* to scan as fluent --- the elision is invisible precisely when the
splice is clean.
So run the check rather than re-reading, and mark any cut you do want with an
ellipsis.

- **Do:** substring-test a quotation against its fetched source, with
  whitespace **and inline markup** normalized on both sides, before pushing
  it.
- **Do:** mark a deliberate cut with an ellipsis, so the quote stops claiming
  a contiguity it does not have.
- **Don't:** settle a quotation's fidelity by reading it against the source; a
  clean splice is exactly the case that survives that.
- **Don't:** normalize whitespace alone and call it done --- the worked
  example below is a quotation that test rejects and the source contains.

(Morrison-Lab/ai-config#1110, 2026-08-03: a `man grep` quotation dropped "the
exit status is 0" from the middle of its source sentence, with no ellipsis.
Caught in review, and confirmed mechanically once the normalization above was
right.
That example is also this section's own worked case for why the raw
instrument is not enough.
Measured against GNU grep 3.7's man page, where the sentence occupies
`EXIT STATUS` lines 440 to 442: literal `grep -c` returns **0**, a
whitespace-only normalization still returns **False** because the quotation
adds Markdown backticks the man page does not have, and only whitespace plus
markup returns **True**.
The same rule holds for a repo artifact that claims to be verbatim; see
[`fixtures-are-not-evidence`](../workflow/fixtures-are-not-evidence.md), where
the deception runs by addition rather than by deletion.)

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

**A citation generated from the cited file's *name* is the sharpest form of
this, because the name is exactly what you did not check.**
The bullet above catches a citation whose *phrasing* was mirrored from a
precedent.
This one catches a citation whose *target* was chosen from what the file's
name evokes: you want an example of pattern X, a file's name reads like X, and
you cite it without opening it.
It is worse in a corpus of well-named skills and fragments, where a name
reliably suggests a behaviour --- so "the adversarial one" resolves to
`skills/opposition-research/SKILL.md` and "the fan-out one" to
`skills/ardia/SKILL.md` on nominal fit alone, and the citation reads as apt
while asserting a content claim nobody verified.
The check is one grep against the cited file for the behaviour you are attributing to it, per [`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)'s rule to mark which claims are measured and which are recalled, and cite the recalled ones.
A zero-hit result is the tell that the name carried the citation.

- **Do:** grep the cited file's own text for the behaviour you cite it as an
  example of, before writing the citation.
- **Do:** treat a skill's or fragment's name as a hypothesis about its
  content, not as evidence of it.
- **Don't:** reach for a file as an example of pattern X because its name
  evokes X --- the name is the one thing you have not read.
- **Don't:** let a citation's nominal aptness stand in for checking that the
  target actually exhibits the pattern.

(Morrison-Lab/ai-config#1205, 2026-08-05: a new `shared/workflow/agent-teams.md`
cited `skills/opposition-research/SKILL.md` as the headless counterpart of
adversarial/competing-hypothesis debate, and `skills/ardia/SKILL.md` as doing
per-dimension review fan-out over security, performance, and coverage lenses.
Neither holds.
`grep -ciE "adversar|disprove|hypothes" skills/opposition-research/SKILL.md`
returns 0 --- that skill mines community demand in blind parallel, and the
adversarial-verify pass it was reaching for lives in
[`when-to-orchestrate`](../workflow/when-to-orchestrate.md) --- and
`grep -ciE "dimension|lens|security|performance|coverage" skills/ardia/SKILL.md`
returns 0, since `ardia` fans out one worker per PR, while the per-dimension
skill is `skills/grade-work/SKILL.md`.
The reviewer named the mechanism exactly: "this reads as a case of the citation
being generated from the *name* 'opposition research' rather than from the
skill's actual content."
Both were accepted and fixed.)

**A sibling entry cited by POSITION rather than by name is the same defect at
its cheapest-to-check and least-checked, because proximity reads as
already-known.**
The section above catches a citation whose target was chosen from a file's
name.
This catches one chosen from where it sits: "the sibling bullet above", "as the
previous section shows", "per the entry directly preceding this".
No name is involved, so nothing about the phrasing prompts a lookup, and the
target is usually on the same screen --- which is exactly what makes re-reading
it feel unnecessary.
What makes it costly is invisibility rather than frequency: a reviewer has to
open the neighbour to catch it, and a reader almost never does.
(Measured on `shared/`, markdown-link citations outnumber position-referring
phrases 823 to 225, so this is *not* the commonest citation type --- an earlier
draft of this very entry said it was, unmeasured, and review caught it.
The rule below is what would have caught it first.)

**Check it against the instances you personally hold, not only against the
cited text.**
That is the half a grep will not supply.
A generalizing sentence is usually written from a *sense* that some pattern
varies, and the instances actually in hand can all point the other way --- in
which case the claim had no supporting case at all, rather than a mis-cited
one.
So before writing "X varies" or "the sibling shows the reverse", enumerate the
instances you have observed and check that at least one of them is the case you
are claiming.
When none is, withdraw the generalization rather than hunting for a precedent
to prop it up: stating that a direction is *not established* is accurate, and
the durable half of an entry rarely depends on the generalization anyway.

- **Do:** re-read a sibling entry you cite by position, with the same grep you
  would run on a file cited by name.
- **Do:** enumerate your own observed instances before publishing a claim that
  a pattern varies, and require one to be the case you assert.
- **Don't:** treat adjacency as verification --- a neighbour on the same screen
  is the citation least likely to be re-read and most likely to be assumed.
- **Don't:** keep a generalization alive by searching for a supporting
  precedent; withdraw it and say which direction is unestablished.

(Morrison-Lab/ai-config#1506, 2026-08-16, review round 1: a new bullet in
`memories/github-mcp-tools.md` recording that a raw merge 403s while the MCP
merge succeeds closed with "the generalizable part is the direction, since the
sibling bullet above has the MCP tool 403ing where raw works."
The sibling `actions_run_trigger` bullet, forty lines up in the same file,
shows nothing of the kind: every 403 it records is MCP-side for want of
`actions: write`, its fallbacks are a push or a human rather than a raw call,
its one recorded success is itself an MCP success, and `"raw" in
sibling.lower()` is `False`.
Worse than a mis-citation: one instance cannot establish that a direction
varies, and the merge was the only client split actually on record --- the
sibling never attempts a raw call at all, so it is silent about raw rather than
a counterexample to it.
Withdrawn in `50aea145` in favour of stating that neither direction is
established, which left the entry's durable half untouched.)

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

**That instrument settles a QUOTE and cannot settle a DERIVED FIGURE.**
A percentage, ratio, or total computed from quantities the source prints
appears nowhere in its text, so an exact-substring check returns zero whether
the attribution is sound or invented.
Derive it before calling such a citation unsupported, per
[`grep-is-not-coverage`](../workflow/grep-is-not-coverage.md)'s "A derived
figure is supported by a source that never prints it".

**Then fix what the challenge was really pointing at.**
A wrong finding can still mark a genuine weakness.
One case worth checking: the quoted sentence lives in a
**version-conditional fragment**,
so a reader who finds the other branch first sees different wording
and reasonably concludes the quote was misremembered.
Name the exact source file and the branch the quote comes from,
and say whether the claim survives the other branch's wording.
That converts a citation a reader has to trust into one they can check.

## A paraphrase-only attribution is invisible to every check above

Everything above verifies a **quote**.
`grep -c "<the quoted sentence>"` settles fidelity outright, splice detection
reads the two side by side, and the version-conditional case asks which branch
the wording came from.
All three need a quoted sentence to operate on.

So the citation that carries no quote passes all of them by default.
"`upstream-issues` already draws the line this needs",
"the lab manual requires this",
"`fail-fast` says the same thing" ---
each attributes an argument to a source without reproducing anything from it,
so there is nothing to grep and nothing to compare.
The instrument does not fail; it never engages.

It is more dangerous than a misquote, because a paraphrase **launders**.
A quote that has drifted still shows a reader the words and lets them
disagree.
A paraphrase reports the source's *conclusion* in your own voice, so a reader
gets your reading of it with the source's authority attached, and the only way
to check is to go read the file --- which is exactly what the citation was
offering to save them.

The failure is not carelessness about a source you never opened.
The likelier case is the one that feels safest: you **did** read the file, a
sentence in it genuinely bears on the topic, and what you wrote is what you
took away rather than what it says.
Attribution drifts between reading and writing, and rereading your own sentence
cannot detect it, because it is a claim about the *other* file.

**So quote the sentence you are relying on, or attribute nothing.**
When a source is worth citing for an argument, one clause of it is worth
pasting --- and the paste is what makes every instrument above apply.
When you cannot find a sentence to quote, that is the finding: make the
argument in your own voice and cite the source for what it does supply.

Two mechanical checks, both cheap:

- Grep the cited file for the **claim's own load-bearing words**, not for the
  topic.
  A citation asserting a source weighs merge cost is refuted by
  `grep -oiwc` returning zero for `merge`, `wait`, `cost`, and `land`.
- Read the cited file's sentence on the subject and check its **direction**.
  A source can address your topic and conclude the opposite, which is the case
  a topic-level grep confirms rather than catches.

- **Do:** paste the sentence you are attributing an argument to, so the
  quote-fidelity instruments above can run at all.
- **Do:** grep the cited file for the claim's load-bearing words before
  writing "already establishes" or "already draws the line".
- **Don't:** attribute a conclusion to a source in your own words --- that is
  the form no check above can see.
- **Don't:** treat having read the file as having verified the attribution;
  the drift happens between reading and writing.

(Measured 2026-08-21 on
[ai-config#1847](https://github.com/Morrison-Lab/ai-config/pull/1847).
A passage claimed `upstream-issues.md` "already draws the line this needs"
between a repo we administrate and a genuine external upstream.
That file's only sentence on the subject runs the other way ---
"The same judgment applies to repos we administrate, rather than being a
courtesy owed only to strangers" --- collapsing the distinction rather than
drawing it, and `merge`, `wait`, `cost`, and `land` each appear zero times in
it.
The file had been read; the attribution was still wrong.
A reviewer caught it, and both refuting commands took under a minute.)

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

## The user's own words are on disk, so quoting them is checkable

The instruments above assume the source is a file, a commit, or a page.
A sentence attributed to the user in conversation feels like none of those, so the natural conclusion is that no check applies and the quotation has to be trusted.

That conclusion is false, and believing it is the whole of this failure.
Claude Code writes every turn, the user's included, to a JSONL transcript under `~/.claude/projects/`.
This repository already knows: as of 2026-08-28, **29** non-test hooks reference it.

```bash
grep -l transcript_path hooks/*.py | grep -v /test- | wc -l
```

How many of those 29 go on to open the transcript is a question a one-line grep does not settle, since several hooks reach the file through a helper, so that second figure is not quoted here.
So the source is fetchable, and "it was only chat" is not a reason to skip the check but the belief that makes skipping it feel reasonable.

[`scripts/check-user-quote.py`](../../scripts/check-user-quote.py) runs it.

```bash
python3 scripts/check-user-quote.py "the sentence you are about to quote"
```

**What the script does not do is the design, and it took ten revisions to arrive at.**
It does not decide who wrote the phrase.
It prints every record containing it, with that record's shape, `origin.kind`, flags and `userType`, and stops.

The reason is that `message.role == "user"` is a **transport** role, not an authorship claim.
The same role carries harness continuations, stop-hook output, injected skill bodies, task notifications, tool results, compaction summaries, inter-agent coordinator messages, editor selections appended to the user's own prompt, another agent's `teammate-message`, and --- in a subagent's transcript --- the dispatch brief the assistant wrote.

Ten revisions tried to separate those from the user's own words, and every one of them certified harness or assistant prose at some point: classification on exclusions alone, then on the harness's `origin.kind` label, then per record, then per block, then per non-envelope region, then against a four-name tag list, then against a structural opener test.
Each was broken in turn --- by an appended reminder, a mid-block one, leftovers joined across a cut, a repeated opener, a literal closing tag inside injected content, a fifteen-name vocabulary against a list of four, a truncated opener, an entity-escaped tag (`&lt;system-reminder&gt;`, which is what the harness itself writes when it neutralizes control tags), a namespaced one, and an envelope split across two blocks.

The eleventh finding is what settled it: the harness's text **is not lexically identifiable**.
It can arrive with no `<` in it at all.
So a test returning *this is the user's* is a test that will eventually be wrong in the one direction that matters, and no amount of narrowing changes that --- which is the general lesson, and the reason this section describes a reporter rather than a checker.

The mirror failure is the half that is easy to forget, and it took its own round to surface.
Reading one record shape means reporting "no record contains it" over text the user produced, and a prompt lives in several: written to `queue-operation` at enqueue, becoming a `message` record at dequeue between 6 ms and eight minutes later, and carried by `last-prompt` and `attachment` besides.
The sharpest is a `tool_result` block, whose payload sits under `content` rather than `text`.
There were 2,451 in one root, every one inside a `role: "user"` record --- and an `AskUserQuestion` answer, which is where this corpus routes the user's **decisions**, exists in no other shape.
Skipping it meant reporting an absence over precisely the sentences most tempting to quote as authorization.

So the run reports which shapes it matched rather than asserting a number of shapes covered, since a count of shapes read is a completeness claim and the list of shapes matched is an observation.
Identical texts are collapsed, keyed on provenance as well as content --- merging on text alone showed a human-labelled record's harness twin's flags, which is the tool's whole product, silently wrong.

The exit codes keep apart a phrase found in no record (`1`) and a search that was degraded or impossible (`2` --- a missing or unresolvable root, an unreadable file or directory, an unparseable line, an empty phrase, or a crash).
Collapsing them turns "I could not look" into "the user never said it", which is the stronger claim and the wrong one.
Exit `0` asserts only that a record contains the phrase, which is the whole of what the tool now claims.

Two things make the quotation marks worse than an ordinary misremembering.

**They are the construction that tells a reader not to check.**
A paraphrase invites verification.
A quote asserts that verification already happened, which is why reaching for quotation marks is most tempting where they are least supportable.

This is the reverse of the ordering in the section above, and the two are consistent because the sources differ.
There the source is a document, so a drifted quote still shows the reader the words and lets them disagree, while a paraphrase launders the source's authority into your voice.
Here the source is a person who is not reading over your shoulder, so the quotation marks are the laundering:
they report a verification against a transcript nobody consulted.
Which form is safer depends on whether the reader can reach the source, and that is the axis to check before reusing either rule.

**A correction to a fabricated quote can itself carry one, and accepting it feels like diligence.**
Being told you misquoted someone produces an immediate impulse to publish the real sentence, and the replacement arrives from the same kind of recollection as the original.
Run the check on the correction too, before repeating it.

The remedy is the neighbouring section's, reached by a different route.
That section already carries the un-quotable branch:

> When you cannot find a sentence to quote, that is the finding: make the argument in your own voice and cite the source for what it does supply.

What differs here is only that the source can be searched, so which branch you land on is a question with an answer rather than a judgment.
Run the script and read what it returns.
Quote a record you have read and judged to be the user's own typed turn;
fall back to your own voice, marked as your reading --- "as I understood it" --- when no record is theirs, or when you cannot tell.

`CLAUDE.md`'s "Post in-chat feedback to the PR" is not an exception.
Its paraphrase is unquoted, so nothing there needs the transcript at all, and the required marker --- `_Posted by Claude Code (AI agent) --- not written by a human._` --- exists because such a comment is written in the user's voice under the user's login.
It discloses the author; it does not license a quotation.
If you do put the user's words in quotation marks in a PR comment, that is the case most in need of the script, since the person who could refute the attribution may not be reading the thread.

- **Do:** run `scripts/check-user-quote.py` before putting the user's words in quotation marks, and read the records it prints.
- **Do:** run it again on a correction that supplies the "real" sentence.
- **Do:** state your reading unquoted and attributed to yourself when no record is the user's, or when you cannot tell which is.
- **Do:** check a remembered quote hardest when it authorizes something you were about to do, which is the direction the one recorded case ran.
- **Don't:** read exit `0` as a verdict.
  It says a record contains the phrase.
  Which record, and who wrote it, is what the provenance beside it is for.
- **Don't:** read exit `2` as an absence.
  It says the search was degraded or never happened, and reporting that as "never said" is the substitution one level up.
- **Don't:** take a record's `origin.kind` as settling authorship.
  It is the harness's own label and the strongest signal available, and the CLI still rewrites it on some paths and stamps a relayed channel message with it on others.
- **Don't:** point at an issue or PR body you wrote afterwards from the same memory and call it the record.
  That is a copy of the claim, and it is the move that most looks like compliance.

The Claude Code paths above are specific to that harness.
On another agent, `--root` takes a transcript directory;
where no such directory exists, the source genuinely is unavailable and the neighbouring section's branch applies unchanged.

(2026-08-28, [ai-config#2538](https://github.com/Morrison-Lab/ai-config/issues/2538).
Driving [#2529](https://github.com/Morrison-Lab/ai-config/pull/2529) to a merge decision, I put a sentence of my own inside quotation marks and attributed it to the user.
It stated a criterion for merging on a light review verdict, which is the direction I was already moving.
A review pass flagged it and supplied what it gave as the user's actual message;
I repeated that into the issue and into the first draft of this section without checking either.
A second review pointed out that the transcript exists.
Running the script on the replacement --- "This is the last correction round: fix the five, push, report the head" --- returned 35 distinct texts across 38 records when this was written.
**Not one carries `origin.kind == "human"`**, which is the fact that settles it;
nine carry no flag at all, so "they were all flagged" would have been the convenient summary and a false one.
The unflagged ones are `queue-operation` and `attachment/queued_command` records --- the shape a user's *own* queued command uses --- carrying task-notification text, which is exactly why the reader is shown the provenance rather than a verdict.
The clause I fabricated appears in no record except my own later writing about it, so it is not reproduced here.
Every figure in this paragraph is a reading rather than a constant, and the categorical claims are the ones to re-derive rather than trust: an earlier version of this sentence asserted "every one of them is flagged", which running the command refutes.
The first two drafts of this section asserted the opposite premise, and ten subsequent revisions each shipped a check that certified something the user had not written;
every one passed its own local suite, and what refuted every one was executing it.)

## A permalink that resolves can still cite the wrong content

The paraphrase-only section's metadata-versus-content split has a link-checking
form, and there the false signal is stronger: an HTTP `200` feels like
verification.
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

## Cite an external result by name, never by its rendered number

The section above is a citation whose target is wrong.
This is the one where the target is right, the link is right, and only the
human-readable label silently stops matching what it points at.

Quarto and every comparable generator assign a theorem, a figure, or a
section its number from its **position in the document**, at render time.
The anchor is written by hand and is stable.
The number is derived and is not.
So `[Theorem 15](.../math-prereqs.html#thm-log-prod)` pins a stable anchor
to a volatile label, and a theorem inserted anywhere earlier in that book
renumbers this one, in a repository you do not watch, in a commit that
never mentions you.

Name the result instead, and let the anchor carry the reader:
`[the logarithm-of-a-product theorem](.../math-prereqs.html#thm-log-prod)`.
A name is a claim about content, so it survives renumbering.

**Nothing reports the drift**, which is why this needs a rule rather than
care.
The link keeps resolving, so a link sweep passes, which is the
reachability-is-not-accuracy point above arriving one step further out.
Both repositories also stay individually correct: the cited book renumbers
its own theorems properly, and the citing sentence is unchanged.
The defect lives only in the relation between them, so neither one's CI can
see it, and the citation goes on rendering as a confident, correctly linked
reference.

**The test is whether the cited document can be re-rendered.**
Apply it to any ordinal its generator assigns, not to theorems alone:
section and chapter numbers, figure, table, equation and listing numbers, a
numbered list item's position, and a page number in a document that is
rebuilt rather than published once.
A frozen artifact is the exception, because its ordinals cannot move.
So when a number is genuinely needed, cite a pinned version alongside it ---
a DOI, a tagged release, an archived snapshot --- so the number and the
artifact it was true of travel together, the same move as pinning a commit
for provenance above.

**Internal references are the same root defect with the opposite remedy**,
which is why they belong elsewhere rather than here.
A literal ordinal typed by hand is the failure in both cases.
Externally nothing will regenerate the number for you, so you name the
thing.
Inside your own document the renderer regenerates it on every build, so the
remedy is to write the crossref and never a literal:
[`definition-crossrefs`](definition-crossrefs.md) establishes that a Quarto
theorem-family crossref already emits the number as well as the type word,
and [`memories/preferences.md`](../../memories/preferences.md) makes the
same call for a computed figure,
preferring an inline R expression over a hard-coded analysis number so the
text cannot go stale on re-render.
Those two own the internal case; this section owns the external one.

- **Do:** cite an external result by its name, with the stable anchor as the
  link target.
- **Do:** pin the version beside the number on the rare occasion a number is
  needed, so a reader can reach the artifact it was true of.
- **Don't:** type an ordinal that someone else's renderer assigns --- its
  author can change it without touching anything of yours.
- **Don't:** read a resolving link as evidence the reference still reads
  correctly; the anchor and the number decay independently.

(UCD-SERG/serocalculator, 2026-08-09: `vignettes/methodology.qmd` cited
`[Theorem 15](https://d-morrison.github.io/rme/chapters/math-prereqs.html#thm-log-prod)`,
in *Regression Models for Epidemiology*.
That number is literally an ordinal position.
In `d-morrison/rme`, `thm-log-prod` is the 15th theorem div in
`chapters/algebra.qmd`, which is the first file `chapters/math-prereqs.qmd`
includes, so a theorem added above it in any earlier include moves it:
`grep -n '{#thm-' chapters/algebra.qmd | grep -n 'thm-log-prod'` returns
`15:279:`, whose leading field is the ordinal.
Fixed in `84d0052de` by naming the result rather than numbering it.)

## A bare `#NNN` is repo-relative, so a cross-repo citation is unresolvable by construction

Every rule above concerns a citation that resolves to the wrong thing.
This one concerns a citation that resolves to **nothing at all**, and it has a shape a careful author walks straight into: writing `#794` in this repo about a PR in another one.

A bare issue or PR reference is interpreted against whatever repository the reader is standing in.
In the authoring repo it renders as a link to that repo's own `#794` -- a real, unrelated item -- and in a plain-text read it is just a number.
Either way the reader cannot reach the thing being cited, and cannot tell a genuine citation from an invented one.

That last part is what makes it worse than an ordinary broken link.
A reviewer doing exactly the right thing -- grepping this corpus for the cited numbers to find their backing -- comes up empty and reasonably concludes the citation was fabricated.
So a true, checkable, first-hand incident gets reported as a possible hallucination, and the author has to spend a round proving the numbers were real.

The rule is therefore not "avoid cross-repo citations", which would be absurd in a corpus whose whole subject is work done in other repositories.
It is that a cross-repo citation has to carry enough to be **followed**:

- the repository, as `owner/repo#NNN` rather than `#NNN`; and
- where the backing actually lives, when the backing is a document rather than the forge item -- the file, and the section inside it.

The second half matters more than it looks.
This corpus keeps its case records in `*.cases.md` files, so a reader's instinct is to grep here for any cited incident.
When the record lives in the *consumer* repo instead, no amount of grepping here will find it, and only naming the file redirects the reader to where it is.

- **Do:** write `owner/repo#NNN` for anything outside the repository the text lives in.
- **Do:** name the backing document and section when the evidence is a file in another repo, not just the forge number.
- **Don't:** assume a number that resolves for you resolves for the reader -- it resolved because of where you were standing.
- **Don't:** read "the numbers are real" as a rebuttal --- a citation the reader cannot follow is defective whether or not its target exists.

(Measured 2026-08-22 on [ai-config#1989](https://github.com/Morrison-Lab/ai-config/pull/1989).
A hook docstring cited Lacaedemon/sparta#794, Lacaedemon/sparta#861, Lacaedemon/sparta#866 and Lacaedemon/sparta#1199 as its dated case record -- written here in the very form this section prescribes, because the bare numbers autolink to unrelated items of THIS repository wherever the file renders.
All four are genuine, and all four are backed in that repo's own `.claude/skills/sparta-demos/SKILL.md`.
The review flagged them as "unverifiable / misattributed (possible hallucination)" after grepping this corpus and finding nothing -- correct reasoning from what was available to it.
Fixed by naming the source repo, document and section rather than by dropping the numbers.)

## A quoted section title decays too, and the link resolving is what hides it

The section above ends by prescribing the **name** in place of the number, because the name is the stable half.
It is stabler, and it is not stable.
A heading renamed in place leaves the file where it was, so the link still resolves, the target still exists, and only the title quoted beside the link now describes a section that no longer goes by that name.

Nothing in this repo reports it, and that is a property of the instruments rather than an oversight.
`scripts/check-links.py` captures only the link **target**: its `\[[^\]]*\]\(([^)]+)\)` never captures the link text, since `[^\]]*` is a character class rather than a group and the one capture group holds the target.
It then splits any `#anchor` off the path before testing (`re.split(r"[#?]", target, maxsplit=1)[0]`), so its only assertion is `resolved.exists()`.
So the sweep that would plausibly catch a bad citation passes with the citation intact, which is worse than having no check at all: a green link run reads as having validated the reference.

Two things follow about where to look.
The decay is invisible to the **citing** file, since nothing there changed --- it is the *renaming* edit that breaks it, one file away, and that edit has no reason to grep for its own old heading.
So the obligation sits with the rename: when you retitle a section, search the corpus for the old title as a quoted string before you finish, per [`reorganize-prose`](reorganize-prose.md)'s rule that a move is authorship.
Use a whitespace-tolerant search rather than `grep`, since a quoted title long enough to be worth citing is long enough to have been split across a semantic line break --- [`memories/debugging.md`](../../memories/debugging.md)'s "An empty grep for one spelling is not evidence the concept is absent" owns that trap and its remedies.

- **Do:** search the corpus for a section's old title whitespace-tolerantly (`grep -Pz` with a `\s+` pattern, or `rg -U`) in the same edit that renames it, rather than a literal `grep`.
- **Do:** quote a title you are citing only if you have just read it, since a resolving link is no evidence about the text beside it.
- **Don't:** read a green `check-links.py` as covering a quoted title --- it discards link text and strips anchors by construction.
- **Don't:** expect the citing file's own review to catch this --- the edit that invalidated it happened somewhere else.

## A resolving DOI is not a correct DOI

`scdenney/open-science-skills`'s `citation-check` names a check this corpus doesn't state anywhere: "a DOI that resolves to a *different* real work is the single most common LLM-fabrication signature --- never treat 'DOI resolves' as 'DOI correct.'"
How common the pattern is, is their own measurement to defend;
the mechanism is checkable on its own terms and worth adopting regardless of the ranking.
A syntactically valid, registered DOI is a much higher bar than an invented one, so a fabricated citation is more likely to carry a real DOI that belongs to some *other* paper than to carry one that resolves to nothing.
So the check a citation needs is not "does this DOI resolve" but "does the resolved **title and authors** match *this* entry."
A resolving DOI pointing at the wrong paper passes every naive existence check while being exactly the error worth catching.
Verify against the DOI's own metadata --- Crossref's `https://api.crossref.org/works/<doi>` is a stable, unauthenticated lookup;
add `&mailto=<address>` to a *search* query (`works?rows=5&query.bibliographic=<title first-author year>`) for Crossref's documented "polite pool" of higher rate limits, and fall back to OpenAlex on an HTTP 429 --- rather than trusting resolution alone.

**The reason a wrong DOI stays hidden: a citation style can render every field except the one that would catch the error.**
BibTeX's classic styles --- `plain`, `unsrt`, `abbrv`, and `alpha`, shipped with the original 1985 BibTeX distribution, plus the similarly long-standing `apalike` --- predate the DOI system (launched 2000) by roughly fifteen years, so their format routines were never written to print a field that didn't exist yet.
A wrong or dead DOI in a `.bib` entry using one of these is invisible in the compiled PDF while author, year, title, volume, issue, and pages all render correctly and look checked.
**Verify the specific style actually in use against its own `.bst` source or documentation before assuming it omits (or prints) the field** --- this list is not exhaustive, and a style can be patched or forked to add DOI support.
The general lesson holds regardless of which style is in play: for a field a reader can see, a compiled read is itself a partial check;
for one they can't, only checking the field directly against its target catches an error there.

**Scope any `.bib` audit to the keys actually `\cite`d, not every entry in the file.**
A LaTeX document only prints entries reached by `\cite` (transitively, following any `\input`/`\include`), so an unused `.bib` entry can carry an arbitrary DOI with no reader ever seeing it render.
Auditing it spends effort on a defect nobody can encounter, and skipping this scoping step risks reporting false urgency on an entry the document never surfaces.

The mechanical half --- given a `.bib`, resolve each cited DOI and diff the
returned title and first author against the entry --- is a deterministic check
with an exact verdict, the shape
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) says should not
stay a prose instruction;
[`scripts/check_doi_bib.py`](../../scripts/check_doi_bib.py) implements it.

- **Do:** verify a cited DOI resolves to a work whose title and authors match the citation, not just that it resolves.
- **Do:** confirm which fields your document's actual citation style renders before trusting a compiled-PDF read to catch a wrong DOI.
- **Do:** scope a `.bib` audit to the keys the document actually `\cite`s.
- **Don't:** treat "the DOI resolves" as "the DOI is correct."
- **Don't:** assume a style renders (or omits) the DOI field without checking that style's own `.bst` or documentation.
- **Don't:** audit every `.bib` entry when only the cited subset can ever reach a reader.

(Pattern observed in `scdenney/open-science-skills`'s `citation-check`, CC BY-NC 4.0 --- pattern only, nothing copied;
ai-config#882.)

## A cross-reference by heading quotes the heading, or does not claim to

A cross-reference of the form "see the section of the same name in X" asserts that X carries a heading identical to the one here.
That is a claim about another file's text, and it is checkable by one grep --- so check it, and when the headings differ, say "the same rule" (or name the target heading verbatim) rather than "the same name".
The near-miss is writing "same name" from memory of what the sibling entry is *about*, which reads as a precise pointer and sends the reader looking for a heading that is not there.

- **Do:** grep the target file for the heading before writing "of the same name", and quote it verbatim when it differs.
- **Don't:** write "the section of the same name" as a synonym for "the corresponding section".

(Review finding on ai-config#2924, 2026-09-01: a `memories/delegation.md` entry pointed at `CLAUDE.md`'s "section of the same name", and the two headings differed;
reworded to "section of the same rule".)

## A figure carried from a source keeps the source's unit

A count restated from a source is a claim about the source, so the unit travels with the number.
"27 files whose signatures use the +4 form" and "27 signatures at +4" are different quantities, since one file can hold several, and only the first is what the cited comment measured.
The near-miss is compressing the source's phrasing for rhythm and letting the unit change under the compression, which reads as a paraphrase and is a new, unmeasured claim.

- **Do:** restate a cited figure with the noun the source counted, and re-run the count if you want the other unit.
- **Don't:** shorten "27 files with X" to "27 X" in the name of concision.

(Review finding on ai-config#2955, 2026-09-01: a case record wrote "27 multi-line signatures at +4" where the cited serocalculator#672 comment had counted 27 files.)
