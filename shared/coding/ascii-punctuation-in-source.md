Never use em-dashes (U+2014) in tracked source files. This covers `.R`,
`.py`, `.qmd`, `.md`, and any other source file in the repository, including
the comments, roxygen/docstring prose, and string literals inside code
files, and the body of Markdown docs (README, NEWS, docs pages, this corpus's
own fragments). Use ASCII punctuation instead: a comma, colon, or semicolon
where the em-dash joined clauses, a spaced run of hyphens (`---` or `--`) when
a dash is genuinely wanted, or a plain hyphen (`-`) for a compound.

Worked-example case records for the rules below live in
[`ascii-punctuation-in-source.cases.md`](ascii-punctuation-in-source.cases.md), moved out of the auto-loaded context.

**Either spaced form is fine, and `---` is what this corpus actually writes.**
Both are ASCII, so neither can break the rule above:
the choice is house style rather than hygiene.
As of 2026-08-05 the corpus held 1747 spaced `---` against 434 spaced `--`,
so a new fragment matching its neighbours will use `---`.
Do not flag either form in review,
and do not convert a file from one to the other as a drive-by.

That last sentence is the point of this paragraph rather than a footnote to it.
An earlier wording named only `--`,
which left roughly 80% of the corpus nominally in breach of its own convention
--- so a reviewer reading the rule would flag the majority form
and ask the author to make their own block the minority style
inside the very file they were editing.
Two reviewers on one diff duly reached opposite verdicts,
one quoting this rule and one describing the practice,
and both were reasoning honestly from what the corpus told them.
(Morrison-Lab/ai-config#1169, from a finding on #1168.)

The same rule extends to the other non-ASCII punctuation that slips in from
the same source (copy-paste from rendered text, an editor's smart-quote
autocorrect): en-dashes (U+2013), curly quotes (U+201C U+201D U+2018 U+2019,
which become `"` and `'`), and the multiplication sign (U+00D7, which
becomes `x`, or a context-appropriate escape when the glyph must survive
in output). These are the only symbols this rule bans -- other non-ASCII
characters, like an accented name or a quoted foreign term, are unaffected.

**Scope: every tracked source file, `.md` included.** Markdown files are
source too. They are version-controlled, diffed, and rendered, so the same
smart-quote/copy-paste corruption and whole-paragraph-reflow diffs apply.

This is a separate concern from [`find-ai-tells`](../writing/ai-tells.md)'s
em-dash-*overuse* signal, which is about frequency, not presence -- a single
em-dash there is explicitly called innocent. This rule bans em-dashes in
tracked source files regardless of frequency, for the ASCII-hygiene reasons
above.

Do not exempt a README, a `NEWS.md`, a docs page, or any other Markdown doc,
and do not exempt this corpus's own `shared/` fragments, `CLAUDE.md`s, or
skill files. Chat replies and other ephemeral, non-tracked text are outside
this rule's scope, but the same plain-ASCII habit there avoids
re-introducing the glyphs on the next copy-paste into a file.

**Why this holds even where CI does not gate it.** Some file types are gated
by a check that makes a stray em-dash a hard build failure, though the two
common ones reject different things:

- R CMD check's "checking R files for non-ASCII characters" flags
  non-ASCII bytes in code and string literals in `R/`, but not in comments
  -- "Writing R Extensions" explicitly says other characters "are accepted
  in comments" (verified against the current manual). Under `error_on =
  "note"` a flagged (non-comment) occurrence fails the build. Note that a
  helper defined in `data-raw/` (excluded from the build) passes silently
  until the function moves into `R/`, at which point the same em-dash in
  code starts failing CI.
- Some repos run a dedicated non-standard-character workflow -- e.g. the
  UCD-SERG lab manual's own check, or `d-morrison/gha`'s reusable
  `check-non-standard-chars` -- which rejects only a specific glyph set
  (em-dashes, curly quotes, en-dashes), not every non-ASCII code point, over
  the file types it scans.

Where no CI gate covers a file (commonly a Markdown doc in a repo whose check
only scans `.R`/`.qmd`), the rule is still required, not optional: keep the
file's punctuation and the specific stray symbols named above (the
multiplication sign, U+00D7) ASCII anyway.
Treat adding or extending the repo's non-ASCII check to also scan `.md` as
the enforcement follow-up: a repo with no such check yet needs to add one, and
a repo whose check already scans `.R`/`.qmd` needs to extend it.
For `Morrison-Lab/gha`'s `check-non-standard-chars` specifically, that follow-up is tracked in gha#322, which is now **partly done**.

Both halves were re-measured on 2026-08-17, by reading `check-non-standard-chars/check-non-standard-chars.py` at the `v2` tag --- the ref consumers actually pin --- and they now differ:

- **The glyph set is complete, as of 2026-08-17.**
  `NON_STANDARD_CHARS` carries all seven glyphs this rule bans: the four curly quotes, the en-dash, the em-dash, and `'\u00d7': 'Multiplication sign'`, whose own source comment reads "Added in gha#322".
  An earlier version of this paragraph said the set had no U+00D7 entry, and that has been false since roughly 2026-08-15.
- **The extension list is still hard-coded**, also re-measured 2026-08-17: `extensions = ['.qmd', '.R']` remains a literal, so `.md` is still unscanned and a consumer still cannot narrow or widen the list without forking the script.

So gha#322's remaining scope is `.md` scanning and making that list a configurable input, per [`configurable-parameters`](configurable-parameters.md).
Cite that issue rather than re-deriving the gap: a follow-up named in prose with no tracker reads as untracked, and settling it is one search.

When the glyph must appear in rendered output, keep the source ASCII in a
context-appropriate way.
In an R or Python string literal (a status message, a plot label), use the
`\uXXXX` escape, which the language decodes to the character.
In `.qmd`/`.md` prose, `\uXXXX` is not interpreted by Pandoc and renders
literally: use a math span (`$\times$`), an HTML entity (`&times;`), or
reword to avoid the glyph.

**A passing glyph check is not an ASCII certificate.**
A green `check-non-standard-chars` is evidence about the seven code points in its set, and about nothing else in the file.

That reading is easy to slide past now precisely *because* the gap above closed.
The checker's set and this rule's banned list agree exactly, so the check finally means what the rule says --- which makes it tempting to read a pass as "this file is clean" rather than as "this file is free of those seven glyphs".
Every other non-ASCII code point is outside both, by design: this rule bans six symbols plus the multiplication sign and explicitly leaves an accented name or a quoted foreign term alone.
So the checker is not deficient here, and a pass still settles far less than it appears to.

Measured 2026-08-17 on `UCD-SERG/lab-manual` PR #461, run 32071165557, job `check-chars / check-chars`, against `coding-practices/benchmarking.qmd` at commit `60b5136`.
The checker reported `Found 1 non-standard character(s) in 1 file(s)`.
An independent scan of the same file at the same commit found **four** distinct non-ASCII code points at **nine** sites:

| code point | name | sites | in the checker's set |
| --- | --- | --- | --- |
| U+00B2 | SUPERSCRIPT TWO | 2 | no |
| U+00B5 | MICRO SIGN | 2 | no |
| U+00D7 | MULTIPLICATION SIGN | 1 | yes |
| U+2192 | RIGHTWARDS ARROW | 4 | no |

One of nine sites was reported, and that is the checker working correctly.
Derive the population yourself when the question is whether a file is ASCII, rather than reading it off a check built to answer a narrower question.

The duration is the part worth carrying.
That multiplication sign has been in the file since commit `0030720` (2026-01-27), and the check reported green over it for roughly seven months, until the instrument's glyph set changed.
A repo can therefore carry a real violation indefinitely while its check stays green, so a clean history of that check is not evidence the rule was being followed.

The converse --- a check that starts failing on a file no PR touched, which is a signal to look at the checker's version before hunting for a new violation --- is already recorded in [`memories/github.md`](../../memories/github.md)'s "A moving upstream tag can turn a consumer's default branch red with no local change" section, from this same incident family.
Read it there rather than re-deriving it here.

- **Do:** read a green glyph check as covering its own glyph set, and say which set when reporting the result.
- **Do:** scan for the whole non-ASCII population yourself when the claim you are about to make is that a file is ASCII.
- **Don't:** report a file, a diff, or a repo as ASCII-clean on the strength of a passing `check-non-standard-chars` run.
- **Don't:** read a long green history of that check as evidence no violation was present --- it went green over this one for about seven months.

**The Edit tool cannot perform that substitution, so build the character with
`chr()` rather than trying to type its escape.**
Putting the literal glyph in `old_string` and its own `\uXXXX` escape in
`new_string` is refused outright, with `old_string and new_string are exactly
the same`: the escape has been decoded to the character by the time the two
sides are compared, so the edit is a no-op.
Where the escape names a *different* character the edit succeeds and writes
that character, so the six literal characters never reach the file either way.
Read the refusal as this mechanism rather than as the stale read or the
transcription typo that the same message usually means.

The workaround introduces no escape sequence at all: build the character at
runtime and interpolate it, as `LDQ, EMD = chr(0x201C), chr(0x2014)`.
`hooks/no-misattributed-quote.py` does exactly this for the four glyphs its
regexes must match, which is what keeps the hook's own source ASCII.
Where a literal escape sequence really is the wanted content, write the file
from a script rather than through an edit.

**Which layer decodes it is not settled, and this probe cannot settle it.**
Separating "the tool decodes both parameters" from "the transport decodes such
an escape in any tool parameter" would mean measuring an escaping layer
through itself, which
[`address-every-comment`](../workflow/address-every-comment.md) already rules
out for the shell case and for the same reason.
So record the behaviour and leave the mechanism open.

- **Do:** build a needed non-ASCII character from `chr(0x2014)` when an edit
  has to introduce one into ASCII source.
- **Do:** name a code point as `U+2014` in prose, since a concrete `\uXXXX`
  written into an edit lands in the file as the glyph it names --- which is
  the violation this whole rule exists to prevent.
- **Don't:** try to convert a glyph into its own escape with an edit; it
  refuses as a no-op, and the refusal is not the stale read it resembles.
- **Don't:** report which layer decoded it --- the probe travels the layer it
  would be measuring.

Apply it when writing and when reviewing a diff: a raw em-dash in a roxygen
block, a `.qmd`, or a `.md` doc is a review finding, regardless of whether
this particular file is one a CI check currently scans.
Give it the **same review weight** as a CI-breaking issue -- this is not a
claim that it always breaks CI, since not every file type is scanned.

**When self-checking a multi-commit PR, re-scan the WHOLE diff against the
base branch before each push -- not just the files touched by the latest
commit.** A narrower check (`git diff -U0 <files-from-this-commit> | grep
...`) can miss an em-dash sitting in a file an *earlier* commit introduced,
because that file never entered the narrower command's scope again. Use
`git diff -U0 origin/main -- <all-changed-files>` (or `git diff -U0
origin/main` with no path filter) so a fix pushed in round 2 doesn't
silently leave round 1's violation standing.

**Use the three-dot range for that scan, not the two-dot one, or a `main`
that has advanced turns the check into a flood of false positives.**
`git diff origin/main` compares the two *tips*, so a `+` line means "present
in your HEAD, absent from main's tip" --- which is true of your own additions
**and** of anything `main` has since deleted or moved that your branch still
carries.
Those deletions are the ones that flood the scan, and note the inversion:
content `main` *added* shows up as `-` and is invisible to a `+`-only scan,
so the direction that bites is the opposite of the intuitive one.
A file whose content moved elsewhere on `main` is the worst case, since every
line of it reappears as yours.

The failure is loud rather than silent, which is its one mercy, but it is
still worse than useless: a scan reporting dozens of violations in files you
never touched trains you to dismiss the check, and the real hits are buried
among them.

`git diff origin/main...HEAD` compares against the **merge base** instead ---
the state your branch actually diverged from --- so it reports only your own
additions no matter how far `main` has moved:

```bash
git diff -U0 origin/main...HEAD        # your additions only
git diff -U0 origin/main               # plus anything main deleted or moved
```

Two follow-ons.
The gha `check-new-line-breaks` workflow already uses the three-dot form
internally, which is why it can report clean on the same head where a
hand-rolled two-dot scan reports scores of hits --- so a disagreement
between the two is a signal about your range, not about the file.
And merging `main` first collapses the difference, since the merge base
becomes `main`'s tip; that is the better habit anyway, per
[`sync-with-main`](../workflow/sync-with-main.md).

**Writing into a file that predates this rule is the likeliest way to break
it, because the surrounding prose is the wrong model to imitate.**
Ordinary practice is to match the file you are editing, and in a long-lived
document full of em-dashes that instinct produces a new em-dash with no
decision ever being made.
The check only judges **added** lines, so the existing ones are not evidence
of anything -- they are grandfathered, not permitted.
Match the rule, not the file.

The same asymmetry governs
[`semantic-line-breaks`](../writing/semantic-line-breaks.md), which is also
diff-scoped: prose added to a fill-column-wrapped paragraph inherits that
wrapping and lands two sentences on one line, flagged even though every
neighbouring line does the same.
So when adding prose to an older-conventions file, scan your own added lines
for both before pushing --- and scan for punctuation **after** fixing the line
breaks, never before.
Splitting a long line retires it and creates two new ones, so a punctuation
scan run first is reporting on lines the reflow has since deleted.
[`semantic-line-breaks`](../writing/semantic-line-breaks.md)'s section on a
reflow expiring a check owns that ordering.

**Editing an existing line for an unrelated reason makes its pre-existing
violations yours, because the diff cannot tell the two apart.**
The section above is about prose you *write*, where the risk is imitating a
grandfathered neighbour.
This is the case where you write nothing objectionable at all: you change
three words in a long-standing line for some other purpose, and the em-dash
that line has carried for a year arrives in the diff as an added line with
your name on it.

Note how it inverts the grandfathering the section above relies on.
Untouched, that line is exempt indefinitely.
Touched, it is judged in full --- not just the part you changed --- because
the check reads added lines, and a modified line is an added line.
So the exemption is not a property of the *content* but of whether anyone has
edited it lately, which is why this fires on changes that feel purely
incidental.

The fix is cheap and worth taking rather than resenting: you are already
editing the line, so bring it into compliance while you are there.
The same applies to
[`semantic-line-breaks`](../writing/semantic-line-breaks.md), since it is
diff-scoped in the same way --- editing half of a two-sentence line makes the
whole line yours to split.

- **Do:** scan any line you modify for banned glyphs and multi-sentence
  structure, not only the lines you add outright.
- **Do:** fix what you find in the same edit, since the line is open in front
  of you and the alternative is a review round about punctuation you did not
  write.
- **Don't:** expect a line's grandfathered status to survive your touching it.
- **Don't:** read such a flag as the check misfiring --- it is reporting the
  diff correctly, and the diff genuinely contains that character.

**Splicing into a line creates a violation neither half carried, and it lands
at the seam.**
The section above is about a violation the line already had, which your edit
merely re-adds.
This is the case where nothing was wrong before: you insert a sentence into an
existing line, your clause is clean, the line you inserted it into is clean,
and the joined line now carries two sentences.
That worked example violates
[`semantic-line-breaks`](../writing/semantic-line-breaks.md) rather than this
file's own rule --- splicing ASCII into ASCII cannot manufacture a glyph --- and
it sits here because the *seam* mechanism is shared: both checks are
diff-scoped, so both fire on the joined line and neither fires on either half.
Nothing here is grandfathered, and the check is not being harsh --- the
violation is new text you wrote, in the one place you were not looking.

Where it lands is predictable enough to check directly rather than by
re-reading the whole hunk.
A splice creates a new adjacency at each end of what you inserted --- two of
them when you land in the middle of a line, one when you append or prepend ---
and the failure sits at one of those, rather than inside either half.
Check both ends: reading only the join you were thinking about is how the other
one survives.
Re-reading what you inserted therefore passes every time, which is exactly why
the seam is the thing to read.

- **Do:** re-read the joined line in full after splicing into an existing one,
  rather than the sentence you inserted, and check both ends of what you
  inserted rather than the one you were thinking about.
- **Don't:** treat a clean insertion as evidence of a clean line --- the check
  reads the line, and the line is now both halves at once.

**Relocating prose is the strongest form of touching it, not an exception to
this rule.**
The section above is about a line you *edit*.
Moving a section to another file edits none of its lines, and every one of them
still lands in the diff as an added line --- so a file split, an extraction, or
a move between fragments makes the whole moved body yours at once.

The reasoning that talks you out of this is the scope-creep rule in this same
fragment ("Fixing one flagged glyph is a one-line edit; fixing it with a
whole-file replace is a different, much larger change"), which correctly says
not to answer a one-line finding with a whole-file replace.
It does not apply here, and the difference is worth stating because the two look
identical from the inside.
That rule protects a diff from growing *beyond* what the change was for.
A relocation's diff is already the whole file, so fixing the moved prose adds no
scope at all --- it just makes the lines you are already publishing conform.

The corpus-wide sweep tracked in
[#731](https://github.com/Morrison-Lab/ai-config/issues/731) is not a reason to
defer either.
That issue exists for the lines nobody is touching; a line you are moving is by
definition not one of them, and leaving it puts a known-bad line into a diff a
reviewer is about to read.

This applies equally to
[`semantic-line-breaks`](../writing/semantic-line-breaks.md), which is
diff-scoped for the same reason: a relocated multi-sentence line is a
multi-sentence line you just added.
Verify the result with the real check rather than a hand-rolled one, and confirm
the reflow changed nothing but whitespace --- a whitespace- and
markup-normalized word-level comparison against the pre-move version should come
back identical.

- **Do:** fix banned glyphs and multi-sentence lines throughout any prose you
  relocate, in the same change that moves it.
- **Do:** prove a mechanical reflow preserved content *and added nothing*, by
  word-level comparison in both directions --- a one-sided "did anything go
  missing" check cannot see a line the move introduced, per
  [`fail-fast`](../principles/fail-fast.md)'s third pattern direction.
- **Don't:** treat "I only moved it" as grandfathering --- the diff cannot tell
  a move from an authoring pass, and neither can a reviewer.
- **Don't:** defer to the corpus-wide sweep for lines your own diff is
  republishing.

**Fixing one flagged glyph is a one-line edit; fixing it with a whole-file
replace is a different, much larger change that happens to touch the same
line.**
The two look identical in intent --- both make the check pass --- but a
blanket `str.replace()` or `sed -i` run against the whole file does not stop
at the flagged occurrence.
It rewrites every instance the file already carried, including the ones
grandfathered under exactly the "writing into a file that predates this
rule" reasoning two sections above.

The failure is not that the result is wrong --- every rewritten line is
individually correct, and a repo-wide sweep of this rule is a legitimate
goal on its own.
It is that the fix silently exceeds what the diff was for.
A one-line finding can triple or worse the diff size, touching content no
reviewer asked about, in a PR whose whole point was a small, targeted
addition.
That is scope creep by mechanism, not by intent, which is what makes it easy
to do without noticing: nothing about running a global replace *feels* like
expanding scope, and the tool reports success either way.

Fix the flagged occurrence with a targeted edit --- `Edit`'s exact-match
`old_string`, or a line-anchored substitution --- never a bare find-and-replace
across the file.
If a repo-wide sweep is worth doing, it is worth doing as its own change,
not as a side effect of answering one review comment.

- **Do:** fix a flagged glyph with an edit scoped to that occurrence.
- **Do:** propose a corpus-wide punctuation sweep as a separate, explicit
  change when the file's other grandfathered violations are worth clearing.
- **Don't:** reach for a whole-file search-and-replace to answer a
  single-line finding, even when the replacement itself is correct.
- **Don't:** assume a diff is clean because the check now passes --- check
  its size against what the finding actually asked for.

**The mistake recurs even while actively self-reviewing for exactly this
rule, and the scale grows with the number of files touched at once.**
Fixing multiple flagged glyphs across several files in one pass invites
running one `str.replace()` loop over all of them, rather than a separate
targeted edit per occurrence --- and the same "does the diff size match the
finding" check catches it just as cheaply here as it does for a single file.
