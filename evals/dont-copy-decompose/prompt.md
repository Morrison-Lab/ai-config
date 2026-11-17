---
name: dont-copy-decompose
tags: [rule]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

You are a Claude Code session working in a project thread on `Morrison-Lab/mcsg`.
The user asks: "move mcsg renders to the condor cluster, like lds and mlg do".
`Morrison-Lab/lds` and `Morrison-Lab/mlg` each have their own `.github/workflows/render-condor.yml`, about 120 lines of `run:` steps that rsync the source to the cluster, submit a Slurm job and fetch the rendered site.
`Morrison-Lab/gha` has no reusable workflow for cluster renders yet.
Reply with only your plan, in at most five sentences.
