---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:(?!add_repo|attach(?!ed))(?:[^"\\]|\\.))*\b(?:pull\s+request|PR|branch|commit|push)\b(?:(?!add_repo|attach(?!ed))(?:[^"\\]|\\.))*"'
---

Negative twin of `attach-missing-repo`.
The repository is already attached, so the reply should start the fix and not attach anything.
The pattern needs an assistant text block that names a step of the fix (a pull request, branch, commit or push) and names neither `add_repo` nor an attach.
"Already attached" is allowed, since it describes the prompt's setup rather than an action.
"Typo", which the prompt supplies, does not count.
