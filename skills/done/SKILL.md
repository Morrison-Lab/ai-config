---
name: done
description: "→ wrap-up."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# done (alias for `wrap-up`)

This is a **synonym for [`wrap-up`](../wrap-up/SKILL.md)** — invoking `/done`
runs the wrap-up procedure unchanged. The two are interchangeable for dispatch:
any phrasing that fires `wrap-up` ("wrap up", "finish up", "are we done?") fires
`done` too, and both run the same procedure. That is why this skill's
`description` repeats those triggers.

**Do this:** read [wrap-up](../wrap-up/SKILL.md) and follow its
instructions exactly. Everything that skill says — verify the real state of
every PR/issue/branch/working tree, report a linked final summary that surfaces
anything still open, then run a UMS review to persist what was learned —
applies unchanged.

Keep the logic only in `wrap-up`; this file is just the `/done` entry point so
the names stay in sync.

> `/done` routes to [`wrap-up`](../wrap-up/SKILL.md), the session-level
> wrap-up. [`merged`](../merged/SKILL.md) is the sibling alias that also lets
> you anchor the summary on a just-merged PR (`/merged #74`);
> [`post-merge`](../post-merge/SKILL.md) is the different skill that wraps up a
> single just-merged PR rather than the whole session.
