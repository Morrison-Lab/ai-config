# Ask the user to leave auto mode when an action needs their approval

Applies to every agent that runs under a permission-classifier or approval mode:
Claude Code's auto mode, Codex approval modes, Gemini and Antigravity approval settings.
The mechanics below are written for Claude Code, whose auto-mode classifier is the measured case;
read "auto mode" as the equivalent unattended-approval mode elsewhere.

When the classifier denies an action the task genuinely needs,
the user can approve it directly the moment they leave auto mode.
They know this, and so should you: **ask them to switch**.
It is always an available request, so make it before improvising anything else.

The denial is not a verdict on the action.
The classifier cannot see what the user said hours ago,
and a standing grant does not clear it
(see [`use-existing-pr-branch`](use-existing-pr-branch.md) for the measured denial labels and the lasting `autoMode` fix).
A manual-mode permission prompt costs the user one click.
Every substitute costs more:
a stalled turn, a workaround that defeats the guard
(see [`claude-code-permissions`](../../memories/claude-code-permissions.md)),
or a script handed over for the user to run,
which fails for reasons the agent could have seen and takes longer than the approval would have.

Measured 2026-10-05 in a `psw` session.
The classifier denied a `git remote set-url` ("Remote Repoint") and an edit to `~/.claude/settings.json` ("Self-Modification").
The agent stalled and handed the user a script, and the script failed on its first run.
The user then left auto mode, approved the action, and it succeeded in one step.
The user's words: "I took you out of auto mode so I can approve things; remember you can always ask me to do that if helpful."
Related: [ai-config#4286](https://github.com/Morrison-Lab/ai-config/issues/4286), [ai-config#4033](https://github.com/Morrison-Lab/ai-config/issues/4033).

## When to ask

Ask when all three hold:

- The action is needed to finish the task.
- The user has authorized it, or it is within a standing grant.
- The denial is a classifier or approval-mode denial, not a hard-prohibited category.

Hard-prohibited categories are never made acceptable by a click:
entering credentials, financial transfers, permanent deletion, and the other items in the Prohibited list of the agent's safety rules.
For those, say the rule and ask the user to do it themselves.

## What to say

Name the refused command and the stated denial reason,
batch every action that will need approval,
and ask the user to switch out of auto mode for that stretch.
Then continue with the approved actions and do not retry the refused one in auto mode.

## Say when it is over

Once the actions that needed approval are done,
tell the user explicitly that they can switch back to auto mode.
Do not leave them in manual mode by silence:
nothing else tells them the stretch has ended,
and every later action keeps raising a prompt until they notice.

- **Do:** on a classifier denial of a needed, authorized action, say which command was refused and why, and ask the user to switch out of auto mode so they can approve it.
- **Do:** batch the actions that need approval into one manual-mode stretch, then say plainly, "you can switch back to auto mode now".
- **Don't:** stall, retry, rephrase, or route around the denial, or hand the user a script to run in place of the approval.
- **Don't:** ask to leave auto mode for a hard-prohibited category (credentials, financial actions, permanent deletion); approval does not make those acceptable.
