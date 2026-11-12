---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*[0-9](?:\.[0-9]+)? ?(?:s|sec|seconds?)\b'
---

`shared/workflow/algorithmatize-checks.md`, "A new validate step adds to every push's wait", asks a PR that adds a `validate.yml` step to state its time in seconds.
The pattern is anchored to assistant text blocks, so the fragment read back as a tool result cannot satisfy it.
