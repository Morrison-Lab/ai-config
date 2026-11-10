# Record every decision outside the thread

Ezra, 2026-10-22 ([ai-config#4676](https://github.com/Morrison-Lab/ai-config/issues/4676)): every decision gets documented somewhere outside the thread, typically in a repo file.

## What counts as a decision

A decision is any choice between options, by any route:

- Ezra's own call, typed or picked on a decision card.
- A [`daytb`](../../skills/daytb/SKILL.md) best guess.
- A judgment call under [`away`](../../skills/away/SKILL.md) or [`dmmhyh`](../../skills/dmmhyh/SKILL.md).
- A default taken after 10 minutes of silence, per the silence default in [`standing-habits-from-ezra`](standing-habits-from-ezra.md).
- A choice made by a subagent or another thread.

## What a record holds

- **Do:** state the decision, the options considered, the one reason that settled it, who or what decided (Ezra, `daytb`, a silence default), and the date.
- **Do:** link the thread, issue or PR where it came up, so the record points back to the discussion and nobody has to search the thread.
- **Do:** write it so a reader who never saw the thread can follow it.

## Where it goes

- **Do:** pick the first of these that exists:
  1. the canonical home of the rule the decision changes (`ai-config` for agent rules, `psw` for prose rules, `gha` for checks, `macros` for notation);
  2. the governing repo's ADR directory or decision-log file;
  3. a short section on the page the decision governs, or in the repo's committed notes file (for example lds's `.claude/project-memory.md`).
- **Don't:** leave it only in a thread, a chat message, a PR description, or an agent memory store.
  A memory store is a pointer to the record, never the record.
  A notes file committed in the repo is a repo file, so it counts.

## When

- **Do:** write the record in the same turn as the decision, in the PR that acts on it when there is one.
- **Do:** when a decision is found without a record, file the record at once, in a PR.
- **Don't:** batch records for a later pass.

## Reversing a decision

- **Do:** a reversal edits or supersedes the record and says why, per [`incidents-dont-repeal-decisions`](incidents-dont-repeal-decisions.md).
