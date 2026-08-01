Never use em-dashes (U+2014) in tracked source files. This covers `.R`,
`.py`, `.qmd`, `.md`, and any other source file in the repository, including
the comments, roxygen/docstring prose, and string literals inside code
files, and the body of Markdown docs (README, NEWS, docs pages, this corpus's
own fragments). Use ASCII punctuation instead: a comma, colon, or semicolon
where the em-dash joined clauses, a spaced double hyphen (`--`) when a dash is
genuinely wanted, or a plain hyphen (`-`) for a compound.

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
a repo whose check already scans `.R`/`.qmd` needs to extend it. For
`d-morrison/gha`'s `check-non-standard-chars` specifically, the follow-up
also needs to ensure its glyph set covers all four named glyphs (en/em-dash,
curly quotes, multiplication sign), not just `.md` scanning -- as of this
writing its `NON_STANDARD_CHARS` set has no U+00D7 entry yet.
When the glyph must appear in rendered output, keep the source ASCII in a
context-appropriate way.
In an R or Python string literal (a status message, a plot label), use the
`\uXXXX` escape, which the language decodes to the character.
In `.qmd`/`.md` prose, `\uXXXX` is not interpreted by Pandoc and renders
literally: use a math span (`$\times$`), an HTML entity (`&times;`), or
reword to avoid the glyph.

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
silently leave round 1's violation standing. (gha#286: a changelog fragment
added in the PR's first commit had a raw em-dash that a same-session grep
check caught on that commit but missed on a later, narrower re-check scoped
only to the commit being amended -- the gap was closed by the repo's own
automated `@claude` self-review, not by the author's manual check.)

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
(Morrison-Lab/ai-config#816, 2026-07-29: a pre-push scan reported 88 banned
glyphs, mostly in `memories/github-actions.md`, none of them in the diff.
`main` had since moved 609 of that file's lines into a new
`memories/claude-bot-workflows.md`, so the two-dot diff re-attributed every
one of them to the branch --- `+609/-5` on a file the branch never opened.
The same scan with `...` reported 0 over 66 added lines.)

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
for both before pushing.
(ai-config#754, 2026-07-28: four multi-sentence lines and one em-dash, each
a faithful imitation of the paragraph it was written next to.)

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

(Twice on 2026-07-29/30.
`Morrison-Lab/gha#374`: retargeting an owner name inside
`sync-upstream.yml`'s generated PR-body string re-added that line's
long-standing em-dash, flagged on the next scan.
`Morrison-Lab/ai-config#863`: rewording `CLAUDE.md`'s `compress-session`
live-state list to match a new bright line re-added both an em-dash and a
mid-line semicolon, flagged by `check-new-line-breaks` and the punctuation
scan respectively.
Neither glyph was authored in either session.)

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

(Morrison-Lab/ai-config#916, 2026-07-30: a review flagged one em-dash in a
newly added heading.
The first fix ran a file-wide replace of the banned em-dash (U+2014) with
`---` against
`skills/agent-builder/SKILL.md`, which also rewrote 52 pre-existing
em-dashes elsewhere in that same file, turning a 33-line addition into a
104-line diff.
Caught before pushing by checking the diff's size against the single-line
finding it was meant to answer; recovered via `git checkout -- <file>`
against the still-staged pre-replace version, since the file had been
`git add`-ed before the mistake.)

**The mistake recurs even while actively self-reviewing for exactly this
rule, and the scale grows with the number of files touched at once.**
Fixing multiple flagged glyphs across several files in one pass invites
running one `str.replace()` loop over all of them, rather than a separate
targeted edit per occurrence --- and the same "does the diff size match the
finding" check catches it just as cheaply here as it does for a single file.
(Morrison-Lab/ai-config#973, 2026-08-01: a self-review found 8 flagged
em-dashes across three memory files.
A first pass ran a global `text.replace(em_dash, " --- ")` per file, which
touched 663 removed lines across the three files against an expected ~50 ---
caught by `git diff --stat` before pushing, reverted with
`git checkout -- <files>`, and redone with anchored, uniqueness-asserted
substitutions for only the 8 flagged lines.)
