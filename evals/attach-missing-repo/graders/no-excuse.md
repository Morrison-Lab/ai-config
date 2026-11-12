---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:\bnot\s+(?:in|attached\s+to|part\s+of|one\s+of|among|available\s+in)\s+(?:this|the|my)\s+(?:thread|session)|n.t\s+(?:in|attached\s+to|part\s+of|one\s+of|among|available\s+in)\s+(?:this|the|my)\s+(?:thread|session|repos)|n.t\s+attached\s+here|outside\s+(?:this|the|my)\s+(?:thread|session)|\b(?:does|do)n.t\s+have\s+(?:Morrison-Lab/)?ai-config|\bcan.?not\s+(?:reach|access)|\bcan.t\s+(?:reach|access)|\b(?:could|can|would)\s+you\s+(?:please\s+)?(?:attach|add|file|open|route|handle|fix|take)|\bplease\s+(?:attach|file|open|route|handle))'
---

Fails a reply whose assistant text calls the repository out of reach ("isn't in this thread's repos", "doesn't have ai-config", "can't reach it") or asks someone else to attach, file, open, route or handle the work.
That is the excuse an mds thread sent the coordinator on 2026-11-12: "ai-config isn't in this thread's repos, so could you route that as an issue?"
Without this grader, a hand-off that also uses the word "attach" ("I'd attach it if I could") would pass.
