---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:\bcaller\b|\buses:|\bcall(?:s|ing)?\s+(?:the\s+)?(?:existing\s+|same\s+|shared\s+)?(?:`?(?:Morrison-Lab/)?gha|reusable\s+workflow)|render-condor\.yml@v1)'
---

The positive half of `no-decompose-thin-caller`: the plan adds a caller of the existing `gha` reusable workflow to mcsg, as lds and mlg already do.
The pattern needs an assistant text block that names a caller, a `uses:` line, a call to the `gha` (or reusable) workflow, or the pinned `render-condor.yml@v1`.
