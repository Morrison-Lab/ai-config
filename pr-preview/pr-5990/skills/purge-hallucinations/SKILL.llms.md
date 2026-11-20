# purge-hallucinations — verify references resolve, then purge the fakes

LLM-written content (memories, skills, `CLAUDE.md`, code, docs, PR descriptions) drifts into **hallucinations**: concrete references that read as authoritative but don’t resolve to anything real. This skill checks each checkable reference against ground truth and, for every one proven fabricated, proposes a fix interactively.

The prime directive: **only purge what you can prove is fake.** A reference you *can’t* verify (network down, ambiguous symbol, private resource) is **unverifiable**, not a hallucination — report it, never silently delete it.

## When this fires

- “purge hallucinations”, “ph”, “check for hallucinations”, “fact-check this”
- “verify the references”, “find made-up / fabricated references”
- “does everything in this file actually exist”, “what did you make up”
- “audit my memories/skills for stale references”
- Proactively when reviewing AI-generated text/code that asserts concrete, checkable facts (file names, function names, versions, links, citations) — especially memory and instruction files, which compound errors over time.

## Step 1 — Detect (forked)

Run the `detect-hallucinations` skill on the target the user named. It runs forked as the read-only `hallucination-detector` agent: it resolves the target, extracts every concrete, checkable reference, verifies each one against ground truth, and returns each as ✅ Resolves, ❌ Fabricated or ❓ Unverifiable, with its file, line and evidence. The target precedence, the reference types and the check for each type live in that skill’s file, not here.

When in doubt, it’s ❓ not ❌. False deletions are worse than a flagged maybe.

## Step 2 — Propose a fix for each fabrication (interactive)

Default action is **propose, then apply on confirmation** — never bulk-edit silently. For each ❌, present: the reference, where it is, the evidence it’s fake, and a proposed fix — exactly one of:

1.  **Correct it** — when a real target is an obvious near-match (typo, moved path, renamed symbol, bumped version). Show the before→after. Prefer this over deletion when a true referent clearly exists (`grep`/`gh` for the nearest real name).
2.  **Remove it** — when the reference is wholly invented and removing it leaves the sentence/code correct.
3.  **Rewrite around it** — when removal would leave a dangling clause or broken code; restate without the fake reference.

Apply each fix only after the user confirms (batch obvious typo-corrections together if the user prefers). Re-verify after editing. If the target is a memory or instruction file, the global *“verify before recommending”* rule is the reason this matters — a fabricated memory poisons every future session.

## Step 3 — Report

Summarize: N references checked → ✅ resolved, ❌ fixed (list before→after), ❓ unverifiable (list, with why each couldn’t be checked). The ❓ list is a feature, not a failure — it tells the user exactly what still needs a human eyeball.

## Why the detect phase is its own skill

With `context: fork`, a skill’s whole body runs in the forked agent, so a skill cannot fork only one step ([ai-config#914](https://github.com/Morrison-Lab/ai-config/issues/914)). Steps 2 and 3 need Edit and the user’s confirmation, which the read-only `hallucination-detector` agent cannot provide, so the detect phase lives in `detect-hallucinations` and this skill keeps the follow-through in the main session.

## Relationship to other skills

- **`detect-hallucinations`** — this skill’s forked, read-only detect phase (Step 1); run it alone for a report with no fixes.
- **`record-learnings`, `ums`, `memorize` / `remember`** — these *write* the memory/skill/instruction corpus; `purge-hallucinations` *audits* it. A natural hand-off: after a big memory/skills write, run this to catch fabricated cross-links and stale paths.
- **`claude-api`** — the source of truth for Claude/Anthropic model ids and params; defer to it instead of guessing when verifying those references.
- **`simplify` / `tidy`** — clean *structure* (dead code, redundancy); this cleans *truth* (references that don’t resolve). Complementary passes.
- **`reprexes`** — if verifying a code reference needs actually running it, isolate it as a reprex first.
- **`check-rendered-refs` / `crr`** — the output-side counterpart. This skill audits *source* references; `crr` scans *rendered* HTML for crossrefs/citations that broke at render time and leaked into the page as `?@key`. Hand a `?@key` hit here to trace the dangling key back to its source line.
- **`check-info-quality` / `ciq`** — this skill checks whether a reference **exists**; `ciq`’s check C checks whether an existing, real reference **actually supports** the claim it’s attached to. A citation can pass here and still fail `ciq` if it resolves but doesn’t say what the text claims.

## Anti-patterns

- ❌ Deleting an **unverifiable** reference as if it were proven fake — the cardinal sin. Network/permission failures are ❓, not ❌.
- ❌ Flagging prose, opinions, or design rationale — only concrete, checkable references are in scope.
- ❌ Confirming a symbol exists by finding a *mention* of it rather than its *definition*.
- ❌ Bulk-editing without proposing fixes first (default is interactive).
- ❌ Treating a network 403/429/timeout the same as a 404.
- ❌ Guessing whether a Claude/Anthropic model id or param is real instead of deferring to `claude-api`.

Back to top
