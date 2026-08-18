---
name: resync-branch
description: "Alias."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# resync-branch

This is a **synonym for [`sync-pr-branch`](../sync-pr-branch/SKILL.md)** — the
two are interchangeable. There is no separate behavior here.

**Do this:** read [sync-pr-branch](../sync-pr-branch/SKILL.md) and follow its
instructions exactly, against the current branch (or the branch the user
named). Everything that skill says — fetch origin, merge `origin/main`, merge
`origin/<current-branch>`, resolve conflicts, run the repo's pre-commit checks
(render / lint / spell), then push — applies unchanged.

Keep the logic only in `sync-pr-branch`; this file is just the `/resync-branch`
entry point so the names stay in sync.
