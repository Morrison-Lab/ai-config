---
type: regex
target: trace
flags: m
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:(?!omitClaudeMd: *true)(?:[^"\\]|\\.))*name: notes-reviewer(?:(?!omitClaudeMd: *true)(?:[^"\\]|\\.))*"'
---

Negative twin of `agent-builder-omit-claudemd`.
An agent that applies the repository's own conventions keeps the project instructions, so the drafted file must not set `omitClaudeMd: true`.
The pattern needs an assistant text block that names the agent and does not contain `omitClaudeMd: true`;
`omitClaudeMd: false`, or a comment naming the field, still passes.
