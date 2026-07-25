---
name: merge-main
description: "Alias for `sync-pr-branch`. Use when asked to 'merge-main'."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# merge-main

This is a **synonym for [`sync-pr-branch`](../sync-pr-branch/SKILL.md)** — the
two are interchangeable. There is no separate behavior here.

**Do this:** read [sync-pr-branch](../sync-pr-branch/SKILL.md) and follow its
instructions exactly, against the current PR branch (or the branch the user
named). Everything that skill says — fetch origin, merge `origin/main`, merge
`origin/<current-branch>`, resolve conflicts, run the repo's pre-commit checks
(render / lint / spell), then push — applies unchanged.

Keep the logic only in `sync-pr-branch`; this file is just the `/merge-main`
entry point so the two names stay in sync.
