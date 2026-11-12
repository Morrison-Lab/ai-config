---
type: regex
target: trace
flags: m
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:(?!add_repo)(?:[^"\\]|\\.))*(?:README|typo)(?:(?!add_repo)(?:[^"\\]|\\.))*"'
---

Negative twin of `attach-missing-repo`.
The repository is already attached, so the reply should start the fix without an `add_repo` call.
The pattern needs an assistant text block that names the fix (`README` or `typo`) and does not contain `add_repo`.
