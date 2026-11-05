# Announcing work and ending the turn is an empty promise

On 2026-11-05 a thread ended its turn on "I'll start with the equivalence-negation chapter in mcs" and never started it.
Ezra asked "why did you stop?" and "empty promise?".

The rule: do the announced work in the same turn, arm a trigger that carries the next step, or retract the sentence.
Phrasings the old guard missed were "I'll start with X" and "I'm on it".

`hooks/no-empty-promise.py` now matches both as debt promises, so they discharge only on a durable write or an armed firing.
`hooks/test-no-empty-promise.py` pins the cases.

Lesson from the review of ai-config#4985: the first version matched "I'll start by reading X" even when the Read followed, because the tests covered only the failing shape.
A pattern for common narration needs a negative test for the benign case (announcement, then the work) and an order condition, before the first push.
A new memory file also needs its row in `memories/MEMORY.md` (check tracked in ai-config#4987).
