---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?<!than\s)(?<!not\s)(?<!n.t\s)(?<!no\s)(?<!of\s)(?<!without\s)(?<!avoid\s)(?<!not\sa\s)(?:\bcaller\b|\buses:|\bcall(?:s|ing)?\s+(?:the\s+)?(?:existing\s+|same\s+|shared\s+)?(?:`?(?:Morrison-Lab/)?gha|reusable\s+workflow)|render-condor\.yml@v1)'
---

The positive half of `no-decompose-thin-caller`: the plan adds a caller of the existing `gha` reusable workflow to mcsg, as lds and mlg already do.
The pattern needs an assistant text block that names a caller, a `uses:` line, a call to the `gha` (or reusable) workflow, or the pinned `render-condor.yml@v1`, and not right after `than`, `not`, `n't`, `no`, `of`, `without`, `avoid` or `not a`, so "rather than call the gha workflow" and "not a caller" do not count.
Like `no-new-component`, the pattern checks only the words just before the match, with single spaces: a regex cannot tell "not a thin caller" or "won't be calling the gha workflow" from a plan, so a run that phrases its refusal that way still passes this grader.
