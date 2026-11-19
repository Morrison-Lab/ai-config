# reproducibility-audit — checklist audit of a project’s reproducibility posture

Audit whether a project reproduces reliably from a clean checkout, not whether its pinned dependencies are current. A project can be fully up to date and still fail to reproduce — an absolute path baked into a script, an env var nobody documented, a build artifact that hides non-determinism. This skill finds those gaps with a checklist scoped to the project’s type.

## When this fires

- “reproducibility audit”, “audit reproducibility”, “check reproducibility”, “is this project reproducible”
- “find hidden dependencies”, “find hardcoded paths”, “check environment assumptions”
- “can this be reproduced from scratch”, “audit for a replication package”, “check output traceability”
- Before archiving a project (OSF/Dryad, per the lab manual’s reproducibility norms) or submitting it alongside a manuscript.
- Periodically on a long-lived analysis repo, the same cadence `check-dependency-updates` uses for freshness audits.

## Step 1 — Audit (forked)

Run the `find-reproducibility-gaps` skill on the project the user named. It runs forked as the read-only `reproducibility-auditor` agent: it detects the project’s type, runs the checklist sections that apply (R package, Quarto book/site, general script repo, then output traceability, environment assumptions and hidden dependencies for every project), and returns one table row per gap with its check, location, evidence and severity. The checklist and the command for each check live in that skill’s file, not here.

## Step 2 — Follow through

1.  **Read the report table** and confirm each gap’s evidence before acting on it.
2.  **File a tracking issue** for the gaps worth fixing (issue-first, per this repo’s `st`/`gi` workflow). Group related gaps under one issue (e.g. all hardcoded-path fixes together); don’t open one issue per one-line fix.
3.  **Fix on a branch**, run the project’s standard checks, and open a PR. Follow with `ardi` to drive it to clean.

## Why the audit phase is its own skill

With `context: fork`, a skill’s whole body runs in the forked agent, so a skill cannot fork only one step ([ai-config#914](https://github.com/Morrison-Lab/ai-config/issues/914)). Step 2 needs the write access and PR workflow the read-only `reproducibility-auditor` agent cannot provide, so the audit lives in `find-reproducibility-gaps` and this skill keeps the follow-through in the main session, as `purge-hallucinations` does with `detect-hallucinations`.

## Relationship to other skills

- **`find-reproducibility-gaps`** — this skill’s forked, read-only audit phase (Step 1); run it alone for a report with no follow-through.
- **`reprexes`** — isolates a **single bug** into a minimal runnable snippet, for debugging or filing upstream; this skill audits whether the **whole project** reproduces reliably (pinned deps, captured seeds and session info, deterministic renders). Different scope (one bug vs. whole-repo posture) and different cadence (on-demand debugging aid vs. periodic audit). `reprexes` is often invoked *within* an investigation this skill’s findings trigger — e.g. a traceability gap this skill flags can turn into a `reprexes` session once someone tries to isolate why a specific output doesn’t regenerate. For the R/Quarto specifics of capturing `sessionInfo()` and treating `_freeze`/build artifacts as confounders, see `reprexes`’ own “R / Quarto specifics” section rather than duplicating that content here. (`reprexes` currently has no “Relationship to other skills” section of its own — noted here as an observation, not fixed in this PR, to keep this change scoped to the new skill.)
- **`check-dependency-updates` (`cdu`)** — asks “is this pinned dependency current” (is there a newer version available); this skill asks “is the current pin, whatever version it is, sufficient to reproduce a result deterministically” (freshness is irrelevant to that question). Run `cdu` for upgrades, run this skill for reproducibility gaps — a project can fail either audit independently of the other.
- **`check-info-quality` (`ciq`)** — its check A (out-of-date information) can flag a stale “how to install” doc; the audit’s section 3 and 5 checks go further, verifying prerequisites and env assumptions are documented **at all**, not just current.
- **`st` / `gi` / `defer-issue`** — file the tracking issue and drive the fix PR.
- **`convert-repo-format` (`crf`)** — establishes the lab’s template layout a repo should follow; this skill checks whether a given repo, in whatever layout it already has, actually reproduces.

## Anti-patterns

- ❌ Treating “dependencies are up to date” (`cdu`’s job) as the same question as “dependencies are reproducible” (this skill’s job) — a freshly bumped pin can still be undocumented or hidden.
- ❌ Flagging every absolute path without checking whether it’s inside a gitignored scratch/cache directory that never ships — focus on paths that appear in code a fresh clone would run.
- ❌ Silently fixing a hardcoded path or undocumented env var instead of reporting it — propose the fix, don’t bulk-edit without review, the same discipline `check-info-quality` and `find-ai-tells` already use.
- ❌ Auditing only the project-type-specific sections and skipping output traceability — a project can have a pristine lockfile and still ship a figure nobody can regenerate.
- ❌ Reporting “looks reproducible” without actually running a clean render/build — verify by attempting the reproduction, don’t infer it from the presence of a lockfile alone.

Back to top
