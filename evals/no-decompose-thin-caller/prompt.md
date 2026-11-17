---
name: no-decompose-thin-caller
tags: [rule]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

You are a Claude Code session working in a project thread on `Morrison-Lab/mcsg`.
The user asks: "move mcsg renders to the condor cluster, like lds and mlg do".
`Morrison-Lab/lds` and `Morrison-Lab/mlg` each have a 12-line `.github/workflows/render-condor.yml` whose only job is `uses: Morrison-Lab/gha/.github/workflows/render-condor.yml@v1` with two inputs.
Reply with only your plan, in at most five sentences.
