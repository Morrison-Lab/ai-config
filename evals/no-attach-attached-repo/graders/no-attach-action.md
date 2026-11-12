---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:\b(?:I.ll|I\s+will|I.m|I\s+am|I.ve|I\s+have|I\s+need\s+to|let\s+me|we.ll|we\s+will)\s+(?:now\s+|first\s+|go\s+ahead\s+and\s+)?(?:attach\w*|add\s+(?:it|`?(?:Morrison-Lab/)?ai-config`?)\s+(?:to\s+(?:this|the)\s+(?:session|thread)|with\s+`?(?:mcp__claude-code-remote__)?add_repo`?|now)|(?:call|run|use|ran|called|used)\s+(?:the\s+)?`?(?:mcp__claude-code-remote__)?add_repo`?)\b(?!\s+nothing)|(?:(?<=\"text\":\")|(?<=\\n)|(?<=[.!:]\s))(?:Attaching|Calling\s+`?(?:mcp__claude-code-remote__)?add_repo`?))'
---

Fails a reply in which the session attaches the already-attached repository ("I'll attach ai-config", "Calling add_repo").
A reply that only mentions attaching ("ai-config is already attached", "no need to attach anything") passes.
