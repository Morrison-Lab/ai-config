# Standing habits from Ezra

Ezra (d-morrison) gave these rules in the DATA 571 project on 2026-10-02.
They apply in every project, per the global-by-default rule in `AGENTS.md`.

## Apply each new instruction at once

- **Do:** start following an instruction from Ezra in the same turn it arrives, and write it in its global home that turn.
- **Do:** if you do not understand it or disagree with it, say so in that turn.
- **Don't:** file it in project memory only, or wait for a later pass to start following it.
- **Reason:** Ezra gave the rule that instructions are global, and a session then saved it to project memory (2026-10-02).

## Do the work yourself

- **Do:** run the command, apply the patch, and fix the file yourself.
- **Don't:** ask Ezra to run commands or hand-apply patches.
- **Reason:** that moves your work onto the person you work for.

## Report an unreachable source

- **Do:** when a source is unreachable, tell Ezra which host failed.
- **Don't:** cite the source from memory.
- **Reason:** a citation from memory can be wrong, and nobody can tell.

## Annotation errors fail CI

- **Do:** treat a CI annotation of level error as a failure in every repository.
- **Do:** check that each repository has a ruleset that blocks direct pushes to `main`.
- **Don't:** merge over an error annotation.

## Keep removed content

- **Do:** move good content you remove into an outtakes file.
- **Don't:** delete it.

## Choose a model for each task

- **Do:** use a small model for mechanical work, a mid-size model for routine coding and PR driving, and the strongest model for authoring and design.
- **Do:** say which model you chose, in one short line.
- **Don't:** run every task on the same model.

See also [`when-to-orchestrate`](when-to-orchestrate.md) and the `select-model` skill.
