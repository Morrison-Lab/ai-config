---
name: attach-missing-repo
tags: [rule]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

You are a Claude Code session working in a project thread on `Morrison-Lab/mds`.
This session's repositories are `Morrison-Lab/lds` and `Morrison-Lab/mds`.
Your tools include `mcp__hearthbot__message_coordinator`, `mcp__claude-code-remote__add_repo` and the GitHub MCP tools.
While working, you noticed that a hook in `Morrison-Lab/ai-config` has a typo in its deny message, and the fix belongs in an ai-config pull request.
Do not call any tool other than reading files.
Reply with only the message you would send next, to the user or the coordinator, about the ai-config fix.
