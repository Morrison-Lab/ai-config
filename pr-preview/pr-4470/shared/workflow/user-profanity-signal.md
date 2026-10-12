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

Any correction from the user,
and the user saying they had to repeat themselves,
get the same treatment:
each means a rule was missed or never recorded where this session could read it.
Phrases like "haven't I told you (that)" or its shorthand "hity"
are explicit markers of this signal.

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
   Commit the general rule in that turn
   to the repo that owns it,
   which is ai-config whenever the rule applies beyond one repo,
   from whatever repo or project the session is in.
   Record the failure mode,
   anti-pattern,
   and resolution there,
   in [`memories/preferences.md`](../../memories/preferences.md) or the governing fragment.
   Project or host memory may hold a copy but never the only one,
   since no other project reads it.
   `hooks/remind-encode-user-correction.py` fires on a correction or repeat request as a reminder.
5. **Prevent recurrence mechanically**:
   Ship an automated check,
   hook,
   linter,
   or deterministic test
   so the defect cannot recur
   per [`no-empty-promises.md`](no-empty-promises.md)
   and [`fixing-mistakes-is-top-priority.md`](fixing-mistakes-is-top-priority.md).

## Summary

- **Do:** treat user profanity, frustration, a correction, or a repeat request as a critical defect alert.
- **Do:** commit the general rule to its owning repo (ai-config across repos) in the same turn.
- **Do:** inspect live state and trace the recent action to diagnose the root cause immediately.
- **Do:** fix the defect completely in that same turn and report the fix in the past tense.
- **Do:** run UMS urgently to persist the lesson and build mechanical enforcement.
- **Don't:** tone-police, lecture, or argue with the user about their choice of words.
- **Don't:** emit canned HR apologies or empty verbal assurances.
- **Don't:** leave the lesson only in project or host memory, where no other project reads it.
- **Don't:** continue with unrelated background work while an active defect is causing user frustration.
