# Case records: forward-references

Worked-example case records for the rules in
[`forward-references.md`](forward-references.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "The detection heuristic" --- numbered pointer inside a procedure

(ai-config#691: `ums`'s step 2 said "grep before writing, per step 3";
dropping the pointer left "grep before writing", which carries the
mechanism on its own, while the anti-patterns entry's own `(step 3)`
correctly stayed.)

## "Moving prose makes self-references stale"

(Morrison-Lab/ai-config#966 split `memories/github-mcp-tools.md` out of
`memories/github.md`.
A moved entry at `memories/github-mcp-tools.md:45` still said
`This is the "Postcondition gate" bullet at the top of this file made concrete:`.
After the split, that bullet remained in `memories/github.md:10`, so the
sentence pointed to the wrong file until the reference was rewritten.)

## Sweeping the general directional pattern, not literal phrases

(Morrison-Lab/ai-config#1194, 2026-08-06: a pre-push self-review grepped
`(below)` / `case below` / `as the case` / `per #N below` across 15 relocated
fragments and reported none, but the round-1 `claude-review` found 7 dangling
`above`/`below`/`here` references across 6 of them.
The general `\b(above|below|here)\b` sweep that fixed them turned up an eighth
the review had missed, and its remaining hits --- timeline and
within-block/quoted phrasing --- were correctly left.
The fixes named the referent inline rather than flipping the direction word.)

## "Inserting prose makes a downstream back-reference stale"

(Morrison-Lab/ai-config#1091, 2026-08-03: a new section was inserted between
"A negative control must enter at the real input" and "A reminder guard's
discharge condition...", whose opening "The two sections above test a guard's
fire condition" then counted back to the new, unrelated section instead of the
two fire-condition sections it described.
Review caught it; the fix relocated the inserted section out of the arc so the
count resolved again.
CI was fully green throughout --- no mechanical check sees this.)

## "Direction is not the test"

(Morrison-Lab/ai-config#1849, 2026-08-21.
Round 3 of the review flagged one backwards `below` --- the referent was above
it --- which is a broken reference rather than a forward one.
The sweep that followed used the fragment's own grep over the whole file,
examined each remaining hit, and cleared two of them on the ground that they
pointed forward *accurately*.
That reasoning was posted to the reviewer, so it is on the record as having
been applied deliberately rather than carelessly.
Round 4 flagged one of those two, plus a third that the round-3 fix commit
`ea91b375` had itself introduced.
All three were removed in `6e195693`.
The cross-vendor review that caught the overclaiming in the first draft of this
entry is on [#1874](https://github.com/Morrison-Lab/ai-config/pull/1874).)
