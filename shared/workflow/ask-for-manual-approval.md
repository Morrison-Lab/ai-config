# Ask the user to leave auto mode when an action needs their approval

Applies to every agent that runs under a permission classifier or approval mode.
The measured case is Claude Code's auto mode.
Codex approval modes, Gemini, and Antigravity are covered by analogy, since none of their behaviours has been measured here;
read "auto mode" as the equivalent unattended-approval mode there.

When the classifier denies an action the task needs, the user can approve it directly as soon as they leave auto mode.
Asking the user to switch is available whenever the conditions under "When to ask" hold, so ask before improvising anything else.

The denial is not a verdict on the action.
A standing grant does not clear a classifier denial.
Only a user message that "directly and specifically describes the exact action" clears a `soft_deny` block, and nothing in the conversation clears a `hard_deny` block (see [`use-existing-pr-branch`](use-existing-pr-branch.md) for the measured denial labels and the lasting `autoMode` fix).
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

Ask when both of these hold:

- The action is needed to finish the task, and the user has authorized it or a standing grant covers it.
  An edit to the agent's own settings (`~/.claude/settings.json`) counts when the user authorized it, since that was the motivating case.
- The denial comes from the classifier or approval mode, not from a managed-settings `permissions.deny` rule.

A first denial can be a transient misfire (see [`claude-code-hooks`](../../memories/claude-code-hooks.md) on retrying an identical command once).
Retry the identical command once at most, never rephrased, then ask.
You cannot tell a `soft_deny` from a `hard_deny` block from inside the turn, so ask once and report the result.
If the user switches modes and the action is still refused, report that and stop.
A managed-settings `permissions.deny` denial applies in every mode, so report it as a denial and do not ask to switch.

If the user has not authorized the action, do not ask to switch modes.
Ask the user whether to do it at all, and proceed only on a yes.

Approval never makes a hard-prohibited category acceptable.
The list is not exhaustive: credentials, financial actions, and permanent deletion are examples, and the agent's own safety rules hold the full list.
For those, state the rule and ask the user to do the action themselves.

## What to say

Name the refused command and the stated denial reason, batch every action that will need approval, and ask the user to switch out of auto mode for that stretch.
Name `autoMode` in `~/.claude/settings.json` or managed settings as the lasting fix.
Until the user switches, continue with any work the denial does not block, and arm a wake to resume the denied step.

## Say when it is over

Once the actions that needed approval are done, tell the user explicitly that they can switch back to auto mode.
Nothing else tells them the stretch has ended, and every later action keeps raising a prompt until they notice.

## Do and Don't

- **Do:** on a classifier denial of a needed, authorized action, name the refused command and its stated reason, and ask the user to switch out of auto mode so they can approve it.
- **Do:** batch the actions that need approval into one manual-mode stretch, then say plainly, "you can switch back to auto mode now".
- **Don't:** end the turn after a denial without naming the mode switch, or offer only the `autoMode` configuration, which takes a settings change the user has to make.
- **Don't:** stall, retry more than once, rephrase, or route around the denial, or hand the user a script to run in place of the approval.
- **Don't:** ask to leave auto mode for a hard-prohibited category, or for an action the user has not authorized.
