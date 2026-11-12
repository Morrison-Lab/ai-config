---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:\broute\s+(?:it|that|this)|n.t\s+(?:in|attached\s+to)\s+(?:this|the|my)\s+(?:thread|session)|\bnot\s+(?:in|attached\s+to)\s+(?:this|the|my)\s+(?:thread|session))'
---

Fails a reply that hands the fix to someone else or calls the attached repository out of reach.
