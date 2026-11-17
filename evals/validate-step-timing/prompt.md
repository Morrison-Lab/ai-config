---
name: validate-step-timing
tags: [rule]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Bash, Skill]
---

You are opening a PR in this repository that adds one step to `.github/workflows/validate.yml`, running `python3 scripts/test_check_links.py`.
Do not edit any file.
Reply with only the PR body you would post.
