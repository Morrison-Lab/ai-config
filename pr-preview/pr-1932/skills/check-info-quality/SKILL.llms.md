# check-info-quality — flag stale, irrelevant, and misleading content

Three information-quality problems slip past both `purge-hallucinations` (fabricated references) and `find-ai-tells` (AI writing style), because each one requires **judgment about a claim’s relationship to something outside the claim itself** — not just checking whether a reference resolves:

1.  **Out-of-date** — the claim was true, but the world moved. Needs comparing the claim to its **current** state.
2.  **Irrelevant** — the claim is true and current, but doesn’t belong **here**. Needs judging the claim against its **surrounding context**.
3.  **Misleading / out-of-context** — the claim is true in isolation, but **misrepresents** something (a source, a comparison, a scope) when read as written. Needs comparing the claim against **what it’s used to support**.

All three are relational checks, not existence checks — the reason this is one skill with three passes rather than a `purge-hallucinations` variant.

## When this fires

- “check info quality”, “check-info-quality”, “ciq”, “audit this for information quality”
- “is this out of date / still accurate”, “find stale information”, “find outdated info”, “does this cite the current version”
- “is this relevant”, “does this belong here”, “is this off-topic”
- “is this misleading”, “is this out of context”, “check this citation supports the claim”, “does this quote/citation actually say that”
- Proactively, as part of a thorough content review (PR review, `ardi` cycle on documentation, or a `grade-work` pass) — fold in a pass of this catalog alongside `find-ai-tells` and `purge-hallucinations`.

## Step 1 — Resolve the target and its context

Pick the narrowest target the user named: a file, a PR/MR diff (`gh pr diff <n>` / `mcp__github__pull_request_read` `method: get_diff` per `tool-mappings.md` in a remote session), or pasted text.

Unlike `purge-hallucinations`, this skill needs **context beyond the target itself**:

- For staleness — the *current* state of whatever the claim describes (a package’s latest version, a tool’s current API, a policy’s latest revision).
- For relevance — the *surrounding document* (the chapter, the PR’s stated scope, the section’s topic) the claim sits inside.
- For misleading/out-of-context — the *source* a citation or quote points to, read in full, not just confirmed to exist.

Gathering that context is the expensive part of this skill; budget for it per finding, not just per target.

## Step 2 — Run the three checks

### A. Out-of-date information

For each factual claim that has a “current” value (a version, a status, a deprecation state, a guideline, a headcount, a “as of ” statement):

1.  Find the **current** value — check the package’s release page / CHANGELOG, the tool’s current docs, the policy’s latest revision, or (matching `check-dependency-updates`’ method) the relevant lockfile / manifest / `uses:` ref.
2.  Compare. Flag when the claim’s value **differs from current** and the claim doesn’t already hedge it (e.g. “as of 2023,” or “in v2,” makes an old value correct, not stale).
3.  Distinguish **evergreen** claims (a fact that doesn’t change, a historical statement correctly framed as historical) from **stale** ones (an unhedged “current” claim that’s since moved) — don’t flag the former.

Grep starting points for likely staleness carriers: version-looking tokens (`\bv?\d+\.\d+(\.\d+)?\b`), date-anchored phrases (“currently”, “as of”, “the latest”, “now supports”), and deprecation language (“deprecated”, “no longer”, “legacy”).

### B. Irrelevant information

For each passage, ask: **does removing it change what the surrounding claim/task/section needs to establish?** If the answer is no, it’s a candidate.

- **Off-topic tangent** — a paragraph or aside that doesn’t serve the section’s stated purpose (a chapter on coding style digressing into deployment infrastructure).
- **Scope creep** — a PR/issue introducing changes unrelated to its stated goal.
- **True-but-unrelated fact** — a statistic or citation that’s accurate but doesn’t bear on the claim it’s attached to (padding, not support).

Weigh relevance against the **document’s own stated scope** — a section heading, a PR’s title/description, an issue’s acceptance criteria — not against a generic notion of what’s interesting.

### C. Misleading / out-of-context information

The check that most needs source-reading, not just source-existence:

1.  **Citation-claim mismatch** — read the actual source the citation points to. Does it support the specific claim attached to it, a *weaker* version of the claim, or something else entirely? (Per `shared/writing/citations.md` — cite sources thoroughly means the citation must back the claim as stated, not just be topically related.)
2.  **Cherry-picked evidence** — a true statistic or quote presented without the surrounding context that would change its reading (a result cited without its confidence interval, caveat, or contradicting follow-up finding in the same source).
3.  **False scope** — a claim true for a narrow case presented as general (“X is faster” when the source measured one specific workload), or a comparison missing a relevant confound.
4.  **Missing context that reverses the takeaway** — omitting a fact the reader would need to reach the same conclusion the author reaches.

This differs in kind from A and B: it requires **reading the cited source’s actual content**, not just checking a link resolves (that’s `purge-hallucinations`’ job) or checking currency (check A) or placement (check B).

## Step 3 — Report

One table per target, each finding tagged with which check (A/B/C) it falls under:

    | Check | Finding | Location | Evidence | Severity | Proposed fix |
    |-------|---------|----------|----------|----------|---------------|
    | A: stale | "supports Node 14" | docs/setup.md:22 | package.json requires Node ^20 | blocking | update to current requirement |
    | B: irrelevant | paragraph on CI caching | chapter3.qmd:80-95 | chapter scope is citation style | nit | move to a CI chapter or cut |
    | C: misleading | "reduces errors by half" | README.md:5 | source reports 50% only for the largest of 3 cohorts tested | blocking | qualify the claim or cite the overall figure |

Severity mirrors the reviewer labels already in use in this corpus (“nit”, “minor”, “non-blocker”, “optional”) — see `shared/workflow/address-every-comment.md` for the treatment of each. Then, same discipline as `find-ai-tells` and `purge-hallucinations`: **propose the fix, apply only on confirmation** — never bulk-edit silently. A misleading-citation finding in particular needs a human call on how to reframe the claim; don’t auto-rewrite it.

## Custom agent for the detect phase

Steps 1-2 need no Edit/Write access. When the target is large (a whole PR, a full chapter, a batch of docs), delegate detection to a read-only agent so nothing gets modified before the report is reviewed — see `agent-builder` if this skill’s fan-out step needs a dedicated persona, matching the pattern `hallucination-detector` and `dependency-auditor` already set for their skills.

## Relationship to other skills

- **`purge-hallucinations`** — checks whether a reference **exists**; this skill (check C) checks whether an existing, real reference **actually supports** the claim it’s attached to. Run both — a citation can pass `purge-hallucinations` (it resolves) and still fail this skill (it doesn’t say what the text claims).
- **`find-ai-tells`** — checks *how* text is written; this skill checks *what* it claims. Complementary passes over the same target.
- **`check-dependency-updates` (`cdu`)** — the dedicated, deeper tool for check A when the staleness is specifically a pinned dependency/version; this skill’s check A is the general-purpose, lighter-weight version for any “current” claim, not just dependency pins.
- **`check-rendered-refs` (`crr`)** — scans *rendered* output for broken crossrefs; this skill scans *source* content for quality, not render breakage.
- **`shared/writing/citations.md`** — the standing rule this skill’s check C enforces: citations must actually back the claim.
- **`fact-check-prose` (`fcp`)** — the truth-side sibling: `fact-check-prose` verdicts a claim **Accurate / Inaccurate** (including re-deriving math and cross-checking rendered output); this skill’s check C catches a claim that passes that verdict — it’s **true** — yet still misleads through missing context, cherry-picking, or a citation that only weakly supports it. Checks A and B (staleness, relevance) have no `fact-check-prose` counterpart at all. Run both on a substantive prose review; neither subsumes the other. `fact-check-prose` also flags **undefended** claims (no citation, no internal reasoning, even if true) — a fourth failure mode distinct from this skill’s check C, which only fires when a citation already exists but doesn’t back its claim.
- **`address-every-comment` / `ardi`** — findings from this skill route through the same Address/Rebut/Defer discipline as any other review finding.
- **`shared/workflow/challenge-unnecessary-complexity.md`** — a sibling standing review rule, not a skill: flags unnecessary complexity or verbosity in prose, math, or code and asks for a simplification. Orthogonal to this skill’s three checks — content can be maximally simple and still stale, off-topic, or misleading, and vice versa. Fold both into the same review pass.

## Anti-patterns

- Flagging a correctly-hedged historical claim (“as of 2023…”) as stale — hedged claims are evergreen by construction.
- Flagging check C from a citation’s **title or existence** alone — read the actual cited content before judging mismatch.
- Judging relevance (check B) against a generic “is this interesting” standard instead of the document’s own stated scope.
- Bulk-editing findings without proposing fixes first.
- Treating an unverifiable “current value” (paywalled source, private doc) as proof of staleness — report it as unverifiable, don’t guess.

Back to top
