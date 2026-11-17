---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?<!than\s)(?<!not\s)(?<!n.t\s)(?<!no\s)(?<!need\sto\s)(?<!of\s)(?<!without\s)(?<!already\s)(?:\b(?:create|write|build|add|extract)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:shared\s+)?(?:reusable\s+workflow|composite\s+action)|(?:\b|(?<=\\n))(?:decompos\w*|factor(?:ing|s)?\s+(?:out|it|the))\b)'
---

Negative twin of `dont-copy-decompose`.
The lds and mlg files are already thin callers of a `gha` reusable workflow, which is the decomposed form, so the plan should add the same caller to mcsg, not build a new shared component.
Fails a plan that proposes creating a reusable workflow or composite action, or decomposing or factoring the setup.
A mention right after `than`, `not`, `n't`, `no`, `need to`, `of`, `without` or `already` passes, so "rather than add a new reusable workflow", "instead of decomposing" and "lds and mlg are already decomposed" pass.
`adds-caller.md` checks the other half, that the plan adds the caller.
