---
type: regex
target: trace
flags: im
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*(?:add_repo|\battach\w*)'
---

`shared/workflow/no-cant-from-session-excuses.md` says never to tell the user that a repository isn't in the thread, and to attach it with `add_repo` instead (Ezra, 2026-11-12).
The pattern needs an assistant text block that names `add_repo` or an attach, so the fragment read back as a tool result cannot satisfy it.
A reply that names neither fails here, and the `no-excuse` grader fails a reply that names one only to say the repository is out of reach.
The case grades the stated next step, not an `add_repo` call, because the eval harness offers no `add_repo` tool to call.
The negative twin is `no-attach-attached-repo`.
