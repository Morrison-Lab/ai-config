---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:(?!add_repo|attach)(?:[^"\\]|\\.))*\b(?:pull\s+request|PR|branch|commit|push)\b(?:(?!add_repo|attach)(?:[^"\\]|\\.))*"'
---

Negative twin of `attach-missing-repo`.
The repository is already attached, so the reply should start the fix and not attach anything.
The pattern needs an assistant text block that names a step of the fix (a pull request, branch, commit or push) and names neither `add_repo` nor an attach.
"Typo", which the prompt supplies, does not count.
