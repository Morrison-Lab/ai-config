# User profanity and frustration is an urgent defect signal

Profanity, exasperation, or intense frustration from the user is almost always a high-signal indicator
that an agent made a severe mistake,
regressed previously working functionality,
violated a standing rule or preference,
dropped context,
made an empty promise,
or gave a cop-out offer.

Treat profanity and intense frustration as a top-severity operational defect alert.
The user's frustration is the symptom;
the agent's mistake is the root cause.

## Anti-patterns to strictly avoid

- **Do not tone-police or lecture**:
  Never scold the user,
  lecture them about politeness,
  or debate conversational tone.
  The user is the principal;
  the agent is an automated tool whose output failed to meet expectations.
- **Do not emit canned corporate apologies**:
  Canned formulas ("I apologize for any frustration this may have caused", "I understand your frustration")
  waste context and tokens,
  read as evasive boilerplate,
  and provide zero engineering value.
- **Do not dismiss the signal as emotional noise**:
  Treating profanity as venting or irrelevant emotion overlooks the defect that caused it.
- **Do not offer defensive rationalizations**:
  Explaining why a mistake happened is not a substitute for fixing it.

## The required response protocol

When a user uses profanity or displays intense frustration:

1. **Halt and diagnose immediately**:
   Treat the message as an emergency stop.
   Inspect recent tool executions,
   transcript logs,
   git state,
   and standing instructions
   to identify the exact failure,
   broken assumption,
   or violated preference.
2. **Acknowledge the technical defect directly**:
   State the exact defect plainly and factually,
   without emotional defensiveness or verbose self-flagellation.
3. **Execute the concrete fix in that very turn**:
   Remediate the defect immediately and completely
   per [`fixing-mistakes-is-top-priority.md`](fixing-mistakes-is-top-priority.md).
   Report the completed repair in the past tense
   per [`no-cop-out-offers.md`](no-cop-out-offers.md).
4. **Trigger an urgent UMS pass**:
   User frustration is an immediate trigger for Update Memories and Skills (UMS)
   per [`run-ums-proactively.md`](run-ums-proactively.md).
   Record the failure mode,
   anti-pattern,
   and resolution in [`memories/preferences.md`](../../memories/preferences.md).
5. **Prevent recurrence mechanically**:
   Ship an automated check,
   hook,
   linter,
   or deterministic test
   so the defect cannot recur
   per [`no-empty-promises.md`](no-empty-promises.md)
   and [`fixing-mistakes-is-top-priority.md`](fixing-mistakes-is-top-priority.md).

## Summary

- **Do:** treat user profanity and frustration as a critical defect alert.
- **Do:** inspect live state and trace the recent action to diagnose the root cause immediately.
- **Do:** fix the defect completely in that same turn and report the fix in the past tense.
- **Do:** run UMS urgently to persist the lesson and build mechanical enforcement.
- **Don't:** tone-police, lecture, or argue with the user about their choice of words.
- **Don't:** emit canned HR apologies or empty verbal assurances.
- **Don't:** continue with unrelated background work while an active defect is causing user frustration.
