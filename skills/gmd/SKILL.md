---
name: gmd
description: "Run GIA with MWC and AWAY."
user-invocable: true
allowed-tools:
  - Bash
  - Agent
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# GMD — GIA + MWC + Delegated (Away)

Clear the repo's **entire** work queue end to end (`gia`) while acting with full session-wide decision latitude (`away`) and merge authority (`mwc`). (The "D" in GMD stands for Delegated, mapping to the `away` skill for a session-wide grant).

## When this fires

- "gmd"
- "gia mwc away", "/gia /mwc /away"
- "burn down the queue and just merge whatever looks good, don't ask me"

## Procedure

This is a compound macro. Expand it immediately into its three component skills:

1. **[`gia`](../gia/SKILL.md)**: Clear the existing PR queue first (Phase 1), then work through the open issues in order (Phase 2).
2. **[`mwc`](../mwc/SKILL.md)**: You hold explicit authority to merge the PRs you drive to a clean review verdict.
3. **[`away`](../away/SKILL.md)**: You hold a standing session-wide grant to make subjective design or implementation decisions yourself across all tasks, rather than blocking the loop to ask the user. Apply the option you would have recommended, note it in your report, and keep moving.

See the `gia` skill for the actual loop mechanics and reporting format.
