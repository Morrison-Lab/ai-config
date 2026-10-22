Keep always-loaded instruction files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) compact and budgeted.

`AGENTS.md` is gated at 32 KiB (32,768 bytes) to fit within OpenAI Codex's `project_doc_max_bytes` default without truncation.

The closure's total against the Claude Code CLI's instruction limit, the root file's character cap, a per-fragment cap, and a near-cap growth ratchet on the root file all gate CI (`scripts/check-context-closure.py`).

**Measure `AGENTS.md` before committing an addition, not after.**
Nothing warns at edit time ([ai-config#4684](https://github.com/Morrison-Lab/ai-config/issues/4684)).
Measured 2026-10-22: `main` sat 1 byte under the cap, so an agent's appended paragraph left the file 619 bytes over.
Only the adversarial reviewer caught it (the `main` figure is reproducible: `wc -c AGENTS.md` gave 32,767 at `427219fe`).

- **Do:** run `python3 scripts/check-context-closure.py` before committing an `AGENTS.md` addition, and move the detail into a `shared/` fragment, leaving a one-line pointer.
- **Don't:** append a paragraph to `AGENTS.md` without measuring the cap, least of all when the last run reported tight headroom ([ai-config#4214](https://github.com/Morrison-Lab/ai-config/issues/4214)).
