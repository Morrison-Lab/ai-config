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
- **The `Summary:` line's exact wording changes between markdownlint-cli2
  versions, so pin the version rather than reading CI's wording as a
  property of the check itself.**
  [`fail-fast.rationale.md`](../shared/principles/fail-fast.rationale.md)'s
  "A zero-shaped summary can be sound, and the scope line is what decides
  it" already covers the wording ambiguity this format creates --- read that
  section for why `Summary: 0 issues in 0 files` is not itself evidence
  about scope, and the `Linting: N file(s)` line above it is.
  What that section doesn't name is that the wording is **version-dependent**:
  the newer format (0.23.2, whatever an unpinned `npx` resolves to) prints
  `N issues in M files`; the version this repo pins (0.23.0) prints
  `N error(s)`.
  Reproduced on this repo's own tree: `npx markdownlint-cli2@0.23.2 --config
  .markdownlint-cli2.jsonc` printed `Linting: 752 files` / `Summary: 0 issues
  in 0 files` over the whole corpus, and the identical command against a
  genuinely empty match printed `Linting: 0 files` / `Summary: 0 issues in 0
  files` too --- same summary, opposite population, confirming the section
  above holds for this version as well as the one it measured.
  **Do:** pin the markdownlint-cli2 version so local runs match CI's wording
  and rule set, and read `fail-fast.rationale.md`'s zero-shaped-summary
  section for why the `Linting:` line is the one that matters.
  **Don't:** re-derive "the summary line doesn't show scope" from scratch ---
  it's already recorded there and in
  [`nested-worktree-instrument-inflation.md`](nested-worktree-instrument-inflation.md).
  (Morrison-Lab/ai-config#3377, 2026-09-09.
  `Morrison-Lab/gha`'s CLAUDE.md cites this same version-wording difference
  from gha#744, correctly, as evidence an unpinned run resolved a different
  tool version with potentially different rule behavior --- "the same
  verdict through a different output contract" --- not as an empty-match
  signal; an earlier draft of this entry mistook the wording difference
  itself for an empty-match signal, which direct reproduction disproved, and
  a review round then caught the entry substantially duplicating the
  already-on-main sections cited above.)
- **Don't tag a non-shell CLI block `bash`/`sh` (MD040).**
  MD040 wants a language on every fence, which invites tagging anything command-shaped as `bash`.
  Claude slash commands (`/ums`, `/plugin`, `/also`) and other application-level directives are not shell-executable, so `bash` implies a reader can run them and they fail when someone tries.
  Tag those `text` instead.

- **`lint-qmd` in Morrison-Lab/gha enforces line-length (MD013) on `.qmd` files even when repo-level `.markdownlint-cli2.jsonc` disables it.**
  Markdown in `.md` files in this repository permits long lines (MD013 disabled), but Quarto markdown (`.qmd`) files checked by the reusable `lint-qmd.yml` workflow enforce line-length limits (80 characters for prose, headings, and lists).
  When authoring or updating `.qmd` documents (such as `agents.qmd`), wrap prose lines to <= 80 characters, and take care when editing wrapped lines to avoid truncating mid-sentence clauses across line boundaries.
  (Morrison-Lab/ai-config#3619, 2026-09-12.)

(Recovered 2026-07-30 from `a739c69`, an orphaned commit on `ums/ardi-review-link-handling`: it landed about 30 minutes after its own PR [#650](https://github.com/Morrison-Lab/ai-config/pull/650) merged, so it never reached `main` and sat unnoticed for a week.
Both rules were first learned on [#645](https://github.com/Morrison-Lab/ai-config/pull/645).)
