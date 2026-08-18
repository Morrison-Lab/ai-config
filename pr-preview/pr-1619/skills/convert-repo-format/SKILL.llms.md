# convert-repo-format — convert a repo between SERG project formats

Take a repo that’s built as one project format and rebuild it as another. The lab has four formats, each with a template repo that is the **source of truth** for what that format’s files, config, and CI look like:

| Format | Template | `project.type` | Output dir | Is it an R package? |
|----|----|----|----|----|
| R package | [`rpt`](https://github.com/UCD-SERG/rpt) | — (no `_quarto.yml`) | altdoc site | Yes — full package |
| Quarto website | [`qwt`](https://github.com/UCD-SERG/qwt) | `website` | `_site` | Yes — light package |
| Quarto book | [`qbt`](https://github.com/UCD-SERG/qbt) | `book` | `docs` | No (`Type: Book`) |
| Quarto manuscript | [`qmt`](https://github.com/d-morrison/qmt) | `manuscript` | `_manuscript` | Yes — light package |

The core move is **diff against the target template, not rewrite from scratch.** The four formats share most of their scaffolding (R tooling, spell/lint/link checks, the `@claude` and Copilot workflows). A conversion keeps that shared layer, swaps the project config, and changes only the format-specific files.

## When this fires

- “convert this repo to a Quarto book / website / manuscript / R package”
- “crf”, “convert repo format”, “change this repo’s project type”
- “turn this book into a website”, “make this manuscript an R package”, “reformat this as a Quarto manuscript”
- Any request to re-home an existing repo’s content into a different one of the four template formats above.

This is normal new work, so run it **issue-first** (the `st` skill): file a tracking issue, branch, convert, open a PR, and ARDI to clean.

## Step 1 — detect the current format

Read the signature files. Each format has a tell:

``` bash
ls -A
cat DESCRIPTION 2>/dev/null
sed -n '1,15p' _quarto.yml 2>/dev/null
```

- **R package** (`rpt`): no `_quarto.yml`; `DESCRIPTION` with `Package:` + `Imports:`/`Suggests:` + `Roxygen:`; `R/`, `man/`, `NAMESPACE`, `tests/testthat/`, `vignettes/`, `altdoc/`, `NEWS.md`, `renv.lock`.
- **Quarto website** (`qwt`): `_quarto.yml` with a `profile:` key **plus** a `_quarto-website.yml` whose `project.type` is `website` (`output-dir: _site`); `index.qmd`, `chapters/`, reveal.js files (`styles-reveal.scss`, `qwt-reveal-toggle.html`, `revealjs-*.lua`).
- **Quarto book** (`qbt`): `_quarto.yml` with `project.type: book` (`output-dir: docs`, `pre-render: pre-render.py`) and a `book:` block listing chapters; `macros-header.html`; `DESCRIPTION` is `Type: Book` (not a package).
- **Quarto manuscript** (`qmt`): `_quarto.yml` with `project.type: manuscript` (`output-dir: _manuscript`) and a `manuscript:` block with `article:` + `notebooks:`; `notebooks/`, `_repo-links.lua`.

State the detected source and the requested target before touching anything.

## Step 2 — get the target template as your reference

Work against the **actual** target template, not memory — the templates evolve.

- If the template repo is checked out locally (a sibling dir), read it there.
- Otherwise fetch files over raw HTTP (works for public repos even when `gh`/MCP aren’t scoped to them): `https://raw.githubusercontent.com/<owner>/<template>/main/<path>` (`UCD-SERG` for `rpt`/`qwt`/`qbt`, `d-morrison` for `qmt`).
- List the target’s `.github/workflows/` and top-level files first so you know the full target shape.

## Step 3 — keep the shared scaffolding

These exist in every format; carry them across unchanged (update repo-specific strings only):

- R/build tooling: `.Rbuildignore`, `.Rprofile`, `.lintr.R`, `.gitattributes`, `.gitignore`, `project.Rproj`, `inst/WORDLIST`.
- Repo docs: `LICENSE`, `README.Rmd` → `README.md`, `CONTRIBUTING.md` / `CODE_OF_CONDUCT.md`.
- Shared CI: `.github/workflows/` `claude.yml`, `claude-code-review.yml`, `copilot-setup-steps.yml`, `check-spelling.yaml`. Most workflows are thin callers of the reusable workflows in [`d-morrison/gha`](https://github.com/d-morrison/gha) pinned `@v1`, so “convert the CI” mostly means copying the target template’s `.github/workflows/` and updating repo-specific inputs — not rewriting logic.

## Step 4 — swap the project config and format-specific files

Add what the target needs; remove what only the source needed. Per target:

### → R package (`rpt`)

- **Remove** all Quarto config and content: `_quarto.yml`, `_quarto-website.yml`, `_extensions/`, `*.qmd` site pages, `styles*.css/scss`, reveal.js filters, `macros/` (submodule), `lychee.toml`, `pre-render.py`, `_repo-links.lua`, `references.qmd`.
- **Add** the full package skeleton: `R/`, `man/` (generated), `NAMESPACE` (generated), `tests/testthat/`, `vignettes/`, `data-raw/`, `altdoc/`, `NEWS.md`, `renv.lock`, `codecov.yml`, `CHECKLIST.md`.
- **`DESCRIPTION`** becomes a full package: real `Imports:`/`Suggests:`, `Roxygen: list(markdown = TRUE)`, `Config/testthat/edition: 3`, `VignetteBuilder`, `Config/Needs/website: quarto`. Move any prose content into a vignette (`.qmd`/`.Rmd`) under `vignettes/`.
- Docs are built by **altdoc** (not pkgdown, no `_quarto.yml`) via the `docs.yaml` workflow. The `rpt` template uses the lab’s own altdoc config — a committed `altdoc/` directory (`altdoc/quarto_website.yml`, `_extensions/`, `scripts/`) plus a custom `d-morrison/altdoc` fork — so `render_docs()` generates `.qmd` files into `altdoc/man/` from `man/*.Rd` at build time (not committed), then renders the site. Mirror `rpt`’s `altdoc/` directory rather than configuring altdoc from scratch.

### → Quarto website (`qwt`)

- **Add** `_quarto.yml` (with `profile: default: website`) **and** `_quarto-website.yml` (`project.type: website`, `output-dir: _site`, the `website:` nav/footer block). Add `index.qmd`, `chapters/`, `references.qmd` + `references.bib`, `styles.css`, `_extensions/`, the reveal.js slide files (`styles-reveal.scss`, `qwt-reveal-toggle.html`, `revealjs-*.lua`), `lychee.toml`, and the `macros/` submodule.
- Keep a **light** R package (`R/<pkg>-package.R`, `man/`, `NAMESPACE`, `DESCRIPTION` with `Depends`/`Suggests`) — it’s what gives the repo R tooling.

### → Quarto book (`qbt`)

- **Add** `_quarto.yml` with `project.type: book` (`output-dir: docs`, `pre-render: pre-render.py`) and a `book:` block listing `chapters:` (`index.qmd`, `chapter*.qmd`, `references.qmd`) and `appendices:`. Add `pre-render.py`, `macros-header.html`, `styles.css`, `references.bib`, `lychee.toml`, and the `macros/` submodule.
- **`DESCRIPTION`** is minimal (`Type: Book`, no `Imports`/`Roxygen`). The book template is **not** a full R package — there’s no `R/`/`NAMESPACE`, and `qbt` carries no top-level `CLAUDE.md`. Drop the package skeleton if converting from a package or light-package format.

### → Quarto manuscript (`qmt`)

- **Add** `_quarto.yml` with `project.type: manuscript` (`output-dir: _manuscript`) and a `manuscript:` block (`article: index.qmd`, `notebooks:`). Add `index.qmd` (the article), `notebooks/` (supplementary notebooks), `_repo-links.lua`, `_extensions/`, `styles.css`, `references.bib`, `lychee.toml`.
- Keep a **light** R package skeleton, like the website format.

## Step 5 — convert the CI workflows

Replace the source’s `.github/workflows/` with the target’s set (keeping the shared four from Step 3). The format-specific workflows:

- **R package** (`rpt`): `R-CMD-check.yaml`, `R-check-docs.yml`, `check-readme.yaml`, `docs.yaml` (altdoc deploy), `lint-changed-files.yaml`, `news.yaml`, `pr-commands.yaml`, `test-coverage.yaml`, `version-check.yaml`.
- **Quarto, all three**: `check-bibliography-dois.yml`, `check-links.yml`, `check-non-standard-chars.{yaml,yml}` (the extension varies by template — `.yaml` in `qwt`/`qmt`, `.yml` in `qbt`), `lint-project.yaml`, `preview.yml`, `publish.yml` (deploy to `gh-pages`), `summary.yml`. The website and manuscript formats also carry `lint-changed-files.yaml`; the book format does not.

Update each workflow’s repo-specific inputs (output dir, deploy paths, package name). Don’t hand-rewrite reusable-workflow logic — adjust the caller’s `with:`.

## Step 6 — verify against the target’s checks

Run the checks the **target** format uses, not the source’s:

- **R package**: `devtools::document()` (sync `man/`/`NAMESPACE`), `lintr::lint_package()`, `devtools::test()`, `devtools::check()`; add a `NEWS.md` bullet.
- **Quarto (any)**: `quarto render` (output lands in the format’s output dir), `lintr::lint_dir()`, spell check against `inst/WORDLIST`, link check (`lychee.toml`), and scan the rendered HTML for broken cross-refs/citations (the `crr` / `check-rendered-refs` skill).

Then open the PR (`Closes #<issue>`), explain the source → target conversion in the body, and ARDI it to clean.

## Notes

- **Scope the diff honestly.** A conversion is large; keep it to the format change. Don’t smuggle in content rewrites beyond what the new format requires (e.g. splitting prose into chapters for a book, or into a vignette for a package).
- **`macros/` is a git submodule** in `qwt`/`qbt` — add it with `git submodule add <url> macros`, don’t copy the files. Read `<url>` from the target template’s `.gitmodules` (currently `https://github.com/d-morrison/macros`).
- **Generated files** (`man/`, `NAMESPACE`, `README.md`, `_site/`/`docs/`/ `_manuscript/`) are build outputs — regenerate them, don’t hand-edit.
- When the conversion is between the two **light-package** Quarto formats (website ↔︎ manuscript), the R skeleton and most workflows are already right — the change is mostly the `_quarto.yml` project block and the content entrypoints.

Back to top
