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

## "Inserting prose makes a downstream back-reference stale"

(Morrison-Lab/ai-config#1091, 2026-08-03: a new section was inserted between
"A negative control must enter at the real input" and "A reminder guard's
discharge condition...", whose opening "The two sections above test a guard's
fire condition" then counted back to the new, unrelated section instead of the
two fire-condition sections it described.
Review caught it; the fix relocated the inserted section out of the arc so the
count resolved again.
CI was fully green throughout --- no mechanical check sees this.)
