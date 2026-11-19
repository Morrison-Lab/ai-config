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

## Step 1 — Detect (forked)

Run the `find-info-issues` skill on the target the user named. It runs forked as the read-only `info-quality-auditor` agent: it resolves the target and the context each check needs, runs the pre-flight readiness gate before check C, runs checks A, B and C, and returns a `| Check | Finding | Location | Evidence | Severity | Proposed fix |` table. The gate and the three checks live in that skill’s file, not here.

## Step 2 — Propose fixes; apply only on confirmation

Same discipline as `find-ai-tells` and `purge-hallucinations`: **propose the fix, apply only on confirmation** — never bulk-edit silently. A misleading-citation finding in particular needs a human call on how to reframe the claim; don’t auto-rewrite it. Apply confirmed fixes in the main session with `Edit`.

## Why the detect phase is its own skill

With `context: fork`, a skill’s whole body runs in the forked agent, so a skill cannot fork only one step ([ai-config#914](https://github.com/Morrison-Lab/ai-config/issues/914)). Step 2 needs `Edit` and a confirmation from the user, which the read-only `info-quality-auditor` agent cannot provide, so the checks live in `find-info-issues` and this skill keeps the fixes in the main session, as `purge-hallucinations` does with `detect-hallucinations`.

## Relationship to other skills

- **`find-info-issues`** — this skill’s forked, read-only detect phase (step 1); run it alone for a report with no edits.
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
