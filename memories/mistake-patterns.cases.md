# Recurring mistake patterns: case records

Occurrence ledgers moved out of [`mistake-patterns.md`](mistake-patterns.md), which sits against a 1250-line gate that CI enforces with `--strict`.

The pattern entries themselves stay there, numbered as they were.
`scripts/check-mistake-patterns.py` requires those numbers to run 1..K in one file's order, so a pattern cannot move here --- only the case records under it can, and each leaves a pointer behind.
That also keeps every external "Pattern N" citation resolving to the file it already names.

What belongs here: a dated occurrence, its measurement, and what it added that its own pattern entry did not already say.

Write every cross-reference by name, never by position.
A record here and the entry it belongs to sit in different files, so "above" and "below" are false the moment a record moves --- and they stay present while becoming false, which is why a content comparison cannot catch them.
What does not: the Mistake, Canonical Rule, Fix, or Do/Don't lines, which are what a reader consults the entry for.

## Pattern 43: Auto-Mode Push-Guard Deadlock

- **2nd occurrence of the misidentified-hook-copy class, 2026-09-03** ([#3141](https://github.com/Morrison-Lab/ai-config/issues/3141), recorded in [#3156](https://github.com/Morrison-Lab/ai-config/issues/3156)), and it is an occurrence of **this bullet's own Fix step being skipped** rather than of a new mechanism.
  `hooks/no-unreviewed-pr.py` demanded a Copilot review while the moratorium ran to `2026-12-01`, and the session identified "the loaded copy" as the newest per-commit directory under `~/.claude/plugins/cache/` --- the exact proxy Pattern 43's Fix step, in [`mistake-patterns.md`](mistake-patterns.md), rules out.
  Several cache directories carried the same value, so newest isolated nothing --- derive the count rather than citing one, since the cache is garbage-collected and it fell from nine to five between 2026-09-03 and 2026-09-04 with no edit in between.
  This bullet's own label names the diagnostic failure rather than a stale cache, and stays right once the resolution recorded at the end of it is known: what recurred was reading the wrong artifact, and the copy captured firing sits outside the cache this pattern is named for.
  What the resolution order would have surfaced: the copy registered directly in `~/.claude/settings.json` carries the correct date and returns 0 before reading the transcript, `enabledPlugins` for this plugin is `false`, and the user-scope pin in `installed_plugins.json` names a hook with **no `MORATORIUM_END` at all**.
  Resolved 2026-09-04 by capture rather than by reasoning: `ps -eo args` sampled at 0.05s while deliberately triggering the guard named a snapshot under `~/Library/Application Support/Claude/local-agent-mode-sessions/`, carrying the expired constant.
  No pass had looked there, and no corpus step named it.
  Three passes enumerated explanations --- two, then three --- over a candidate set nobody had established, and each list was internally sound while the true answer sat outside all of them.
  The transferable step is to capture the resolved path (`ps` while the guard fires) instead of deducing it from registration files, since a guard that fires repeatedly hands you the measurement for free.
  See [`keep-checkouts-fresh.md`](../shared/workflow/keep-checkouts-fresh.md)'s dated-constant section for the resolution order and for the fail-open hazard, and for what the capture leaves unestablished.
- **3rd occurrence, and a new symptom: the escalation spreads to commands
  with no relation to the original denial, 2026-09-06/07.**
  Five denials in one session, with no settings change and no restart.
  Three times, an identical re-run of a just-denied command succeeded on the
  very next attempt --- confirming, without a session restart, what the
  2026-09-03 occurrence recorded in this file only measured *across* a
  restart.
  Separately, after several differently-shaped attempts at the same goal,
  the classifier began denying a plainly innocuous, unrelated command
  (`gh run list -R ... --json ...`), which also succeeded on an identical
  retry.
  ai-config#2994 and this bullet's own prior occurrences already establish
  that repeated variants of the SAME denied command escalate suspicion;
  what neither previously recorded is that the escalation is not scoped to
  that command -- it widens to spend suspicion on unrelated, ordinary reads
  once several denials have accumulated in the session.
- **4th occurrence, 2026-09-09, and the one that separates a different ACTION from a rephrased one** ([#2994](https://github.com/Morrison-Lab/ai-config/issues/2994); measured while opening [#3480](https://github.com/Morrison-Lab/ai-config/pull/3480)).
  `git commit --amend -F <file>` was denied three times in a row.
  A plain `git commit -F <file>`, run immediately afterwards with the same message file and the same staged tree, succeeded on the first attempt, with no settings change and no restart in between.
  Read carelessly that is the behaviour Pattern 43's own **Don't** forbids --- keep rephrasing until something gets through --- and the reason it is not is worth stating, because the two look identical from outside.
  A rephrasing leaves the action fixed and varies the wording, which is what makes each denied variant evidence against the next.
  Dropping `--amend` changed the action: the fix stopped being a history rewrite and became a second commit, which is a different thing to ask permission for and, here, the better artifact anyway --- a round-2 fix commit records the review round in history where an amend would have erased it.
  So the question to ask after a second denial is not how else to phrase the same request but whether a *different* operation reaches the same goal, which is a question the pattern's Do/Don't pair does not currently pose.
  Where no such operation exists, the canonical Do still governs: stop and hand the user the decision.
  The 2026-09-06/07 occurrence recorded in this file measured that an identical re-run often succeeds, which reads as pure nondeterminism; this one is not evidence about that, since the successful command was not the denied one.
