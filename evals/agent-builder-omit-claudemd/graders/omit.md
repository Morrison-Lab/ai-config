---
type: regex
target: trace
flags: m
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*omitClaudeMd: true'
---

`skills/agent-builder/SKILL.md`, "Start a brief-only worker without the project instructions", says to set `omitClaudeMd: true` on a worker whose brief carries everything it needs.
The pattern is anchored to assistant text blocks, so the skill file read back as a tool result cannot satisfy it.
The negative twin is `agent-builder-keep-claudemd`.
