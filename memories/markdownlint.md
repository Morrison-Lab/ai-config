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
  ai-config#3737 failed on the same pattern in `README.md:473`:
  shell alternations inside code spans (`` `gh issue|pr comment` ``, `` `gh issue|pr create|edit` ``, `` `glab issue|mr note` ``)
  inflated a 3-column row to 7 cells ("Expected: 3; Actual: 7").
  `scripts/check-md056-table-columns.py` provides a pure-Python, zero-dependency pre-commit scan that checks all GFM tables for MD056 column-count mismatches and unescaped pipes inside code spans, avoiding the need for an npm/node runtime locally when verifying table syntax before pushing.
  **Do:** spell alternatives out in prose (`` an `HH:MM` stamp suffixed `PDT`, `PST`, or `PT` ``) or escape the delimiter (`\|`) inside the code span (as `520db260` did for PR #3737) instead of leaving an unescaped `|`-joined alternation inside a table cell.
  **Do:** run `python3 scripts/check-md056-table-columns.py` before pushing to verify table column counts and code span pipes locally without npm.
  **Don't:** write a regex-style alternation containing `|` in a table cell and trust the backticks to shield it -- MD056 reads raw text, not rendered Markdown.
  (Morrison-Lab/ai-config#2906, 2026-09-01.
  Morrison-Lab/ai-config#3764, 2026-09-17.)
- **A line that begins with an issue reference is parsed as a heading (MD018).**
  Covered in full by [`semantic-line-breaks`](../shared/writing/semantic-line-breaks.md)'s MD018 section, which owns the rule, the collision with bare references, and both remedies (link the reference, or reword so the line does not open with it).
  Recorded here only for the sweep, since this file is where the linter's rule numbers are indexed: `grep -rn --include='*.md' '^#[0-9]' .` finds every instance.
  **Third occurrence, 2026-09-17:** `memories/hooks.md:365` opened a line with `#3744 carries the two-tree measurement...`.
  The fix prefixed "Issue ", which is the reword remedy above rather than a third one.
  The same idiom already sits at `memories/claude-code.md:1041` ("Issue #3230's done-when...").
  Checked whether any local hook catches this before CI, rather than assuming a gap.
  `hooks/warn-new-line-breaks-on-push.py` is the only `PreToolUse` guard on this class of prose defect, and it runs the semantic-line-breaks (clause-density) checker, not markdownlint, so neither it nor any other hook reads column 1.
  A line-initial `#NNNN` therefore reaches CI's `lint-markdown` job before anything local reports it.
  The corpus's current mitigation is the manual scan `semantic-line-breaks.md` already prescribes ("scan added lines for a column-1 `#` before pushing"), not a hook.
  **Do:** run that manual scan before pushing prose that adds `#NNNN` references, since nothing automated does it yet (measured: no hook in `hooks/` reads markdownlint's rule set or column 1).
  **Don't:** read `warn-new-line-breaks-on-push.py`'s presence as covering this rule --- it is scoped to clause density and semicolons, not to ATX-heading collisions (inferred from its own match conditions, which name neither MD018 nor markdownlint).
  (Morrison-Lab/ai-config#3060, 2026-09-03.
  Third occurrence Morrison-Lab/ai-config#3745, 2026-09-17.)
- **markdownlint-cli2 runs locally with no install step, at CI's exact version.**
  `npx --yes markdownlint-cli2@<version>` reads `.markdownlint-cli2.jsonc` and lints the whole repo in seconds;
  take the version from the `lint-markdown` job log, which prints it as its first line.
  Note precisely what this does and does not clear.
  `scripts/run-local-validation.py` offers the tool, unpinned via `npx --no-install`, as a `PARTIAL` equivalent for the `lint-markdown` job: gha's action runs four checks (markdownlint, code-block length, list-item splices, table splits) and a bare call reproduces one, so the runner tags the result `PARTIAL` and names the three it does not cover in `MARKDOWNLINT_UNCOVERED`.
  It used to refuse the partial outright, until refusing left the markdown gate absent from every markdown-only pre-push run (ai-config#3120).
  Running the tool by hand as one named check is sound, and reporting it as the job is the failure that runner exists to prevent.
  **Do:** run it before pushing markdown, and say which of the four checks it covered.
  **Don't:** read a clean markdownlint run as the `lint-markdown` job passing.
  (Morrison-Lab/ai-config#3060, 2026-09-03.)
  **The two flags this bullet already names diverge on a cold cache, and reading the wrong one's failure as "not installable" is a distinct, measured mistake.**
  `--yes` (line above) installs on demand.
  `--no-install` (the `run-local-validation.py` equivalent) refuses instead, by design, whenever the package is not already cached --- that is the whole point of the flag, not a defect in it.
  Measured 2026-09-17 in a remote session's container: `npx --no-install markdownlint-cli2 --version` failed with `npm error npx canceled due to missing packages and no YES option`, and a commit message reported "markdownlint itself is not installable in this container and was not run".
  That commit was `c40259f8` and it was **amended away** once the tool did run, so the quoted wording is no longer reachable from any ref --- a later `git log --all` search finds only the replacement, which says "not installed" rather than "not installable".
  An adversarial review of this entry duly reported the quote as a misquote on exactly that evidence.
  Cite the superseded SHA whenever quoting a commit message you then amended, or the quote is uncheckable by anyone without that repository's dangling objects.
  `npx --yes markdownlint-cli2@0.23.2` then installed and ran cleanly in the same container, reporting 772 files linted and 0 issues.
  **Do:** on a `--no-install` refusal, retry with `--yes` (or a plain install) before concluding the tool is unavailable --- a cold cache and a genuinely missing tool produce the identical error text.
  **Don't:** read `run-local-validation.py`'s own `--no-install` "missing tool" SKIP as a verdict on the tool's availability.
  The script reports it correctly as a cache/install-hint state (see its `install_hint` field), which is the distinction the commit message above collapsed.
  See [`ardi`](../shared/workflow/ardi.md)'s "A flag whose whole job is to forbid the thing being tested" and [`ardi.cases.md`](../shared/workflow/ardi.cases.md)'s "Attempting the base form is not attempting its variants" for the general rule this instantiates.
  (Morrison-Lab/ai-config#3745, 2026-09-17.)
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

- **One sentence per line and gha's list-item-splice check collide inside a list, and the check names the item you did not touch.**
  The two rules are individually reasonable and jointly mean a multi-sentence list item cannot be split in place.
  `lint-markdown`'s `check_list_item_splices.mjs` (Morrison-Lab/gha, read 2026-09-15) walks the file and, for every line that is a list marker, looks at the line *before* it: a finding is raised when that previous line is non-blank and is not itself a list item, heading, blockquote, table row, or horizontal rule.
  Splitting item K across two source lines makes item K's second sentence a bare continuation line, so item **K+1** becomes a marker following a continuation line and is what the error names.
  Diff-scoping does not save you: the check reports the finding when either the flagged line or the previous line is in the added set, and the continuation line you added is the previous line.
  So the reported line number and quoted text belong to an item the commit never edited, which sends the fix to the wrong place.
  The remedy is a blank line between the items.
  The alternative is to leave that item on one line.
  Markdownlint itself has no rule for this gap --- MD032 governs a list's outer boundaries, not the space between items, and is disabled here (`.markdownlint-cli2.jsonc`) --- which is why gha ships a separate checker for it.
  [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md) enumerates that checker among `lint-markdown`'s four, and [`batch-merge-and-resolve`](../shared/workflow/batch-merge-and-resolve.md) owns the splice's other direction: a *merge* that deletes a blank line adds neither line, so the added-lines scoping is blind to it.
  The split case is the opposite --- you add the continuation line, and that is the `prevLineNo` the check tests.
  **Do:** after applying one-sentence-per-line inside a list, put a blank line between every pair of items in that list, and read a splice finding as pointing at the item *after* the one you split.
  **Don't:** debug the item the error names --- check the line above it first.
  **Candidate check.**
  `scripts/run-local-validation.py`'s `lint-markdown` equivalent is tagged `PARTIAL` and names list-item splices among the checks it does not cover (`MARKDOWNLINT_UNCOVERED`), so no derived pre-push run covers this checker.
  Running it means a `Morrison-Lab/gha` checkout and, from the repo you are about to push, `MARKDOWNLINT_GLOBS='*.md' LIST_ITEM_SPLICE_BASE_REF=origin/main node <gha-checkout>/lint-markdown/check_list_item_splices.mjs`.
  Its `git ls-files` and `git diff` run in the process cwd, so running it from the gha checkout checks gha and prints the same clean line.
  Otherwise the checker arrives as a red CI job.
  `scripts/vendor/gha-check-new-line-breaks.py` plus `scripts/sync-nlb-checker.py` is the established shape for vendoring one of gha's checkers so it can run before the push.
  The splice checker is the same kind of small, self-contained, diff-scoped script.
  (ucdavis/lbt#7, 2026-09-15: a numbered link checklist was reflowed one-sentence-per-line, `lint-markdown` went red, and `b3f3ba2` fixed it by separating the items with blank lines.)

- **Don't tag a non-shell CLI block `bash`/`sh` (MD040).**
  MD040 wants a language on every fence, which invites tagging anything command-shaped as `bash`.
  Claude slash commands (`/ums`, `/plugin`, `/also`) and other application-level directives are not shell-executable, so `bash` implies a reader can run them and they fail when someone tries.
  Tag those `text` instead.

- **`lint-qmd` in Morrison-Lab/gha enforces line-length (MD013) on `.qmd` files even when repo-level `.markdownlint-cli2.jsonc` disables it.**
  Markdown in `.md` files in this repository permits long lines (MD013 disabled), but Quarto markdown (`.qmd`) files checked by the reusable `lint-qmd.yml` workflow enforce line-length limits (80 characters for prose, headings, and lists).
  When authoring or updating `.qmd` documents (such as `agents.qmd`), wrap prose lines to <= 80 characters, and take care when editing wrapped lines to avoid truncating mid-sentence clauses across line boundaries.
  (Morrison-Lab/ai-config#3619, 2026-09-12.)

- **Do/Don't guidance bullet ordering within contiguous blocks (ai-config#3751).**
  The corpus convention across guidance blocks is that in any contiguous run of guidance bullets,
  all `- **Do:**` bullets appear before any `- **Don't:**` bullets.
  A block is a contiguous run of top-level `- **Do:**` and `- **Don't:**` bullets.
  A blank line, intervening prose, a heading, or a code fence ends the block,
  and indented lines continue the current bullet.
  Interleaving a Do bullet after a Don't bullet breaks visual scanning and convention consistency.
  `scripts/check-do-dont-order.py` provides an automated checker reporting examined blocks alongside flagged blocks.
  It runs advisory in `validate.yml` and pre-commit until historical blocks are addressed in a dedicated sweep.
  - **Do:** place every `- **Do:**` bullet before any `- **Don't:**` bullet in a guidance block.
  - **Do:** run `python3 scripts/check-do-dont-order.py` locally to verify guidance block bullet order.
  - **Don't:** interleave `- **Do:**` bullets after `- **Don't:**` bullets within the same contiguous guidance block.
  (Morrison-Lab/ai-config#3751, 2026-09-17.)

(Recovered 2026-07-30 from `a739c69`, an orphaned commit on `ums/ardi-review-link-handling`: it landed about 30 minutes after its own PR [#650](https://github.com/Morrison-Lab/ai-config/pull/650) merged, so it never reached `main` and sat unnoticed for a week.
Both rules were first learned on [#645](https://github.com/Morrison-Lab/ai-config/pull/645).)
