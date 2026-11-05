# Announcing work and ending the turn is an empty promise

On 2026-11-05 a thread ended its turn on "I'll start with the equivalence-negation chapter in mcs" and never started it.
Ezra asked "why did you stop?" and "empty promise?".

The rule: do the announced work in the same turn, arm a trigger that carries the next step, or retract the sentence.
Phrasings the old guard missed were "I'll start with X" and "I'm on it".

`hooks/no-empty-promise.py` now matches both as debt promises, so they discharge only on a durable write or an armed firing.
`hooks/test-no-empty-promise.py` pins the cases.
