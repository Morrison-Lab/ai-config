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

Four more misses sent [#5615](https://github.com/Morrison-Lab/ai-config/pull/5615) through [#5618](https://github.com/Morrison-Lab/ai-config/pull/5618) to a second push (2026-11-13):

- **Do:** count the diff before pushing (`git diff --shortstat origin/main`), and keep the hook, its test, its README row and its rule section within 10 files and 300 lines.
  Split first when over, since `hooks/no-oversized-pr-push.py` refuses the push.
- **Don't:** push a new hook, test, README row and rule section together without counting them.
- **Do:** add the `README.md` hook-catalog row in the same commit as the hook (`check-hook-catalog.py`).
- **Don't:** leave the row for the review round.
- **Do:** give every algorithmic check both a writer rule and a reviewer instruction, then run `python3 scripts/check-check-has-instructions.py`.
- **Don't:** ship the writer rule alone.
- **Do:** run `python3 scripts/check_regex_patterns.py` on a new regex and flatten any nested quantifier (a repeat inside a repeat).
- **Don't:** leave a nested quantifier for CI to find.

Changing an existing hook's event or matcher in `hooks/hooks.json` needs the same two follow-ups as a new hook.
[#5631](https://github.com/Morrison-Lab/ai-config/pull/5631) widened a matcher from `Bash` to `.*` and failed `validate` twice, once for each follow-up (2026-11-13):

- **Do:** after any edit to `hooks/hooks.json`, run `python3 scripts/gen-hooks-plugin.py`, update the hook's `README.md` catalog row, and then run `python3 scripts/check-hook-catalog.py`.
- **Don't:** treat a matcher change as a one-line edit to `hooks/hooks.json`.

- **Do:** split a shell command into stages with `shlex` (`punctuation_chars=";&|\n"`), as [`least-flexible-tool`](../coding/least-flexible-tool.md) says, and test a quoted operator, a trailing operator and an unbalanced quote.
- **Don't:** split on `&&`, `|` or `;` with a regex that cannot see quoting, as #5631 first did and broke on `rg "a|b" f` and `grep x f;`.

For a guard against a destructive command ([`destructive-actions-catalog`](destructive-actions-catalog.md)):

- **Do:** test it by feeding the hook a payload, or inside a throwaway repository made for that test.
- **Don't:** run the command it guards against in a real checkout, even one you expect the hook to refuse.
