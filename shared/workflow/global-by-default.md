# Instructions are global by default

An instruction from the user applies to every project and repository unless the user explicitly limits it to one.
"We are working on project X" is not a limit.

## Where to record it

- Prose rules go in [`psw`](https://github.com/Morrison-Lab/psw/).
- Agent rules go in [`ai-config`](https://github.com/Morrison-Lab/ai-config).
- Checks go in [`gha`](https://github.com/Morrison-Lab/gha).
- Project memory may also hold the rule, but it is not enough alone.

## What to do

- **Do:** record a new instruction in its global home in the same turn it arrives.
- **Do:** start following it in that same turn.
- **Do:** have project files link to the global copy.
- **Do:** once the global copy has merged, decide whether to shorten the project copy.
  The default is a one-line pointer to the global copy.
- **Don't:** record the instruction only in project memory.
- **Don't:** wait for the user to say it is global.

## Track it in an issue first

- **Do:** file an issue for a new general-purpose rule in `ai-config` immediately, before or alongside the PR that records it.
  Search for a duplicate first, label it as [`issue-first.md`](issue-first.md) requires, and link the PR to it.
- **Do:** file an issue in the repository itself for a repo-specific rule, also immediately.
- **Don't:** treat an open PR as the tracker, or wait for the PR to exist before filing.

Rule from Ezra, 2026-10-16.
See [ai-config#4554](https://github.com/Morrison-Lab/ai-config/issues/4554).
