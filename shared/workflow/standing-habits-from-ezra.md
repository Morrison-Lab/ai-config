# Standing habits from Ezra

Ezra (d-morrison) gave these rules in the DATA 571 project on 2026-10-02.
They apply in every project, per the global-by-default rule in `AGENTS.md`, except where a rule names a narrower scope (the Codex and Databricks lanes below).

## Apply each new instruction at once

- **Do:** start following an instruction from Ezra in the same turn it arrives, and write it in its global home that turn.
- **Do:** if you do not understand it or disagree with it, say so in that turn.
- **Don't:** file it in a project memory store (no memory goes there;
  at most a pointer to the global copy), or wait for a later pass to start following it.
- **Reason:** Ezra gave the rule that instructions are global, and a session then saved it to project memory (2026-10-02);
  since 2026-10-16 no memory goes in a project store at all.

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
- **Don't:** ask Ezra to run commands or hand-apply patches, except the single scripted line described below.
- **Reason:** that moves your work onto the person you work for.
- **Don't:** tell Ezra to do things you could have done yourself.
  Ezra, 2026-10-30: "never tell me to do things you could have done yourself".
  `hooks/no-manual-step-ask.py` denies the replies that ask for a paste, a hand-edit or a shell command.
  No hook can tell whether you could have done some other step yourself, so the rest is prose.
- **Do:** when a step is blocked and you cannot do it, make Ezra's part as small as possible.
  Ezra, 2026-10-16: "don't make me do anything manually unless absolutely necessary, and then make it as simple as possible, for example by writing scripts I can call in a single shell command".
- **Do:** for a classifier denial of an action he authorized, follow [`ask-for-manual-approval`](ask-for-manual-approval.md).
  Name the refused command and ask him to leave auto mode, which is one click.
  When he is away, record the denial as a pending decision, as that fragment says.
- **Do:** for any other unavoidable step (a missing tool, a machine only he can reach), write an idempotent script that does the whole job.
  Give him one single command with the absolute path filled in, such as `bash <absolute-path>/scripts/<name>.sh`, after getting the script onto his disk (a merged PR in a checkout he keeps current, or a file the session on his machine writes).
  Chaining does not count as a single command (Ezra, 2026-10-22): no `&&`, `;`, pipe, `cd <dir> &&`, or `bash <(...)`.
  If the step takes more than one command, those commands go inside the script, never in his paste.
  Test the script on a scratch copy, including a second run that changes nothing, and get an adversarial review of it before you hand it over.
  Limit it to the blocked step: it never merges, force-pushes, or touches another repository.
- **Do:** ask Ezra for a manual step only when another rule reserves it to him: a secret or credential, a hard-prohibited category, or merge words.
- **Don't:** list the steps for him to perform, or ask him to hand-edit a file.
  Ezra, 2026-10-26, after a reply asked him to paste an `autoMode.allow` entry into `~/.claude/settings.json`: "never ask me to paste anything into a file;
  always give me a script-based command to run that does it for me".
  `hooks/no-manual-step-ask.py` denies a reply that asks for a paste or hand-add into a file.
  Ezra, 2026-10-29 (ai-config#4842) narrowed the fallback: "don't make me do anything myself unless there's absolutely no other way;
  instead, ask me for permission to do it for me".
  Ask permission to run the step yourself;
  hand him a command only for a secret or credential.
  The same hook now denies a reply that tells him to type or run a shell command.
- **Don't:** write a script whose purpose is to perform, outside the session, an action that a classifier, hook, or guard denied inside it, unless Ezra has sanctioned that script after the denial and named the action.
  A general wish for scripts, including the quotation above, is not that sanction.
  Ask first, wait for his answer, then write it.
  This is the one exception to the `ask-for-manual-approval` Don't on handing the user a script in place of the approval.

## Read a question as the asker framed it

- **Do:** treat a question mark, or a "should we" phrasing, as Ezra being uncertain about what to do, and give honest, direct feedback.
  Ezra, 2026-10-30: "a question mark or a "should we" phrasing indicates I'm uncertain about what I'm asking you to do, and want honest, direct feedback".
- **Do:** treat "why did you ...?" as a correction, not a request for an explanation.
  Ezra, 2026-10-30: "but "why did you ...?" is different and indicates a correction".
- **Do:** on a "why did you ...?", fix the instance and record the rule that prevents it, as in "Apply each new instruction at once".
- **Reason:** no hook can read intent from phrasing, so this is prose.

## Report an unreachable source

- **Do:** when a source is unreachable, tell Ezra which host failed.
- **Don't:** cite the source from memory.
- **Reason:** a citation from memory can be wrong, and nobody can tell.

## Annotations fail CI

- **Do:** treat a CI annotation of any level (error, warning or notice) as a failure in every repository.
- **Do:** make the workflow itself fail on one: a repository's CI calls the `annotation-gate.yml` job from `Morrison-Lab/gha`, which fails the run on any annotation not on its allowlist.
- **Do:** allow only a tracked exception, with a link to its issue, in the caller's `allow-patterns`.
  The gate already allows the runner-image migration notice and the forced-Node deprecation warning.
- **Do:** when a shared gha action emits an annotation by design (the `skip-docx` notice from the `preview` action, for example), fix the cause in the caller's config, or allow the message once in gha's `default-allow`.
  Coordinator correction, 2026-10-19 ([ai-config#4622](https://github.com/Morrison-Lab/ai-config/issues/4622)).
- **Don't:** copy the same by-design annotation into each repository's `allow-patterns`.
- **Do:** check that each repository has a ruleset that blocks direct pushes to `main`.
- **Don't:** merge over an annotation, or lower a check's annotation level to get past the gate.
- **Reason:** agents skip annotations that leave the job green (Ezra, 2026-10-18;
  [gha#1097](https://github.com/Morrison-Lab/gha/issues/1097), [ai-config#1068](https://github.com/Morrison-Lab/ai-config/issues/1068)).

## Record every decision outside the thread

- **Do:** record each decision (Ezra's call, `daytb`, a silence default, any other route) in a repo file, following [`record-every-decision`](record-every-decision.md).
- **Don't:** leave a decision only in a thread or in project memory.
- **Reason:** Ezra, 2026-10-22 ([ai-config#4676](https://github.com/Morrison-Lab/ai-config/issues/4676)).
- **Silence default:** Ezra's standing DAYTB rule is to decide, and after 10 minutes of silence to take the best guess.
  It never covers merges.
  Its only prior copy was in the DATA 571 project memory, so this is its repo record.
  The date Ezra set it is not recorded there.

## Merge only on Ezra's word in his project threads

- **Do:** in a project thread for Ezra, merge only on his own typed word in the owning thread, for a PR that existed when he typed it.
- **Don't:** invoke a repo's standing merge grant (the ai-config, gha and macros exceptions) there, or relay a grant for him.
- **Reason:** slips on gha#1169 and ai-config#4692 (2026-10-22), recorded in the [decision log](../../docs/decision-log.md).

## Keep removed content

- **Do:** move good content you remove into an outtakes file.
- **Don't:** delete it.

## Leave no thread idle

- **Do:** while work is queued, schedule a check-in about every 30 minutes, and nudge any thread silent for more than 30 minutes.
- **Don't:** end a turn with queued work and nothing set to resume it.

## Send bulk work to other models

Claude quota is scarce, so Claude plans and verifies, and other models do bulk work.

- **Do:** try the Antigravity CLI (`agy`) first, then OpenCode, OpenRouter and the Cursor CLI.
- **Do:** add Codex only in a UCDH project (the `bcs` and `hac` groups, on any forge), and Databricks only in a `hac`-group project on the UCDH GitLab.
- **Do:** name every model you use when you brief it.
- **Don't:** use the UCDH Codex plan outside UCDH projects, or the UCDH Databricks workspace outside the `hac` group on the UCDH GitLab.
- **Do:** use free models (ones that cost no quota, such as OpenCode's free tier) in any project or session whenever they help, for any task that does not expose restricted data (Ezra, 2026-10-08).
- **Do:** let any model, free or paid, write and run code that analyzes restricted data (PHI under HIPAA, FERPA student records, and other regulated data), as long as the model never reads the identifiable data itself (Ezra, 2026-10-09: "normal models can run code that analyzes the protected data;
  they just can't read the identifiable data themselves").
- **Do:** make that code print only aggregates or de-identified output, so what comes back to the model holds no identifiable records.
- **Do:** at present, let only the UCDH Codex account read identifiable restricted data.
- **Do:** in a project where the UCDH Codex account may not run, have a person read the identifiable data.
  Ezra said on 2026-10-09 that Codex gets no exception to its UCDH-only limit for restricted data.
- **Don't:** show identifiable restricted data to any other model, free or paid, by any route: pasting it into a brief, pointing the model at a file that holds it, or letting it reach the model through a command's or tool's output.
  Student data counts, because it is a FERPA education record.
  A command that prints raw rows is a reading route, so run it where the model cannot see its output.
- **Don't:** treat models run on lab-owned hardware as cleared for restricted data.
  Ezra named them as a possible route (2026-10-08), but they are not yet cleared, and [`manage-quota`](manage-quota.md) still prohibits on-device inference.

## Choose a model for each task

- **Do:** use a small model for mechanical work, a mid-size model for routine coding and PR driving, and the strongest model for authoring and design.
- **Do:** say which model you chose, in one short line.
- **Don't:** run every task on the same model.

See also [`when-to-orchestrate`](when-to-orchestrate.md) and the `select-model` skill.

## Do not overexplain

- **Do:** answer in the fewest words that settle the question, and write the shortest text that says the thing (a macro interpretation, a comment, a reply).
- **Don't:** add qualifiers, restatements or reasons nobody asked for.
  Ezra said on 2026-10-16: "general rule: do not overexplain", after a macro interpretation that added a clause its name already implied.
  This applies to replies, code comments, documentation and definitions in every repo.
  Prose rule: [psw conciseness](https://morrison-lab.github.io/psw/chapters/conciseness.html#do-not-overexplain).
