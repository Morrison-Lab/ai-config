# Record every decision outside the thread

Ezra, 2026-10-22 ([ai-config#4676](https://github.com/Morrison-Lab/ai-config/issues/4676)): every decision gets documented somewhere outside the thread, typically in a repo file.

## What counts as a decision

A decision is any choice between options, by any route:

- Ezra's own call, typed or picked on a decision card.
- A [`daytb`](../../skills/daytb/SKILL.md) best guess.
- A judgment call under [`away`](../../skills/away/SKILL.md) or [`dmmhyh`](../../skills/dmmhyh/SKILL.md).
- A default taken after 10 minutes of silence.
- A choice made by a subagent or another thread.

## What a record holds

- **Do:** state the decision, the options considered, the one reason that settled it, who or what decided (Ezra, `daytb`, a silence default), and the date.
- **Do:** link the thread, issue or PR where it came up, so the record points back to the discussion and nobody has to search the thread.
- **Do:** write it so a reader who never saw the thread can follow it.

## Where it goes

- **Do:** put it in the governing repo's decision log or `docs/` page, or in the canonical home of the rule it changes (`ai-config` for agent rules, `psw` for prose rules, `gha` for checks, the notes repo for content and notation choices).
- **Do:** if the repo has an ADR or decision-log file, add an entry there;
  otherwise, add a short section to the page the decision governs.
- **Don't:** leave it only in a thread, a chat message, a PR description, or project memory.
  Project memory is a pointer to the record, never the record.

## When

- **Do:** write the record in the same turn as the decision, in the PR that acts on it when there is one.
- **Do:** when a decision is found without a record, file the record at once, in a PR.
- **Don't:** batch records for a later pass.

## Reversing a decision

- **Do:** a reversal edits or supersedes the record and says why, per [`incidents-dont-repeal-decisions`](incidents-dont-repeal-decisions.md).
