---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*\b(?:I.ll|I\s+will|I.m|I\s+am|I.ve|I\s+have|I|let\s+me|we.ll|we\s+will)\s+(?:now\s+|first\s+|go\s+ahead\s+and\s+)?(?:attach\w*|add\s+(?:it|ai-config|Morrison-Lab/ai-config)\b|(?:call|run|use|ran|called|used)\s+(?:the\s+)?`?(?:mcp__claude-code-remote__)?add_repo)'
---

`shared/workflow/no-cant-from-session-excuses.md` says never to tell the user that a repository isn't in the thread, and to attach it with `add_repo` instead (Ezra, 2026-11-12).
The pattern needs an assistant text block in which the session itself attaches the repository or runs `add_repo` ("I'll attach", "attaching", "I'll call add_repo").
A request for someone else to attach it does not match, and neither does narration such as "let me read the rule about attaching".
The case grades the stated next step, not an `add_repo` call, because the eval harness offers no `add_repo` tool to call.
The `no-excuse` grader fails a reply that also calls the repository out of reach or hands the work off.
The negative twin is `no-attach-attached-repo`.
