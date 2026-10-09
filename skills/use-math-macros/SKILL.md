---
name: use-math-macros
description: "Use shared semantic math macros in all lab math."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# use-math-macros — condense manuscript math onto the shared macros submodule

Rewrite the math expressions in a lab Quarto/LaTeX document so they use the
shared [`Morrison-Lab/macros`](https://github.com/Morrison-Lab/macros) submodule
(migrated from `d-morrison/macros`, whose URLs redirect to it)
(`\Ep`, `\Prf`, `\paren`/`\sb`/`\cb`, `\expit`, `\logit`, `\Var`, `\hp`, `\S`,
`\h`, …) instead of ad-hoc raw LaTeX. This gives every lab document the same
polished, condensed notation, and centralizes the definitions in one versioned
place.

## When this fires

- "macroize", "macroize the math", "use macros", "use the macros submodule",
  "convert math to macros", "polish the math with macros".
- **Every time you write, edit, or review LaTeX math anywhere**: any project or repo, and any format (Quarto, R Markdown, LaTeX, roxygen and `.Rd`, slides, Markdown docs, notebooks), a manuscript or a single equation alike --- this is mandatory, not a polish pass.
  Use the semantic macro for each concept the library names (`\Ep` for a bare expectation operator, `\E{x}` for one subscripted by `x`, `\Var`, `\Cov`, `\P`, …) rather than writing its raw LaTeX, and when no macro names the concept, add one (step 6) rather than writing raw LaTeX (standing rule;
  see `memories/preferences.md`).

## Procedure

### 1. Locate and check out the macros submodule

It is typically vendored at `inst/analyses/macros` (URL in `.gitmodules`):

```bash
grep -A2 'submodule.*macros' .gitmodules      # confirm path + macros URL (either owner name)
git submodule update --init inst/analyses/macros   # checkout at recorded commit
```

To bring it up to date with `Morrison-Lab/macros`:

```bash
git submodule update --remote inst/analyses/macros
```

> **`--remote` bumps the tracked gitlink**, which dirties `git diff HEAD`. If
> the checkout is running SLURM/simulation jobs that stamp git provenance at
> completion (e.g. a `consolidate_provenance`-style reproducibility guard),
> that poisons the run. Do the update in a **separate worktree**, never the
> running checkout:
> `git worktree add ../<repo>-macros -b macros-update origin/main`.

### 2. Wire the include once, at the top of the manuscript

Include the macro definitions before any math renders:

```bash
# working example — inst/analyses/paper.qmd:
#   {{< include macros/macros.qmd >}}
# from vignettes/articles/ the relative path is:
#   {{< include ../../inst/analyses/macros/macros.qmd >}}
grep -rn 'include .*macros/macros.qmd' <manuscript-dir>   # check if already wired
```

Place it near the top of the **top-level** `.qmd` (the one that assembles the
`{{< include >}}`d children), before the first section with math.

The definitions do not blindly override existing LaTeX, and the two definition
forms behave differently: `\def` **always** redefines a name, but MathJax
**skips `\providecommand` for a name that is already defined** — including a
LaTeX built-in like `\v` (caron), `\b`, `\u`, or `\c`. So a `\providecommand`
whose name shadows a built-in silently no-ops: the built-in meaning survives and
the render breaks with no error. The library therefore uses `\def` /
`\renewcommand` (not `\providecommand`) for built-in-shadowing names — e.g.
`\renewcommand{\v}{...}`, `\renewcommand{\vec}{...}`. See the "MathJax ignores
`\providecommand`" note in `memories/preferences.md`.

### 3. Read the macro inventory before rewriting

`macros.qmd` may define macros with any of `\def`, `\providecommand`,
`\newcommand`, or `\renewcommand` (the built-in-shadowing names like `\v`, `\vec`
use `\renewcommand`), so match all four forms:

```bash
grep -cE '^\\(def|providecommand|newcommand|renewcommand)' inst/analyses/macros/macros.qmd   # ~600+ macros
grep -nE '\\(def|providecommand|newcommand|renewcommand)\{?\\(Ep|Prf|paren|sb|cb|expit|logit|Var|hp|S|h)\b' \
  inst/analyses/macros/macros.qmd
```

**Measured 2026-09-06 on `d-morrison/rme`, whose copy of this same macros
library is mounted at `latex-macros/` rather than at the
`inst/analyses/macros/` path used above.**
It is the same `d-morrison/macros` repo either way --- `rme`'s
`.gitmodules` gives `url = https://github.com/d-morrison/macros.git` ---
so the mount path is what varies between consumers, not the library.
An earlier draft of this entry said "not `d-morrison/macros`", which
read as a claim that these are two unrelated macro libraries.
A sweep pattern-matching only `\newcommand{...}`/`\providecommand{...}` reported `\vX` and `\vbeta` as undefined; both are `\def`-defined.
Widening the grep to all four forms above found 30 distinct `v`-prefixed names
defined in that library --- counting distinct defined names rather than uses
(the definition *sites* number 32, since `\v` is defined three times), and including
non-vector names such as `\var` and `\violet` that share the prefix ---
and exactly 2 genuinely undefined (`\vL`, `\vl`).
Same class as the built-in-shadowing case this step already names --- a definition-site grep is only as complete as its list of definition mechanisms, and any macros file mixing TeX primitives can use all four.

- **Do:** run the four-form grep above (or an equivalent covering `\def`, `\providecommand`, `\newcommand`, `\renewcommand`) before asserting any macro is undefined, in every `.qmd`-based macros file, whatever path the consumer mounts it at.
- **Don't:** conclude a macro is undefined from a grep that only matches `\newcommand`/`\providecommand` --- confirm against `\def` and `\renewcommand` too.

### 4. Rewrite the math — using only defined macros

Delegate the heavy rewrite to the `codex` CLI to conserve tokens (pass the macro
inventory and the target file in the prompt), then verify:

```bash
codex exec -C "$PWD" -s read-only --skip-git-repo-check -o /tmp/macroized.out - <<'EOF'
Rewrite the math in <target>.qmd to use ONLY macros defined in
inst/analyses/macros/macros.qmd plus standard LaTeX. Preserve every formula's
meaning exactly and keep all {#eq-...}/{#tbl-...} labels and @eq- refs. Output
the rewritten .qmd, then a list of the custom macro names used.
EOF
```

(Flags per `codex exec --help` — the `exec` subcommand, `-s`/`--sandbox
read-only`, `--skip-git-repo-check`, and `-o`/`--output-last-message` all exist;
verify against your installed codex-cli version, since flag names can shift
between releases.)

**Never invent a macro name** — an undefined command silently breaks the
Quarto/MathJax render. Verify every backslash-command resolves:

```bash
# every custom command in the rewrite must be defined in macros.qmd or be standard LaTeX
comm -23 \
  <(grep -oE '\\[A-Za-z]+' <target>.qmd | sort -u) \
  <(grep -oE '\\(def|providecommand|newcommand|renewcommand)\{?\\[A-Za-z]+' inst/analyses/macros/macros.qmd \
      | grep -oE '\\[A-Za-z]+$' | sort -u)
# review the remainder: each must be standard LaTeX (\frac, \text, \sim, \hat, …)
```

**When the math being rewritten is a *definition*, expand both sides before
believing it.**
The library aliases heavily, so a definition can name a concept on the left and
define it in terms of a second macro on the right, while both expand to the same
glyph.
`\score(\lambda) \eqdef \llik'(\lambda)` reads as a definition in source and
renders as a symbol defined as itself, because `\def\score{\ell'}` and
`\def\llik{\ell}` collapse the two sides.
This is the opposite failure from inventing a macro name: every command resolves,
so the `comm -23` check above passes cleanly and the render emits no warning.

Two greps settle it, and both are cheap:

```bash
# what each side of the definition actually expands to
grep -nE '^\\def\\(score|hess|llik)\b' <macros-dir>/macros.qmd

# whether the library already defines this concept canonically
grep -nE '^\\def\\def[A-Z]' <macros-dir>/macros.qmd
```

The library's own canonical definitions spell the operator out rather than
restating an alias, so prefer that form: `\deriv{\lambda}\llik(\lambda)` for a
score, `\dderiv` for a Hessian.
An alias-only definition is a deviation from house style, not a shorthand for it.
Verify the result by reading the **rendered** page, per
[`fact-check-prose`](../../shared/writing/fact-check-prose.md)'s "A definition
can resolve, render, and still say nothing" --- source cannot show this, and
neither can a check that the crossref resolves.

### 5. Fix the vignette spellcheck leak

Custom macro command-names (`paren`, `Ep`, `expit`, `Prf`, `cb`, …) **leak into
`spelling::spell_check_package()` for `.qmd` files under `vignettes/`** — the
spelling LaTeX filter strips common commands like `\text`/`\frac` but not custom
macros. Add every custom macro name used, plus genuine terms (`expit`,
`exchangeability`), to `inst/WORDLIST`:

```bash
printf 'expit\nexchangeability\nparen\nEp\nPrf\n' >> inst/WORDLIST   # + the names step 4 listed
LC_ALL=C sort -u -o inst/WORDLIST inst/WORDLIST
```

Files under `inst/analyses/` are **not** spell-checked, so this only bites for
math in `vignettes/`.

### 6. Add missing macros to the submodule when helpful

If a needed concept has no macro, add it to `Morrison-Lab/macros` via a PR to that
repo — do **not** define a one-off command inline in the manuscript:

```bash
cd inst/analyses/macros
git checkout -b add-<concept>-macro
# edit macros.qmd, then push + open a PR to Morrison-Lab/macros
```

Name the new macro for the concept it denotes, not for its typography, so it stays semantic.
The macros repo carries a standing `mwc` grant, so merge the macro PR yourself once it is fully clean (see `STANDING_MERGE_GRANT_REPOS` in `hooks/no-unauthorized-merge.py`).
Bump the submodule pointer in the manuscript repo once that macro PR merges.

When the macros PR can't happen in this session,
a repo-local macro file is an acceptable stopgap
(such as `_subfiles/_macros-sds.qmd` in sds);
an inline one-off command in a document still is not.
Every macro added to a repo-local macro file
gets an issue in [`Morrison-Lab/macros`](https://github.com/Morrison-Lab/macros) in the same turn,
listing each new definition, what it means, and any existing macro it overlaps.
In a remote session that has the repo attached under its old name,
the issue tool accepted owner `d-morrison` and GitHub redirected the issue to the migrated repo
(measured once, 2026-10-05: [Morrison-Lab/macros#103](https://github.com/Morrison-Lab/macros/issues/103)).

- **Do:** file the `Morrison-Lab/macros` issue in the same turn
  that you add a macro to any repo-local macro file.
- **Don't:** leave a repo-local macro for a later upstreaming pass;
  [Morrison-Lab/sds#54](https://github.com/Morrison-Lab/sds/pull/54) accumulated 13 of them before anyone filed the issue.

### 7. Verify the render and spellcheck, then ship

Run the raw-notation lint over what you changed, pointing it at the library so its operator macros extend the rules:

```bash
python3 <ai-config>/scripts/check-raw-math.py --macros inst/analyses/macros/macros.qmd <changed files or dirs>
```

It exits 1 and prints `file:line: raw -> use macro` for each hit.
`hooks/warn-raw-math-notation.py` runs the lint's built-in patterns at write time and warns, never blocks.

```bash
quarto render <manuscript>.qmd            # must render with the macros include
Rscript -e 'print(spelling::spell_check_package())'   # must be 0 rows
```

Commit the rewritten `.qmd`, the `include` line, the submodule pointer, and the
`WORDLIST` on a branch, open a PR, and drive it to clean.

## Relationship to other skills

- **`convert-repo-format`** — scaffolds the `macros/` submodule when converting a
  repo to a Quarto book/website (`git submodule add`); this skill rewrites math
  *onto* an already-present submodule. Adjacent concerns.
- **`use-preferred-style` / `find-ai-tells`** — the prose counterparts: they
  polish and de-slop written prose; this skill polishes math notation.
- **`memorize` / `remember`** — the paired standing rule ("always use the macros
  submodule for math") lives in `memories/preferences.md`; this skill is the
  executable how.
- **`ardi` / `request-pr-review`** — used to ship and clean the PR this skill
  produces.

## Macros that `\renewcommand` a standard command take a mandatory argument

`macros.qmd` redefines `\exp` (`\renewcommand{\exp}[1]{\operatorname{exp}\cb{#1}}`), `\vec`, and `\v` with one mandatory argument each.
A bare `$\exp$` (the function name, no argument) makes the macro swallow the closing math delimiter as its argument, which leaves `\cb`'s `\left`/`\right` unbalanced.
MathJax renders that without complaint; lualatex fails with `Missing \right. inserted`.
So an HTML render is no evidence that the PDF builds.

Similarly, writing `\exp\paren{...}` or `\exp(...)` triggers delimiter failures in LaTeX:
because `\exp` wraps its mandatory `#1` in `\cb{#1}`,
passing `\paren` makes `\exp` take `\paren` as `#1`,
leaving unbalanced delimiters in LuaLaTeX (`! Missing delimiter (. inserted)`).
Writing `\exp(...)` makes `\exp` consume only the opening parenthesis `(` as `#1`,
leaving the closing `)` unmatched.
The required form is `\exp{...}` or `e^{...}`.

Measured 2026-09-28 on `Morrison-Lab/pds`: Quarto Publish run 36516449603 failed on `$\exp$` in `_subfiles/_sec-distributions.qmd`.
Fixed by Morrison-Lab/pds#34, which spelled out "the exponential function";
the zero-argument `\expt` also works.
Tracked in Morrison-Lab/pds#33.
Recurred 2026-10-06 on `Morrison-Lab/mds#175`
with `\exp\paren{-\frac{x^2}{2}}` and `\exp(x^8)`,
breaking LuaLaTeX compilation with missing delimiter errors;
fixed by changing to `\exp{-\frac{x^2}{2}}` and `\exp{x^8}`.

- **Do:** write `\exp{...}` or `e^{...}` when applying the exponential function to an argument.
- **Do:** name the function in prose, or use a zero-argument form (`\expt`), when no argument is meant.
- **Do:** grep for bare uses, e.g. `grep -rnE '\\(exp|vec|v)([^a-zA-Z{]|$)' --include='*.qmd'`, and render the PDF target when touching math.
  The grep is a candidate finder: it also flags valid space-separated arguments (`\vec \beta`) and the definitions themselves, so read each hit.
- **Don't:** write `\exp\paren{...}` or `\exp(...)` — `\exp` takes a mandatory `#1` wrapped in `\cb{#1}`.
  Use `\exp{...}` or `e^{...}` instead.
- **Don't:** write a bare `$\exp$` (or `\vec`, `\v`).
- **Don't:** treat a clean HTML render as evidence the PDF builds.

## Common undefined shorthand and macro collisions in `macros.qmd`

- **Undefined matrix and vector shorthands (`\mA`, `\vw`)**: while `macros.qmd` defines `\mX` (`\matr{X}`), `\mx`, `\vx` (`\vecf{x}`), `\va`, etc., it does **not** define arbitrary shorthands like `\mA` or `\vw`.
  Bare `\mA` or `\vw` are undefined and break LuaLaTeX during PDF compilation.
  Use `\matr{A}` for matrices and `\vec{w}` or `\vecf{w}` for vectors.
- **Undefined square bracket macro (`\bracket`)**: `macros.qmd` does **not** define `\bracket{...}`.
  Using `\bracket{...}` (such as for definite integral evaluation limits)
  fails in LaTeX as an undefined control sequence.
  Use `\sb{...}` (square bracket) instead
  (`\sb{...}` wraps in `\mathopen{}\left[...\right]\mathclose{}`).
  ([`Morrison-Lab/mds#175`](https://github.com/Morrison-Lab/mds/pull/175), 2026-10-06.)
- **Latin vector collision with `\vb`**: `macros.qmd` defines `\def\b{\beta}` and `\def\vb{\vec \b}`, which expands to Greek `\vec{\beta}` rather than Latin vector $b$.
  When denoting a Latin vector (such as an intercept or bias vector $b$), do not use `\vb`;
  use `\vec{b}` or `\vecf{b}`.
  ([`Morrison-Lab/mds#48`](https://github.com/Morrison-Lab/mds/pull/48), 2026-09-29.)

## No Greek letters in math source: name macros for meaning

A semantic macro is named for what a symbol means, not for the letter it prints.
`\vdelta`, `\vbeta`, `\hb`, `\bfbeta`, `\vth`, `\eps` and `\lam` only spell a Greek letter, so they are no more semantic than the raw `\delta`.
Outside a passage that discusses the notation itself (a symbol table, a note on which letter a field uses), write no Greek letter in a math expression, either raw or inside a letter-named macro.
Use the macro that names the concept (`\vcoef`, `\regcoef`, `\mean`, `\lincomp`, `\odds`, `\rate`, `\haz`, `\sigmoid`), and when none exists, add one named for the concept to `Morrison-Lab/macros` first (step 6).
For example, write the backpropagation error as `\backerr^{(\ell)}`, not `\vdelta^{(\ell)}`, and the step size as `\learnrate`, not `\eta`.
[`Morrison-Lab/macros#113`](https://github.com/Morrison-Lab/macros/pull/113) added a concept macro for each meaning the course sites use
(`\sdpar`, `\varpar`, `\noise`, `\regpar`, `\param`, `\slack`, `\siglevel` and the rest; `interpretations.tsv` lists them all), so search it before adding one.
A new name must not clash with a TeX primitive or a package command: `\penalty` (a primitive) broke every PDF, and `siunitx` defines `\ang`.
One letter often means different things on different pages (`\sigma` for a standard deviation and for the sigmoid;
`\lambda` for a rate, a penalty and an eigenvalue), so choose the macro from each use's meaning, not from the letter.
(Directive from the user, 2026-10-08: "except when we're discussing notation directly, I don't want any hardcoded greek letters in latex expression, even in compounds like \vdelta;
that's still not a semantic macro".
Prose rule: [`Morrison-Lab/psw#136`](https://github.com/Morrison-Lab/psw/pull/136); detection: [`Morrison-Lab/ai-config#4381`](https://github.com/Morrison-Lab/ai-config/issues/4381).)

### Decorators name a role too: `\est{}`, not `\hat`

The same rule covers decorators.
`\hat`, `\tilde` and `\bar` say how a symbol is drawn, not what it means, and a hat can mark an estimate, a fitted value or a transform.
So `\hat{\mean}` is no more semantic than `\mu`: write `\est{\mean}` (from `Morrison-Lab/macros`, which prints a hat) for an estimate, and the `\est`-based forms where a compound exists (`\ecoef{j}`, `\evcoef`, `\esdpar`) rather than the hat-based `\hcoef{j}`, `\hvcoef`, `\hsdpar`.
Pick a compound built on a concept macro: `\esig` and `\hs` also spell the Greek letter, so the section above already rules them out.
When a decorated quantity has no role macro, add one to `Morrison-Lab/macros` first, as for Greek letters.
Keep `\hat` only where the text discusses the notation itself.
This is the target state rather than a blocker on current work: write new math this way now, and convert existing hats in their own sweep PRs.

- **Do:** write `\est{\mean}` or `\ecoef{j}` for an estimate in new or edited math.
- **Don't:** introduce `\hat{...}` or a hat-based compound (`\hcoef`, `\hvb`) in new math.

(Directive from the user, 2026-10-08: "eventually, we want to remove even non-semantic decorators like \hat in favor of semantic macros like `\est`".
Prose rule: [psw `chapters/notation/shared-macros.qmd`](https://github.com/Morrison-Lab/psw/blob/main/chapters/notation/shared-macros.qmd); sweep and detection: [`Morrison-Lab/ai-config#4438`](https://github.com/Morrison-Lab/ai-config/issues/4438).)

### Latin letters with a fixed role: `\outvar`, `\predvar`, `\resid`

A Latin letter that stands for a role in a model needs a role macro too.
Write `\outvar`/`\Outvar`/`\voutvar` for the outcome variable, not a bare `y` or `\vy`.
Write `\predvar`/`\Predvar`/`\vpredvar` for a predictor, not a bare `x` or `\vx`.
Write `\eoutvar` for a predicted outcome.
Write `\resid`/`\vresid` for a residual (observed minus predicted) and `\prederr` for a prediction error (predicted minus observed), not a bare `e` or `\ve`;
for an observation used in the fit, the residual is the negative of the prediction error (sds `#thm-prediction-error-residual`).
For a parameter estimate, write `\erf{\eparam}` (estimate minus truth, sds `#def-estimation-error`).
A letter used generically (a function argument, an integration variable) stays a letter.
`\vx` and `\vy` remain defined;
existing uses are converted in the sweep, [`Morrison-Lab/ai-config#4440`](https://github.com/Morrison-Lab/ai-config/issues/4440), not as a side edit.
The macros land with `Morrison-Lab/macros#117`;
until a repo's `latex-macros` pin includes it, keep the existing letters there.

- **Do:** write `\resid_i = \outvar_i - \eoutvar_i` in new or edited math.
- **Don't:** write `e_i = y_i - \hat{y}_i`.

(Directive from the user, 2026-10-09: "let's use a semantic macro rather than a bare `e`. even `y` should be a macro for outcome variable, and `x` should be a macro for predictor variable(s)".
Macros: [`Morrison-Lab/macros#117`](https://github.com/Morrison-Lab/macros/pull/117); sweep: [`Morrison-Lab/ai-config#4440`](https://github.com/Morrison-Lab/ai-config/issues/4440).)

## Prefer command operator macros that take arguments over manual delimiter wrappers

There should be very few instances where it is necessary to write `\cb` (curly braces), `\sb` (square brackets), or `\paren` directly with a bare operator.
Instead, use the functional command version of the operator macro that takes its operand as an argument and wraps it in delimiters automatically:

- **Expectation**: write `\Expf{X}` or `\E{X}` (expands to `\distop{E}\sb{X}`), not bare operator `\Ep` followed by manual `\sb{X}` (`\Ep\sb{X}`).
- **Variance / Covariance**: write `\Var{X}` or `\Cov{X, Y}`, not `\Vart\paren{X}`.
- **Probability / Quantile**: write `\Prf{A}` or `\Qf{p}`, not `\Pr\paren{A}` or `\Q\paren{p}`.
- **Exponential**: write `\expf{x}` or `\exp{x}` (or `e^{x}`), not `\expt\paren{x}`.
- **Indicator**: write `\indicp{P}` or `\indic{A}(x)`.

Reserve direct `\sb{...}`, `\cb{...}`, and `\paren{...}` for mathematical grouping, sets ($\cb{1, \dots, n}$), evaluation limits, or raw algebra that does not denote an operator with a dedicated macro.
(Directive from the user, 2026-10-07.)

## Prefer dot products over transpose products and inner products

When two vectors multiply to give a number, write a dot product, `\dprod{\vx}{\vbeta}` ($\vx \cdot \vbeta$),
not a transpose product (`\vx^\top \vbeta`, `\vx' \vbeta`, `\tprod{\vx}{\vbeta}`)
or inner-product brackets (`\langle \vx, \vbeta \rangle`, `\iprod{\vx}{\vbeta}`).
For example, write a linear model as $f(\vx) = \dprod{\vx}{\vbeta}$, not $f(\vx) = \vx^\top \vbeta$.
Keep the transpose where the product is not a dot product of two vectors:
a matrix product (`\tp{X} X`), an outer product, or a quadratic form (`\tprod{\vx}{\matr{A}} \vx`).
Keep inner-product brackets where the text means a general inner product,
such as the definition of an inner product space.
The prose rule is psw's [Writing dot products](https://github.com/Morrison-Lab/psw/pull/135).
(Directive from the user, 2026-10-08, on `Morrison-Lab/lds#488`.)

## Anti-patterns

- ❌ Inventing a macro name not defined in `macros.qmd` — it silently breaks the
  render. Verify every command resolves (step 4).
- ❌ Using bare `\mA` or `\vw` expecting them to expand to matrices or vectors --- they are undefined in `macros.qmd` and break LuaLaTeX during PDF compilation.
  Use `\matr{A}` and `\vec{w}` / `\vecf{w}` instead.
- ❌ Using `\bracket{...}` for square brackets — `\bracket` is undefined in `macros.qmd`.
  Use `\sb{...}` instead.
- ❌ Writing `\exp\paren{...}` or `\exp(...)` — `\exp` wraps its mandatory `#1` in `\cb{#1}`;
  passing `\paren` or `(...)` breaks delimiter balance in LuaLaTeX (`! Missing delimiter (. inserted)`).
  Use `\exp{...}` or `e^{...}` instead.
- ❌ Using `\vb` for Latin vector $b$ (e.g. bias or intercept) --- `macros.qmd` defines `\vb` as `\vec{\beta}` (Greek beta), colliding with Latin vector $b$.
  Use `\vec{b}` or `\vecf{b}` instead.
- ❌ Running `git submodule update --remote` in a checkout that is running
  provenance-stamped SLURM jobs — it dirties the tree and poisons the run. Use a
  worktree.
- ❌ Forgetting the `inst/WORDLIST` additions for macros used in `vignettes/`
  math — spellcheck fails on the leaked command-names.
- ❌ Defining a one-off `\newcommand` inline instead of adding it to the shared
  submodule.
- ❌ Defining a built-in-shadowing macro (`\v`, `\b`, `\u`, `\c`, accents, …)
  with `\providecommand` — MathJax skips it because the built-in is already
  defined, so the built-in survives and the render breaks silently. Use `\def` /
  `\renewcommand` for those names (see step 2 and `memories/preferences.md`).
- ❌ Defining a macro'd concept by restating another macro (`\score \eqdef
  \llik'`) --- the aliases collapse, so the rendered page shows a symbol defined as
  itself while the source reads as a proper definition.
  Spell the operator out (`\deriv`, `\dderiv`), and check the rendered output
  rather than the source.
- ❌ Changing a formula's meaning while "condensing" — preserve the math exactly;
  only re-express it.
