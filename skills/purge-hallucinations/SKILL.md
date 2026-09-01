---
name: purge-hallucinations
description: "Verify and purge fake citations."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# purge-hallucinations — verify references resolve, then purge the fakes

LLM-written content (memories, skills, `CLAUDE.md`, code, docs, PR
descriptions) drifts into **hallucinations**: concrete references that read as
authoritative but don't resolve to anything real. This skill checks each
checkable reference against ground truth and, for every one proven fabricated,
proposes a fix interactively.

The prime directive: **only purge what you can prove is fake.** A reference you
*can't* verify (network down, ambiguous symbol, private resource) is
**unverifiable**, not a hallucination — report it, never silently delete it.

## When this fires

- "purge hallucinations", "ph", "check for hallucinations", "fact-check this"
- "verify the references", "find made-up / fabricated references"
- "does everything in this file actually exist", "what did you make up"
- "audit my memories/skills for stale references"
- Proactively when reviewing AI-generated text/code that asserts concrete,
  checkable facts (file names, function names, versions, links, citations) —
  especially memory and instruction files, which compound errors over time.

## Step 1 — Resolve the target

Pick the narrowest target the user named, in this precedence order:

1. **Explicit target** — a file, a directory, a PR diff, or pasted AI output
   the user pointed at. For a PR: `gh pr diff <n>` (local) or
   `mcp__github__pull_request_read` `method: get_diff` (remote/web — see
   `memories/github-mcp-tools.md`); audit only the references the diff *introduces*.
2. **The memory/instruction corpus** — the ai-config repo's `memories/`,
   `skills/`, and `CLAUDE.md`. Find the repo root with
   `git -C ~/.claude/skills/purge-hallucinations rev-parse --show-toplevel`.
3. **The current repo's code & docs** — when the user says "this repo" or
   names no target while inside a project.

If the target is genuinely ambiguous, ask once; otherwise proceed with the
narrowest reasonable reading and state which you chose.

## Step 2 — Extract concrete, checkable references

Scan the target for references that have a definite right/wrong answer. Ignore
prose, opinions, and design rationale — those aren't hallucinations, just
claims. Pull out, with file + line for each:

| Reference type | Examples |
|---|---|
| File / path | `src/foo.R`, `here("data/x.csv")`, a relative link in a `.qmd` |
| Function / object / symbol | `pkg::fn()`, an R object, a shell command, a Make target |
| Action ref + version | `uses: org/action@v3`, `@<sha>`, a tag/release |
| Skill name | `~/.claude/skills/<name>/`, a `/slash-command` |
| Memory cross-link | `[[some-memory-name]]` in a memory body |
| URL / link | `https://…`, a docs anchor, a badge target |
| Citation / package | a CRAN/Bioconductor package, a DOI, a `DESCRIPTION` dep |
| Flag / option / config key | a CLI flag, an env var, a YAML key the schema defines |
| API / SDK method or model id | an SDK method, a model name, an endpoint |

## Step 3 — Verify each against ground truth

Use the cheapest check that *proves existence or absence*. Match the tool to
the reference type:

- **File / path** — `test -e <path>`, `git ls-files -- <path>`, `ls`.
- **Function / object** — grep for the *definition*, not just a mention
  (`grep -rn "fn <- function" R/`); for an exported R fn check `NAMESPACE` /
  `Rscript -e 'library(pkg); exists("fn")'`. Shell command — `command -v`.
- **Action ref + version** — confirm the tag/SHA exists
  (`gh api repos/<org>/<repo>/git/refs/tags/<tag>` or `.../commits/<sha>`).
- **Skill name** — `ls skills/<name>/` in the local ai-config directory. If
  not found locally, check the session's available-skills list (appears in
  system reminders) before classifying as ❌; a globally-available system skill
  with no local directory is ❓ Unverifiable, not ❌ Fabricated.
- **Memory cross-link** — `[[target]]` links resolve to **skill directories**
  (`ls skills/<target>/`); if no matching skill, search memory headings
  (`grep -rn "^# .*<target>" memories/`).
- **URL / link** — `curl -sSI -o /dev/null -w '%{http_code}' <url>` (local) or
  `WebFetch` (remote). **A 404/410 is fabricated; a timeout, 403, 429, or
  DNS failure is *unverifiable*** — distinguish them.
- **Citation / package** — CRAN: `https://cran.r-project.org/package=<pkg>`;
  installed: `Rscript -e 'find.package("<pkg>")'`; dep: check `DESCRIPTION`;
  DOI / `.bib`: `python3 scripts/check_doi_bib.py <path-to-.bib>` (or `--root <dir> --cited-only`).
- **Flag / option / config key** — grep the tool's `--help`, its schema, or
  its source; for a YAML key, the consuming code/schema.
- **API / SDK method or model id** — check the SDK source/docs. For
  Claude/Anthropic specifics (model ids, params), **defer to the `claude-api`
  skill** rather than guessing.

Sort every reference into exactly one bucket:

| Bucket | Meaning | Disposition |
|---|---|---|
| ✅ **Resolves** | proven to exist | leave it |
| ❌ **Fabricated** | proven absent (404, no definition, no such tag/file) | propose a fix (Step 4) |
| ❓ **Unverifiable** | can't be checked here (network, private, ambiguous) | **report, do not edit** |

When in doubt, it's ❓ not ❌. False deletions are worse than a flagged
maybe.

## Step 4 — Propose a fix for each fabrication (interactive)

Default action is **propose, then apply on confirmation** — never bulk-edit
silently. For each ❌, present: the reference, where it is, the evidence it's
fake, and a proposed fix — exactly one of:

1. **Correct it** — when a real target is an obvious near-match (typo, moved
   path, renamed symbol, bumped version). Show the before→after. Prefer this
   over deletion when a true referent clearly exists (`grep`/`gh` for the
   nearest real name).
2. **Remove it** — when the reference is wholly invented and removing it leaves
   the sentence/code correct.
3. **Rewrite around it** — when removal would leave a dangling clause or broken
   code; restate without the fake reference.

Apply each fix only after the user confirms (batch obvious typo-corrections
together if the user prefers). Re-verify after editing. If the target is a
memory or instruction file, the global *"verify before recommending"* rule is
the reason this matters — a fabricated memory poisons every future session.

## Step 5 — Report

Summarize: N references checked → ✅ resolved, ❌ fixed (list before→after),
❓ unverifiable (list, with why each couldn't be checked). The ❓ list is a
feature, not a failure — it tells the user exactly what still needs a human
eyeball.

## Custom agent for the detect phase

Steps 1--3 (resolve target, extract references, verify against ground truth)
have no need for Edit/Write access. Delegate them to the
`hallucination-detector` custom agent (`.claude/agents/hallucination-detector.md`)
for a hard, harness-enforced guarantee against Edit/Write tool use before the
report in Step 4 is reviewed --- tighter than this skill's own
instruction-only discipline, though the agent retains `Bash` for read-only
checks, so avoiding a write-capable shell command is still instruction-level.
Run Step 4 (propose/apply fixes) in the main session afterward.

## Relationship to other skills

- **`record-learnings`, `ums`, `memorize` / `remember`** — these *write* the
  memory/skill/instruction corpus; `purge-hallucinations` *audits* it. A
  natural hand-off: after a big memory/skills write, run this to catch
  fabricated cross-links and stale paths.
- **`claude-api`** — the source of truth for Claude/Anthropic model ids and
  params; defer to it instead of guessing when verifying those references.
- **`simplify` / `tidy`** — clean *structure* (dead code, redundancy); this
  cleans *truth* (references that don't resolve). Complementary passes.
- **`reprexes`** — if verifying a code reference needs actually running it,
  isolate it as a reprex first.
- **`check-rendered-refs` / `crr`** — the output-side counterpart. This skill
  audits *source* references; `crr` scans *rendered* HTML for crossrefs/citations
  that broke at render time and leaked into the page as `?@key`. Hand a `?@key`
  hit here to trace the dangling key back to its source line.
- **`check-info-quality` / `ciq`** — this skill checks whether a reference
  **exists**; `ciq`'s check C checks whether an existing, real reference
  **actually supports** the claim it's attached to. A citation can pass here
  and still fail `ciq` if it resolves but doesn't say what the text claims.

## Anti-patterns

- ❌ Deleting an **unverifiable** reference as if it were proven fake — the
  cardinal sin. Network/permission failures are ❓, not ❌.
- ❌ Flagging prose, opinions, or design rationale — only concrete, checkable
  references are in scope.
- ❌ Confirming a symbol exists by finding a *mention* of it rather than its
  *definition*.
- ❌ Bulk-editing without proposing fixes first (default is interactive).
- ❌ Treating a network 403/429/timeout the same as a 404.
- ❌ Guessing whether a Claude/Anthropic model id or param is real instead of
  deferring to `claude-api`.
