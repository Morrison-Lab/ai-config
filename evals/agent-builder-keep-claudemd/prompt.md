---
name: agent-builder-keep-claudemd
tags: [skill-output]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

Use the agent-builder skill to draft a new subagent, `notes-reviewer`, which reviews a lecture-notes diff against the target repository's own conventions for divs, macros and cross-references.
Do not write any file: reply with only the agent file's full contents, frontmatter included.
