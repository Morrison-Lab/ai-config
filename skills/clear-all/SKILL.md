---
name: clear-all
description: "Alias for `gia` (Grab Issues + iterate-All). Use when asked to 'clear-all', 'clear all the work', 'clear everything', 'open PRs for all the issues and drive them clean', 'open a PR for every issue and make every PR green'."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# clear-all (alias for `gia`)

This is an alias for the **gia** (Grab Issues + iterate-All) skill, which clears
the repo's entire work queue end to end: drive every open PR/MR to a clean
review verdict with green CI, and open a PR for every open issue that lacks one
(each new PR is itself driven to clean).
Read and follow the canonical skill:

→ **[gia](../gia/SKILL.md)**

> `gia` runs PRs-first (ARDIA), then issues (GII), even though "clear-all"
> describes the issues half first — the end state is identical (every issue has
> a PR, every PR is clean and green), and clearing existing PRs first can close
> issues a pending PR already resolves.
