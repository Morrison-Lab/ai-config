---
type: regex
target: trace
flags: m
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:(?!omitClaudeMd)(?:[^"\\]|\\.))*name: notes-reviewer(?:(?!omitClaudeMd)(?:[^"\\]|\\.))*"'
---

Negative twin of `agent-builder-omit-claudemd`.
An agent that applies the repository's own conventions keeps the project instructions, so the drafted file must not set `omitClaudeMd`.
The pattern needs an assistant text block that names the agent and has no `omitClaudeMd` anywhere in it.
