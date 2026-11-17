---
name: find-info-issues
description: "Find stale or misleading text."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
  - WebFetch
context: fork
agent: info-quality-auditor
background: false
---

# find-info-issues --- read-only check for stale, irrelevant and misleading content

The *detect* half of `check-info-quality`, factored out so it runs forked ([ai-config#914](https://github.com/Morrison-Lab/ai-config/issues/914)).
It runs the three relational checks below and returns a findings table with a proposed fix per row.
It changes nothing: `check-info-quality` runs it, then proposes fixes and applies them in the main session only on the user's confirmation, and you can run this skill on its own for a report with no edits.

1. **Out-of-date** --- the claim was true, but the world moved.
   Needs comparing the claim to its **current** state.
2. **Irrelevant** --- the claim is true and current, but doesn't belong **here**.
   Needs judging the claim against its **surrounding context**.
3. **Misleading / out-of-context** --- the claim is true in isolation, but **misrepresents** something (a source, a comparison, a scope) when read as written.
   Needs comparing the claim against **what it's used to support**.

## Pre-flight Readiness Gate (Hard Stop for Check C)

Before evaluating Check C (Misleading / out-of-context information),
check whether the repository's local source corpus (`sources/` or equivalent) actually contains the needed sources:
**(Note: Checks A and B do not require a source corpus.
If the target document contains zero citations to external works, skip this gate and proceed directly to evaluate Check C).**

1. **Are required sources missing from the local corpus?**
2. **Is the required source present but unconverted?**
   For example, a `.pdf`, `.docx`, or `.epub` file without a corresponding Markdown conversion.

If **either** of these conditions hold, **refuse to run Check C**.

- Do NOT partially check Check C by evaluating only the sources that are present (rescoped only on explicit user request).
- Do NOT fall back to memory or the open web for the missing sources.
- If you discover during verification that a local source is incomplete (e.g. missing a chapter), abort Check C and return **`Pre-flight: NOT READY`**.

For Check C, return **`Pre-flight: NOT READY`** instead of a report,
and print remediation instructions.
For example, "Populate the `sources/` directory with Markdown conversions of the cited works so they can be verified locally."
You must still execute Checks A and B.

## Step 1 --- Resolve the target and its context

Pick the narrowest target the user named: a file, a PR/MR diff (`gh pr diff <n>` / `mcp__github__pull_request_read` `method: get_diff` per `tool-mappings.md` in a remote session), or pasted text.
A forked run cannot ask the user, so when the target is ambiguous, take the narrowest reasonable reading and state at the top of the report which reading you chose.

Unlike `purge-hallucinations`, this skill needs **context beyond the target itself**:

- For staleness --- the *current* state of whatever the claim describes (a package's latest version, a tool's current API, a policy's latest revision).
- For relevance --- the *surrounding document* (the chapter, the PR's stated scope, the section's topic) the claim sits inside.
- For misleading/out-of-context --- the *source* a citation or quote points to, read in full, not just confirmed to exist.

Gathering that context is the expensive part of this skill;
budget for it per finding, not just per target.

## Step 2 --- Run the three checks

### A. Out-of-date information

For each factual claim that has a "current" value (a version, a status, a deprecation state, a guideline, a headcount, a "as of <date>" statement):

1. Find the **current** value --- check the package's release page / CHANGELOG, the tool's current docs, the policy's latest revision, or (matching `check-dependency-updates`' method) the relevant lockfile / manifest / `uses:` ref.
2. Compare.
   Flag when the claim's value **differs from current** and the claim doesn't already hedge it (e.g. "as of 2023," or "in v2," makes an old value correct, not stale).
3. Distinguish **evergreen** claims (a fact that doesn't change, a historical statement correctly framed as historical) from **stale** ones (an unhedged "current" claim that's since moved) --- don't flag the former.

Grep starting points for likely staleness carriers: version-looking tokens (`\bv?\d+\.\d+(\.\d+)?\b`), date-anchored phrases ("currently", "as of", "the latest", "now supports"), and deprecation language ("deprecated", "no longer", "legacy"):

```bash
# Grep for likely staleness carriers: versions, dates, temporal and deprecation phrases
rg -ni '\bv?\d+\.\d+(\.\d+)?\b|\b(currently|as of|the latest|now supports|deprecated|no longer|legacy)\b' <target>
```

### B. Irrelevant information

For each passage, ask: **does removing it change what the surrounding claim/task/section needs to establish?**
If the answer is no, it's a candidate.

- **Off-topic tangent** --- a paragraph or aside that doesn't serve the section's stated purpose (a chapter on coding style digressing into deployment infrastructure).
- **Scope creep** --- a PR/issue introducing changes unrelated to its stated goal.
- **True-but-unrelated fact** --- a statistic or citation that's accurate but doesn't bear on the claim it's attached to (padding, not support).

Weigh relevance against the **document's own stated scope** --- a section heading, a PR's title/description, an issue's acceptance criteria --- not against a generic notion of what's interesting.

### C. Misleading / out-of-context information

The check that most needs source-reading, not just source-existence:

1. **Citation-claim mismatch** --- read the actual source the citation points to.
   Does it support the specific claim attached to it, a *weaker* version of the claim, or something else entirely?
   (Per `shared/writing/citations.md` --- cite sources thoroughly means the citation must back the claim as stated, not just be topically related.)
2. **Cherry-picked evidence** --- a true statistic or quote presented without the surrounding context that would change its reading (a result cited without its confidence interval, caveat, or contradicting follow-up finding in the same source).
3. **False scope** --- a claim true for a narrow case presented as general ("X is faster" when the source measured one specific workload), or a comparison missing a relevant confound.
4. **Missing context that reverses the takeaway** --- omitting a fact the reader would need to reach the same conclusion the author reaches.

This differs in kind from A and B: it requires **reading the cited source's actual content**, not just checking a link resolves (that's `purge-hallucinations`' job) or checking currency (check A) or placement (check B).

## Step 3 --- Return the report

Return the report only: one table per target, each finding tagged with which check (A/B/C) it falls under:

```
| Check | Finding | Location | Evidence | Severity | Proposed fix |
|-------|---------|----------|----------|----------|---------------|
| A: stale | "supports Node 14" | docs/setup.md:22 | package.json requires Node ^20 | blocking | update to current requirement |
| B: irrelevant | paragraph on CI caching | chapter3.qmd:80-95 | chapter scope is citation style | nit | move to a CI chapter or cut |
| C: misleading | "reduces errors by half" | README.md:5 | source reports 50% only for the largest of 3 cohorts tested | blocking | qualify the claim or cite the overall figure |
```

Severity mirrors the reviewer labels already in use in this corpus ("nit", "minor", "non-blocker", "optional") --- see `shared/workflow/address-every-comment.md` for the treatment of each.
A current value or source you could not reach (paywalled source, private doc) is reported as unverifiable, not as proof of staleness.
Do not edit or write anything, even with `Bash`.

## Runs forked; `background: false` for synchronous return

This whole skill runs isolated as the `info-quality-auditor` custom agent (`context: fork` + `agent: info-quality-auditor`), as `check-prose-claims` does with `prose-claim-auditor`.
Every step above needs only that agent's tools (`Bash`, `Read`, `Grep`, `Glob`, `WebFetch`).
The harness gives the fork no Edit or Write tool;
the agent keeps `Bash` for its checks, so avoiding a write-capable shell command is still instruction-level.
`background: false` returns the report before the caller continues, because the caller acts on it.

## Relationship to other skills

- **`check-info-quality` (`ciq`)** --- the act half: runs this skill, then proposes the fixes this report names and applies them on confirmation.
- **`purge-hallucinations`** --- checks whether a reference **exists**;
  check C here checks whether an existing, real reference **actually supports** the claim it's attached to.
- **`check-prose-claims`** --- the truth-side sibling: it verdicts a claim accurate or inaccurate, while check C here catches a true claim that still misleads.
