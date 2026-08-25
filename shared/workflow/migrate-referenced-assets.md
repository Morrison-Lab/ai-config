When moving or removing content that references local files by relative path
--- images, data files, other assets a document embeds rather than links to
externally --- move or remove those referenced files too, not just the
document text. Grep the moved/removed files for asset-path patterns (image
extensions, `assets/`, `images/`, or whatever the project's own convention
is) and confirm each referenced file exists at the destination before
considering a migration or excision complete.

This is easy to miss because the failure mode is often silent or delayed:

- HTML rendering typically degrades gracefully --- a missing image becomes a
  broken-image icon or a rendered "image not found" placeholder, not a
  build failure. A migration can look completely clean in the common render
  target and still be missing files.
- A LaTeX-backed PDF render does **not** degrade gracefully: it hard-fails
  the whole document when it can't find a referenced image, often well after
  the rest of the render succeeded. If PDF (or another format sharing the
  same asset resolution) isn't part of the default CI render, this can stay
  undiscovered until someone builds that format specifically.
- Spell-check, link-check, and lint passes don't catch a missing local
  asset --- a relative image path isn't a spelling word or an external link,
  so none of the usual content-quality CI catches this gap.

**Copying the assets to a plausible destination is not enough --- the
destination must match the renderer's actual resolution base.** For Quarto
`{{< include >}}` fragments, a relative image path written inside a fragment
resolves against the **master/including file's** directory in the outputs
that matter --- the rendered master HTML page and the LaTeX PDF compile ---
not the fragment's own directory, and not the project root. Verify
empirically instead of reasoning from the source layout: check where the
renderer copies the asset into the output tree (`_site/...`), and for a PDF
failure read the `.log` file's own path (e.g. `chapters/coding-agents.log`
means lualatex ran from `chapters/`, so `assets/images/...` must exist
under `chapters/`).

**Also check which CI job exercises the failing format before trusting a
green PR.** A PR preview job often renders HTML only, while the deploy job
on the default branch renders all formats --- so a PR fixing a PDF-only
failure can pass every one of its checks without ever testing the fix. Say
so in the PR body, and verify the deploy job actually goes green after
merge before calling the fix done.

When *removing* content instead of moving it, check the inverse case too:
does an asset referenced only by the removed content become orphaned? Decide
whether to delete it along with the text, or leave a note for a follow-up
cleanup pass --- don't leave it silently unreferenced with no record of why.

**Migrating a referenced include from a local file to a git submodule breaks
*staged*-render tools even though *in-place* renderers keep working.** A
renderer that builds documents where they sit (pkgdown) resolves a relative
`{{< include ../macros/macros.qmd >}}` against the repo tree, so it doesn't
care whether `macros/` is a plain dir or a submodule. A renderer that copies
selected source trees into a build staging dir first (altdoc's `_quarto/`,
which stages `vignettes/`/`man/`/`altdoc/` but not a repo-root `macros/`
submodule) resolves the same `../macros/...` against the *staging* dir, where
the submodule was never copied --- so the include hard-fails
(`could not find file .../_quarto/macros/macros.qmd`). Two consequences when
a repo migrates a shared asset (LaTeX macros, a common header) from a local
`_*.qmd` include to a submodule: (1) the staged renderer's checkout step needs
`submodules: true` *and* the renderer itself must stage the submodule's
content into the build dir (fixed upstream in d-morrison/altdoc's
`quarto_website` flow, PR #27 --- `submodules: true` alone is necessary but not
sufficient); (2) the docs CI workflow's `paths:` trigger filter should include
the submodule path (e.g. `macros`, `.gitmodules`) so a submodule-pointer bump
actually rebuilds the docs. (UCD-SERG/serocalculator#503, 2026-07: `main`
migrated the macros to the `d-morrison/macros` submodule while the pkgdown-to-altdoc
PR was open; pkgdown had rendered fine, altdoc's staged build could not find
`../macros/macros.qmd`.)

(d-morrison/wai#6, 2026-07-14: a chapter migration from one Quarto repo to
another moved 25 `.qmd` fragments referencing five meme images, but never
copied the `assets/images/` directory itself. HTML rendering silently
degraded to missing-image placeholders and every other CI check passed, so
the gap wasn't caught until the PDF render --- part of the same "render all
formats" publish job, just slower to reach --- hard-failed with a LaTeX
"file not found" error. Two follow-up fixes put the images at plausible but
wrong locations --- wai#13 at the project root, wai#15 next to the fragments
--- and each merged green because the PR checks render HTML only; the
correct, master-file-relative fix landed in wai#16.)
