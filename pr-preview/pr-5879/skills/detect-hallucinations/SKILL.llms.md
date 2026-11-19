# detect-hallucinations — read-only check that references resolve

The *detection* half of `purge-hallucinations`, factored out so it runs forked ([ai-config#914](https://github.com/Morrison-Lab/ai-config/issues/914)). It checks each concrete, checkable reference in a target against ground truth and returns a report. It changes nothing: `purge-hallucinations` proposes and applies the fixes in the main session afterward, and you can run this skill on its own to ask “what here is made up?”.

The prime directive: **only call fake what you can prove is fake.** A reference you *can’t* verify (network down, ambiguous symbol, private resource) is **unverifiable**, not a hallucination.

## Step 1 — Resolve the target

Pick the narrowest target the user named, in this precedence order:

1.  **Explicit target** — a file, a directory, a PR diff, or pasted AI output the user pointed at. For a PR: `gh pr diff <n>` (local) or `mcp__github__pull_request_read` `method: get_diff` (remote/web — see `memories/github-mcp-tools.md`); audit only the references the diff *introduces*.
2.  **The memory/instruction corpus** — the ai-config repo’s `memories/`, `skills/`, and `CLAUDE.md`. Find the repo root with `${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/detect-hallucinations rev-parse --show-toplevel 2>/dev/null || pwd)}`.
3.  **The current repo’s code & docs** — when the user says “this repo” or names no target while inside a project.

A forked run cannot ask the user, so when the target is ambiguous, take the narrowest reasonable reading and state at the top of the report which reading you chose.

## Step 2 — Extract concrete, checkable references

Scan the target for references that have a definite right/wrong answer. Ignore prose, opinions, and design rationale — those aren’t hallucinations, just claims. Pull out, with file + line for each:

| Reference type | Examples |
|----|----|
| File / path | `src/foo.R`, `here("data/x.csv")`, a relative link in a `.qmd` |
| Function / object / symbol | `pkg::fn()`, an R object, a shell command, a Make target |
| Action ref + version | `uses: org/action@v3`, `@<sha>`, a tag/release |
| Skill name | `skills/<name>/`, `~/.claude/skills/<name>/`, a `/slash-command` |
| Memory cross-link | `[[some-memory-name]]` in a memory body |
| URL / link | `https://…`, a docs anchor, a badge target |
| Citation / package | a CRAN/Bioconductor package, a DOI, a `DESCRIPTION` dep |
| Flag / option / config key | a CLI flag, an env var, a YAML key the schema defines |
| API / SDK method or model id | an SDK method, a model name, an endpoint |

## Step 3 — Verify each against ground truth

Use the cheapest check that *proves existence or absence*. Match the tool to the reference type:

- **File / path** — `test -e <path>`, `git ls-files -- <path>`, `ls`.
- **Function / object** — grep for the *definition*, not just a mention (`grep -rn "fn <- function" R/`); for an exported R fn check `NAMESPACE` / `Rscript -e 'library(pkg); exists("fn")'`. Shell command — `command -v`.
- **Action ref + version** — confirm the tag/SHA exists (`gh api repos/<org>/<repo>/git/refs/tags/<tag>` or `.../commits/<sha>`).
- **Skill name** — `ls skills/<name>/` in the local ai-config directory. If not found locally, check the session’s available-skills list (appears in system reminders) before classifying as ❌; a globally-available system skill with no local directory is ❓ Unverifiable, not ❌ Fabricated.
- **Memory cross-link** — `[[target]]` links resolve to **skill directories** (`ls skills/<target>/`); if no matching skill, search memory headings (`grep -rn "^# .*<target>" memories/`).
- **URL / link** — `curl -sSI -o /dev/null -w '%{http_code}' <url>` (local) or `WebFetch` (remote). **A 404/410 is fabricated; a timeout, 403, 429, or DNS failure is *unverifiable*** — distinguish them.
- **Citation / package** — CRAN: `https://cran.r-project.org/package=<pkg>`; installed: `Rscript -e 'find.package("<pkg>")'`; dep: check `DESCRIPTION`; DOI / `.bib`: `python3 scripts/check_doi_bib.py <path-to-.bib>` (or `--root <dir> --cited-only`).
- **Flag / option / config key** — grep the tool’s `--help`, its schema, or its source; for a YAML key, the consuming code/schema.
- **API / SDK method or model id** — check the SDK source/docs. For Claude/Anthropic specifics (model ids, params), **defer to the `claude-api` skill** rather than guessing.

Sort every reference into exactly one bucket:

| Bucket | Meaning | Disposition |
|----|----|----|
| ✅ **Resolves** | proven to exist | leave it |
| ❌ **Fabricated** | proven absent (404, no definition, no such tag/file) | `purge-hallucinations` proposes a fix |
| ❓ **Unverifiable** | can’t be checked here (network, private, ambiguous) | **report, do not edit** |

When in doubt, it’s ❓ not ❌. False deletions are worse than a flagged maybe.

## Step 4 — Return the report

Return the report only: for each reference, its file and line, its bucket, and the evidence (for ❌, what proves it absent; for ❓, why it could not be checked). End with the count in each bucket. Do not edit or write anything, even with `Bash`.

## Runs forked; `background: false` for synchronous return

This whole skill runs isolated as the `hallucination-detector` custom agent (`context: fork` + `agent: hallucination-detector`), as `find-overlap` does with `overlap-detector`. Every step above needs only that agent’s tools (`Bash`, `Read`, `Grep`, `Glob`, `WebFetch`), so nothing is lost by forking the whole procedure. The harness gives the fork no Edit or Write tool; the agent keeps `Bash` for its checks, so avoiding a write-capable shell command is still instruction-level. `background: false` returns the report before the caller continues, because `purge-hallucinations` acts on it.

## Relationship to other skills

- **`purge-hallucinations` / `ph`** — the act half: runs this skill, then proposes each fix and applies it on confirmation.
- **`check-info-quality` / `ciq`** — this skill checks whether a reference **exists**; `ciq`’s check C checks whether a real reference **supports** the claim it is attached to.
- **`check-rendered-refs` / `crr`** — the output-side counterpart, for crossrefs and citations that broke at render time and leaked into the page as `?@key`.

Back to top
