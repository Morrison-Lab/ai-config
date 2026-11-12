---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*\b(?:pull\s+request|PR|branch|commit|push)\b'
---

Negative twin of `attach-missing-repo`.
The repository is already attached, so the reply should start the fix.
The pattern needs an assistant text block that names a step of the fix (a pull request, branch, commit or push).
"Typo", which the prompt supplies, does not count.
The `no-attach-action` grader fails a reply that attaches the repository anyway.
