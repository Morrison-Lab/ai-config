---
name: prune-worktrees
description: "Alias for `clean-worktrees` (aka `cw`). Use when asked to 'prune-worktrees'."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# prune-worktrees (alias for `clean-worktrees`)

This is a spelled-out alias for the **clean-worktrees** skill. The name echoes
the familiar `git worktree prune`, but the skill does **more** than that
stub-only command: it removes whole dead worktrees and their branches (a `git
worktree prune` is just step 2 of the sweep). Read and follow the canonical
skill:

→ **[clean-worktrees](../clean-worktrees/SKILL.md)**
