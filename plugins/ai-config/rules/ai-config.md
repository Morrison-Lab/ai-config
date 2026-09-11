---
trigger: always
description: Universal AI Agent Instructions (AGENTS.md) and Antigravity operating rules for Morrison-Lab repositories.
---

# Universal AI Agent Instructions for Antigravity

These instructions define standardized operating rules for Antigravity operating within Morrison-Lab repositories.

## Core Universal Rules (from AGENTS.md)

1. **Gate external repository communication on membership:** Positively verify user membership before sending any outward communication to a repository (PRs, issues, comments, reviews).
2. **Worktree isolation:** Always isolate work in a dedicated `git worktree` so parallel sessions never step on or clobber working directory or branch state.
3. **Check remote immediately before every push:** Run `git ls-remote --heads origin <branch>` immediately before every `git push`. Never bare `git push --force`; use `--force-with-lease --force-if-includes`.
4. **No empty promises:** A commitment about future behavior must ship an implemented accountability mechanism in the same turn, or not be made at all.
5. **Resume every non-clean pause:** Arm a wake mechanism or schedule whenever work remains at a pause.
6. **Prefer optionality over removal:** Never remove existing functionality outright when you can add an opt-in/opt-out configuration or parameter.
7. **Research existing solutions before implementing (DRW):** Check existing libraries and upstream packages before hand-rolling custom code.
8. **Always give recommendations with questions:** Whenever asking a question or presenting choices, provide a concrete recommended option.
9. **Status and diagnostic requests are not report-only:** Diagnose and repair issues immediately in the same turn rather than waiting for follow-up prompts.
10. **Run UMS proactively:** Run UMS when scrutinized and before pausing when learnings have accumulated.
11. **Timestamp recaps in local time:** Use Pacific Time (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`).

## Antigravity Workflow Conventions

- **Reactive Wakeup vs Background Task Polling:** In Antigravity, background commands, subagents, and schedules resume execution reactively via incoming messages (`MESSAGE_PRIORITY_HIGH`). Do NOT poll `manage_task(Action='status')` in a loop. End the tool turn and let the system wake up when ready.
- **Subagent Review Asynchrony:** `invoke_subagent` returns immediately and runs in the background. Once the subagent finishes and returns a verified clean review report and fingerprint, use `ALLOW_UNREVIEWED_PUSH=1` for the `git push` invocation.
