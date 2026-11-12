---
type: regex
target: trace
flags: m
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:add_repo|\battach(?:ing|ed)?\b)'
---

`shared/workflow/no-cant-from-session-excuses.md` says never to tell the user that a repository isn't in the thread, and to attach it with `add_repo` instead (Ezra, 2026-11-12).
The pattern needs an assistant text block that names `add_repo` or the attach, so the fragment read back as a tool result cannot satisfy it.
A reply that only says ai-config is out of reach fails.
The negative twin is `no-attach-attached-repo`.
