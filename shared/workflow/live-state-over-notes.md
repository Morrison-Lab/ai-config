# Probe a changing condition live; never decide it from a note

A note records what was true when someone wrote it.
Quota, availability, runner state, outages and a PR's state change.
Decide such a condition from a live check, never from a memory entry, an instruction file or an earlier session's report.

Ezra, 2026-11-06: "agy is not exhausted, you cant rely on out of date notes", "same with opencode", "cai: never rely on static notes to determine dynamic conditions" (ai-config#5018).
The slip: a thread waived the cross-harness review because a project-memory note said the agy and OpenCode quotas were exhausted.
Both were available.

Extends [`check-sources-over-recall`](check-sources-over-recall.md), which covers recalled facts.
This rule covers a note's claim about a condition that changes.

Conditions that change include quota, availability, outages, pauses, CI state, branch or PR state, and open or merged status.
Memories, handoffs, recaps and earlier transcript turns are hints, not evidence.
An earlier case: a remembered "agy Argon quota out until 2026-11-04" note was acted on after Argon had recovered (Ezra, 2026-11-05).
This text started as the `AGENTS.md` section in ai-config#5019, which this file replaces.

- **Probe before you act on the condition.**
  Probe each route.
  For agy, make a real call on cf463-02 through Remote Control, since agy is absent in cloud containers.
  For OpenCode, run `opencode run` or curl `https://opencode.ai/zen/go/v1/chat/completions`.
  For anything else, call the runner or the API.
  A version flag proves installation, not quota.
- **A probe is per decision.**
  Probe again in the turn that makes the waiver or the skip.
  An earlier probe is a note.
- **A note may point you at what to probe, never settle it.**
  Use a note's claim to order your checks.
  Do not report it as the state.
- **Say what the probe returned.**
  Quote the error or the success, with the time.
- **Record an expiry on every note about a changing condition.**
  A note about a quota, a runner, an outage, availability or similar carries `expires YYYY-MM-DD`.
  After that date it is a hint only.
  Write a note without an expiry only for a fact that does not change.
  (Ezra, 2026-11-06: "notes on dynamic conditions must record their expiration dates".)

Enforced by `hooks/no-waiver-without-live-probe.py`, which denies a reply or relay message that calls agy, OpenCode or a cross-harness reviewer exhausted, unavailable or waived when the current turn shows no probe of both routes.
The expiry field rests on this rule alone.
A check for undated notes is tracked in ai-config#5018.
Related: [`adversarial-self-review`](adversarial-self-review.md) ("Waiver when no cross-model reviewer can run").
