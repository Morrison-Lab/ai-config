# Agent-curated knowledge bases & anti-bloat discipline (`benchbook`)

Patterns, failure modes, and architectural principles for LLM- and agent-maintained
knowledge bases, extracted from [`Ulef1005/benchbook`](https://github.com/Ulef1005/benchbook)
(reviewed 2026-08-31; lineage from Andrej Karpathy's LLM Wiki concept,
grounded in six months of operational logs across 1,563 pages and 9 domains).

Relevant to repository instructions, agent prompt architecture,
memory indexing, and multi-turn project state tracking.

---

## 1. Failure modes: rot vs. bloat under zero maintenance cost

Traditional human knowledge systems fail from **rot** (abandonment, stale notes, neglected indexes)
because human bookkeeping cost exceeds human attention.

When an LLM agent maintains a knowledge base, the failure mode flips to **bloat**:
- Maintenance cost drops to near zero, so the agent writes *too much*, in the wrong places.
- Eager agents duplicate narratives across multiple files, mirror task lists, and expand logs.
- A rotting repository looks empty and unmaintained;
  a bloated repository looks deceptively productive while degrading retrieval precision and context efficiency.
- *Core rule:* "Boredom was never the enemy.
  Enthusiasm was."
  System contracts must explicitly constrain agents to write less,
  in strictly designated single-source-of-truth locations.

---

## 2. Empirical anti-bloat rules & logging discipline

Operating rules derived from measured failures in production agentic wikis:

### Top-level logs must not accept an `update` operation
- When an `update` log operation existed, an audit showed 17 of 26 log entries were updates
  averaging 139 words (against a 1--3 line specification),
  duplicating narrative that was already written on specific project or entity pages.
- **The fix:** Central logs accept only structural operations (`ingest`, `create`, `lint`, `query`, `skill`),
  capped at 1--3 lines (~40 words max).
- **Placement rule:** Project progress narrative belongs in that project's own `## Log` section;
  entity or infrastructure state changes belong in that entity's `## Change History`.
  If an event requires a long log entry,
  that is a diagnostic signal that it belongs on a dedicated page instead.

### Central lists point; they never mirror
- Mirroring project-level todos into a central todo file resulted in 60 of ~76 mirrored items
  silently drifting from their source pages (completed tasks remained open, phases were renamed).
- **The fix:** Central hub/todo files must be pointer-only (markdown links).
  State lives on the originating page alone.
  Duplicated state inevitably diverges silently.

### Calibrate check thresholds to avoid alarm fatigue
- A simplistic rule ("keep pages concise, split beyond ~500 words") triggered on 27% of all pages.
  A rule that flags a quarter of a repository becomes noise and ceases to steer behavior.
- **The fix:** Measure accurately and exempt structural needs:
  - Exclude append-only sections (`## Log`, `## Change History`) from word counts.
  - Exempt page types whose length is inherent (raw source transcriptions, project templates with mandatory sections).
  - Raise thresholds for operational hub / entity pages where density is deliberate (splitting 1 lookup into 3 is a downgrade).
  - Report the worst offenders and a standing backlog count rather than dumping hundreds of warnings.

---

## 3. Persistent compounding knowledge base vs. ephemeral RAG / transcripts

Agent workflows frequently suffer from **reasoning decay**:
decisions, rejected alternatives, constraints, and platform quirks
are reasoned out in chat transcripts that scroll away,
leaving artifacts whose design rationale cannot be reconstructed.

| Mechanism | Strengths | Failure mode / Limitations |
|---|---|---|
| **Chat transcripts** | Captures complete dialogue | Surfaces nothing; search returns discussion timestamps rather than settled conclusions. |
| **Naive RAG / Chunks** | Handles large volume | Ephemeral; re-derives synthesis from scratch on every query and discards it; misses cross-document contradictions. |
| **Persistent Agent Wiki** | Compounds over time; integrates sources into entity hubs and decision records | Requires strict anti-bloat rules and human approval gates to avoid bloat. |

The agent serves three distinct roles over the knowledge base:
1. **Librarian:** Ingests raw material, places entities, maintains indexes, and flags contradictions explicitly.
2. **Advisor:** Answers queries by navigating structured domain indexes rather than blind vector searches.
3. **Project Manager:** Tracks lifecycle status, phases, and rejected options on dedicated project pages.

---

## 4. Deterministic vs. LLM-judgment quality gates

Linting and verification should be bifurcated cleanly:

- **Mechanical checks (deterministic scripts):**
  Frontmatter schema validation, enum checks, relative link resolution,
  domain/directory consistency, secret pattern scanning, and word-count thresholds.
  Run via fast Python scripts (`scripts/lint.py`) on every commit or in CI with clear exit codes.
- **Judgment checks (agent review passes):**
  Entity placement triage, staleness evaluation, contradiction detection between superseding documents,
  and identifying standalone scripts inlined in documentation that should be migrated to dedicated files.
- **Posture:** Agent linting is strictly **report-only** for content (never silently mutating bodies or schemas);
  mechanical writes are restricted to safe, non-destructive file archival.

---

## 5. Context budgeting via satellite contracts

To avoid overflowing context windows with monolithic instructions:
- Maintain a concise, universal root contract (`agents-core.md` or `AGENTS.md`) loaded at session start.
- Keep domain-specific rules (`agents-domain-*.md`), formatting conventions (`agents-page-conventions.md`),
  and detailed lint criteria (`agents-lint-checks.md`) in modular satellite files.
- Instruct agents to load satellite files lazily and on demand only when executing corresponding operations
  (e.g., loading lint specifications only during lint passes).

---

## 6. Source immutability & reference integrity

- Raw inputs (`raw/`) are treated as immutable sources
  and archived automatically after an aging window (e.g., 14 days);
  they are never mutated in place.
- **Link discipline:** Page bodies must link only to canonical URLs or wiki pages,
  storing local raw file paths in frontmatter (`raw_file:`) only.
  Linking raw file paths within page bodies creates brittle links that break upon archival.

---

## 7. Memory file size caps and splitting discipline

- **Strict line cap (`scripts/check-memory-file-size.py`):**
  Memory files under `memories/` have an enforced 1250-line limit (`DEFAULT_MAX_LINES`),
  validated via `scripts/check-memory-file-size.py --strict` in CI (`validate.yml`).
- **Warning band and pre-append checks:**
  The checker warns when files are within 100 lines of the cap.
  Appending new patterns or lessons to memory files (such as `memories/mistake-patterns.md`)
  when the file is within 10 lines of the 1250-line limit breaches `scripts/check-memory-file-size.py --strict` in CI `validate.yml`.
- **Split or condense rather than overflowing:**
  Files at or near the cap must be split into satellite files
  (e.g., extracting occurrence ledgers into `*.cases.md` or topical satellites per ai-config#694)
  or condensed before adding new entries;
  files must never be appended past 1250 lines.
- **Contiguity invariant awareness:**
  When splitting a file with sequential numbering constraints like `memories/mistake-patterns.md`
  (checked by `scripts/check-mistake-patterns.py`),
  moving non-contiguous sections creates numbering gaps unless downstream headings and citations are renumbered
  or stub pointers are preserved in place.

---

## 8. Pre-existing guideline violations and post-hoc DRW retirement

- **Filing pre-existing violations:**
  When agents or contributors notice pre-existing guideline violations in a repository
  (not introduced by the current task),
  they must file them as issues in the owning repository's tracker
  rather than letting them pass unrecorded or expanding active branch scope.
- **Post-hoc DRW violations:**
  A tool or helper built in-house may be legitimate when written because no suitable external solution existed.
  Over time, new external tools or upstream packages evolve that replicate or exceed its capabilities.
  Once noticed, this becomes a post-hoc DRW violation:
  the internal tool should be retired to reduce maintenance burden.
  Filing an issue tracks the retirement and upstream migration
  as a clean, scoped unit of work
  ([ai-config#4349](https://github.com/Morrison-Lab/ai-config/issues/4349),
  [`file-pre-existing-violations`](../shared/workflow/file-pre-existing-violations.md)).


