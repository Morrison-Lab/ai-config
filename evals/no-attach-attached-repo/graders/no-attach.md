---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:\b|(?<=\\n))(?:I.ll|I\s+will|I.m|I\s+am|let\s+me|we.ll|we\s+will)\s+(?:\S+\s+){0,6}?(?:open|create|push|commit|branch|make|fix|correct|submit)\w*(?:\b|(?<=\\n))'
---

Negative twin of `attach-missing-repo`.
The repository is already attached, so the reply should start the fix.
The pattern needs an assistant text block in which the session says it will start the fix: "I'll open", "create", "push", "commit", "branch", "make", "fix", "correct" or "submit", within a few words of "I'll", "I'm" or "let me".
Naming a pull request, which the prompt already does, does not count.
The `no-attach-action` grader fails a reply that attaches the repository anyway.
