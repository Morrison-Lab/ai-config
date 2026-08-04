# check-rendered-refs — find crossrefs/citations that broke in the render

Quarto and pandoc resolve cross-references (`@fig-…`, `@tbl-…`, `@sec-…`, `@def-…`, `@thm-…`, `@eq-…`) and citations (`@key`, `[@key]`) at **render time**. When a key has no target, the build doesn’t fail — it emits a warning to the render log and writes a **literal failure marker into the output file**. Those markers survive into the published HTML, where readers see them.

This skill scans the **rendered artifacts** (not the `.qmd` source) for those markers and reports each one. It’s the output-side counterpart to `purge-hallucinations`, which audits *source* references.

The canonical example: a `@def-coef-interp-procedure` reference with no matching `::: {#def-coef-interp-procedure}` definition renders as the literal text **`?@def-coef-interp-procedure`** in the page body.

## When this fires

- “check rendered refs”, “crr”, “check for broken crossrefs / cross-references”
- “find unresolved references in the rendered site / book”
- “scan the HTML for `?@`”, “did any crossrefs or citations break in the render”
- Proactively right after a Quarto/bookdown render or a PR preview deploy — before announcing the page is ready.

## The failure markers

| What broke | How it renders in the output | Reliable grep |
|----|----|----|
| Cross-reference with no target (`@fig-x`, `@def-x`, `@sec-x`, …) | literal `?@x` in the body (often `**?@x**`) | `?@` — **rock-solid, Quarto-specific** |
| Citation key absent from the bibliography | the key in bold with a trailing `?`: `**key?**` → renders **key?**; render log warns `Citeproc: citation key not found` | bold-with-`?` is heuristic — confirm against the log |
| Citation never processed (citeproc off / no `bibliography:`) | raw `[@key]` or `@key` left in the body text | `[@` — heuristic, can match intentional literals |

`?@` is the one true positive — anything matching it is a broken reference. The citation patterns are heuristics: confirm them before reporting (an `@handle` or an email can match `@key`).

## Step 1 — Resolve the target

Pick what to scan, narrowest first:

1.  **A URL** the user pasted (a PR-preview or published page, e.g. a `…github.io/…/pr-preview/pr-NNN/…` link). Fetch and scan it (Step 2b).
2.  **A local output file or directory** the user named.
3.  **The repo’s rendered output dir** when the user says “the site/book” and names no path. Find it from the project config — common roots:
    - Quarto book/site: `_book/`, `_site/`, or the `output-dir` in `_quarto.yml`
    - bookdown: `_book/` or `docs/`
    - a single rendered file next to its `.qmd`

    ``` bash
    grep -E 'output-dir|output_dir' _quarto.yml _bookdown.yml 2>/dev/null
    ```

If the rendered tree might be **stale**, say so — the authoritative signal is a fresh render. Offer to re-render (`quarto render` / `quarto preview`) and read the warnings, which name every unresolved key directly. This skill checks the *artifacts*; a stale artifact can hide a break that a re-render would surface, and can show a break already fixed in source.

## Step 2a — Scan local output files

Grep the rendered files. `?@` is the primary signal; `-F` keeps `?` literal:

``` bash
# Primary: unresolved cross-references (and Quarto's unresolved-citation marker)
grep -rnoF --include='*.html' '?@' <output-dir>

# Secondary heuristic: missing citation key rendered bold with a trailing ?
# (the **key?** marker becomes <strong>key?</strong> in HTML, so the greps
# above miss it)
grep -rnoE --include='*.html' '<strong>[A-Za-z0-9_:.#-]+\?</strong>' <output-dir>

# Secondary heuristic: raw citation syntax left in the body
grep -rnoE --include='*.html' '\[@[A-Za-z0-9_:.#-]+' <output-dir>
```

For each `?@…` hit, pull the surrounding text so the report is actionable:

``` bash
grep -rnE --include='*.html' '.{0,40}\?@[A-Za-z0-9_:.#-]+.{0,40}' <output-dir>
```

Also covers PDF/docx when those are the rendered output — for PDF, extract text first (`pdftotext file.pdf - | grep -nF '?@'`); a broken crossref shows as `?@key` there too.

## Step 2b — Scan a URL

For a deployed/preview page, fetch and look for the markers:

    WebFetch(url, "List every literal '?@…' token in the body and quote ~40 chars
    of surrounding text for each. Also flag any citation rendered as a bold key
    with a trailing question mark (e.g. **key?**) or any raw '[@key]' text.")

To scan a whole previewed site, start from the index and repeat per chapter, or grep the locally rendered tree if you have it (Step 2a is cheaper and exact).

## Step 3 — Report

List every confirmed break with its location and context, grouped by file/page:

    chapters/count-regression.html
      ?@def-coef-interp-procedure
        "Applying ?@def-coef-interp-procedure to the log-rate linear predictor"
        → no ::: {#def-coef-interp-procedure} target; fix the key or add the definition.

Distinguish **confirmed** breaks (`?@…`) from **heuristic** citation hits that need a human eye. If the scan is clean, say so plainly — “no `?@` markers or stray citation syntax in ”. Don’t edit source here; fixing the underlying `.qmd` is a normal edit the user can ask for next (or hand to `purge-hallucinations` to trace the dangling key back to source).

## Relationship to other skills

- **`purge-hallucinations` / `ph`** — the source-side counterpart. It audits `.qmd`/code references for keys that don’t resolve; this skill catches the ones that already leaked into rendered output. Use `ph` to trace a `?@key` hit back to the offending source line.
- **`r-pkg-spellcheck`** — a sibling “check before you publish” gate; both run on rendered/user-facing text before a push or announce.
- **`reprexes`** — when a break needs a minimal reproducer to file upstream.

## Anti-patterns

- ❌ Grepping the `.qmd` source for `?@` — the marker only exists in *rendered* output; source has the un-broken `@key`. Scan the artifacts.
- ❌ Trusting a stale `_book/`/`_site/` — a fixed-in-source break can still show, and a new break can hide. Re-render when in doubt.
- ❌ Reporting every `@`-containing string as a broken citation — `@handle`, emails, and code can match. `?@` is certain; `[@…]`/`@key` is heuristic.
- ❌ Dropping the `-F` (or escaping) so the shell/grep mangles `?@`.

Back to top
