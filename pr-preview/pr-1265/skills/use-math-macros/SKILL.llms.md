# use-math-macros — condense manuscript math onto the shared macros submodule

Rewrite the math expressions in a lab Quarto/LaTeX document so they use the shared [`d-morrison/macros`](https://github.com/d-morrison/macros) submodule (`\Ep`, `\Prf`, `\paren`/`\sb`/`\cb`, `\expit`, `\logit`, `\Var`, `\hp`, `\S`, `\h`, …) instead of ad-hoc raw LaTeX. This gives every lab document the same polished, condensed notation, and centralizes the definitions in one versioned place.

## When this fires

- “macroize”, “macroize the math”, “use macros”, “use the macros submodule”, “convert math to macros”, “polish the math with macros”.
- Any time you write or review substantial math in a lab `.qmd` — apply the macros rather than one-off LaTeX (standing rule; see `memories/preferences.md`).

## Procedure

### 1. Locate and check out the macros submodule

It is typically vendored at `inst/analyses/macros` (URL in `.gitmodules`):

``` bash
grep -A2 'submodule.*macros' .gitmodules      # confirm path + d-morrison/macros URL
git submodule update --init inst/analyses/macros   # checkout at recorded commit
```

To bring it up to date with `d-morrison/macros`:

``` bash
git submodule update --remote inst/analyses/macros
```

> **`--remote` bumps the tracked gitlink**, which dirties `git diff HEAD`. If the checkout is running SLURM/simulation jobs that stamp git provenance at completion (e.g. a `consolidate_provenance`-style reproducibility guard), that poisons the run. Do the update in a **separate worktree**, never the running checkout: `git worktree add ../<repo>-macros -b macros-update origin/main`.

### 2. Wire the include once, at the top of the manuscript

Include the macro definitions before any math renders:

``` bash
# working example — inst/analyses/paper.qmd:
#   {{< include macros/macros.qmd >}}
# from vignettes/articles/ the relative path is:
#   {{< include ../../inst/analyses/macros/macros.qmd >}}
grep -rn 'include .*macros/macros.qmd' <manuscript-dir>   # check if already wired
```

Place it near the top of the **top-level** `.qmd` (the one that assembles the `{{< include >}}`d children), before the first section with math.

The definitions do not blindly override existing LaTeX, and the two definition forms behave differently: `\def` **always** redefines a name, but MathJax **skips `\providecommand` for a name that is already defined** — including a LaTeX built-in like `\v` (caron), `\b`, `\u`, or `\c`. So a `\providecommand` whose name shadows a built-in silently no-ops: the built-in meaning survives and the render breaks with no error. The library therefore uses `\def` / `\renewcommand` (not `\providecommand`) for built-in-shadowing names — e.g. `\renewcommand{\v}{...}`, `\renewcommand{\vec}{...}`. See the “MathJax ignores `\providecommand`” note in `memories/preferences.md`.

### 3. Read the macro inventory before rewriting

`macros.qmd` may define macros with any of `\def`, `\providecommand`, `\newcommand`, or `\renewcommand` (the built-in-shadowing names like `\v`, `\vec` use `\renewcommand`), so match all four forms:

``` bash
grep -cE '^\\(def|providecommand|newcommand|renewcommand)' inst/analyses/macros/macros.qmd   # ~600+ macros
grep -nE '\\(def|providecommand|newcommand|renewcommand)\{?\\(Ep|Prf|paren|sb|cb|expit|logit|Var|hp|S|h)\b' \
  inst/analyses/macros/macros.qmd
```

### 4. Rewrite the math — using only defined macros

Delegate the heavy rewrite to the `codex` CLI to conserve tokens (pass the macro inventory and the target file in the prompt), then verify:

``` bash
codex exec -C "$PWD" -s read-only --skip-git-repo-check -o /tmp/macroized.out - <<'EOF'
Rewrite the math in <target>.qmd to use ONLY macros defined in
inst/analyses/macros/macros.qmd plus standard LaTeX. Preserve every formula's
meaning exactly and keep all {#eq-...}/{#tbl-...} labels and @eq- refs. Output
the rewritten .qmd, then a list of the custom macro names used.
EOF
```

(Flags per `codex exec --help` — the `exec` subcommand, `-s`/`--sandbox read-only`, `--skip-git-repo-check`, and `-o`/`--output-last-message` all exist; verify against your installed codex-cli version, since flag names can shift between releases.)

**Never invent a macro name** — an undefined command silently breaks the Quarto/MathJax render. Verify every backslash-command resolves:

``` bash
# every custom command in the rewrite must be defined in macros.qmd or be standard LaTeX
comm -23 \
  <(grep -oE '\\[A-Za-z]+' <target>.qmd | sort -u) \
  <(grep -oE '\\(def|providecommand|newcommand|renewcommand)\{?\\[A-Za-z]+' inst/analyses/macros/macros.qmd \
      | grep -oE '\\[A-Za-z]+$' | sort -u)
# review the remainder: each must be standard LaTeX (\frac, \text, \sim, \hat, …)
```

### 5. Fix the vignette spellcheck leak

Custom macro command-names (`paren`, `Ep`, `expit`, `Prf`, `cb`, …) **leak into `spelling::spell_check_package()` for `.qmd` files under `vignettes/`** — the spelling LaTeX filter strips common commands like `\text`/`\frac` but not custom macros. Add every custom macro name used, plus genuine terms (`expit`, `exchangeability`), to `inst/WORDLIST`:

``` bash
printf 'expit\nexchangeability\nparen\nEp\nPrf\n' >> inst/WORDLIST   # + the names step 4 listed
LC_ALL=C sort -u -o inst/WORDLIST inst/WORDLIST
```

Files under `inst/analyses/` are **not** spell-checked, so this only bites for math in `vignettes/`.

### 6. Add missing macros to the submodule when helpful

If a needed concept has no macro, add it to `d-morrison/macros` via a PR to that repo — do **not** define a one-off command inline in the manuscript:

``` bash
cd inst/analyses/macros
git checkout -b add-<concept>-macro
# edit macros.qmd, then push + open a PR to d-morrison/macros
```

Bump the submodule pointer in the manuscript repo once that macro PR merges.

### 7. Verify the render and spellcheck, then ship

``` bash
quarto render <manuscript>.qmd            # must render with the macros include
Rscript -e 'print(spelling::spell_check_package())'   # must be 0 rows
```

Commit the rewritten `.qmd`, the `include` line, the submodule pointer, and the `WORDLIST` on a branch, open a PR, and drive it to clean.

## Relationship to other skills

- **`convert-repo-format`** — scaffolds the `macros/` submodule when converting a repo to a Quarto book/website (`git submodule add`); this skill rewrites math *onto* an already-present submodule. Adjacent concerns.
- **`use-preferred-style` / `find-ai-tells`** — the prose counterparts: they polish and de-slop written prose; this skill polishes math notation.
- **`memorize` / `remember`** — the paired standing rule (“always use the macros submodule for math”) lives in `memories/preferences.md`; this skill is the executable how.
- **`ardi` / `request-pr-review`** — used to ship and clean the PR this skill produces.

## Anti-patterns

- ❌ Inventing a macro name not defined in `macros.qmd` — it silently breaks the render. Verify every command resolves (step 4).
- ❌ Running `git submodule update --remote` in a checkout that is running provenance-stamped SLURM jobs — it dirties the tree and poisons the run. Use a worktree.
- ❌ Forgetting the `inst/WORDLIST` additions for macros used in `vignettes/` math — spellcheck fails on the leaked command-names.
- ❌ Defining a one-off `\newcommand` inline instead of adding it to the shared submodule.
- ❌ Defining a built-in-shadowing macro (`\v`, `\b`, `\u`, `\c`, accents, …) with `\providecommand` — MathJax skips it because the built-in is already defined, so the built-in survives and the render breaks silently. Use `\def` / `\renewcommand` for those names (see step 2 and `memories/preferences.md`).
- ❌ Changing a formula’s meaning while “condensing” — preserve the math exactly; only re-express it.

Back to top
