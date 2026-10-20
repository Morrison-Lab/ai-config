# Read published HTML from the `gh-pages` branch

Every Morrison-Lab notes repo (`lds`, `mds`, `pds`, `sds`, `rme` and the rest) publishes its rendered site to the `gh-pages` branch.
Pull request previews sit on the same branch under `pr-preview/pr-<N>/`.
An agent can read those files directly, with git or the GitHub contents API.
It needs no browser, and it does not wait on the Pages CDN or its cache.

Use this route first to check rendered HTML, anchors, links and MathJax source, per [`check-the-renders`](check-the-renders.md) and [`browser-last-resort`](browser-last-resort.md).

## How

- **Contents API (MCP):** `mcp__github__get_file_contents` with `ref: refs/heads/gh-pages` and `path: pr-preview/pr-<N>/<page>.html` (main site: `<page>.html` at the branch root).
- **Git:** `git fetch --depth 1 origin gh-pages`, then `git show FETCH_HEAD:pr-preview/pr-<N>/<page>.html`.
- **Which build is deployed:** read the branch's commit log (`list_commits` with `sha: gh-pages`), because a preview comment can be older than the build.
- **Large pages:** grep the saved file for a string unique to your change;
  do not read the page whole.
- **Layout is a default, not a guarantee:** a repo that overrides `preview-branch` or `umbrella-dir` in its workflow needs those values read from its own workflow file.

## What to check

- An anchor id exists (`id="exm-..."`), and a cross-site link's target page exists on the target site's branch.
- The MathJax source is what you expect: `lds` defines macros in the page header, while `mds`, `pds` and `sds` inline the expanded macro in each equation.
  Report that you read the source, not the drawn glyph.
- A string unique to your commit appears, which separates "not fixed" from "not deployed yet".

## Limits

- A publish run that is still `in_progress` serves the old build, so check the run before concluding a fix failed.
- The branch holds bytes, not a drawn page.
  Check visual layout in a browser only when nothing else can, per [`browser-last-resort`](browser-last-resort.md).
- Pages hosts (`*.github.io`) are policy-blocked in some sandboxes;
  this route works there too.
  See [`github-remote-sessions`](../../memories/github-remote-sessions.md) for the measured details and [`verify-the-right-artifact`](verify-the-right-artifact.md) for stale-CDN reads.
