# Claude Code web fetching: what `WebFetch` returns, and where the real source lives

How a session gets at content on the web, and the two ways that misleads.
A rendered docs site can refuse the fetch outright while its source file serves
fine, and the fetch itself answers with a model-written *summary* rather than
the page --- so the running theme is that what comes back is one step removed
from the thing you asked about, in a way nothing in the output announces.
Split out of [`claude-code.md`](claude-code.md) (ai-config#694 pattern) at the
1200-line gate.


## WebFetch answers with a SUMMARY, so read the source when the answer is an exact literal
- `WebFetch` parses HTML into Markdown via `TurndownService` (capped at 100,000 characters)
  and runs `applyPromptToMarkdown` using `queryHaiku` (which resolves dynamically to the harness's default Haiku model) to synthesize an answer.
  For "what does this do" that is the point.
  For "what exactly does it write" it is a paraphrase of the thing you asked
  for, and a paraphrase can silently change a character.
- Measured 2026-08-24 on
  <https://usethis.r-lib.org/reference/git_vaccinate.html>, asked to quote the
  exact list of patterns verbatim.
  It returned `.Rdata`.
  The page's own roxygen, and `r-lib/usethis`'s `git_ignore_lines` in
  `R/git.R`, both say `.RData`.
- The single wrong character was consequential, which is the argument for the
  rule rather than for more care.
  gitignore matching is case-sensitive on Linux, so a check built from the
  returned literal would never have matched the file R actually writes --- and
  nothing about the output would have said so.
  It was caught only because the value was about to become a hard-coded
  default and got cross-checked against the source.
- This is [`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md)
  one layer further in than that fragment's own examples reach.
  The rendered page was the right artifact; the **summarizer** was the
  adjacent one, and asking it to "quote exactly" does not make it a
  transcription tool.
- **Preflight domain safety and egress checks (`api.anthropic.com/api/web/domain_info`)**:
  Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236).
  Before fetching, `WebFetch` checks domain safety against Anthropic's preflight endpoint
  (cached for 5 minutes, 128 domain LRU).
  Domains in `PREAPPROVED_HOSTS` (`docs.python.org`, `go.dev`, `react.dev`, `en.cppreference.com`, `agentskills.io`, etc.)
  or sessions with `skipWebFetchPreflight` bypass this step.
  Redirects are capped at 10 hops and restricted to same-origin (or www-prefix changes).
  Endpoints and allowed host lists are server-configured and subject to provider change.
- **Do:** raw-fetch the source (per the section below) when the answer is a
  pattern list, a default value, a flag name, a version string, or anything
  else you are about to copy character-for-character.
- **Do:** prefer a repository's own code over its rendered reference page for
  such a literal, since the page is generated and the code is the thing that
  runs.
- **Don't:** read a `WebFetch` result as a quotation, however literal it
  looks, and however explicitly the prompt asked for one.
- (Tracked as ai-config#2144.
  Found while building `Morrison-Lab/gha`'s `check-junk-files` capability,
  whose default pattern set is exactly this list.)

## WebFetch 403 on a rendered docs site -> raw.githubusercontent.com; WebSearch to find the exact source path
- A GitHub-Pages/Quarto-rendered docs site (e.g. `jarl.etiennebacher.com`,
  `ucd-serg.github.io/lab-manual/...`) can reject `WebFetch` outright (403 —
  likely anti-scraping), even though the plain-text/markdown **source** it was
  built from is a public file in a public repo and fetches fine via
  `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`.
  This isn't `d-morrison/gha`-specific (that repo's own `CLAUDE.md` documents it
  for the lab manual) — it generalizes to any Quarto/Docusaurus-style site,
  including third-party tool docs with no relation to our own repos.
- **When the exact source path isn't obvious** (unlike the lab-manual case
  where `foo.html` predictably maps to `foo.qmd`), guessing candidate paths
  one `curl -o /dev/null -w "%{http_code}"` at a time is slow and often wrong.
  `WebSearch` for `<repo-or-tool-name> <topic> site:github.com` (or just
  `<tool> <config-file> github`) surfaces the actual repo file path (e.g.
  `jarl/docs/reference/config-file.md`) from its indexed GitHub listing —
  faster than blind guessing, and the found path fetches cleanly via
  `raw.githubusercontent.com` immediately after. (Confirmed on jarl's docs
  site: `jarl.etiennebacher.com/reference/config-file` 403'd, but
  `WebSearch` surfaced `docs/reference/config-file.md` as the underlying
  file, which raw-fetched with the full field-by-field config reference.)
- **A 404 from `raw.githubusercontent.com` is often a filename-case mismatch, not a missing file.**
  The rendered URL's slug is lowercased by the site generator while the source file's own name may not be.
  Advanced R serves `function-operators.html` from `Function-operators.Rmd`, so the obvious raw URL 404s and the capitalized one returns the chapter.
  Retry with the repo's own capitalization before concluding the source lives at some other path.
  (ai-config#760, 2026-07-28: `adv-r.hadley.nz` 403'd through the proxy, and the first raw attempt 404'd purely on the leading capital.)
- **Reddit is the inverse of the pattern above: the rendered HTML serves, and
  the machine-readable form 403s.**
  Every other entry in this section reaches for a site's *source* when the
  rendered page refuses, so the instinct on a Reddit URL is to append `.json`
  or switch to `api.reddit.com` --- the two documented ways to get structured
  post and comment data.
  Both return 403 to an unauthenticated datacenter client, and adding
  `api.reddit.com` to an egress allowlist does not help, since the refusal is
  Reddit's rather than the proxy's.
  `old.reddit.com/r/<sub>/comments/<id>/` HTML fetches fine and carries the
  post body and its comment tree, so read that and stop looking for a
  structured endpoint.
  Screenshots stay unreadable either way, so a post whose substance is in an
  image is only partly recoverable --- say so rather than reporting the post as
  read.
  (2026-08-16, reading three r/ClaudeCode and r/ClaudeAI workflow posts for
  ai-config#1563: the `.json` paths and `api.reddit.com` each 403'd, old.reddit
  HTML worked, and post 1's heartbeat config and post 3's dashboard images were
  never legible.
  Note `skills/opposition-research/SKILL.md` names "the Reddit `.json`
  endpoints" as a data source, which holds for a session that can authenticate
  and not for this one.)
  In a **local** session even the HTML route above is closed --- WebFetch
  refuses all three reddit.com hosts before Reddit answers, probably at its
  domain safety preflight rather than under any permission rule.
  [`reddit-access.md`](reddit-access.md) carries the five failed routes and
  the working Claude-in-Chrome route (measured 2026-08-23/24).
- **`docs.github.com` itself can be blocked outright by a remote session's
  network policy** (proxy 403 on every page, and `api.github.com` too —
  both at the curl/WebFetch level; the GitHub MCP tools route through
  their own server and keep working), not
  just anti-scraping — but `raw.githubusercontent.com` stays reachable, and
  GitHub's docs are built from the public `github/docs` repo.
  Verify a docs claim or URL against that source instead: page content lives under
  `content/<area>/.../<slug>.md`, but live-URL paths do NOT map 1:1 to
  source paths (the docs get reorganized; e.g.
  `/billing/managing-billing-for-your-products/...` now lives at
  `content/billing/concepts/product-billing/github-actions.md`).
  If a page was moved, its frontmatter carries a `redirect_from:` list — an old URL
  appearing there means it still works for readers via redirect — and
  shared text is factored into `data/reusables/<area>/<name>.md` includes,
  so grep for a `{% data reusables.<area>.<name> %}` tag and fetch that
  file when a section's body looks like one include line.
  Version-gated (`{% ifversion <flag> %}`) passages resolve via `data/features/<flag>.yml`:
  its `versions:` block (e.g. `fpt: '*'`) says which plans the gated text
  applies to: `fpt` = Free/Pro/Team on github.com, `ghec` = GitHub Enterprise
  Cloud (also github.com-hosted), `ghes` = GitHub Enterprise Server
  (self-hosted). (Used on
  ai-config#601 to verify the GitHub Actions billing and `jobs.<job_id>.if`
  citations offline, and on gha#272 to confirm the approval-required
  `pull_request`-runs exception applies to github.com.)
