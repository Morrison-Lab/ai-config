# Cursor Cloud specific instructions

This repo has no compiled app or long-running service.
The "product" is three things: a Quarto documentation website, a suite of
Python validators/tests under `scripts/`, and the enforcement hooks under
`hooks/`.
Standard commands are already documented --- lint/test steps in
[`.github/workflows/validate.yml`](../../.github/workflows/validate.yml) and the
quality gates in [`README.md`](../../README.md) --- so consult those rather than
re-deriving them; the build and preview commands are in the bullets below.
The startup update script keeps the `shared/sembr-skills` submodule current;
the system tools below (Quarto, the `python` shim, `pre-commit`) are already
present in the environment.

Non-obvious caveats worth knowing:

- **Lint:** the three fast checks under
  [`Verify changes before pushing`](../../AGENTS.md#verify-changes-before-pushing) cover this;
  see that section rather than a second pinned command list here.
- **Test:** the `scripts/test_*.py` suites (each runnable directly with
  `python3`); `validate.yml` lists the full set CI runs.
  `scripts/test_compare_shell_forms.py` spawns a real `bash` that invokes
  `python` (not `python3`), so it needs a `python` shim on `PATH`
  (`python-is-python3`); without it six of its subtests fail.
- **Build:** `quarto render` writes the static site to `_site/`
  (takes ~90s to render ~189 pages).
- **Run (dev):** `quarto preview --port 4444 --host 0.0.0.0 --no-browser`
  serves the site with hot reload; edits to a `.qmd` rebuild that page live.
  `quarto preview` also appends a redundant `/.quarto/` line to `.gitignore`
  on first run --- revert that incidental change before committing.
  `_site/` and `.quarto/` are already gitignored.
- **Submodule:** `shared/sembr-skills` must be initialized
  (`git submodule update --init`) or `validate-skills.py` warns and the plugin
  source check only ever reports its empty-directory branch.
- **pre-commit:** installed to `~/.local/bin`, which is not on `PATH` by
  default; run it as `~/.local/bin/pre-commit run --all-files`.
  Its first run builds the gitleaks (Go) and markdownlint (Node) hook
  environments, which is slow but cached thereafter.
