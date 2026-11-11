# do-it-for-me (difm)

The user is telling you to stop handing a step back and do it yourself. It usually fires right after you reported a block (“denied”, “needs your approval”) or offered a command for the user to run.

## When this fires

- The keyword `difm` or `do it for me`, bare or slashed.
- Close variants aimed at a step you just reported blocked or handed back: “you run it”, “run it yourself”.

## What it grants

Authority to run the specific step that was just blocked or handed back. Each new blocked step needs its own `difm`. It does not lift the prohibited-action rules.

## Procedure

1.  **Name the step** in one clause: the exact command or action.
2.  **Run it as one command, exactly as before.** A classifier denial is a sample, not a wall. The mechanics and limits are in [`ask-for-manual-approval`](../../shared/workflow/ask-for-manual-approval.md): retry the identical command once, never rephrased.
3.  **If it is denied again, turn auto mode off for this step.** Switch the session to `default` with `mcp__ccd_session_mgmt__set_session_permission_mode`, run the command once, then restore the original mode even if the command failed or timed out. Read the original mode first with `mcp__ccd_session_mgmt__get_session`. The self-switch, the stop conditions, and the managed-settings exception are in `ask-for-manual-approval`. How a standing grant interacts with a denial is in [`default-to-action-grants`](../../shared/workflow/default-to-action-grants.md).
4.  **Verify and report in the past tense**: what ran, the read-back or exit status, and that auto mode was restored. Count attempts honestly: “denied N times, succeeded on run N+1”, never “cannot”.

## What it does not grant

- A standing change to permission mode: auto mode is off for one step only.
- A wider step: same command, same target, nothing extra.
- Edits to settings files or allow rules: ask the user to add one if it would help.

## Relationship to other skills

- **[`dmmhyh`](../../skills/dmmhyh/SKILL.llms.md)** makes you ask less. `difm` carries out a step already blocked or handed back.
- **[`daytb`](../../skills/daytb/SKILL.llms.md)** decides a pending question. `difm` carries out a pending action.

## Anti-patterns

- Rephrasing the denied command instead of re-running it identically.
- Leaving auto mode off after the step.
- Offering a one-liner for the user to run when you can run it.

Back to top
