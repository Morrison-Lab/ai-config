# Instructions are global by default

An instruction from the user applies to every project and repository unless the user explicitly limits it to one.
"We are working on project X" is not a limit.

## Where to record it

- Prose rules go in `psw`.
- Agent rules go in `ai-config`.
- Checks go in `gha`.
- Project memory may also hold the rule, but it is not enough alone.

## What to do

- **Do:** record a new instruction in its global home in the same turn it arrives.
- **Do:** start following it in that same turn.
- **Do:** have project files link to the global copy.
- **Do:** once the global copy has merged, decide whether to shorten the project copy.
  The default is a one-line pointer to the global copy.
- **Don't:** record the instruction only in project memory.
- **Don't:** wait for the user to say it is global.
