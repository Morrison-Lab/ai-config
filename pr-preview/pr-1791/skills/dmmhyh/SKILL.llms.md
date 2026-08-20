# dmmhyh – don’t make me hold your hand

A correction, not just a grant: the user is telling you that you’re asking for more guidance than the moment calls for – checking in, hedging with a question, or pausing for confirmation on something you had enough information to just decide. Three things happen when it fires: whatever is pending gets decided and acted on immediately, the threshold for asking at all moves up for the rest of the session, and the correction itself gets written down so it doesn’t have to be repeated in the next session.

That third part is what separates this from [`daytb`](../../skills/daytb/SKILL.llms.md). A session-scoped recalibration is exactly the kind of promise about your own future behavior that [`no-empty-promises`](../../shared/workflow/no-empty-promises.md) rules out unless it ships a mechanism in the same turn – “I’ll ask less going forward” is costless to say and evaporates with the session. The mechanism here is the memory write in step 4: it is not optional, and it is not “the same thing, later.”

## When this fires

- The bare or slashed keyword `dmmhyh`.
- The full phrase “don’t make me hold your hand” or close variants (“stop hand-holding”, “quit checking in”, “you don’t need to ask me that”, “you’re asking too much”, “just decide”, “figure it out yourself”).
- A pattern, not necessarily a single utterance: several small check-ins or hedged questions in a row on things that didn’t need one.

## What it grants

Three effects: one immediate, one standing for the session, one durable across sessions.

1.  **Resolve the pending item now**, using [`daytb`](../../skills/daytb/SKILL.llms.md)’s procedure: pick the option you would have recommended, act, and report in the past tense.
2.  **Recalibrate for the rest of the session.** Raise the bar for what counts as “worth asking about.” Use [`away`](../../skills/away/SKILL.llms.md)’s judgment-call vs. information-or-authorization split (its Scope and limits section) as the test: a judgment call – which approach, whether a finding matters, how to scope something – gets decided and reported, not asked. Only a genuine information-or-authorization gap (a fact only the user holds, or an action the safety rules require confirming) still stops for a question.
3.  **Persist the correction as feedback**, per step 4 below, so the next session starts already calibrated instead of relearning this from scratch.

Effects 2 and 3 are `dmmhyh`’s own contribution over plain `daytb`: `daytb` alone would only fix the one instance and leave both the in-session pattern and the cross-session recurrence untouched.

## What it does not grant

- **Not merge or destructive-action authority.** [`mwc`](../../skills/mwc/SKILL.llms.md) is the separate grant for that; `dmmhyh` doesn’t imply it.
- **Not the safety rules.** Everything in the system prompt’s action categories (destructive, explicit-permission-required) still applies.
- **Not permission to stop reporting.** The recalibration is about *asking* less, not *saying* less – keep narrating decisions as they’re made; a silent decision is indistinguishable from an ignored request.
- **Not a one-time apology.** Don’t just answer the triggering question and revert to the old asking frequency on the next one – the whole point is that the *next* several decisions get the same treatment, and that the pattern gets recorded so it doesn’t need re-teaching next time.

## Procedure

1.  **Name what triggered it.** State, in one clause, which question or hedge the user is reacting to – this confirms you understood the correction rather than just acknowledging it reflexively.
2.  **Decide and act on that item immediately**, per `daytb`’s procedure.
3.  **State the recalibration explicitly, once**: “noted – deciding more, asking less for the rest of this session” (or similar), so the shift is visible rather than assumed. For the remainder of the session, apply the away-style judgment-call test before drafting any question or hedge: if it’s a judgment call, decide; if it’s information or authorization only the user holds, ask – and say which bucket it’s in if it’s a close call, so the user can correct the calibration itself if you get it wrong.
4.  **Persist it – this step is mandatory, not optional.** A `dmmhyh` firing is a user correction under [`ums`](../../skills/ums/SKILL.llms.md)’s own trigger list (“A user correction is a mandatory immediate trigger”), so run its memory-write step now rather than only recalibrating in-session:
    - **Grep first** (`memories/preferences.md` if the working repo is `ai-config`, otherwise wherever this user’s cross-project preferences live) for an existing entry on over-asking/hand-holding. If one exists, extend it in place and note the recurrence with a date, per `ums`’s own dedupe rule – don’t add a sibling bullet.
    - If none exists, write one as a **feedback**-type entry: the specific thing you asked that didn’t need asking, **why** it didn’t need asking, and the Do/Don’t pair per [`CLAUDE.md`](../../CLAUDE.md)’s “Record both the pattern and the anti-pattern” – e.g. “Do: decide a reversible, in-scope judgment call without confirming. Don’t: pose a confirming question when you already have enough information to act.”
    - Route the destination the way `ums`/`config-ai` already do: a cross-project preference goes to `ai-config`’s `memories/preferences.md` (via `memorize` if the working repo already is `ai-config`, via `push-memory` otherwise); a preference that’s genuinely scoped to one project stays in that project’s own memory.
    - **On a third or later recorded occurrence of the same class of over-asking**, treat it as [`deterministic-tools`](../../shared/principles/deterministic-tools.md)’s third-occurrence bar: a prose rule that keeps needing repeating is a rule not holding, so route through [`config-ai`](../../skills/config-ai/SKILL.llms.md) to ask whether a decidable sub-pattern (e.g. a message that poses a confirming question and takes no other action) can become a hook, instead of only sharpening the wording again.
    - Don’t let this block the rest of the turn – fold it into whatever UMS pass is already owed, or open the memory PR the same way any other UMS-triggered write would (see `ums`’s own procedure for the branch/commit/push/PR mechanics). Report it in the past tense, not as an intention: “recorded” is a UMS pass that ran, not one that’s queued.
5.  **If the user pushes back that you’re now deciding things you shouldn’t have** (“that one needed a check”), don’t argue the general policy – narrow it for the rest of the session and note the exception, the same way `away`’s Scope and limits section honors a narrowed grant over the default. Note the narrowing in the same memory entry from step 4 if it reveals a boundary worth keeping (a class of question that genuinely should keep being asked).

## Relationship to other skills

- **[`daytb`](../../skills/daytb/SKILL.llms.md)** – supplies the immediate-decision mechanics `dmmhyh` uses for the triggering item. `daytb` alone doesn’t change future behavior in-session or across sessions; `dmmhyh` layers both on top.
- **[`away`](../../skills/away/SKILL.llms.md)** – supplies the judgment-call vs. information-or-authorization split `dmmhyh` uses to decide what still gets asked in-session. `away` presumes the user is *gone*; `dmmhyh` presumes the user is *here* and is telling you to ask them less anyway. Where they overlap (both raise the decide-vs-ask threshold), `away`’s scope is broader (it also drops the requirement to report before the session ends, keeps a decision log, etc.) – `dmmhyh` doesn’t imply those extras, and doesn’t need `back` to end, since it isn’t a suppression mode. Both can be active at once without conflict.
- **[`ums`](../../skills/ums/SKILL.llms.md)** – owns the mechanics step 4 invokes: the scan-categorize-write-commit procedure, the grep-before-write dedupe rule, and the recurrence-count convention `dmmhyh` reuses rather than duplicating.
- **[`config-ai`](../../skills/config-ai/SKILL.llms.md)** – the escalation path step 4 reaches for once a class of over-asking has recurred enough to justify more than a memory bullet (a hook, most likely).
- **[`no-empty-promises`](../../shared/workflow/no-empty-promises.md)** – the rule that makes step 4 mandatory rather than a nice-to-have: a session-only recalibration is a forward-looking commitment with no shipped mechanism, which is exactly what that rule forbids.
- **[`back`](../../skills/back/SKILL.llms.md)** – doesn’t revoke `dmmhyh`, since it never granted `away`’s suppression-of-questions mode. Revoking the recalibration is just the user asking more questions again or saying “ask me more” – no named counterpart needed, matching `daytb`’s no-counterpart design.
- **[`prompt-me`](../../skills/prompt-me/SKILL.llms.md) / [`prompt-me-all`](../../skills/prompt-me-all/SKILL.llms.md)** – the opposite direction, surfacing queued questions rather than suppressing new ones; unaffected by `dmmhyh`.

## Anti-patterns

- Treating it as only fixing the one question in front of you and reverting to the same asking frequency immediately after – that is `daytb` without the correction `dmmhyh` exists to make.
- Recalibrating in-session (step 3) but skipping the memory write (step 4) – an unrecorded correction is exactly the empty promise `no-empty-promises` rules out, and the next session starts back at zero.
- Escalating it into a full `away` grant on your own – `dmmhyh` doesn’t presume the user is unavailable, so keep reporting decisions as you make them rather than batching a decision log for later.
- Reading it as authorization for a destructive or explicit-permission action – it only changes the threshold for *judgment* calls.
- Going silent instead of narrating – the fix for over-asking is deciding more, not communicating less.
- Arguing the correction instead of applying it, when the user’s complaint is about a pattern visible in the transcript.
- Writing a vague memory entry (“be more decisive”) instead of the specific Do/Don’t pair with the triggering instance – `ums`’s own anti-patterns already rule this out; `dmmhyh` doesn’t get an exemption.

Back to top
