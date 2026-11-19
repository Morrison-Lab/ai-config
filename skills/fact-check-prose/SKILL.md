---
name: fact-check-prose
description: "Verify claims and values in prose. Aliases: fcp."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
  - WebFetch
  - Edit
  - Write
---

# fact-check-prose — verify claims, reasoning, and computed values in prose

Prose review usually stops at style. This skill goes further: it checks
whether the prose is actually **true** and its **logic actually holds** —
per the standing rule in `Morrison-Lab/ai-config`'s
[`shared/writing/fact-check-prose.md`](../../shared/writing/fact-check-prose.md),
which is the canonical statement of this policy (edit that file, not this
skill's procedure, if the policy itself changes).

## When this fires

- "fact-check this", "check the math", "verify this reasoning", "check this
  proof", "is this accurate", "does this claim check out"
- As part of any PR/MR review where the diff touches narrative prose — docs,
  READMEs, lecture notes, textbook chapters, commit/PR descriptions making a
  substantive claim. Run it alongside (not instead of) style review
  (`use-preferred-style`, `find-ai-tells`) and terminology review
  (`challenge-ambiguous-terminology`, folded into `ard`/`ardi`).

## Procedure

### 1. Check (forked)

Run the `check-prose-claims` skill on the target the user named.
It runs forked as the read-only `prose-claim-auditor` agent: it extracts the factual claims, reasoning chains, computed values and citations, runs the pre-flight readiness gate for cited sources, checks each unit against local sources, a re-derivation or the rendered output, and returns a `| Claim/step | Verdict | Basis |` table plus citations worth adding.
The extraction rules, the gate and the check for each kind of unit live in that skill's file, not here.

For a document with many independent claims, the main session can instead fan the units out to `prose-fact-checker` workers in a `Workflow`, one unit each;
the forked agent has no `Agent` tool, so it checks every unit itself.

### 2. Offer to apply corrections

On request, fix the flagged inaccuracies and reasoning gaps in place with `Edit`, preserving the author's intent and voice, the same posture as `find-ai-tells`'s apply step.
Don't silently rewrite without being asked;
report first.

### Why the check phase is its own skill

With `context: fork`, a skill's whole body runs in the forked agent, so a
skill cannot fork only one step
([ai-config#914](https://github.com/Morrison-Lab/ai-config/issues/914)).
Step 2 needs `Edit`, which the read-only `prose-claim-auditor` agent cannot
provide, so the checks live in `check-prose-claims` and this skill keeps the
corrections in the main session, as `purge-hallucinations` does with
`detect-hallucinations`.

## Relationship to other skills

- **`check-prose-claims`** --- this skill's forked, read-only check phase
  (step 1); run it alone for a report with no edits.
- [`challenge-ambiguous-terminology`](../../shared/workflow/challenge-ambiguous-terminology.md) —
  catches phrasing whose meaning is *unresolved*; this skill catches claims
  and reasoning that are resolved but *wrong*. Run both during review.
- **`use-preferred-style` / `find-ai-tells`** — style and AI-tell scans; this
  skill is the accuracy/reasoning counterpart, not a replacement.
- **`ard` / `ardi`** — when a reviewer (human or bot) flags a factual or
  reasoning error, `ard` handles the response disposition; this skill is how
  you (as reviewer) *find* that class of error in the first place.
- **`prose-fact-checker` agent** --- checks one unit handed to it, for
  fanning claim-checking out across a `Workflow` when a document has many
  independent claims to verify at once.
- **`check-info-quality` (`ciq`)** — this skill verdicts a claim
  **Accurate / Inaccurate / Undefended**; `ciq`'s check C catches a claim
  that's accurate by this skill's own standard yet still misleads (missing
  context, cherry-picking, a citation that only weakly supports it). `ciq`
  also covers two failure modes this skill doesn't: stale claims (check A)
  and irrelevant content (check B). Run both.

## Anti-patterns

- **Don't** accept a claim because it sounds authoritative — check it.
- **Don't** skip a derivation step because "it's probably fine" — re-derive
  it or flag it as unverified, not silently pass it.
- **Don't** trust the prose's own description of a computed value when a
  rendered artifact (preview or local render) is available to check it
  against directly.
- **Don't** limit citation suggestions to claims already flagged as uncited —
  suggest them anywhere they'd help a reader, per the fragment's policy.
