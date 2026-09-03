# Quarto site authoring and rendering

Quarto **site** gotchas --- project configuration, build, layout, crossrefs,
and the render toolchain.

Split out of [`r-quarto.md`](r-quarto.md) at the 1200-line memory-file gate,
following the same pattern as [`r-cloud-sessions.md`](r-cloud-sessions.md).
R-toolchain material (renv, the linters, R-package CI gates, testthat) stays
there; anything about how a Quarto site is configured or rendered belongs
here.

## Quarto HTML sites (build & layout gotchas)
Hit while adding a mobile within-chapter TOC to `d-morrison/rme` (#929); apply to
any Quarto website (rme, psw, qwt, …).
- **Single-file `quarto render <file>.qmd` serves cached compiled theme CSS.**
  Edits to `custom.scss` / theme SCSS may NOT appear in the output — Quarto reuses
  the cached sass bundle.
The tell: the
  `_site/site_libs/bootstrap/bootstrap-*.min.css` content hash stays identical
  across renders.
Force a recompile by clearing the sass cache and the stale libs
  first: `rm -rf ~/.cache/quarto/sass _site/site_libs`, then re-render. (A
  "verified" CSS rule was actually stale until I cleared this.)
- **The within-chapter "On this page" TOC is hidden on mobile with no built-in
  replacement.**
Quarto's bootstrap hides `#quarto-margin-sidebar` below the `md`
  breakpoint (`@media (max-width: 767.98px)` in `_bootstrap-rules.scss`).
There is
  no `toc:` option to re-enable it; the `quarto-toc-toggle` "convert TOC to a
  floating menu" in `quarto.js` is an overlap-avoidance feature for wide screens,
  not a mobile feature (on a phone the margin sidebar is already `display:none`,
  so it never fires).
- **A cloned within-chapter TOC must NOT carry `role="doc-toc"`.**
Quarto's mobile
  CSS includes a bare `nav[role=doc-toc] { display: none }` (inside the `md` media
  query), so any clone with that role stays hidden even when you mean to show it.
  Use a plain `<nav aria-label="…">` instead.
- **Navbar headroom = reveal-on-scroll-up.**
Quarto attaches Headroom to
  `#quarto-header`; on scroll it toggles `sidebar-unpinned` on the header AND on
  every `.sidebar` / `.headroom-target` element (see `quarto-nav.js`).
To make a
  custom element hide-on-scroll-down / reappear-on-scroll-up in step with the
  navbar, place it inside `#quarto-header` (it inherits the header's transform) or
  give it `.headroom-target`. (Used to put a "Contents" TOC button in the navbar.)
- **`quarto render` auto-modifies `.gitignore`.**
On first render, Quarto appends
  `/.quarto/` and `**/*.quarto_ipynb` to `.gitignore`.
If `.quarto/` is already
  present, `/.quarto/` is redundant (the unanchored form already covers the root).
  Remove `/.quarto/` only when `.quarto/` is already present; keep `**/*.quarto_ipynb`.
- **Manuscript projects do NOT support `repo-url` / `repo-actions` natively.**
  `book` and `website` inherit `base-website` schema (which includes these keys);
  `manuscript-schema` is `closed: true` with no `super`, so the keys are silently
  ignored even when placed under `website:` or `format: html:` in `_quarto.yml`.
  Workaround: a Lua filter that reads those keys from metadata and injects the links
  via inline JS — see `Morrison-Lab/qmt/_repo-links.lua` for a full implementation.
  Upstream issue: quarto-dev/quarto-cli#14627.
- **In Quarto Lua filters, use `quarto.doc.input_file` (not `PANDOC_STATE.input_files[1]`)
  to get the real source path.**
Quarto preprocesses `.qmd` files into temp files before
  passing them to Pandoc; `PANDOC_STATE.input_files[1]` gives the temp path, not the
  original `.qmd`.
`quarto.doc.input_file` reads the `quarto-source` param and returns
  the real path.
To compute the repo-relative path: strip `os.getenv("QUARTO_PROJECT_DIR")`
  from the front (`abs_input:sub(#project_root + 2)`). (Learned while writing `_repo-links.lua`
  for Morrison-Lab/qmt.)
- **A plain project-wide `quarto render` (no `--to`) DOES render every format a
  document's own front matter lists** — even formats the project's `_quarto.yml`
  doesn't configure.
Verified from a clean state (`rm -rf _site .quarto` first,
  no priming single-file renders) on `d-morrison/macros`: `_quarto.yml` there
  configures only `format: html:`, yet a bare `quarto render` still produced
  `.pdf`, `.docx`, and reveal.js `.html` output for every doc whose own front
  matter lists those formats — the project config sets the *default* for docs
  with no local `format:` override, it doesn't cap docs that declare their own.
  So a CI step that just runs `quarto render` **likely already exercises** the
  PDF/other-format renders a `CONTRIBUTING.md` separately documents as
  `quarto render <doc>.qmd --to pdf` — don't assume a bare project render is
  HTML-only without checking. (Corrected in ai-config#408 after re-verifying
  from a clean state; the empirical result contradicted both an earlier claim
  logged here and a reviewer's proposed replacement.)
The durable lesson
  survives: don't write "CI covers this" in a PR description from assumption —
  verify what CI *actually* does before asserting either that it does or
  doesn't cover a given check.
- **Custom Quarto shortcode Lua files belong under YAML `shortcodes:`, not
  `filters:`.**
A Lua file that returns a shortcode table (for example
  `return { ['slidebreak'] = slidebreak }`) does **not** register that
  shortcode when listed under `filters:`; Quarto treats it as a Pandoc filter,
  leaves `{{< slidebreak >}}` literal in rendered HTML, and warns
  `Shortcode 'slidebreak' not found`.
Put the path under front-matter or
  project metadata `shortcodes:` instead (e.g.
  `shortcodes: [../_extensions/d-morrison/slidebreak/slidebreak.lua]`), even
  when the file lives inside `_extensions/`. (Observed directly in
  UCD-SERG/serocalculator, 2026-07-22: switching the same Lua path from
  `filters:` to `shortcodes:` made the shortcode render and removed the
  warning in a standalone `quarto render` smoke test.)
- **Large site renders crash Deno's default 8 GB V8 heap — deterministically,
  not flakily.**
Quarto's launcher script hardcodes
  `--max-old-space-size=8192,--max-heap-size=8192` and *prepends* those
  defaults before any user-supplied `$QUARTO_DENO_V8_OPTIONS` inside one
  `--v8-flags=` argument; V8 lets the last occurrence of a flag win, so
  setting `QUARTO_DENO_V8_OPTIONS=--max-old-space-size=12288,--max-heap-size=12288`
  in the environment is the supported override.
The crash signature: all
  chapters render fine individually, then `Fatal JavaScript out of memory:
  Ineffective mark-compacts near heap limit` late in the ~35-40-file site
  render (cumulative heap, worst in finalization/search-indexing), exit code
  133 — SIGTRAP, not the SIGABRT (134) a classic `abort()` would give:
  V8's fatal-error handler dies on a trap instruction, and the launcher's
  own log line confirms it (`Trace/breakpoint trap (core dumped)` followed
  by `Process completed with exit code 133`, observed identically in both
  failing runs).
Reproducible on every re-run.
Fixed fleet-wide in gha#263 (the
  `preview`/`quarto-publish` composites export the 12 GB override; standard
  runners have 16 GB).
To validate a heap-flag change without a 20-minute
  render: run Quarto's own bundled deno
  (`/opt/quarto/bin/tools/x86_64/deno eval` with the launcher-composed flag
  string) against a >8 GB JS-heap allocation loop — crashes under the
  default string, survives with the override appended, minutes instead of
  hours. (rme #1040/#1042, 2026-07-17: four identical CI OOMs across two
  PRs; not a Quarto version change — v1.9.38 predated both green and red
  runs.)
- **`aliases:` is a per-format option, so a document-level one lets the LAST
  format win --- on a multi-format doc the redirect can point at the slides.**
  A `.qmd` rendering to both `html` and `revealjs` with a document-level
  `aliases:` generates a redirect stub aimed at the *revealjs* output, not the
  article.
  That is silently wrong rather than broken: the stub exists, the link
  resolves, and the reader lands on slides.
  Scope it under `format: html:` instead.
  Measured on quarto 1.9.36, the same doc rendered both ways, by reading the
  `var redirects` line the stub emits (it is a JS `window.location.replace`,
  not a `<meta http-equiv=refresh>` --- so grep for `var redirects`, not
  `url=`):

  | `aliases:` location | `var redirects` in the stub |
  |---|---|
  | document level | `{"":"doc-slides.html"}` |
  | under `format: html:` | `{"":"doc.html"}` |

  Also: the alias path resolves relative to the **document's** directory, not
  the site root --- `sub/doc.qmd` with `aliases: [old-name.html]` puts the stub
  at `_site/sub/old-name.html`.
- **Verify a redirect on a site build, not on a single-file render.**
  An alias stub is an artifact of the *site* build, so a local single-format
  `quarto render <file>.qmd` cannot surface a per-format bug in it at all ---
  there is only one format for the last one to win over.
  Rendering the multi-format collision locally also needs an `output-file:`
  rename on the second format before it will build at all: without one, both
  formats claim `doc.html` and the project render dies with a
  `rename ... No such file or directory` Deno stack trace rather than a
  readable message.
  Read the built stub out of the PR preview per `r-cloud-sessions.md`'s
  `pr-preview/pr-<N>/` recipe.
  (`UCD-SERG/serocalculator` #633/#635, 2026-08: shipped wrong and caught only
  on the deployed preview.)
- **`altdoc::render_docs()` builds the site locally, so a project-config
  artifact can be checked without waiting for CI.**
  `quarto render <file>.qmd` does not read `altdoc/quarto_website.yml`, so
  anything declared there --- project-level `filters:`, shortcodes, extensions
  staged under `altdoc/_extensions/`, the sidebar and navbar --- is simply
  absent from a single-file render.
  That makes a single-file render the wrong instrument for those, and it fails
  in the direction that reads as a defect in the document: a shortcode whose
  extension is registered project-wide comes out unresolved locally and
  resolves fine on the deployed site.
  Reach for `altdoc::render_docs()` before concluding the deployed preview is
  the only way to see a site-build artifact.
  It is slower than a single-file render, so keep using
  `quarto render <file>.qmd` for per-document work (chunk output, per-format
  `echo`, figures) where the project config is not involved.

## Quarto crossref labels are PAGE-scoped, so an include fragment can only reference labels on its own including page

In a Quarto **website** project a `@sec-` (or `@fig-`, `@tbl-`) label resolves
only within the page that renders it.
A `{{< include >}}` fragment has no page of its own --- it is spliced into
whichever chapter transcludes it --- so it can reference a label defined in
that chapter, or in another fragment the *same* chapter includes, and nothing
else.
Reference a label defined in a different chapter and the render emits a
literal broken `?@sec-...` into the page rather than failing the build.

The consequence is a design constraint rather than a formatting nit: **a
shared fragment's crossrefs decide which chapter can transclude it.**
A fragment whose topic reads as belonging to chapter A, but which references
two labels defined in chapter B, belongs in B --- or has to stop referencing
them.
That question is settled before the fragment is placed, and re-placing it
later means rewriting its cross-references.

Two things make this easy to get wrong.
The failure is a **rendering** defect, not a build failure, so CI stays green
and the broken ref reaches the deployed page --- which is the same
green-CI-with-a-broken-artifact shape the `check-rendered-refs` skill exists
to sweep for, and the reason that skill greps rendered HTML for `?@` rather
than trusting the build.
And the label being referenced is perfectly real and perfectly defined, just
on another page, so grepping the source for its definition finds it and
suggests the reference is fine.

The same scoping is why such fragments are excluded from standalone rendering.
`Morrison-Lab/wai`'s `_quarto-website.yml:15-18` states it directly, as the
reason for its `- "!chapters/ai-tools/"` exclusion:

> `chapters/ai-tools/*.qmd` are `{{< include >}}` fragments transcluded by
> `chapters/*.qmd`, not standalone pages.
> Their `@sec-ai-*` crossrefs are only defined on the including page, so
> rendering them standalone also produces broken crossref warnings.

Note that comment establishes the **standalone-render** direction; the
cross-page direction above is the same page-scoping property met from the
other side, so a project carrying that exclusion has already conceded the
constraint this section describes.

- **Do:** before placing a shared fragment, list the labels it references and
  confirm every one is defined on the chapter that will include it.
- **Do:** check a rendered page for literal `?@` text after adding a fragment,
  since the build will not fail on one.
- **Don't:** infer a crossref resolves because `grep` finds its label
  somewhere in the project --- the question is which *page* defines it.
- **Don't:** choose the including chapter by topic alone when the fragment
  carries cross-references.

(`Morrison-Lab/wai#54`, 2026-08-09: a new PR-activity fragment read as
belonging to `pr-workflow-with-agents.qmd` by topic, but referenced
`@sec-ai-claude-cloud-env` and `@sec-ai-mcp-server-setup`, both defined in
`coding-agents.qmd`.
Including it from the PR-workflow chapter would have emitted two broken
`?@sec-` refs, so it was transcluded from `coding-agents.qmd` instead.)

## A project's `_quarto.yml` `format:` block is not the set of formats the project renders

Per-document front matter **overrides** the project-level `format:` key rather than adding to it, so a project declaring `format: html` alone can still render PDF, docx, and revealjs --- and will, on any document whose own front matter says so.

The consequence is a CI toolchain you cannot infer from the config file.
Dropping TinyTeX because `_quarto.yml` names only `html` is a change that passes every local check, passes review, and breaks the first publish after merge, on a document nobody opened.

This is [`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md)'s "a neighbour for the target" shape, and it is a comfortable one to fall into: `_quarto.yml` is the project's configuration, it is the file you would name if asked where a project's formats are declared, and reading it feels like checking rather than assuming.
The format set is a property of the **document population**, though, so only a sweep over the documents answers it.

```bash
shopt -s globstar   # bash: ** does not recurse without this, and it is off by default
for f in **/*.qmd; do
  # Print only the YAML front matter, terminated at its closing ---, so the
  # range cannot run on into body text that happens to start at column 0.
  fm=$(awk 'NR==1 && $0 == "---" {inside=1; next} inside && $0 == "---" {exit} inside' "$f")
  case "$fm" in *format:*) echo "== $f"; echo "$fm";; esac
done
```

Note what the toolchain question actually turns on: a `pdf:` anywhere in that sweep requires TinyTeX, and a `revealjs:` may require Chrome, regardless of what the project file says.

- **Do:** derive the rendered format set from every document's front matter before removing a toolchain from CI.
- **Do:** read a demo or example document as a likely format outlier --- it exists to exercise a format, which is exactly why its front matter differs from the project's.
- **Don't:** read the project-level `format:` block as the format set --- a per-document block replaces it.
- **Don't:** expect `freeze: auto` to remove the toolchain requirement --- freeze skips chunk *execution*, not the pandoc/LaTeX render, so a frozen PDF document still needs TinyTeX on the runner.

(Measured 2026-08-24 on `d-morrison/macros`, whose `_quarto.yml` declares `format: html` only while `demo-shortcode.qmd` and `demo-include-in-header.qmd` each declare their own `pdf:` and `revealjs:` blocks --- demonstrating the macros reaching the LaTeX preamble being the entire point of those two pages.
Caught in self-review on [macros#83](https://github.com/d-morrison/macros/pull/83) before the TinyTeX removal merged.)

## The project `format:` block reaches every document that declares no `format:` of its own

The section above is about which **formats** a project renders, and says the project block understates that set.
This is the other axis: which **documents** a given entry in that block reaches.
The answer is every document that declares no `format:` of its own, since the block is those documents' *default* --- so adding a format there to give **one** document a slide deck silently gives it to every such page in the site.
A document carrying its own `format:` block escapes it, which is the same override rule read from the other side, and is why the one page you meant to change may be the only page unaffected.

Both axes fall out of the single rule that section states --- per-document front matter *overrides* the project block rather than adding to it --- so the block understates the format set and overstates the document set at the same time.
What is surprising is the scope rather than the behaviour: the block does exactly what it is documented to do, and the edit was wider than the intent behind it.

The failure is the filename collision already recorded twice in this corpus, reached from the project side with no document edited at all.
Both formats claim `<stem>.html`, and the render dies rather than rendering something wrong.
The "Verify a redirect on a site build" bullet above carries the remedy: an explicit `output-file:` on the second format.
[`debugging.md`](debugging.md)'s "Reproduce heavy-tool project bugs minimally" carries a two-file, R-free reproducer for the same `safeMoveSync`/`renderProject` collision --- reach for that before rendering a real project twice.

Three things the new observation adds to those two records.

**The blast radius is the whole site, and the error names one page.**
Measured on Quarto 1.9.36 / macOS, a `revealjs:` block added under the top-level `format:` key of a website project:

```
ERROR: NotFound ... rename 'docs/design-decisions.html' -> '_site/docs/design-decisions.html'
```

The output directory was left missing `index.html`, `styles.css`, `search.json`, and `site_libs/`.
The page named is not the page the format was added for, and that mismatch is itself the tell that the scope is project-wide rather than per-document.
Don't read the named page as the first one rendered either, or as the last.
The name tracks a *colliding* document --- one inheriting both formats --- rather than render position.
Measured on Quarto 1.9.36 / macOS in a three-page project where `index.qmd` alone declares no `format:` of its own: the render reports `[1/3] docs/design-decisions.md`, `[2/3] index.qmd`, `[3/3] aaa.qmd`, and the error names `index.html`, which is neither first nor last.
Note what that discriminator does and does not settle.
With exactly one colliding document it rules out the name being the first or the last document rendered, which is the misreading worth ruling out.
It says nothing about which colliding document gets named when several collide, since only one could be named here;
render order may well decide that, and this case cannot tell you.
Which stage picks the reported path was not established, and is not needed: the name identifies a document that inherited the project's formats, which tells you the entry is reaching further than you intended.
Read it as the symptom rather than the site of the fix.
The remedy is in the project block and in the front matter of the document you meant to serve --- narrow the one, and give the other an explicit `output-file:` --- not in the page the error happens to name.

**A green CI check here was not weak evidence that the block was fine --- it was no evidence either way.**
Two runs on [ucdavis/hac.sap#9](https://github.com/ucdavis/hac.sap/pull/9) carried that top-level block: run `33432191485` (job `99619966191`) at `8c40c4db`, and run `33567826907` (job `100054940478`) at `e6d9e8a`.
Both `build` checks passed, and both render steps dump the same inputs: `FORMATS` empty, `RENDER_PROFILE` empty, `TINYTEX: false`, and `HAS_LABEL_PDF`, `HAS_LABEL_DOCX`, `HAS_LABEL_REVEALJS` all false.
Read `TINYTEX` as part of that input rather than the labels alone: the action's pdf branch fires on `TINYTEX = true` **or** `HAS_LABEL_PDF = true`, so a false label does not exclude pdf by itself.
On those inputs `Morrison-Lab/gha`'s `preview@v2` takes its no-formats branch, builds `FORMAT_LIST=("html")`, and issues one command: `quarto render . --to html --output-dir _site`.
The runner never echoes the resolved command line, so that reconstruction of the `quarto render` invocation is a derivation over the script text and the `env:` block the runner does print, rather than an observation of the command itself.
Within the project render that command produces one output per document, so no two formats can contend for `<stem>.html`, and the collision was impossible in that phase by construction.
Scope that to the project render deliberately: the same run renders `sap-template.qmd` twice more afterwards, through the `post-render` hook described below.
Those extra renders cannot collide either, for a different reason --- each carries an explicit `output-file:`, so they claim `sap-template-revealjs.html` and `sap-template.docx` rather than a name any other output wants.

**The later run's log reads like a multi-format render, and that is the trap.**
Run `33567826907` carries `Output created: _site/sap-template-revealjs.html` and `_site/sap-template.docx` next to `_site/index.html`, which looks like the project block's revealjs rendering cleanly.
Those two come from the project's `post-render: Rscript scripts/post-render.R`, which runs `quarto render sap-template.qmd --to revealjs` and the same to `docx`: two single-document renders of the one document whose front matter declares its own `format:` block, with an explicit `output-file:`.
The log's ordering settles that without needing any prior belief about the project render, since both lines fall after `Running script 'Rscript'` and before the project render's own `Output created: _site/index.html`.
By this section's own rule `sap-template.qmd` is precisely the document the project block does *not* reach, so those outputs are evidence about per-document front matter and say nothing about the project block.
The earlier run carries no such lines, because `scripts/post-render.R` did not exist at `8c40c4db`.

The reflex explanation is the version, and it is wrong: CI ran Quarto 1.10.18 on Linux against a local 1.9.36 on macOS, but installing 1.10.18 on macOS collides identically, so the version explains nothing.
The difference that mattered was the render command, sitting in the same log as the environment dump.
Reach for the command a check actually ran before reaching for its platform or its version.
[`metacognitive-monitoring.md`](../shared/workflow/metacognitive-monitoring.md) states the general form: a claim about cause owes an alternative you can name and reject.
Reading the deployed preview would not have rescued this either, which is worth knowing before reaching for the `pr-preview/pr-<N>/` recipe the bullet above cites.
Run `33567826907` wrote every page the project declares, so the preview had nothing partial to show;
a preview can only expose what the render command it came from actually built.

- **Do:** put a single document's extra format in that document's own front matter, with an explicit `output-file:`.
- **Do:** render the project locally before trusting CI on a `_quarto.yml` `format:` change.
- **Do:** read a green render check by asking which formats it rendered, and treat a single-format run as silent on any collision between formats.
- **Do:** check a project's `post-render` step before reading an output in the log as the project render's work.
- **Do:** compare the error's source path against the document the format was added for;
  a different path means the entry is reaching documents you did not intend.
- **Don't:** read a green render check as evidence the config is right without asking which formats it rendered.
- **Don't:** read an `Output created:` line as the project render's work before checking the project's `post-render` step.
- **Don't:** add a format to the top-level `format:` key for one document's benefit.
- **Don't:** read the page named in a `rename ... NotFound` as the one whose front matter you edited.
  It names a document that inherited the format, not the one you meant to give it to.

(Measured 2026-09-01 while reviewing a pull request on `ucdavis/hac.sap`, a Quarto website project: a `revealjs:` block added under the top-level `format:` key made `index.qmd` and `docs/design-decisions.md` each render to revealjs as well, colliding with their own HTML outputs.
Tracked as [ai-config#2984](https://github.com/Morrison-Lab/ai-config/issues/2984).)

## quarto-actions/setup with tinytex — two shared-runner failure signatures (win, 2026-07)

- **`ERROR: Unable to determine latest release for rstudio/tinytex-releases / 403 - Forbidden`**
  during "Set up Quarto": `quarto install tinytex`'s latest-release lookup is an
  unauthenticated GitHub API call, and shared runners intermittently rate-limit it.
  Fix: `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (or `${{ github.token }}`) on the
  setup step.
gha's `preview` composite already does this;
`quarto-publish` gap filed
  as gha#270.
(Broke ucdavis/win's preview/publish repeatedly;
fixed in win PR #69.)
- **`renv::restore()` fails compiling `curl` ("libcurl was not found")** on
  current ubuntu runner images: the R build libs are no longer preinstalled, so any
  renv repo needs an explicit apt step.
Working set for a typical
  curl/openssl/xml2/gert/V8/igraph/ragg/textshaping lockfile:
  `libcurl4-openssl-dev libssl-dev libxml2-dev libgit2-dev libnode-dev libglpk-dev
  libfontconfig1-dev libfreetype6-dev libharfbuzz-dev libfribidi-dev libpng-dev
  libtiff5-dev libjpeg-dev` (gha's `preview` reusable workflow's default
  `apt-packages` list is the fuller reference).
- Diagnostic order matters: the TinyTeX 403 masks the renv gap — fixing the first
  failure surfaces the second on the next run, so read each new failed run's log
  fresh instead of assuming the prior diagnosis still applies.
