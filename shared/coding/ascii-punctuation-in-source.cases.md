# Case records: ascii-punctuation-in-source

Worked-example case records for the rules in
[`ascii-punctuation-in-source.md`](ascii-punctuation-in-source.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Re-scan the whole diff, not just the latest commit

(gha#286: a changelog fragment
added in the PR's first commit had a raw em-dash that a same-session grep
check caught on that commit but missed on a later, narrower re-check scoped
only to the commit being amended -- the gap was closed by the repo's own
automated `@claude` self-review, not by the author's manual check.)

## Use the three-dot range for that scan, not the two-dot one

(Morrison-Lab/ai-config#816, 2026-07-29: a pre-push scan reported 88 banned
glyphs, mostly in `memories/github-actions.md`, none of them in the diff.
`main` had since moved 609 of that file's lines into a new
`memories/claude-bot-workflows.md`, so the two-dot diff re-attributed every
one of them to the branch --- `+609/-5` on a file the branch never opened.
The same scan with `...` reported 0 over 66 added lines.)

## Writing into a file that predates this rule

(ai-config#754, 2026-07-28: four multi-sentence lines and one em-dash, each
a faithful imitation of the paragraph it was written next to.)

## Relocating prose is the strongest form of touching it

(Morrison-Lab/ai-config#1067 -> #1069, 2026-08-02: #1067 split six worktree
sections out of `memories/git.md` and left 26 em-dashes and 16 multi-sentence
lines in the relocated file, reasoning that relocation is not authoring
and that #731 covers the sweep.
The user's correction was "fix em-dashes and semantic line breaks on any prose
you touch", pointing at the 10 warnings the `check-new-line-breaks` job had
already posted as annotations on that PR.
Fixed in #1069, with the word-level comparison confirming 1910 words on both
sides.)

## Editing an existing line re-adds its grandfathered glyph

(Twice on 2026-07-29/30.
`Morrison-Lab/gha#374`: retargeting an owner name inside
`sync-upstream.yml`'s generated PR-body string re-added that line's
long-standing em-dash, flagged on the next scan.
`Morrison-Lab/ai-config#863`: rewording `CLAUDE.md`'s `compress-session`
live-state list to match a new bright line re-added both an em-dash and a
mid-line semicolon, flagged by `check-new-line-breaks` and the punctuation
scan respectively.
Neither glyph was authored in either session.)

## Fixing one flagged glyph with a whole-file replace is scope creep

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

## The whole-file-replace mistake recurs across several files at once

(Morrison-Lab/ai-config#973, 2026-08-01: a self-review found 8 flagged
em-dashes across three memory files.
A first pass ran a global `text.replace(em_dash, " --- ")` per file, which
touched 663 removed lines across the three files against an expected ~50 ---
caught by `git diff --stat` before pushing, reverted with
`git checkout -- <files>`, and redone with anchored, uniqueness-asserted
substitutions for only the 8 flagged lines.)
