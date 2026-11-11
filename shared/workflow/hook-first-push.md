# Run these checks before the first push of a new hook

[ai-config#5117](https://github.com/Morrison-Lab/ai-config/pull/5117) took four pushes because scripts that decide each miss ran only in CI and review (2026-11-08).

- **Do:** run `python3 scripts/check-text-encoding.py` (every `open()` takes `encoding="utf-8"`), `python3 scripts/check-hook-output-shape.py` (a Stop hook's test parses the output and asserts `decision` and `reason`), and `python3 scripts/check-hook-catalog.py` before pushing.
- **Do:** block a Stop through `stop_notice` in `scripts/lib/agent_notice.py`, which blocks once per turn, keeps the temp sentinel out of the project, and shows the user the message.
- **Do:** run each checker on its own and read its exit status before any `| tail`.
  `check-hook-catalog.py` prints a clean-looking summary line on failure too (ai-config#5125).
- **Do:** write an alternation matcher in a README hook row with `\|` and no `[...]` character class, which the catalog checker's row regex cannot parse.
- **Do:** count a tool call as an event only when its paired `tool_result` carries no `is_error`, as `hooks/warn-red-own-pr-at-stop.py` does.
- **Don't:** assert a block by searching stdout for the word, or take state from `tool_use` blocks alone.
- **Don't:** keep a block-once marker beside the transcript.

Read the nearest sibling hook before writing the new one, since the reviewer will compare them.

A guard against a destructive command is tested only by feeding it a payload or inside a throwaway repository, never against a real checkout ([`destructive-actions-catalog`](destructive-actions-catalog.md)).
