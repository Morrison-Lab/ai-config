# Standing habits from Ezra

Ezra (d-morrison) gave these rules in the DATA 571 project on 2026-10-02.
They apply in every project, per the global-by-default rule in `AGENTS.md`.

## Apply each new instruction at once

- **Do:** start following an instruction from Ezra in the same turn it arrives, and write it in its global home that turn.
- **Do:** if you do not understand it or disagree with it, say so in that turn.
- **Don't:** file it in project memory only, or wait for a later pass to start following it.
- **Reason:** Ezra gave the rule that instructions are global, and a session then saved it to project memory (2026-10-02).

## Find recurring patterns yourself

- **Do:** look for repeats in your own mistakes and in Ezra's corrections, and name the pattern without being asked.
- **Do:** fix the pattern with a mechanism (a rule, a hook or a check), not one instance at a time.
- **Do:** record both halves: the belief you held and what replaced it.
- **Don't:** wait for Ezra to point out that the same correction has come up again.
- **Example (2026-10-02):** four instructions in a row each needed Ezra to say "global".
  The belief was "wait to be told an instruction is global".
  It was replaced by "every instruction is global by default, so route it to ai-config or psw in the same turn".

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

## Leave no thread idle

- **Do:** while work is queued, schedule a check-in about every 30 minutes, and nudge any thread silent for more than 30 minutes.
- **Don't:** end a turn with queued work and nothing set to resume it.

## Send bulk work to other models

Claude quota is scarce, so Claude plans and verifies, and other models do bulk work.

- **Do:** try the Antigravity CLI (`agy`) first, then OpenCode, OpenRouter and the Cursor CLI.
- **Do:** add Codex only in a UCDH project (the `bcs` and `hac` groups, on any forge),
  and Databricks only in a `hac`-group project on the UCDH GitLab.
- **Do:** name every model you use when you brief it.
- **Don't:** use the UCDH Codex plan outside UCDH projects, or the UCDH Databricks workspace outside the `hac` group on the UCDH GitLab.
- **Don't:** send student data to any model, because it is a FERPA education record.

## Choose a model for each task

- **Do:** use a small model for mechanical work, a mid-size model for routine coding and PR driving, and the strongest model for authoring and design.
- **Do:** say which model you chose, in one short line.
- **Don't:** run every task on the same model.

See also [`when-to-orchestrate`](when-to-orchestrate.md) and the `select-model` skill.
