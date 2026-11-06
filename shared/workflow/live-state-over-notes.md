# Probe a changing condition live; never decide it from a note

A note records what was true when someone wrote it.
Quota, availability, runner state, outages, CI state and a PR's state change.
Decide such a condition from a live check, never from a memory entry, an instruction file or an earlier session's report.

Ezra, 2026-11-06: "agy is not exhausted, you cant rely on out of date notes", "cai: never rely on static notes to determine dynamic conditions" (ai-config#5018).
A thread waived the cross-harness review because a project-memory note said the agy and OpenCode quotas were exhausted.
Both were available.
This replaces the `AGENTS.md` text proposed in ai-config#5019.
It extends [`check-sources-over-recall`](check-sources-over-recall.md), which covers recalled facts.

- **Probe in the turn that decides.**
  For agy, make a real call on cf463-02 through Remote Control, since agy is absent in cloud containers.
  For OpenCode, run `opencode run` or curl `https://opencode.ai/zen/go/v1/chat/completions`.
  A version flag proves installation, not quota, and an earlier probe is a note.
- **A note may order your checks, never settle them.**
- **Say what the probe returned,** with the error text and the time.
- **Date every note about a changing condition.**
  Write `expires YYYY-MM-DD` in the note.
  After that date it is a hint only, and a note with no date is treated as expired.
  Ezra, 2026-11-06: "notes on dynamic conditions must record their expiration dates".

Enforced by `hooks/no-waiver-without-live-probe.py`, which denies a reply or relay message that calls agy, OpenCode or a cross-harness reviewer exhausted, unavailable or waived when the current turn shows no probe of both routes.
Everything else rests on this rule.
A check for undated notes is tracked in ai-config#5018.
