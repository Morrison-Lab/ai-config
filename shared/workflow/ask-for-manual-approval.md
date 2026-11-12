# Leave auto mode, or ask the user to, when an action needs approval

Applies to every agent that runs under a permission classifier or approval mode.
The measured case is Claude Code's auto mode.
Codex approval modes, Gemini, and Antigravity are covered by analogy, since none of their behaviours has been measured here;
read "auto mode" as the equivalent unattended-approval mode there.

When the classifier denies an action the task needs, leaving auto mode lets the action run through the ordinary permission prompt,
or with no prompt where an allow route covers it.
Leaving auto mode is available whenever the conditions under [When to switch or ask](#when-to-switch-or-ask) hold:
switch the session yourself where that section allows it,
or ask the user to switch.
Do that before improvising anything else.

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

## When to switch or ask

Approval never makes a hard-prohibited category acceptable.
The list is not exhaustive: credentials, financial transfers, permanent deletion, and CAPTCHAs are examples, and each agent's own safety rules hold the full list.
For those, state the rule and describe the action, and tell the user that doing it is theirs to choose and to do by hand.
Never do it yourself on their yes, and do not hand them a command to run.
When no one can answer (an `away` session, or a CI or `@claude` run), record it as a pending decision instead.
A dispatched subagent reports it to the session that dispatched it, which handles it the same way.

Leave auto mode for an action only when all of these hold (the switch conditions):

- The action is needed to finish the task, and the user has authorized it or a standing grant covers it.
  An edit to the agent's own settings (`~/.claude/settings.json`) counts as authorized and needed when the user authorized it, since that was the motivating case.
- The denial comes from the classifier or approval mode, not from a managed-settings `permissions.deny` rule.
- The action is outside those hard-prohibited categories.
- The user is present to answer a prompt, so this is not an `away` session or a CI or `@claude` run.
- The session that would take the action is not a dispatched subagent.
  A mode switch changes the mode of the whole session, which a subagent does not own, and the caller holds the context the user needs to decide.
  So a denied subagent reports the refused command and the stated reason to the session that dispatched it, and never switches modes itself;
  the report passes up the dispatch chain until it reaches the first session that can ask the user, and that session decides.

When the switch conditions hold, the next step depends on whether the rerun will raise a prompt.
Leaving auto mode is safe without a question first only because the user then approves or refuses the action at that prompt.
Auto mode drops broad allow rules that `default` mode honours ([permission modes](https://code.claude.com/docs/en/permission-modes)), and other routes allow a command with no prompt at all:
a `permissions.allow` rule in any settings file that applies, a PreToolUse hook that returns an allow decision, a session "always allow" grant, and `--allowedTools`.
This repository's [`grant-personal-permissions`](../../hooks/grant-personal-permissions.py) hook allows `gh pr merge` that way.
So never switch modes yourself for a merge:
that hook would let the rerun through with no prompt, and a merge cannot be undone.
Read the settings files and hooks that apply, and do not switch for an action one of them allows, or when they do not let you tell.
In those cases ask the user to switch out of auto mode instead, naming the refused command and its stated reason.
A session grant or `--allowedTools` cannot be read from inside the session.
Only the user can set one, so a rerun that such a grant lets through runs on the user's own grant, and that residual risk is accepted.
Otherwise, when `mcp__ccd_session_mgmt__set_session_permission_mode` is available, switch the session to `default` yourself with that tool, rerun the command once so the user gets a real approval prompt, and request `auto` again once the actions that needed approval are done.
A switch to a lower mode shows no card, so that prompt is the user's only sign of the switch.
When that tool is not available, ask the user to switch out of auto mode the same way.

A first denial can be a transient misfire (see [`claude-code-hooks`](../../memories/claude-code-hooks.md) on retrying an identical command once).
Retry the identical command once at most, never rephrased, then switch or ask.
You cannot tell a `soft_deny` from a `hard_deny` block from inside the turn, so switch or ask once and report the result.
If the mode is switched, by the user or by you, and the action is still refused, report that and stop;
when you switched it yourself, request `auto` again first.
A managed-settings `permissions.deny` denial applies in every mode, so report it as a denial and do not switch or ask to switch.

For an action outside the hard-prohibited categories that the user has not authorized, do not switch or ask to switch modes.
Ask the user whether to do it at all, and proceed only on a yes.
A yes authorizes the action, so a denial after it follows the steps above.
When no one can answer, record it as a pending decision instead (an `away` session, or a CI or `@claude` run), or report it up the dispatch chain (a dispatched subagent).

## What to say

Name the refused command and the stated denial reason, and batch every action that will need approval.
When you switched the session yourself, say so and say that a prompt is coming;
when the switch conditions hold and you could not switch, ask the user to switch out of auto mode for that stretch.
When an allow route covers the action, such as a merge, tell the user that switching lets it run with no further prompt.
Name `autoMode` in `~/.claude/settings.json` or managed settings as the lasting fix.
When you asked the user to switch, then until the session leaves auto mode, continue with any work the denial does not block, and arm a wake to resume the denied step.
If the user is away (an `away` session, or a CI or `@claude` run), nobody can answer a prompt: do not switch or ask, record the denied action as a pending decision, do not poll for a switch, and continue other work.

## Say when it is over

Once the actions that needed approval are done, end the manual-mode stretch explicitly.
When you switched the session yourself, request `auto` again with the same tool;
otherwise tell the user they can switch back to auto mode.
Nothing else ends the stretch, and every later action keeps raising a prompt until someone does.

## Do and Don't

- **Do:** on a classifier denial, make the one identical retry, then leave auto mode or report as [When to switch or ask](#when-to-switch-or-ask) says, in the session the classifier denied, or, in a dispatched subagent, report it up the dispatch chain.
  (2026-10-22, `apply-all.sh --apply`: two classifier denials, labelled "Modify Shared Resources" then "Auto-Mode Bypass", despite the user's typed "go".
  The user was told to "approve the prompt" when none existed, and was asked "retry?" and "disable auto?" instead of the agent switching the session itself;
  after the user answered `daytb`, the self-switch to `default` let the apply run.)
- **Do:** batch the actions that need approval into one manual-mode stretch, then end it as "Say when it is over" describes.
- **Do:** in a Claude Project, when the user answers the coordinator instead of the denied thread, the coordinator tells that thread, with the user's message attached by id, to ask the user again in its own thread.
  The relayed message is not approval.
- **Don't:** when the switch conditions hold, end the turn after a denial without naming the mode switch, or offer only the `autoMode` configuration, which takes a settings change the user has to make.
- **Don't:** retry a denied command more than once, or rephrase it.
  A rerun after the session has left auto mode is not a retry.
- **Don't:** route around a denial, or hand the user a script to run in place of the approval.
- **Don't:** hand a denied action to another session to run instead: a subagent, or in a Claude Project another thread or the coordinator ([`claude-app-projects`](../../memories/claude-app-projects.md)).
  That is routing around the denial too.
  The one exception is a dispatched subagent returning its denied action up its own dispatch chain, as [When to switch or ask](#when-to-switch-or-ask) says.
  (2026-11-11: after the classifier denied a thread's merge of [gha#1910](https://github.com/Morrison-Lab/gha/pull/1910), the coordinator declined to hand the merge to the project's runner thread.)
- **Don't:** switch or ask to leave auto mode for a hard-prohibited category, or for an action the user has not authorized.
- **Don't:** tell the user to approve a prompt after a classifier denial;
  the denial shows none.
  Say "no prompt was shown".
