# Recurring mistake patterns: case records

Occurrence ledgers moved out of [`mistake-patterns.md`](mistake-patterns.md), which sits against a 1250-line gate that CI enforces with `--strict`.

The pattern entries themselves stay there, numbered as they were.
`scripts/check-mistake-patterns.py` requires those numbers to run 1..K in one file's order, so a pattern cannot move here --- only the case records under it can, and each leaves a pointer behind.
That also keeps every external "Pattern N" citation resolving to the file it already names.

What belongs here: a dated occurrence, its measurement, and what it added that its own pattern entry did not already say.

Write every cross-reference by name, never by position.
A record here and the entry it belongs to sit in different files, so "above" and "below" are false the moment a record moves --- and they stay present while becoming false, which is why a content comparison cannot catch them.
What does not: the Mistake, Canonical Rule, Fix, or Do/Don't lines, which are what a reader consults the entry for.

## Pattern 15: Widening a Fail-Closed Instrument's Exemption Without a Base-Parity Proof

- **2nd occurrence of the class, 2026-08-28** (ai-config#2449 / PR #2515, after #2419 in [`mistake-patterns.md`](mistake-patterns.md)), and the near-miss Pattern 15's entry did not previously name: the base-parity proof WAS built, and was constructed over the wrong quantity.
  It compared what the two revisions *blanked* --- asking whether every extra-blanked character lay inside a code span the change exists to blank --- which cannot return non-zero for any implementation of that shape, because the extra-blanked set is the span set.
  It reported 0 while two real fail-opens were live, and was silent by construction about the passes running downstream of the blanking, where both lived.
  A parity proof is over ACCEPTANCE SETS --- which bodies each revision calls clean --- never over the transformation.
  The replacement instrument, `scripts/check-verdict-scan-parity.py`, demonstrates its own discrimination rather than asserting it --- but only half of that demonstration is reproducible from `main`.
  The `0` for the shipped design re-runs from any clone.
  The 3,924 / 108 / 270 / non-zero off-axis figures were taken against the four designs rejected on the PR branch, which the squash merge as `07847b9` left off `main`;
  recover them with `git fetch origin 'refs/pull/2515/head:refs/remotes/pr/2515'` (`c7ff646`, `4f9d3fc`, `68a14b9`, `a3251bf`) rather than treating them as lost.
  Canonical rule for the general shape: [`verify-the-right-artifact.md`](../shared/workflow/verify-the-right-artifact.md)'s "what a change TRANSFORMS, standing in for what it CONCLUDES".

## Pattern 16: Same-Vendor Subagent Fallback When a Reachable CLI Would Give True Independence

- **2nd occurrence, 2026-08-29** ([ucdavis/hac.it#9](https://github.com/ucdavis/hac.it/pull/9), a docs PR): same shape, one step later.
  `adversarial-reviewer` was unregistered in this Claude Code CLI session (as opposed to Cursor Cloud, where it is registered), so a same-vendor `general-purpose` subagent was dispatched as the substitute reviewer and the PR was pushed on that verdict alone --- with [`self-review-fallback.md`](../shared/workflow/self-review-fallback.md)'s cross-vendor section already loaded in context and not applied.
  The user corrected it directly: "you should have run adv without me having to ask."
  A subsequent `adv --engine cursor` pass produced a genuinely independent verdict (Ready for merge, several non-blocking nits the same-vendor pass had not surfaced) --- concrete evidence the cross-vendor pass adds real signal rather than ceremony, and a second data point toward this pattern's third-occurrence bar for a hook.

## Pattern 18: A Second Refuted Design Is a Prompt to Measure, Not to Design a Third

- **2nd occurrence, 2026-08-28** (ai-config#2449 / PR #2515, after #2409 in [`mistake-patterns.md`](mistake-patterns.md)), on the same module and with a second resolution direction worth adding: where each refuted design breaks a *different* consumer, the measurement to run is over the REPRESENTATION rather than over the failing input.
  Four designs widened what `strip_cited_finding_vocab` blanked, and no two of them failed the same way;
  between them they broke six distinct downstream passes --- anchored negation windows, a markedness check, a sentence-boundary gate, a findings-item tag, a bare-marker guard, and reviewer-identity extraction --- producing nine fail-opens on a fail-closed instrument across five adversarial rounds.
  The three counts are not a one-to-one mapping and should not be read as one: the fourth design alone broke several passes, and one broken pass can fail open on more than one shape.
  What matters is that the failures were *unrelated*, which makes them one fact restated four times rather than four bugs --- namely that many character-and-offset-sensitive consumers read the buffer being edited.
  The design that shipped leaves the scan byte-identical and carries a parallel citation mask, making the class unreachable rather than patched member by member, and giving parity by identity rather than by proof.
  Canonical rule: [`fail-fast.md`](../shared/principles/fail-fast.md)'s "Where many consumers key on a shared buffer, filter the matches rather than editing the buffer".
- **3rd occurrence, 2026-08-28** (ai-config#2538 / PR #2539, after #2409 in [`mistake-patterns.md`](mistake-patterns.md) and #2449), which is the same pattern run to its conclusion and worth recording for what finally stopped it.
  **Twelve** designs, **twelve** certification fail-opens on a fail-closed instrument, **none** caught by a green suite --- every one found by an adversarial round.
  The arc: classification on exclusions alone, then on the harness's `origin.kind` label, then per record, then per block, then per non-envelope region, then against a four-name tag list, then against a structural opener test.
  Each fix was refuted by a shape the previous design had not considered, and by round 9 the sequence had a second, subtler stage worth naming --- the parse was not removed, only moved from **grammar** (where do the delimiters balance) to **vocabulary** (is this name in my list), while the code claimed *"nothing is parsed"*.
  Two of the last three failures were regressions introduced by the fix for the one before, which is Pattern 18's own signal arriving at a higher rate.
  What ended it was abandoning the claim rather than narrowing it: the tool now reports every matching record with its provenance and decides nothing, so the class is unreachable rather than guarded --- the same resolution shape as the 2nd occurrence's parallel mask, one level up.
  A twelfth round then found the mirror failure the eleven had all missed, because every round had been hunting false positives: the tool was *under-reading* the corpus, and reported "no record contains it" over text the user had typed.
  Canonical rule: [`deterministic-tools.md`](../shared/principles/deterministic-tools.md)'s "An enumeration is still a parse", and the recurrence test one level up again --- when refutation recurs past the second design, ask whether the CLAIM is achievable rather than which discriminator to try next.
- **4th occurrence, 2026-08-30** (ai-config#2668, on the same module and citation-stripping machinery as the 2nd/3rd occurrences;
  open, with the driving session still pushing commits, at time of writing), the occurrence that names the axis the first three resolved by trial rather than by rule.
  As the driving session reported it, two separate discriminators in the same file failed open across a review series it logged at roughly sixteen adversarial rounds, and in both cases the fix it settled on was a change of KIND rather than a further narrowing of the same kind. (a) A guard deciding whether a negator scopes over a resolution went through four lexical designs in sequence --- a fixed glue whitelist, a bounded word run, a grammatical-role (preposition-governed) test, then a governed-and-clause-detached test --- and each admitted a fresh false-clean the next round found.
  The design the session settled on abandons the lexical proxy entirely: any negator earlier in the same sentence defeats the exemption, trading a fifth refinement for a documented, bounded over-flag --- the same trade [`learn-from-review-findings.md`](../shared/workflow/learn-from-review-findings.md) already names ("a bounded, nameable false positive beats a silent bypass, and both beat a heuristic nobody can characterize"). (b) A citation strip deciding whether a `(posted <timestamp>, verdict **X**)` aside was narration or a live statement used a positive attribution gate plus a closed vocabulary veto, and each round's re-raise arrived in a phrasing the vocabulary had not enumerated.
  The design the session settled on is a discriminator on a different axis: a structural gate that strips the citation only when the comment body states a verdict of its own, because a cited verdict overriding the reviewer's OWN stated verdict is the only thing the strip ever needed to protect against, and that test is blind to how the citation happens to be phrased. (As of this entry, `origin/fix/check-pr-fully-clean-posted-verdict-citation` --- distinct from `origin/main`, which has neither fix yet --- carries `_POSTED_VERDICT_CITATION`, a general "posted TS, verdict `**X**`" pattern rather than an enumerated word list;
  whether that pushed form is the closed-vocabulary design this entry describes being refuted, an intermediate step, or already the structural gate is not independently reconstructable from the two commits on the remote branch alone, so the round-by-round narrative above is the driving session's own account, not a re-derivation from this checkout.)
  The module carries a directly relevant caution already, in the docstring of `strip_cited_finding_vocab_with_mask` --- verified on both `origin/main` and the PR branch of `scripts/check-pr-fully-clean.py`, about 115 lines above where the PR branch's new citation regex lives in that same function: "the true discriminator...cannot be determined from text alone" (lines 761-763) and, of four earlier attempts at a sibling citation-scan, "every one of those was fail-open on a fail-closed instrument" (line 802).
  Per the driving session's account, that lesson did not travel to the vocabulary veto being written later in the same function.
  A principle stated in one part of a file and contradicted by practice in another part of the same file is itself a signal worth reading, independent of the round count.
  Canonical rule: not a wider or narrower version of the failing test, but a test on a different axis --- structural or positional (does the body carry its own verdict heading at all) rather than lexical (which words appear).
  See also [`learn-from-review-findings.md`](../shared/workflow/learn-from-review-findings.md)'s "A finding class that RECURS is evidence about your instrument, not about its threshold" section, which this occurrence specializes: the replacement axis, not just the recurrence signal.

## Pattern 25: Pushing Prose Without Running the Diff-Scoped `new-line-breaks` Check First

- **2nd occurrence, 2026-09-09** ([PR #3484](https://github.com/Morrison-Lab/ai-config/pull/3484)).
  A push turned CI's `new-line-breaks` job red for a violation
  (job 102715315795, a long line with a mid-line semicolon) that one local
  invocation of `scripts/vendor/gha-check-new-line-breaks.py` would have
  caught first --- the identical shape the pattern's own 2026-08-29 example
  already recorded twice in one session.
  The specific invocation that would have caught it was
  `NLB_BASE_REF=origin/main NLB_GLOBS='*.md' NLB_CLAUSE_BREAKS=true NLB_CLAUSE_MIN_LENGTH=80 NLB_FAIL=true python3 scripts/vendor/gha-check-new-line-breaks.py`,
  which adds nothing new to the pattern's own Do step beyond confirming the
  clause-break flags survive unchanged into a second occurrence.
  (A companion PR from the same day, #3499, was checked and did not in fact
  fail this job --- its own body records a clean local run before merge, so
  it is not cited here as a further occurrence.)
  What recurs is not a gap in the documentation --- Patterns 25 through 27
  are among the most extensively written pre-push checks in this corpus ---
  but the step being skipped anyway.
  [#2590](https://github.com/Morrison-Lab/ai-config/issues/2590), the
  pattern's own Algorithmatizable note (a `PreToolUse` guard on `git push`),
  is closed and shipped as
  [`hooks/warn-new-line-breaks-on-push.py`](../hooks/warn-new-line-breaks-on-push.py);
  whether that guard was active in the sessions that produced these two
  pushes, and why it did not stop them if so, is not established here and
  is worth checking rather than assuming either way.

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
  very next attempt --- confirming, without a session restart, what Pattern
  43's Fix step in [`mistake-patterns.md`](mistake-patterns.md) had measured
  only *across* one (2026-09-01: an override the prior session's classifier
  denied three times was accepted in a fresh session).
  Separately, after several differently-shaped attempts at the same goal,
  the classifier began denying a plainly innocuous, unrelated command
  (`gh run list -R ... --json ...`), which also succeeded on an identical
  retry.
  ai-config#2994 and this bullet's own prior occurrences already establish
  that repeated variants of the SAME denied command escalate suspicion;
  what neither previously recorded is that the escalation is not scoped to
  that command -- it widens to spend suspicion on unrelated, ordinary reads
  once several denials have accumulated in the session.
- **4th occurrence, 2026-09-09, and a violation of this pattern's own canonical Do** ([#2994](https://github.com/Morrison-Lab/ai-config/issues/2994)).
  The denials landed while composing the commit that became `ef2e64e0` on [#3480](https://github.com/Morrison-Lab/ai-config/pull/3480), whose history shows the outcome as two commits where one was intended.
  `git commit --amend -F <file>` was denied three times in a row.
  A plain `git commit -F <file>`, run immediately afterwards with the same message file and the same staged tree, succeeded on the first attempt, with no settings change and no restart in between.
  The canonical Do says to stop after the classifier's second denial of the same goal and hand the user the decision, and the goal here never changed: get one fix round recorded in git history under a corrected message.
  Continuing past the second denial was contrary to that rule, and the first draft of this record argued it was not --- on the ground that dropping `--amend` changed the *action* rather than rephrasing the request.
  Adversarial review rejected that, correctly: the canonical rule is written in terms of the goal, so redefining it as the command shape is a rationalization, and it leaned on an outcome ("the second commit was the better artifact anyway") that nobody could know before trying.
  What survives is the observation and not the licence.
  A different operation reaching the same goal was not denied, where three attempts at one operation were, which is a fact about the classifier that the pattern's Do/Don't pair does not currently describe.
  Whether the pair should distinguish a different operation from a rephrasing is a question for the pattern entry rather than something a case record may settle, and it is filed as [#3483](https://github.com/Morrison-Lab/ai-config/issues/3483).
  The 2026-09-06/07 occurrence recorded in this file measured that an identical re-run often succeeds.
  This occurrence is not evidence about that, since the command that succeeded was not the one denied.
