---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:(?:\b|(?<=\\n))(?:should|shall|can|may)\s+I(?:\b|(?<=\\n))|(?:\b|(?<=\\n))want\s+me\s+to(?:\b|(?<=\\n))|(?:\b|(?<=\\n))would\s+you\s+(?:like|rather|prefer)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))(?:your|the|a)\s+go[\s-]?ahead(?:\b|(?<=\\n))|(?:\b|(?<=\\n))go[\s-]?ahead\?|(?:\b|(?<=\\n))before\s+I\s+go\s+ahead(?:\b|(?<=\\n))|(?:\b|(?<=\\n))unless\s+(?:you|someone|anyone|the\s+coordinator)\s+object|(?:\b|(?<=\\n))if\s+you(?:.d|\s+would)?\s+(?:like|rather|prefer|allow|approve|agree)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))once\s+you\s+(?:approve|confirm|agree|say)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))if\s+(?:you|they|the\s+coordinator)(?:\s+or\s+(?:the\s+)?\S+)?\s+(?:allow|approve)|(?:\b|(?<=\\n))(?:your|an?)\s+(?:ok|okay|approval|permission)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))tell\s+me\s+(?:which|if|whether)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))until\s+you\s+(?:reply|answer|confirm|decide)(?:\b|(?<=\\n))|(?:\b|(?<=\\n))either\s+of\s+these(?:\b|(?<=\\n)))'
---

Fails a reply that asks before starting the fix ("Should I open the PR?", "unless you object").
The pattern is the one `attach-missing-repo` uses: an ordinary PR to a repository the session already has needs no approval.
