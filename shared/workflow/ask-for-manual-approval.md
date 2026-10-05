# Ask the user to leave auto mode when an action needs their approval

Applies to every agent that runs under a permission classifier or approval mode.
The measured case is Claude Code's auto mode.
Codex approval modes, Gemini, and Antigravity are covered by analogy, since none of their behaviours has been measured here;
read "auto mode" as the equivalent unattended-approval mode there.

When the classifier denies an action the task needs, the user can approve it directly as soon as they leave auto mode.
Asking the user to switch is always available, so ask before improvising anything else.

The denial is not a verdict on the action.
The classifier cannot see what the user said hours ago, and a standing grant does not clear it (see [`use-existing-pr-branch`](use-existing-pr-branch.md) for the measured denial labels and the lasting `autoMode` fix).
A manual-mode permission prompt costs the user one click.
Every substitute costs more: a stalled turn, a workaround that defeats the guard (see [`claude-code-permissions`](../../memories/claude-code-permissions.md)), or a script handed to the user to run, which can fail for reasons the agent could have seen and takes longer than the approval would have.

Measured 2026-10-05 in a `psw` session.
The classifier denied a `git remote set-url` ("Remote Repoint") and an edit to `~/.claude/settings.json` ("Self-Modification").
The agent stalled and handed the user a script, and the script failed on its first run.
The user then left auto mode, approved the action, and it succeeded in one step.
The user's words: "I took you out of auto mode so I can approve things;
remember you can always ask me to do that if helpful."
Related: [ai-config#4286](https://github.com/Morrison-Lab/ai-config/issues/4286), [ai-config#4033](https://github.com/Morrison-Lab/ai-config/issues/4033).

## When to ask

Ask when all three hold:

- The action is needed to finish the task.
- The user has authorized it, or a standing grant covers it.
- The denial comes from the classifier or approval mode, not from a managed-settings policy or a `hard_deny` rule.

A managed-settings or `hard_deny` denial is reported to the user as a denial, not switched around: leaving auto mode may not lift it, and the administrator set it deliberately.

Hard-prohibited categories are never made acceptable by approval: credentials, financial actions, and permanent deletion.
For those, state the rule and ask the user to do the action themselves.

## What to say

Name the refused command and the stated denial reason, batch every action that will need approval, and ask the user to switch out of auto mode for that stretch.
Then continue with the approved actions, and do not retry the refused one in auto mode.

## Say when it is over

Once the actions that needed approval are done, tell the user explicitly that they can switch back to auto mode.
Nothing else tells them the stretch has ended, and every later action keeps raising a prompt until they notice.

- **Do:** on a classifier denial of a needed, authorized action, name the refused command and its stated reason, and ask the user to switch out of auto mode so they can approve it.
- **Do:** batch the actions that need approval into one manual-mode stretch, then say plainly, "you can switch back to auto mode now".
- **Don't:** stall, retry, rephrase, or route around the denial, or hand the user a script to run in place of the approval.
- **Don't:** ask to leave auto mode for a hard-prohibited category (credentials, financial actions, permanent deletion).
