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
Measured 2026-11-12 on the [#2889](https://github.com/Morrison-Lab/ai-config/issues/2889) composition: folding six `AGENTS.md` sections into one-sentence bullets dropped eleven qualifiers, found over six review rounds.
They were two exemptions, an alternative remedy, one of three listed mechanisms, a clock-time report, a do-not-wait clause, two of three triggers, a scope limit, a list of wait cases, and an ordering ("first").
The removed headings also left ten citations by name in hooks, fragments, a skill and memories.
Each change tightened or loosened a rule while the bullet still read as the same rule.

- **Do:** before committing a condensed rule, list every clause of the original and point to where the condensed text keeps it, or to the fragment that carries it, and grep the repo for every removed heading's name.
- **Do:** place a composed section after every section whose terms it uses, and lead each folded rule's bullet with its name in bold, so the SessionStart index in `hooks/inject-core-rules.py` still lists it.
- **Don't:** condense several rules in one pass and leave the reviewers to find which conditions went missing.

**A rule moved out of `AGENTS.md` reaches an agent only through a link.**
No harness inlines fragments: opencode loads `AGENTS.md` alone, Codex and Gemini CLI add only a skill listing (`scripts/measure-session-start.py`), and `hooks/inject-core-rules.py` gives Claude Code an index of `AGENTS.md`'s headings.
Slimming `AGENTS.md` for [#5310](https://github.com/Morrison-Lab/ai-config/issues/5310) step 2 on 2026-11-12 hit three variants of this.
An adversarial self-review on [#5554](https://github.com/Morrison-Lab/ai-config/pull/5554) caught absolute rules leaving the file (no pay-per-use API, no PHI, reviewer independence, no bare `#NNN`).
A cross-harness read on [#5548](https://github.com/Morrison-Lab/ai-config/pull/5548) flagged a partial summary in the pointer that dropped a qualifier from each item it named.
An adversarial self-review on [#5551](https://github.com/Morrison-Lab/ai-config/pull/5551) caught a reworded reason that had lost its "can".

- **Do:** keep every absolute rule (a must or a never with no exceptions) inline when its section moves, and leave a pointer that names only the topics the fragment adds.
- **Do:** copy a kept sentence's modal verbs ("can", "may") and scope phrases verbatim when rewording it.
- **Don't:** summarize the moved rules in the pointer, as the [#5548](https://github.com/Morrison-Lab/ai-config/pull/5548) pointer did before its [cross-harness read](adversarial-self-review.md#cross-model-and-cross-harness-reviews-are-required-for-merging-and-the-harness-list-is-concrete) flagged it.
