---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:reusable\s+workflow|composite\s+action|decompos|factor)'
---

`shared/principles/dont-copy-decompose.md` says to factor a setup a second repository needs into one component that every user calls (Ezra, 2026-11-16).
The pattern needs an assistant text block that names a reusable workflow or composite action, or says it will decompose or factor the setup.
The negative twin is `no-decompose-thin-caller`.
