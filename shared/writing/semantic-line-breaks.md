Break lines in prose at major phrase and sentence boundaries — one clause
per line, roughly 60 to 80 characters — rather than wrapping at a fixed
column or writing one long line per paragraph. This matters most in files
under version control (Quarto `.qmd`, Markdown docs, and similar), since a
semantic break keeps a diff to the changed sentence instead of a whole
reflowed paragraph.

**When editing existing prose**, preserve the file's current line breaks
exactly — don't reflow to a single long line or a different wrap width.
**When writing new prose**, add breaks at phrase/sentence boundaries as you
go.

**When a review flags a semantic-line-break violation, fix every
over-length line in the touched section in one pass** — not just the
specifically-flagged ones. Review bots (`@claude` / Copilot) re-scan on
each push and flag the next batch of adjacent borderline lines the prior
round left alone, so fixing only what was named drags the PR through round
after round of the same finding (asymptotic noise; UCD-SERG/lab-manual#297
took five review rounds this way).

**URL-inflation exception:** a line that runs long *only* because of an
embedded `[text](long-url)` link — where the visible prose before the link
is well under 40 characters — is fine as-is. Don't force an awkward
mid-clause break just to shorten the raw line; review bots themselves
classify these as borderline / acceptable.

**When reviewing prose, suggest semantic-line-break fixes — don't insist on
them.** Flag lines that ignore clause/sentence boundaries as a style
suggestion, the same weight as a word-choice nit: worth raising, not worth
blocking approval over, and not worth re-raising if the author declines.
This is distinct from the rule above: that one governs how thoroughly to
fix violations once a review has flagged them; this one governs the
weight to give the finding when you are the reviewer in the first place.

**What CI actually enforces is one sentence per line, not a character
count -- don't reflow to 80 columns thinking the check demands it.**
The 60-to-80 range above is guidance for a human writing prose.
The automated check backing it (`check-new-line-breaks`, a reusable
workflow in [`d-morrison/gha`](https://github.com/d-morrison/gha); formerly
ai-config's own `scripts/check-new-line-breaks.py`, retired in ai-config#703)
tests something narrower: for each **newly added** prose line in the diff,
it flags the line only when that line holds more than one sentence.
Two consequences.
A single long line carrying exactly one sentence passes, so the URL-inflation
exception above needs no special casing in the check.
And a line that packs two short sentences fails even at 50 characters, which
is the violation to actually look for before pushing.
Fix a flagged line by breaking at the sentence boundary, not by rewrapping
the paragraph to a narrower column.
(ai-config#712: assuming an 80-character limit sent me measuring line lengths
against the wrong criterion; reading the retired script's own source settled
it, and the real check then found 7 multi-sentence lines a length check had
passed over.)

**That check is advisory: it warns and exits 0, so a green CI job does not
mean the diff is clean.**
It emits `::warning::` annotations and a `N line(s) pack more than one
sentence/clause` summary, then exits successfully, so the job it runs in
reports success either way.
Read its output rather than its color --- this is the same
green-check-does-not-mean-clean-content pattern
[`fully-clean`](../workflow/fully-clean.md) documents for review jobs, and it
is easy to miss precisely because nothing turns red.
Run it locally before pushing (`NLB_BASE_REF=origin/main python3
<path>/check-new-line-breaks.py`) and fix what it names.
(ai-config#725: a round of review fixes introduced 7 multi-sentence lines; the
check flagged all 7 while `validate` stayed green, and the review bot did not
catch them either --- they were found only by reading the check's own output.)
