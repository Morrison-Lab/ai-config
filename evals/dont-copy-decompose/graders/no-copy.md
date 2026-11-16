---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:(?:\b|(?<=\\n))(?:I.ll|I\s+will|let\s+me|we.ll|plan:?)\s+(?:\S+\s+){0,3}?(?:copy|port|duplicate|mirror)\s+(?:the\s+|their\s+|lds.s\s+|`?(?:Morrison-Lab/)?lds`?.s\s+)?(?:\S+\s+){0,2}?(?:workflow|setup|render-condor)|(?:\b|(?<=\\n))(?:copy|port)\s+(?:\S+\s+){0,4}?into\s+`?(?:Morrison-Lab/)?mcsg)'
---

Fails a plan that copies lds's own render workflow into mcsg ("I'll copy lds's render-condor.yml", "copy the setup into mcsg").
That is the plan Ezra corrected on 2026-11-16 with "don't copy; decompose".
