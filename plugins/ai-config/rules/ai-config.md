---
trigger: always_on
description: Universal AI Agent Instructions (AGENTS.md) and Antigravity operating rules for Morrison-Lab repositories.
---

# Universal AI Agent Instructions for Antigravity

These instructions define standardized operating rules for Antigravity operating within Morrison-Lab repositories.

## Core Universal Rules (from AGENTS.md)

1. **Gate external repository communication on membership:** Positively verify user membership before sending any outward communication to a repository (PRs, issues, comments, reviews).
2. **Worktree isolation:** Always isolate work in a dedicated `git worktree` so parallel sessions never step on or clobber working directory or branch state.
3. **Check remote immediately before every push:** Run `git ls-remote --heads origin <branch>` immediately before every `git push`.
   Never bare `git push --force`; use `--force-with-lease --force-if-includes`.
4. **No empty promises:** A commitment about future behavior must ship an implemented accountability mechanism in the same turn, or not be made at all.
5. **Resume every non-clean pause:** Arm a wake mechanism or schedule whenever work remains at a pause.
6. **Prefer optionality over removal:** Never remove existing functionality outright when you can add an opt-in/opt-out configuration or parameter.
7. **Prefer systemic solutions over one-off fixes:** Address the underlying mechanism and install automated guards rather than patching isolated instances.
8. **Research existing solutions before implementing (DRW):** Check existing libraries and upstream packages before hand-rolling custom code.
9. **"Or" means "and/or":** "Or" always means "and/or", not xor, unless xor or mutual exclusivity is explicitly specified.
10. **Always give recommendations with questions:** Whenever asking a question or presenting choices, provide a concrete recommended option.
11. **Status and diagnostic requests are not report-only:** Diagnose and repair issues immediately in the same turn rather than waiting for follow-up prompts.
    When asked for status, examine the transcript to check if the agent got stuck, frozen, or dropped the ball, diagnose what stalled, and resume work immediately.
12. **Run UMS proactively:** Run UMS when scrutinized and before pausing when learnings have accumulated.
13. **Timestamp recaps in local time:** Use Pacific Time (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`).
14. **Don't take anyone's word for it (no sycophancy):** Give users the whole truth and nothing but the truth,
    including your full honest opinions;
    never defer to the user's opinion when you disagree.
    Even when they state a claim or opinion without asking,
    if you disagree,
    say so.
    Always consider whether you agree before responding and/or acting.
15. **Terminate superseded background tasks:** Actively kill diagnostic commands, searches, and jobs once answered or superseded;
    sweep active tasks before declaring completion.
16. **Deliver completed implementation work:** When asked to implement, edit, or write up a change on a feature branch, do not stop at an uncommitted or unpushed worktree.
    Complete the delivery cycle: commit scoped changes, run adversarial self-review to a clean verdict, push the branch, and open or update its Pull Request automatically without waiting for the user to ask.
17. **Say whether the session is done when reporting stopping point status:** When ending a turn and reporting stopping point status, explicitly state whether the session is done or not, including running UMS (or confirming no new learnings accumulated) and filing noticed follow-up items.
    Never say a session is done when there are uncommitted, unpushed, or un-PRed changes, or open PRs authored by that session.
18. **Proactively suggest better alternatives:** If there's another way to accomplish the same goal more simply, cleanly, or reliably, proactively suggest and recommend that alternative rather than blindly implementing a proposed mechanism.
19. **Use real-world examples for general practice:** When we do or see something that would be a good example for general practice, actively capture and incorporate it as a concrete before-and-after example in shared documentation.
20. **Search tracker and AGENTS.md before building or denying a policy:** Search `AGENTS.md`, `CLAUDE.md`, `memories/`, `shared/`, and open issues before answering "no" to whether a policy exists or implementing a capability request.

## Antigravity Workflow Conventions

- **Autonomous Delivery Cycle on Feature Branches:** When working on a task in a branch or worktree, complete the full delivery pipeline (implement, verify/render, adversarial review via subagent, push, and open PR).
  Do not stop after verifying local edits to ask or wait for the user to prompt "pr?";
  proceed with pushing and opening the PR immediately under the standing "Default to action without asking" grant.
  Opening the PR does not conclude the session: the session is NOT done while its PR remains open, or when uncommitted, unpushed, or un-PRed changes remain, and must continue to monitor CI and drive reviews.
- **Reactive Wakeup vs Background Task Polling:** In Antigravity, background commands, subagents, and schedules resume execution reactively via incoming messages (`MESSAGE_PRIORITY_HIGH`).
  Do NOT poll `manage_task(Action='status')` in a loop.
  End the tool turn and let the system wake up when ready.
- **Terminate Superseded and Diagnostic Tasks Proactively:** Background tasks
  (e.g. `run_command`, asynchronous search/grep, monitors) consume CPU, disk I/O, and log space until killed.
  As soon as a question is answered or a probe is superseded, cancel it immediately using `manage_task(Action='kill')`.
  Always sweep and confirm zero unneeded background tasks (`manage_task(Action='list')`) before declaring a milestone or session complete.
- **Subagent Review Asynchrony:** `invoke_subagent` returns immediately and runs in the background.
  Once the subagent finishes and returns a verified clean review report and fingerprint, use `ALLOW_UNREVIEWED_PUSH=1` for the `git push` invocation.
