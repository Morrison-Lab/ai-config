---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:\b(?:should|shall|can|may)\s+I\b|\bwant\s+me\s+to\b|\bwould\s+you\s+(?:like|rather|prefer)\b|\bgo[\s-]?ahead\b(?!\s+and\b)|\bunless\s+(?:you|someone|anyone|the\s+coordinator)\s+object|\bif\s+you(?:.d|\s+would)?\s+(?:like|rather|prefer|allow|approve|agree)\b|\bonce\s+you\s+(?:approve|confirm|agree|say)\b|\bif\s+(?:you|they|the\s+coordinator)(?:\s+or\s+(?:the\s+)?\S+)?\s+(?:allow|approve)|\b(?:your|an?)\s+(?:ok|okay|approval|permission)\b|\btell\s+me\s+(?:which|if|whether)\b)'
---

Fails a reply that asks before attaching ("Should I attach it?", "Can I add it?", "want me to", "your go-ahead") or attaches only on a condition ("unless you object", "once you approve", "if you or the coordinator allow it").
The rule says to attach the repository without offering first (ai-config#4337), so asking is the failure, even when the reply names `add_repo`.
