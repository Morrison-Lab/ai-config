# Commit, push, and PR any potentially-reusable work you produce

Potentially-reusable work produced incidentally in any medium must be committed,
pushed, and PRed into an owning repository.

When asked to implement, edit, or write up a change, the delivery cycle is clear.
This covers what you produce incidentally:
a script that computed a number, a derivation that settled a question,
a comparison that ruled an option out.
Nobody asked for it, so it never enters an explicit delivery cycle, and it risks dying with the container.

Code is the obvious case and the least of it.
**Math and prose are what get left behind**, because a derivation reads as the explanation of the work rather than an artifact of it --- as something you said rather than something you made.
Each is a document some repository should hold, not a paragraph in a chat log.

## The test is conjunctive

Commit it when reproducing it would cost more than a moment **and** something durable cites it, or will.
A fragment that fails either half stays a scratch file.

## Commit it into the repository that owns its subject

That is what makes it reviewable as a diff, runnable by the next reader, and versioned against the thing it describes.
A forge comment gives none of those, and the durability of a comment is what makes substituting one tempting.
Note what is *not* wrong with a comment: this corpus relies on issues as durable, discoverable records, and `issue-first` and `handoff` both say so.
A comment is a fine record of a finding and a poor home for the artifact behind it.

When no existing repository owns the subject, create one, per the directive below.
Its name, owner and visibility are the user's call rather than yours:
creating a repository is outward and effectively irreversible in those three, and a public repository holding unpublished work is a disclosure decision rather than a filing one.
`Gate external repository communication on membership` and `Default to action without asking` both bear on it.

## Re-run or re-derive the committed form

**Re-run or re-derive the committed form, and say in the commit message that it still supports what you published.**
Work gets tidied on the way into a repository, and a cleaned-up version that no longer reproduces the figures it backs is worse than none, because being committed lends it authority.

Three adjacent rules this one does not replace, cross-linked so a later dupe-check finds them:
`memories/preferences.md`'s rule that memories, skills and commands never stay local-only;
`CLAUDE.md`'s "Encoding reusable feedback into ai-config", which is its learning counterpart;
and [`report-mistakes-proactively`](report-mistakes-proactively.md), which governs filing the finding rather than committing the artifact.

- **Do:** commit and PR it in the same session that produced the claim it backs.
- **Do:** put it in the repository that owns its subject.
- **Do:** re-check the committed form against what you published, and say so in the commit message.
- **Don't:** leave it uncommitted because the deliverable it fed already shipped.
- **Don't:** leave it uncommitted on the grounds that no repository fits --- that is the case to create one for, not the case to skip.
- **Don't:** post it as a comment instead of committing it.
- **Don't:** commit a tidied version you have not re-checked.

See [`AGENTS.cases.md`](../../AGENTS.cases.md), "Commit, push, and PR any potentially-reusable work you produce" for the authentic directive and the serocalculator case.
