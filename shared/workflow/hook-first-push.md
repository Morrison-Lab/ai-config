# Run these checks before the first push of a new hook

[ai-config#5117](https://github.com/Morrison-Lab/ai-config/pull/5117) took four pushes because scripts that decide each miss ran only in CI and review (2026-11-08).

- **Do:** run `python3 scripts/check-text-encoding.py` (every `open()` takes `encoding="utf-8"`), `python3 scripts/check-hook-output-shape.py` (a Stop hook's test parses the output and asserts `decision` and `reason`), and `python3 scripts/check-hook-catalog.py` before pushing.
- **Do:** block a Stop through `stop_notice` in `scripts/lib/agent_notice.py`, which blocks once per turn, keeps the temp sentinel out of the project, and shows the user the message.
- **Do:** run `python3 scripts/check-ascii-punctuation.py <hook>` too.
  Write a curly quote in a regex as the escape `\u201c`, which `re` reads inside a raw string.
  [#5686](https://github.com/Morrison-Lab/ai-config/pull/5686) went red on its first push because the glyph itself landed in the file (2026-11-15).
- **Don't:** trust that an escape typed in an edit reached the file as an escape.
  A Write or Edit call can turn it into the glyph, so print the line back with `cat -A`.
- **Do:** run each checker on its own and read its exit status before any `| tail`.
  `check-hook-catalog.py` prints a clean-looking summary line on failure too (ai-config#5125).
- **Do:** write an alternation matcher in a README hook row with `\|` and no `[...]` character class, which the catalog checker's row regex cannot parse.
- **Do:** count a tool call as an event only when its paired `tool_result` carries no `is_error`, as `hooks/warn-red-own-pr-at-stop.py` does.
- **Don't:** assert a block by searching stdout for the word, or take state from `tool_use` blocks alone.
- **Don't:** keep a block-once marker beside the transcript.

Read the nearest sibling hook before writing the new one, since the reviewer will compare them.

Four more misses sent [#5615](https://github.com/Morrison-Lab/ai-config/pull/5615) through [#5618](https://github.com/Morrison-Lab/ai-config/pull/5618) to a second push (2026-11-13):

- **Do:** count the diff before pushing (`git diff --shortstat origin/main`), and keep the hook, its test, its README row and its rule section within 40 files and 1200 lines.
  Split first when over, since `hooks/no-oversized-pr-push.py` refuses the push.
- **Don't:** push a new hook, test, README row and rule section together without counting them.
- **Do:** add the `README.md` hook-catalog row in the same commit as the hook (`check-hook-catalog.py`).
- **Don't:** leave the row for the review round.
- **Do:** give every algorithmic check both a writer rule and a reviewer instruction, then commit and run `python3 scripts/check-check-has-instructions.py`.
  It diffs `origin/main...HEAD`, so before the commit it reports "no check added" and passes ([#5707](https://github.com/Morrison-Lab/ai-config/pull/5707) went red in CI that way, 2026-11-16).
- **Don't:** ship the writer rule alone.
- **Do:** change a `shared/**/*.md` fragment, `AGENTS.md`, `CLAUDE.md` or `skills/*/SKILL.md` as the writer rule, and a `.claude/agents/*.md` file as the reviewer rule, since `check-check-has-instructions.py` counts only those paths.
  [#5807](https://github.com/Morrison-Lab/ai-config/pull/5807) failed `new-line-breaks` once for lacking both (2026-11-18).
- **Do:** after adding any file under `shared/`, run `python3 scripts/gen-topic-map.py` and commit `docs/topic-map.md`, which `validate` checks with `--check`.
- **Don't:** leave the regenerated topic map for CI to demand (#5807 failed `validate` on it).
- **Do:** run `python3 scripts/check_regex_patterns.py` on a new regex and flatten any nested quantifier (a repeat inside a repeat).
- **Don't:** leave a nested quantifier for CI to find.

Changing an existing hook's event or matcher in `hooks/hooks.json` needs the same two follow-ups as a new hook.
[#5631](https://github.com/Morrison-Lab/ai-config/pull/5631) widened a matcher from `Bash` to `.*` and failed `validate` twice, once for each follow-up (2026-11-13):

- **Do:** after any edit to `hooks/hooks.json`, run `python3 scripts/gen-hooks-plugin.py`, update the hook's `README.md` catalog row, and then run `python3 scripts/check-hook-catalog.py`.
- **Don't:** treat a matcher change as a one-line edit to `hooks/hooks.json`.

- **Do:** split a shell command into stages with `shlex` (`punctuation_chars=";&|\n"`), as [`least-flexible-tool`](../coding/least-flexible-tool.md) says, and test a quoted operator, a trailing operator and an unbalanced quote.
- **Don't:** split on `&&`, `|` or `;` with a regex that cannot see quoting, as #5631 first did and broke on `rg "a|b" f` and `grep x f;`.
- **Do:** when a hook judges a git command by reading local refs, test each command that fetches before it acts (`git pull`, `git fetch ... && git merge FETCH_HEAD`) on a repo that has not fetched the new commits, since there the local ref is stale.
- **Don't:** fetch in every test before running the case, which hid exactly that gap in #5990 until agy's second round.

A hook that parses a CLI's argv (`gh`, `glab`) needs the CLI's complete flag and placeholder table before its first commit.
The hook for [#5784](https://github.com/Morrison-Lab/ai-config/issues/5784) (branch `claude/5784-unnamed-repo-api-paths`) took four adversarial review rounds with 17 findings before its PR opened (session record, 2026-11-18), largely undeclared flags (`glab` `--form`, `--output`, `--placeholder`), placeholder forms, and endpoint forms (query string, fragment, full URL, leading `//`).

- **Do:** derive the flag table, the placeholder forms and the endpoint forms from the tool's own `--help`, docs and source before the first commit, and put that requirement in the implementer brief.
- **Don't:** write the parser from the flags the first test cases happen to use and let review rounds find the rest.

After its PR opened, [#5814](https://github.com/Morrison-Lab/ai-config/pull/5814) took three more adversarial rounds and five kimi-k3 rounds.
Its stacked follow-up [#5821](https://github.com/Morrison-Lab/ai-config/pull/5821) took four of each, the first of each on the branch before its PR opened, so only three kimi-k3 rounds are posted there (session record, 2026-11-18).
The defects found in those rounds were visible only in the CLI's source and argument parser:

- pflag short-flag clusters (`-iX POST`), attached `-R=value`, and `--` termination;
- glab's compound placeholders (`:group/:namespace/:repo`, in `internal/commands/api/api.go`);
- glab's `GITLAB_REPO` fallback (`internal/cmdutils/repo_override.go`);
- glab root persistent flags placed before the subcommand (`internal/commands/root.go`).

- **Do:** emulate the CLI's own argument parser, and read its source for the parser, the placeholder expansion, the environment fallbacks and the root persistent flags, before the first commit.
- **Don't:** take `--help` or the docs as the complete flag and placeholder table.

For a guard against a destructive command ([`destructive-actions-catalog`](destructive-actions-catalog.md)):

- **Do:** test it by feeding the hook a payload, or inside a throwaway repository made for that test.
- **Don't:** run the command it guards against in a real checkout, even one you expect the hook to refuse.
