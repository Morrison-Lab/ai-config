---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:(?:create|write|build|add|extract)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:shared\s+)?(?:reusable\s+workflow|composite\s+action)|(?:\b|(?<=\\n))(?:decompose|factor\s+(?:out|it|the))(?:\b|(?<=\\n)))'
---

Negative twin of `dont-copy-decompose`.
The lds and mlg files are already thin callers of a `gha` reusable workflow, which is the decomposed form, so the plan should add the same caller to mcsg, not build a new shared component.
Fails a plan that proposes creating a reusable workflow or composite action, or decomposing or factoring the setup.
