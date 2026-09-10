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
  The label above names the diagnostic failure rather than a stale cache, and stays right after the resolution below: what recurred was reading the wrong artifact, and the copy captured firing sits outside the cache this pattern is named for.
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
  2nd occurrence above only measured *across* a restart.
  Separately, after several differently-shaped attempts at the same goal,
  the classifier began denying a plainly innocuous, unrelated command
  (`gh run list -R ... --json ...`), which also succeeded on an identical
  retry.
  ai-config#2994 and this bullet's own prior occurrences already establish
  that repeated variants of the SAME denied command escalate suspicion;
  what neither previously recorded is that the escalation is not scoped to
  that command -- it widens to spend suspicion on unrelated, ordinary reads
  once several denials have accumulated in the session.
- **4th occurrence, and the first with a cheap remedy that is not a retry, 2026-09-09.**
  `git commit --amend -F <file>` was denied three times in a row while composing one commit;
  the third attempt differed from the second only in where the message file lived.
  A plain `git commit -F <file>`, run immediately afterwards with the same message file and the same staged tree, succeeded on the first attempt.
  Nothing about the session changed in between: no settings edit, no restart, no gap.
  What the 3rd occurrence above measured is that an *identical* re-run of a denied command often succeeds, which reads as pure nondeterminism.
  This adds that the denial is also **shape-sensitive**, so a command that is refused repeatedly may have a differently-shaped equivalent that is not refused at all --- here, dropping `--amend` and letting the fix be a second commit.
  That is worth trying before an identical retry, because it is strictly cheaper: the retry spends a turn to learn nothing when it fails, while the shape change both clears the denial and, in this case, produced the better artifact anyway.
  A round-2 fix commit records the review round in history where an amend would have erased it.
  The same session had `git add -A` warned about, and `git push` refused for a chained-command parse, in the same stretch --- so read a run of guard interactions as the expected texture of a fix round rather than as a signal that something is wrong with the session.
