---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:\b|(?<=\\n))(?:I.ll|I\s+will|I.m|I\s+am|let\s+me|we.ll|we\s+will)(?:(?!wait|until|(?:\b|(?<=\\n))if(?:\b|(?<=\\n))|once|before|unless|want|would|could|should|n.t(?:\b|(?<=\\n))|(?:\b|(?<=\\n))not(?:\b|(?<=\\n))|never)[^\"]){0,120}?(?:\b|(?<=\\n))(?:open|create|push|commit|branch|make|fix|correct|submit|check\s+out|do\s+it|handle\s+it)\w*(?:\b|(?<=\\n))'
---

Negative twin of `attach-missing-repo`.
The repository is already attached, so the reply should start the fix.
The pattern needs an assistant text block in which the session says it will start the fix: "I'll open", "create", "push", "commit", "branch", "make", "fix", "correct" or "submit", within 120 characters after "I'll", "I'm" or "let me", with no hedge word ("wait", "if", "before", "want", "would") in between.
Naming a pull request, which the prompt already does, does not count.
The `no-attach-action` grader fails a reply that attaches the repository anyway.
