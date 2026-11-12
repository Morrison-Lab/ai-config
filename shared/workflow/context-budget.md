Keep always-loaded instruction files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) compact and budgeted.

`AGENTS.md` is gated at 32 KiB (32,768 bytes) to fit within OpenAI Codex's `project_doc_max_bytes` default without truncation.

The closure's total against the Claude Code CLI's instruction limit, the 100,000-byte closure budget (under `--strict`, ai-config#4685), the root file's character cap, a per-fragment cap, and a near-cap growth ratchet on the root file all gate CI (`scripts/check-context-closure.py`).

**Measure `AGENTS.md` before committing an addition, not after.**
Nothing warns at edit time ([ai-config#4684](https://github.com/Morrison-Lab/ai-config/issues/4684)).
Measured 2026-10-22: `main` sat 1 byte under the cap, so an agent's appended paragraph left the file 619 bytes over.
Only the adversarial reviewer caught it (the `main` figure is reproducible: `wc -c AGENTS.md` gave 32,767 at `427219fe`).

- **Do:** run `python3 scripts/check-context-closure.py` before committing an `AGENTS.md` addition.
  When it reports the file over the cap, move the detail into a `shared/` fragment and leave a one-line pointer.
- **Don't:** append a paragraph to `AGENTS.md` without measuring the cap, least of all when the last run reported tight headroom ([ai-config#4214](https://github.com/Morrison-Lab/ai-config/issues/4214)).

**Condensing a rule drops its qualifiers.**
Measured 2026-11-12 on the [#2889](https://github.com/Morrison-Lab/ai-config/issues/2889) composition: folding six `AGENTS.md` sections into one-sentence bullets dropped eight qualifiers, found over four review rounds.
They were two exemptions, an alternative remedy, one of three listed mechanisms, a clock-time report, a do-not-wait clause, and two of three triggers.
Each change tightened or loosened a rule while the bullet still read as the same rule.

- **Do:** before committing a condensed rule, list every clause of the original and point to where the condensed text keeps it, or to the fragment that carries it.
- **Don't:** condense several rules in one pass and leave the reviewers to find which conditions went missing.
