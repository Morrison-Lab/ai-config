# Markdown linting (markdownlint, lint-qmd)

Split out of [`tools.md`](tools.md) on 2026-09-01 when that file crossed the 1250-line budget `scripts/check-memory-file-size.py` enforces.

- **Table rows must stay on one line (MD055/MD056).**
  Wrapping a cell across lines breaks the `|` alignment and trips both rules.
  Rewrite the cell concisely on a single line rather than word-wrapping it.
  Prefer a short, complete description over hitting a length target.
- **MD056 counts a literal `|` inside a code span as a cell delimiter -- backticks do not protect it.**
  ai-config#2906 went red on `lint-markdown` because two hook-catalog rows contained `` `HH:MM PDT|PST|PT` `` (a regex-style alternation written in backticks).
  `memories/hooks.md:69` reported "Expected: 5; Actual: 7",
  and `README.md:405` reported "Expected: 3; Actual: 5".
  The rule scans the raw row text for `|`, so a code span's contents are counted exactly like bare table syntax, splitting one cell into three and inflating the column count.
  **Do:** spell alternatives out in prose (`` an `HH:MM` stamp suffixed `PDT`, `PST`, or `PT` ``) instead of writing a `|`-joined alternation, in backticks or not, inside a table cell.
  **Don't:** write a regex-style alternation containing `|` in a table cell and trust the backticks to shield it -- MD056 reads raw text, not rendered Markdown.
  (Morrison-Lab/ai-config#2906, 2026-09-01.)
- **A line that begins with an issue reference is parsed as a heading (MD018).**
  Covered in full by [`semantic-line-breaks`](../shared/writing/semantic-line-breaks.md)'s MD018 section, which owns the rule, the collision with bare references, and both remedies (link the reference, or reword so the line does not open with it).
  Recorded here only for the sweep, since this file is where the linter's rule numbers are indexed: `grep -rn --include='*.md' '^#[0-9]' .` finds every instance.
  (Morrison-Lab/ai-config#3060, 2026-09-03.)
- **markdownlint-cli2 runs locally with no install step, at CI's exact version.**
  `npx --yes markdownlint-cli2@<version>` reads `.markdownlint-cli2.jsonc` and lints the whole repo in seconds;
  take the version from the `lint-markdown` job log, which prints it as its first line.
  Note precisely what this does and does not clear.
  `scripts/run-local-validation.py` deliberately declines to offer this as a local equivalent for the `lint-markdown` job, because gha's action runs four checks (markdownlint, code-block length, list-item splices, table splits) and a bare call reproduces one while reporting a clean zero for the other three.
  That reasoning is about the *job*, not about the tool.
  Running it by hand as one named check is sound, and reporting it as the job is the failure that runner exists to prevent.
  **Do:** run it before pushing markdown, and say which of the four checks it covered.
  **Don't:** read a clean markdownlint run as the `lint-markdown` job passing.
  (Morrison-Lab/ai-config#3060, 2026-09-03.)
- **`Summary: 0 issues in 0 files` and `Summary: 0 error(s)` are the same
  clean verdict in two different markdownlint-cli2 output formats, not a
  signal about whether any files were examined.**
  The newer format (0.23.2, whatever an unpinned `npx` resolves to) prints
  `N issues in M files`; the version this repo pins (0.23.0) prints
  `N error(s)`.
  Neither wording distinguishes a real clean pass over hundreds of files from
  a genuinely empty match --- both are reproducible on this repo's own tree:
  `npx markdownlint-cli2@0.23.2 --config .markdownlint-cli2.jsonc` printed
  `Linting: 752 files` / `Summary: 0 issues in 0 files` over the whole
  corpus, and running the identical command in an empty directory against a
  glob matching nothing printed `Linting: 0 files` / `Summary: 0 issues in 0
  files` too --- same summary line, opposite population.
  0.23.0 shows the identical pattern under its own wording (`752 file(s)` /
  `0 error(s)` versus `0 file(s)` / `0 error(s)`).
  The line that actually says whether anything was examined is `Linting: N
  file(s)`/`N files`, directly above the summary, in either version.
  **Do:** read the `Linting:` line's file count to confirm the run examined
  what you expected, and pin the markdownlint-cli2 version so the wording
  matches what CI reports and the rule set stays the one CI actually runs.
  **Don't:** read `Summary: 0 issues in 0 files` as evidence the run matched
  nothing, or `Summary: 0 error(s)` as evidence it matched something --- both
  strings appear on a genuine clean pass and on a genuine empty match alike.
  (Morrison-Lab/ai-config#3377, 2026-09-09.
  `Morrison-Lab/gha`'s CLAUDE.md cites this same wording difference from
  gha#744, correctly, as evidence an unpinned run resolved a different tool
  version with potentially different rule behavior --- "the same verdict
  through a different output contract" --- not as an empty-match signal;
  an earlier draft of this entry mistook the wording difference itself for
  that signal, which direct reproduction (above) disproved before it shipped.
  ai-config#3060 above documents this repo's own local-run command but not
  this wording variance.)
- **Don't tag a non-shell CLI block `bash`/`sh` (MD040).**
  MD040 wants a language on every fence, which invites tagging anything command-shaped as `bash`.
  Claude slash commands (`/ums`, `/plugin`, `/also`) and other application-level directives are not shell-executable, so `bash` implies a reader can run them and they fail when someone tries.
  Tag those `text` instead.

(Recovered 2026-07-30 from `a739c69`, an orphaned commit on `ums/ardi-review-link-handling`: it landed about 30 minutes after its own PR [#650](https://github.com/Morrison-Lab/ai-config/pull/650) merged, so it never reached `main` and sat unnoticed for a week.
Both rules were first learned on [#645](https://github.com/Morrison-Lab/ai-config/pull/645).)
