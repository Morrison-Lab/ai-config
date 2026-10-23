# Instructions are global by default

An instruction from the user applies to every project and repository unless the user explicitly limits it to one.
"We are working on project X" is not a limit.

## Where to record it

- Prose rules go in [`psw`](https://github.com/Morrison-Lab/psw/).
- Agent rules go in [`ai-config`](https://github.com/Morrison-Lab/ai-config).
- Checks go in [`gha`](https://github.com/Morrison-Lab/gha).
- Project memory holds no rule, at most a pointer to one of these homes.

## Record it as a mechanism, not as prose

Ezra, 2026-10-23: "no more prose-only rules if we can help it;
all new rules go straight into hooks."
A prose rule is read by the agents that load it, and a subagent loads almost none of them ([ai-config#4698](https://github.com/Morrison-Lab/ai-config/issues/4698)).

- **Do:** write the hook (agent behaviour, in `hooks/`) or the failing check (content, in `gha`) in the same turn as the rule, with its test.
- **Do:** make the check blocking from its first PR.
  A warn-only check is how sds#444 shipped four divs in one subfile.
- **Do:** add the prose only as the explanation the hook's message links to.
- **Do:** where no mechanism can work, say why in the prose and file the issue that would make one possible.
- **Don't:** record a rule as a paragraph in `AGENTS.md`, a fragment or memory and call it done.

## What to do

- **Do:** record a new instruction in its global home in the same turn it arrives.
- **Do:** start following it in that same turn.
- **Do:** have project files link to the global copy.
- **Do:** once the global copy has merged, decide whether to shorten the project copy.
  The default is a one-line pointer to the global copy.
- **Don't:** record the instruction in project memory.
- **Don't:** wait for the user to say it is global.

## Track it in an issue first

- **Do:** file an issue for a new general-purpose rule in `ai-config` immediately, before or alongside the PR that records it.
  Search for a duplicate first, label it as [`issue-first.md`](issue-first.md) requires, and link the PR to it.
- **Do:** file an issue in the repository itself for a repo-specific rule, also immediately.
- **Don't:** treat an open PR as the tracker, or wait for the PR to exist before filing.

Rule from Ezra, 2026-10-16.
See [ai-config#4554](https://github.com/Morrison-Lab/ai-config/issues/4554).
