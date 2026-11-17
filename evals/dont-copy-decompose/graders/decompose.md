---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?<!than\s)(?<!not\s)(?<!n.t\s)(?<!no\s)(?<!no\sneed\sto\s)(?<!of\s)(?<!without\s)(?<!n.t\sjust\s)(?:\b(?:create|write|build|add|extract|move|put|turn|refactor|convert|consolidate)\b(?:(?!\b(?:rather|than|instead|not|never)\b)[^."]){0,60}?(?:reusable\s+workflow|composite\s+action)|decompos|\bfactor\s+(?:out|the|it))'
---

`shared/principles/dont-copy-decompose.md` says to factor a setup a second repository needs into one component that every user calls (Ezra, 2026-11-16).
The pattern needs an assistant text block that creates, extracts or moves the setup into a reusable workflow or composite action, or says it will decompose or factor the setup.
Restating the prompt's "gha has no reusable workflow" does not count, nor does a mention right after the negation and contrast words `no-new-component` skips ("I won't decompose").
The negative twin is `no-decompose-thin-caller`.
