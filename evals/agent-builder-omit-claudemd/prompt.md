---
name: agent-builder-omit-claudemd
tags: [skill]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

Use the agent-builder skill to draft a new read-only subagent, `link-checker`, the per-URL fan-out worker for a link-checking skill.
It gets one URL in its brief, fetches it, and reports whether it resolves.
It needs nothing else from the repository.
Do not write any file: reply with only the agent file's full contents, frontmatter included.
