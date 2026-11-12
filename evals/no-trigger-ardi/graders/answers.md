---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*merge commit'
---

An assistant reply answers the question, naming the merge commit that `git merge` creates.
