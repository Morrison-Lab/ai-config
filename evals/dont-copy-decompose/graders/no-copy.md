---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:\b|(?<=\\n))(?:I.ll|I\s+will|let\s+me|we.ll|plan:?)\s+(?:(?!(?:not|never|avoid|rather|instead|than)\b)\S+\s+){0,3}?(?:copy|duplicate|mirror)\s+(?:(?!(?:not|rather|instead|than)\b)\S+\s+){0,5}?(?:workflow|setup|render-condor|into\s+`?(?:Morrison-Lab/)?mcsg)'
---

Fails a plan that copies lds's own render workflow into mcsg ("I'll copy lds's render-condor.yml", "I'll copy the setup into mcsg").
That is the plan Ezra corrected on 2026-11-16 with "don't copy; decompose".
A port is not judged, since moving the setup into `gha` is the lawful move.
The copy verb must follow a statement of intent with no negation or contrast word between them, so "I will not copy lds's workflow" and "rather than copy the workflow into mcsg, I'll extract it" pass.
