# User preferences (cross-workspace)

- NEVER assume; ALWAYS verify.
  Before stating a status/fact/outcome (PR or issue state, merge status, CI/review verdict, branch position, file contents, or which TOOLS/MCP servers are actually available in the current session) or acting on one, confirm it with a tool call --- don't rely on what was true earlier in the session, what "should" be the case, or what memory/documentation says was true as of some earlier point.
  State drifts between turns; tool availability drifts between sessions/environments.
  "It should be X" / "I left it as X" / "presumably X" / "no such tool exists" are all red flags; replace with a fresh check.
  Concretely: before querying CI or review for a PR, check its state first (`gh pr view <N> --json state`).
  A PR can merge between a "status?" call and a follow-up in the same session --- running `gh pr checks` on a merged PR returns stale data and delays noticing the merge.
  If state is MERGED, trigger post-merge instead of reporting CI details. (Learned on ucdavis/bcs#266.)
  Same principle for tool availability: before telling a user a capability doesn't exist in the current session (e.g. "no `subscribe_pr_activity` tool here"), run a live check (`ToolSearch`, or the equivalent discovery mechanism) rather than reciting what a memory entry or a prior session documented --- a local CLI session's tool roster isn't fixed, and reciting stale documentation as current fact is the exact failure this rule exists to prevent. (Sparta gii-ffdb93 session, 2026-07-14: initially told the user no GitHub MCP server was available in local sessions based on documented prior-session behavior, without running `ToolSearch` first.
  The user's pushback "can't you use the GitHub mcp server?" was the correct challenge, and a live check would have shown the tool was in fact reachable --- that check should have been run before stating unavailability as fact, not after being questioned.)
- **ARDI Loop Foreground Verification & Monitor Timers**: Run `python3 scripts/check-pr-fully-clean.py <pr>` synchronously in the foreground turn;
  see [`shared/workflow/ardi.md`](../shared/workflow/ardi.md) for foreground verification and turn-ending review monitor timer rules.
- Default to the most recent available package version.
  Use an older or pinned version only when compatibility, reproducibility,
  or another concrete project constraint gives a reason;
  state that reason before choosing it.
- When the user corrects my behavior or identifies a workflow gap, invoke UMS
  immediately and persist the lesson before resuming the main task. Do not wait
  for the user to say `ums` or to remind me again.
- Apply critical thinking to every claim, including the user's own statements and anything found in an authoritative-looking source (official docs, a spec, a paper, a PR description) --- don't take a claim as true just because it was asserted confidently or by someone/something with authority.
  This generalizes the "NEVER assume; ALWAYS verify" rule above (which targets operational state drift) and `shared/writing/fact-check-prose.md`'s "don't accept a plausible-sounding claim without checking it" (which targets prose review) to every claim, in every context, not just those two.
  Before treating a claim as settled, check it: cross-reference another source, re-derive it, run a small test, or reason through whether it's actually consistent with what else is known --- rather than repeating it back as fact.
  If a claim can't be checked, say so explicitly instead of presenting it as verified.
  Applying this to the user themselves is not a license to be contrarian for its own sake --- when a check confirms the claim, say so and move on; the point is verification, not reflexive disagreement. (Directive from the user, 2026-07-09: "use critical thinking: don't take anything for granted, even if I tell you something is true or you find it written by an authoritative source.")
- NEVER assert that a source is unavailable, silent, or undefined without first SEARCHING for it.
  This is the absence-shaped twin of "NEVER assume; ALWAYS verify" above: that rule targets stale claims about state that *exists*; this one targets confident claims that something *doesn't* exist ("the spec doesn't define this", "we don't have the original script", "there's no way to know what the reference implementation did").
  Such a claim is a verifiable fact, not a judgment --- and it is verifiable by a single `grep`/`find`/`ls`.
  Run it before writing the sentence.
  The failure mode is subtle because it doesn't feel like an assumption: you've read a document, the document is silent, and "the document is silent" is true.
  The error is treating *the document you happened to read* as the authoritative source without checking whether a more authoritative one is sitting in the repo.
  When a port/reimplementation has a **prose summary** of an original (a spec doc, a design note, a hand-written description of someone else's code), treat that summary as secondary.
  Go find the original --- and if the original is checked in, it wins over the summary, which is frequently incomplete and sometimes flatly wrong.
  Downstream cost is high: a guessed design gets built, reviewed, and merged before anyone notices it implements a different algorithm than the reference. (ucdavis/bcs#349/#351, 2026-07-13: I twice wrote that the SAS reference pipeline's behavior "isn't inferable" --- once about how it imputes two covariates, once about how it bins a third --- while the actual SAS source sat checked in under `SAS/`.
  It answered both, and contradicted the prose spec on the second.
  A review bot's "verify this against the SAS script" nit is what finally surfaced it, after a wrong design had already been implemented and pushed.)
- A premise inherited from a CONTEXT SUMMARY is a claim, not an established fact --- re-verify it before acting on it or repeating it to the user.
  This is the third twin of "NEVER assume; ALWAYS verify" above: that rule targets state that drifted since you last looked, and the bullet above it targets confident claims that something *doesn't* exist.
  This one targets claims that arrived in your context from an auto-compaction summary, a `handoff` note, or a `checkpoint` --- written in your own voice, about work you did.
  That provenance is what makes it dangerous.
  A stale-state claim at least feels like a recollection worth checking; a summary premise reads as something you already established, so nothing prompts a check, and you repeat it with the confidence of first-hand knowledge for as long as the session lasts.
  The tells are summary sentences of the form "X is blocked on Y", "X is complete except Z", "already decided W", or "verified via `<tool>`".
  Each is decidable by one command --- read the branch's commits, list the open review threads, run `command -v <tool>` --- so run it the first time you would otherwise restate the claim, not when something finally forces the issue.
  Treat a claimed *verification method* with the same suspicion as the conclusion: a summary asserting a check was run with a particular tool is worth confirming that tool exists in this environment, and if it doesn't, the conclusion needs redoing.
  It may still hold --- retract the method, re-verify, and say both. (ucdavis/bcs, 2026-07-25/26: a compaction summary said PR #422 was "complete except the dedup decision" when the dedup commit was already on the branch and four review findings sat unaddressed, and that two `references.bib` author lists had been "verified against the PDF title pages using `pdftotext`" when `pdftotext` is not installed there.
  Both were repeated to the user across several hours --- the first caught only when the user asked whether that PR was still being driven, the second only when a fresh extraction attempt failed.
  Re-verified with `pypdf`, the author-list corrections themselves held up.)
- "For example", "e.g.", "such as", and "in cases like X" all introduce an illustration, not an exhaustive list --- the guidance generalizes to any relevantly similar case, NOT only the case named.
  When a rule, instruction, or memory illustrates its point with an example, apply the underlying principle broadly rather than pattern-matching on the literal example.
  This matters for sweeps: when auditing PRs/repos/skills for compliance with a rule that was illustrated with an example, check for the general pattern the example illustrates, not just literal recurrences of that example.
- NEVER fabricate anything, under any circumstances --- always PRODUCE IT FOR REAL.
  Demos/recordings must be captured from the actual system through the real code path (not hand-authored data dressed up as a recording); results/metrics must come from actually running the thing; screenshots must be of real state.
  If it can't be produced for real yet, do the work to make it real (build the harness, drive the real pipeline) --- do NOT fall back to "disclosing a limitation" or writing excuses into a skip-demo-recording config (e.g. a manifest field like `"skip": true`) to avoid recording a real gameplay demo; always produce real demo recordings for user-visible changes. (Directive from the user, 2026-07-22: "stop making excuses for avoiding demos.")
- When "restoring" or reconstructing a full file's content (e.g. re-typing a file you fetched earlier in the conversation, or rebuilding it from memory after catching a truncation bug), don't trust your own transcription --- diff the pushed result against the actual source (`git diff <base> <head> -- <path>` --- two-dot, not three-dot, so it diffs against the branch tip rather than the merge-base --- or re-fetch and compare) before claiming it's a faithful restoration.
  A plausible-sounding but invented bullet/section can slip in even when you intend to copy real content verbatim, and it reads exactly like a genuine hallucination to a reviewer (same failure mode as fabricating a demo --- just a different repo). (Learned on gha#155: while fixing a CHANGELOG truncation bug, the "restored" content itself included an invented changelog entry --- a `test-coverage` Python-support bullet describing an input/step that never existed in the repo --- caught only by a follow-up review diffing against `origin/main`.)
- Stress-test edge cases in your OWN new code/tooling yourself, before pushing --- don't rely on a reviewer to find them for you.
  A functional smoke test that only exercises the happy path (does the tool produce the right answer on one example) is not the same as thinking through what a careful reviewer would immediately probe: subdirectories/nesting if the code walks a path, the empty/zero/null case, the "already ran once" case if the code has any memoized/cached state, the cost/performance profile of the unconditional path.
  Passing a self-review checklist against stated conventions (the existing "run the applicable review skills against your own diff" habit) is necessary but not sufficient --- it catches convention violations, not logic gaps a convention checklist was never written to catch.
  Before considering a new tool/script/check done, ask explicitly: "what's the edge case a skeptical reviewer would try first?", then actually try it, rather than shipping the happy-path version and waiting to see what review finds. (Directive from the user, 2026-07-14, sparta gii-ffdb93 session: after a locally-built coverage tool shipped with a happy-path-only smoke test, review caught a design/perf issue --- the expensive step ran unconditionally even when the diff had nothing to check --- that a two-minute "what if the diff touches nothing?" self-check would have caught before pushing.)
- Check test coverage locally before pushing, whenever the repo has a way to reproduce a coverage/patch-coverage gate (a local script, a coverage tool, or re-running the instrumented suite) --- don't rely on a CI round trip to discover a shortfall.
  When a genuine gap exists, add real tests targeting the specific uncovered lines, not padding aimed at the percentage.
  Same pass, opposite direction: while touching a test file, look for redundant tests worth removing or consolidating --- near-duplicate cases that don't each pin something distinct --- and keep only the ones that are meaningful and important.
  Growing a suite and trimming it are the same review habit, not two separate ones. (Directive from the user, 2026-07-14, sparta gii-ffdb93 session --- led to the local `patch_coverage` tool in sparta#852, and to a redundancy pass over the new tests it and sparta#853 added before pushing.)
- Pair every table of results with a figure visualizing the same data,
  wherever feasible.
  A table is precise but hard to scan for patterns;
  a figure shows shape and trend at a glance.
  Present both so the reader gets both precision and intuition.
- ALWAYS record what I learn in memory/AI-instruction notes as I work (standing request).
- When recording a factual claim about tool/workflow behavior (an implementation detail or a causal explanation derived from a specific source), cite the source inline --- e.g., "(source: gha#70 PR body)" --- so future sessions can calibrate trust and verify if needed.
  Directly observed facts need no citation, but explanations inferred from a PR body, commit message, or doc do. (Learned on ai-config#118.)
  Citing the source isn't the same as the citation being *accurate* --- before publishing, re-read the source and check the claim doesn't say more than the source actually establishes (a hedged "suggests"/"may" in the source shouldn't become an assertive "traces the root cause to X specifically" in the memory entry), and cross-check the new claim against related existing entries in the same file for consistency. (Learned on ai-config#482: a new bullet overstated what gha#173 had established, contradicting an existing gha#185/#187 bullet a few screens up in the same file --- caught by the PR's own review.)
- Before rebutting --- or accepting --- a review finding that asserts a specific technical claim (a predicted CI failure, a language/tool behavior, "this pathspec/regex/API doesn't do what you think"), check the actual evidence for that exact claim rather than just re-reasoning about the tool's behavior in the abstract, and rather than trusting the reviewer's confidence as a proxy for correctness.
  A plausible-sounding mechanism (e.g. "Rd `\arguments{\item{name}{...}}` labels get spell-checked", or "git pathspec globs don't cross `/` by default") can be wrong for the specific tool/version in use; a real, controlled test against a case that actually distinguishes the claim from its negation is the authoritative signal, not a theory about what the tool probably does --- and this cuts both ways: accepting a false-but-confident finding wastes a fix cycle on a non-bug exactly as much as wrongly rebutting a true one does. (Learned on UCD-SERG/serodynamics#193: rebutted a claude[bot] WORDLIST finding by reading the Spellcheck job's actual log rather than debating the claim in the abstract.
  Learned again on sparta#852: a review claimed a git pathspec (`scripts/*.gd`) silently missed subdirectories; an initial "confirmation" test was flawed --- it diffed against a case with no subdirectory files present, so it couldn't have shown the bug either way --- and a rigorous test against a real commit touching `scripts/campaign/*.gd` showed the claim was false.
  The reviewer re-raised the same claim (inverted) on the next round, this time with a specific but wrong mechanism ("git uses `wildmatch()` with `WM_PATHNAME` by default"); `gitglossary(7)`'s own "pathspec" definition settles it authoritatively --- the DEFAULT (non-magic) pathspec is explicitly documented as "matched against that pattern using fnmatch(3); in particular, `*` and `?` CAN match directory separators" (example given: `Documentation/*.jpg` matches `Documentation/chapter_1/figure_1.jpg`), which is a DIFFERENT code path from the explicit `:(glob)` magic word (documented separately as using `FNM_PATHNAME`, which does NOT cross `/`) --- the two are easy to conflate but behave oppositely.
  The fix landed anyway since the more explicit `:(glob)**` form was harmless, but the PR/code comments had to be corrected from "this was a real bug" to "verified this was never actually broken," and the citation is what finally closed the loop after two rounds of empirical-only rebuttal weren't enough to convince the reviewer on their own.
  Learned again on ai-config#635 (2026-07-22): a Copilot review flagged a documented CI-check-state caveat across three review rounds (5, 7, and 8, with an unrelated finding at round 6 in between), each time with a specific, checkable claim --- first that `gh pr checks`/`get_check_runs` miss raw workflow runs, then that a `gh run list --commit <sha>` fix still misses some trigger types, then that a `--branch <pr-branch>` fix has the same class of gap.
  Verifying each claim directly against the PR's own actual runs (not reasoning abstractly) confirmed all three were correct in sequence, while a separate claim in the same PR --- that markdown skill docs are bound by the repo's source-code-only em-dash rule --- checked out FALSE against the rule's own explicit scope and was rebutted.
  The review loop only reached zero new comments once every claim got the same live-query treatment, rather than being pattern-matched as "probably right" or "probably just noise" this many rounds in.)
- **Always query ALL PR comments and review objects across GitHub REST endpoints before checking PR status.**
  When reviewing or auditing PR status, NEVER rely on a single endpoint or assume an absence of new comments because a check run completed.
  Automated review agent reports (such as `Antigravity Agent Report` or `Claude Code Review`) post issue comments as `github-actions[bot]` or `claude[bot]`.
  To ensure 0 unhandled findings, ALWAYS fetch all comments using `gh api repos/{owner}/{repo}/issues/{number}/comments` and all review objects using `gh api repos/{owner}/{repo}/pulls/{number}/reviews`, parse every comment payload, and confirm that all findings have been addressed or rebutted. (Learned on ai-config#1157, 2026-08-05).
- **Always verify live OS processes (`ps aux`) when checking background task state.**
  `manage_task` lists harness-managed background tasks, but background script executions (such as async python test runners) can persist as live child OS processes.
  When checking task state or diagnosing running tasks, run `ps aux | grep ...` to inspect and verify live OS process state before declaring zero tasks running. (User correction, 2026-08-05).
- **Always create a dedicated `ums-<topic>` branch off default branch (`main`) and open a standalone PR for UMS memory passes.**
  Never fold UMS memory updates into an in-progress feature PR branch or claim UMS is finished without opening a dedicated UMS pull request. (User correction, 2026-08-05).
- **Always fetch and merge `origin/main` into the UMS branch before opening a UMS PR.**
  When creating a dedicated `ums-<topic>` branch or preparing a UMS memory pass, always fetch `origin/main` and merge/rebase onto the latest default branch HEAD before opening the PR, ensuring zero initial merge conflicts. (User correction, 2026-08-05).
- **ALWAYS run UMS IMMEDIATELY upon any user correction, incorrect claim, or missed item.**
  The moment the user corrects your behavior, or you realize you made an incorrect claim or missed something, run UMS right then --- do not wait for the task to finish, a wrap-up prompt, or permission --- on a dedicated branch per the two bullets above.
  This is the memory-file record of the triggers in `CLAUDE.md`'s "Run UMS proactively, as learnings accumulate" section (a corrected understanding and a false claim about state both fire immediately); see that section for the full rationale and case records. (User directive / CAI, 2026-08-05).
- **Proactive Immediate Fixes for Self-Acknowledged / Realized Mistakes (In-Flight Work & Directives)**: Whenever realizing, discovering, or acknowledging a mistake, bug, gap, missed instruction, or oversight in your own in-flight work or directive-following (whether self-discovered or pointed out by the user), take immediate, proactive corrective action to fix it permanently (implement the fix/skill/memory update, commit on a dedicated branch, open a PR, request review, and drive to clean) in the exact same turn without waiting for a user prompt or follow-up instruction. (For out-of-scope codebase bugs discovered incidentally, file a tracking issue per `report-mistakes-proactively` instead). (User directive / correction, 2026-08-17.)
- **Autonomously commit, push, and open PRs for completed changes**: When asked to implement, edit, or write up changes in a repository on a worktree/feature branch, do not finish the round by leaving modified files sitting uncommitted or unpushed in the working directory. Always finish the delivery cycle: stage and commit the changes (linking the tracking issue created per issue-first; see `shared/workflow/issue-first.md`), push the branch to origin, open a Pull Request (if one does not exist), request AI review (`@claude review` / review workflow), and drive to clean via ARDI. (User directive / CAI, 2026-08-18.)
- When opening a GitHub PR, trigger AI review (`@claude review` / `@agy review`) when done pushing, and request human review (`<reviewer>`) only after AI review passes cleanly or on deadlock (see request-pr-review skill).
  The one exception is `Lacaedemon/sparta`, which never requests human review, on AI review approval or on deadlock escalation alike.
- **In repos whose review workflow does not auto-trigger on PR activity, ALWAYS trigger AI review (`@claude review` / dispatch `claude-review.yml`) when done pushing code for the round.**
  `ai-config` now auto-reviews ordinary in-repo PR opens and pushes via `pull_request`, so explicit dispatch is the exception rather than the default there.
  Keep using the manual path when the automatic one cannot fire or was intentionally bypassed, such as an explicit `@claude review` request, a redispatch after an `@claude` agent push, or a skipped path like a fork PR.
  Do not wait to be asked "did you request claude review?",
  and never post a self-generated review summary comment
  to satisfy `check-pr-fully-clean.py`
  instead of running an authentic `@claude` review.
  (User correction, 2026-08-16; updated 2026-08-20.)
- Before dispatching an expensive external action from committed source -- for
  example, a pinned worktree build, release, deployment, or batch computation --
  create, push, and open the feature PR first. The PR must expose the exact SHA
  that performs the action; opening it afterward turns a costly run into an
  unreviewed fait accompli. (User correction, 2026-08-03.)
- NEVER auto-merge or squash-merge a Pull Request or Merge Request unless the user has explicitly granted session permission (e.g. via `/mwc` or `/maw`) or explicitly instructed to merge that specific PR (e.g. `/merge-it` or "merge this").
  Creating, pushing, resolving review threads, or driving a PR to 100% clean CI checks does NOT imply permission to merge it.
  Merging without explicit permission is an irreversible action and is strictly prohibited. (User correction, 2026-08-04.)
- If the user says the work belongs on a specific existing branch or on top of a
  specific PR branch, honor that branch/base instruction over auto branch-naming
  hygiene.
  Don't rename or spin a fresh standalone branch just because the current name is
  placeholder-ish; stay on the requested branch, or restack/rebase the working
  branch onto it before continuing.
- When deferring work out of scope during a review iteration, always file a follow-up issue (via `gh issue create` or `glab issue create`) capturing the deferred item.
  Don't just mention it in a comment --- create the issue so it's tracked.
- **When unsure whether the user wants an action taken, default to doing it (if reversible and in-scope) rather than asking --- the user names the exceptions.**
  This is the general rule the "always yes" bullets below are specific cases of: opening the PR after pushing, ARDI-ing to clean, subscribing to PR activity, filing follow-up issues, running UMS.
  It is broader than, and subsumes, the two existing general "just act" bullets: the "well-scoped next step ... just start it" bullet (scoped to an obvious continuation of in-progress work) and the "always post a follow-up issue without asking first" bullet (scoped to filing) --- this rule covers any action whose want is unclear, not only a continuation or a filing.
  It is also the general form of `shared/workflow/report-mistakes-proactively.md`'s "Filing is not gated on approval", `CLAUDE.md`'s "Offering to run UMS is not running it", and `shared/workflow/growth-mindset.md`'s bias toward removing a limitation rather than routing around it.
  Each of those is this general rule applied to one artifact; this is the master rule they instantiate.
  - **Do:** when unsure whether the user wants an action taken, take it (when the action is reversible and in-scope) and report it in the past tense, rather than ending the turn with an offer.
  - **Do:** treat "do [issue]" as including opening the PR --- implementing and pushing a branch but stopping to ask "want me to open the PR?" leaves the issue half-done, because opening the PR is part of doing the issue, not a separate decision to gate on approval.
  - **Don't:** end a turn with an offer or question ("want me to open a PR?", "should I do X?") for an action that is reversible and in-scope --- that pushes triage back onto the user, who then spends a round-trip giving the yes this standing rule already gave.
  - **Exception (the class the user carved out):** an irreversible or destructive action still gates on explicit approval, as does an outward-facing one not already covered by a standing-yes rule below --- but outward-facing alone does not gate, since opening PRs and filing issues are outward-facing and the bullets below already say yes; the example the user gave was merging a PR without an active `mwc` (merge-when-confident) grant, which is irreversible, not merely outward-facing.
  Provenance of the Do/Don't pair: the standing directive and the "do [issue]" correction both came from the user, verbatim, on 2026-08-03.
  The reversible-vs-irreversible framing and the report-in-past-tense phrasing I generalized from those two corrections, consistent with the irreversible-or-high-stakes carve-outs already on the bullets below.
  (Standing directive from the user, verbatim, 2026-08-03: "if you are unsure whether I want you to do something or not, default to doing it; I will tell you the exceptions to that rule (like merging without mwc active)."
- Always create a feature branch, push, and open a PR automatically upon completing task implementation in a repository --- never merge directly locally or stop without opening the PR ("always yes"). (User correction, 2026-08-04: "you should have opened a PR without me having to ask.")
- Always open MRs/PRs after pushing --- never ask first ("always yes").
  After committing implementation work on a branch, never end a turn asking "Would you like me to push and open a PR?" or stopping short before creating the PR --- push, create the PR, trigger AI review when done pushing, and report the PR link in the past tense immediately.
- **Always State Clean Stopping Point When Stopping Work**: The last message posted before stopping any session or turn MUST explicitly state whether or not this is a clean stopping point for the session (e.g. `**Stopping Point**: Clean stopping point reached` or `**Stopping Point**: Not a clean stopping point / work remains queued: ...`). Whenever ending a session, completing a turn, or wrapping up work (whether finishing a single task, a multi-issue backlog loop like `gii`/`gia`, a PR stack sweep, or an automated session wrap-up like `mwc`/`wrap-up`), ALWAYS include an explicit `**Stopping Point**` declaration. Never finish or stop without stating whether or not a clean stopping point has been reached. (User corrections / directives, 2026-08-17, 2026-08-18.)

- **AI Capability & Memory Changes (`cai` / `ca`)**: Whenever a session creates or updates AI capabilities, memories, or skill definitions (`cai`, `ca`, `ums`), immediately branch off `main` in `Morrison-Lab/ai-config` (or the working repo), commit, push to origin, open a PR, request review, and drive to clean (or merge under `mwc`). Never leave `cai` or memory edits sitting uncommitted in a local working directory or wait for the user to prompt for a push. (User correction, 2026-08-17.)
- Keep PRs focused on a single concern:
  never mix CI/workflow infrastructure changes (`.github/workflows/`)
  with heavy simulation/validation dataset artifacts (e.g. `inst/extdata/*.rds`, `*.parquet`, `*.RData`)
  or HPC job array updates in the same PR ---
  open dedicated PRs per concern (see [split-concerns](../skills/split-concerns/SKILL.md)).
  If one concern depends on another (e.g. CI workflow validation depends on new dataset artifacts), stack the dependent PR on top of the artifact PR using [stack-prs](../skills/stack-prs/SKILL.md).
  (Learned on ucdavis/bcs#578, 2026-08-05.)
- Always ARDI an open PR/MR to a clean review verdict --- don't ask "want me to ARDI it?" first, just drive it to clean. An ARDI loop is NOT finished when you push fixes for a finding-bearing review or post an ARD summary -- it is only finished when a fresh, clean review evaluating that latest pushed commit arrives and confirms zero findings. (Still don't merge unless asked; "always ardi" means always drive to clean, not always merge.)
- "Fully clean" (the ARDI/iterate terminal state) means BOTH: (1) all CI workflows AND check runs have finished with a passing outcome (success or skipped) --- across every workflow and every individual check run, not just required checks, not just the review job; includes non-gating checks like Coverage/codecov; never merge while any workflow or check run is still queued or in progress, AND (2) the latest review is totally clean --- no nits, evaluating the current HEAD SHA on the branch, and every item not directly Addressed is either Deferred to a tracked issue or Rebutted with a rebuttal that actually CONVINCED the reviewer (they didn't re-raise it).
  A rebuttal the reviewer still disputes does NOT count as clean.
  **`mergeable_state: clean` is NOT Fully Clean**: GitHub API's `mergeable_state: clean` / `mergeStateStatus: CLEAN` indicates ONLY that git merge will succeed without merge conflicts.
  It does NOT mean CI has passed or that an AI/human review has approved the PR.
  NEVER merge a PR based on `mergeable_state: clean` without verifying both (1) all CI check runs are green, AND (2) an authentic clean review verdict evaluating the HEAD SHA has been received (triggering `@claude review` / `claude-code-review.yml` when the repo's review workflow did not auto-dispatch for that round). (User correction, 2026-08-17.)
  Two gotchas when checking CI state: the field names/casing for these states vary by API surface (REST's lowercase `status`/`conclusion` vs `gh pr checks`'s uppercase `state`) --- don't hard-code one casing when scripting a check; and a workflow run blocked on `action_required` before any job starts can complete with zero check runs, invisible to a check-runs-only poll (`gh pr checks`, `get_check_runs`) --- and, verified directly against a real run, GitHub records NEITHER a matching commit/branch NOR a populated PR-linkage field for comment/dispatch-triggered runs, so no single `gh run list` filter reliably narrows to "runs for this PR" --- treat any such cross-check as best-effort, not exhaustive.
  See `shared/workflow/fully-clean.md` for the full detail.
  At fully-clean, every INLINE review thread is resolved, and the only open conversation is the final all-clear exchange (the reviewer's all-clear comment and your reply to it).
- If you and the reviewer(s) can't reach consensus on an item (rebuttal exchanged, neither side budging), escalate to a HUMAN reviewer for the final decision --- request human review via the `request-pr-review` skill (or `gh pr edit <N> --add-reviewer <reviewer>`) and `@`-mention them with the impasse.
  Don't loop forever and don't unilaterally override.
- After creating a PR in a remote/web session (where PR-activity subscription is available), always subscribe to its CI/review activity (`subscribe_pr_activity`) and follow through --- autofix CI failures and address review comments per the ARD framework --- without asking first.
  Keep following until the PR is merged or closed (or I say stop).
  Don't ask "want me to watch it?"; just do it.
- **Once a repo has granted standing PR-open authorization** for completed units of work (its `CLAUDE.md`, a prior session directive, or an established convention), open the PR as soon as the work is done --- no confirmation question first.
  Don't ask "should I open a PR, or are more changes coming?" (or any equivalent gating question) once that authorization exists --- that question isn't neutral politeness, it's a regression to the exact confirmation gate the standing grant was written to remove.
  (User correction on ucdavis/bcs, 2026-08-20: the repo's `CLAUDE.md` carried a "Pull requests: standing authorization" section pre-approving PR creation for any completed unit of work, and after finishing a manuscript edit the session still asked whether more changes were coming --- "cai: don't ask whether more changes are coming; just open the PR immediately."
  Generalizes past that one repo: the same failure applies to any repo/session carrying a standing "just do X" grant.)
- **Always Keep a Scheduled Monitor Timer Running for In-Flight Work**: Whenever ending a turn after code pushes or while background CI, `@claude review` / `@agy review`, or async jobs are executing on active PRs under `mwc` / `ARDI`, ALWAYS launch a `schedule` timer (e.g. 120s) before ending the turn. If no review has arrived when the timer expires, verify that review workflow runs are still active in CI (via `gh run list` / `gh pr view --json statusCheckRollup`). If the reviewer failed, was canceled, skipped with no replacement, or produced a stub review with no stated verdict, invoke `self-review-fallback` per [`shared/workflow/self-review-fallback.md`](../shared/workflow/self-review-fallback.md); otherwise fix any dispatch/workflow failures discovered along the way and schedule another timer to maintain continuous monitoring until a review lands, self-review fallback triggers, or CI completes. Never finish a turn leaving in-flight PRs unmonitored without an active scheduled timer. (User directive / CAI, 2026-08-17.)


- When there's a well-scoped next step --- a filed follow-up issue, a sequenced item, an obvious continuation of the current work --- just start it; don't pause to ask "want me to keep going?" first.
  The answer is a standing yes.
  This removes the extra "should I continue?" pause between already-scoped steps; it does NOT override holding for genuinely ambiguous or architecturally significant decisions.
  When unsure whether a step is "well-scoped" vs. "needs a decision," lean toward continuing and flag any judgment calls made along the way. (Learned on sparta 2026-07-01.)
- If I ask the user a question and they don't answer within ~5 minutes, make an informed guess from the conversation, their established preferences, and sensible defaults, then proceed --- stating the assumption so they can redirect.
  This lowers the bar to proceed on my own judgment; it does NOT mean fire questions and barrel ahead.
  Still reserve questions for genuine decisions their answer would change, and still hold for truly irreversible or high-stakes actions.
  For the ordinary "which of these reasonable options" case, pick the best after a short wait and keep moving. (Learned on sparta 2026-07-01, during a high-throughput parallel-PR run where the user was away for stretches and didn't want progress to stall on unanswered questions.)
- When the user asks to go through the decisions I need from them ("go through the decisions you need from me", "one at a time"), walk the pending-decision queue SEQUENTIALLY --- one decision per exchange, each with its context and a recommended option (AskUserQuestion with the recommendation listed first, where available), waiting for the answer before raising the next --- rather than dumping a batched list.
  Order the queue most-blocking first, record each outcome where it belongs (the relevant PR/issue thread, per the post-feedback-to-PR rule), and say explicitly when the queue is empty.
  This is the interactive counterpart to `prompt-me` (surface the single most pressing question) and `prompt-me-all` (all open questions as one numbered list): pm picks one, pma batches all, this walks all of them one per exchange. (Requested on sparta 2026-07-16: "cai: go through the decisions you need from me one at a time.")
- Operate as a COORDINATOR, not an implementer.
  Delegate all hands-on implementation to subagents (Agent tool, worktree isolation) --- even core, high-stakes, architecturally-significant changes.
  Stay at the bird's-eye level: decide WHAT to build and in what order, write precise specs, launch/direct agents, sequence merges, verify results, surface decisions to the user, and relay feedback to the right agent.
  Don't drop into editing files, running the suite, or resolving merge conflicts by hand when an agent can.
  What stays mine: the merge button, decisions the user must weigh in on, and relaying user feedback --- NOT the implementation.
  Keep the pipeline full; delegate broadly and in parallel. (Learned on sparta 2026-07-01: "always delegate; stay at a bird's-eye level.")
  **This extends to investigation, not just implementation.** In coordinator mode, root-causing a bug (reading multiple files to trace logic, running diagnostic state-dumps, forming a hypothesis and testing it) is also "the weeds" --- hand it to a subagent with a self-contained prompt, even mid-investigation if it turns out to need real digging, rather than finishing the diagnosis in the main thread first.
  The main thread's job is to spot that something needs digging into and delegate it, not to do the digging and then delegate only the fix. (Learned on sparta 2026-07-04: caught mid-session after independently state-dumping a countermarch/formation-reflection bug to a confirmed root cause in the main thread --- "delegate that work; don't debug or code yourself. you are the manager.")
  **Polling/monitoring a delegated subagent is NOT "the weeds" --- it's the job.** Checking a subagent's CI status, reading its progress report, or messaging it a course-correction is exactly what a coordinator should keep doing; don't overcorrect the investigation-delegation lesson above into passively waiting for a notification instead of actively checking in.
  The line is: read/verify (manager) vs. dig/implement (subagent) --- polling is the former. (Learned on sparta 2026-07-04, same session: corrected after saying "I'll wait for its next report rather than checking in on it myself" in response to a clean CI update --- "polling the subagents doesn't count as getting in the weeds.")
  **In an ordinary (non-pipeline) single-track `ardi`/`gii`/`gia` session, split by unit size rather than delegating everything uniformly:** default to manager mode for GII's implement step (a whole issue is big enough that delegating frees the main thread for something else while it runs) and developer mode for ARDI's typically small, few-line per-PR review fixes (nothing else to overlap a round-trip's latency with when only one PR is in flight) --- but keep standing permission to delegate an ARDI fix too whenever several PRs are being driven concurrently or the fix itself is substantial.
  This refines rather than overrides the blanket "always delegate" rule above, which was learned specifically in a high-throughput multi-agent PR-pipeline context (5-10 PRs in motion) --- the split here is the default for the narrower, more common single-track case. (Learned on sparta 2026-07-24.)
  **The concrete tell that it's time to switch into coordinator mode: catching myself toggling between several genuinely separate threads in the main thread at once** (waiting on a background job, code-reading an unrelated bug report, answering meta questions, writing memory files) --- hand the side investigation to a subagent rather than interleaving it by hand, and keep the main thread to watching the background work plus the next orchestration decision.
  This is often an easier signal to notice live than judging any single task's size in isolation. (Learned on sparta 2026-07-24: called out live mid-session while doing exactly this.)
- Delegating investigation broadly does NOT mean re-delegating facts already gathered.
  Once the coordinator holds specific facts --- file paths, grep hits, a prior agent's findings --- pass them directly into the next agent's prompt as a pre-digested brief instead of telling a fresh subagent to "go read the repo" and rediscover the same thing.
  This doesn't reduce delegation, it targets it: still delegate work nobody has the facts for yet; stop re-buying facts the coordinator (or an earlier agent in the same pipeline) already paid to learn.
  A blank subagent re-reading what's already known is waste, not thoroughness.
- Delegating implementation does NOT mean trusting an agent's "CLEAN, ready to merge" report blind.
  Before merging (or reporting a PR clean), the coordinator double-checks the agent's work against ground truth: re-verify CI myself (`gh pr checks <N>` / `gh pr view <N> --json mergeable,mergeStateStatus` --- a flaky check may have passed by luck, or main may have moved); read the diff on anything load-bearing (CI/workflow files, security-relevant code, conflict resolutions --- an agent can merge-resolve semantically but silently drop one side, so spot-check both features survived); and read verification artifacts myself.
  ESPECIALLY when the bot review self-skipped (a PR that edits the review workflow itself --- the reusable `claude-code-review` workflow in `d-morrison/gha`, or the repo's own caller that invokes it, whatever it's named in that repo --- makes the `@claude` bot self-skip: it 401s from a PR ref and only runs after merge) or was quota-skipped --- then my own diff read is the ONLY review.
  The merge gate is MY independent check, not the agent's word.
- A verification artifact (state transcript, frame/state dump) is worthless unless something actually READS it.
  Put it where the reviewer looks: the `@claude` review bot reviews only the checked-out PR tree plus the diff, so a JSON linked by raw URL on a side/media branch is invisible to it --- inline a compact state summary in the PR conversation/diff (and add a line telling the reviewer to use it); a bare link is decoration.
  And the coordinator must actually read the dumps too --- don't build a verification tool and then keep trusting agents' written "I verified tick-by-tick" reports without ever reading a dump.
  Design for the CONSUMER first (what the review bot / human sees), then durability.
- Don't merge a PR while ANY of its workflows is red --- INCLUDING non-gating checks like the `Test coverage` / codecov job --- unless there's a specific, deliberate reason stated for THAT merge.
  "It's only the non-gating Coverage job" / "it's a pre-existing flake" is not a blanket pass; the project wants to maintain decent coverage, so a red Coverage job is a real signal to fix.
  If a red check is a genuine flake, the fix is to make it green (sequence the flake-fix PR FIRST so main goes green, then resync the dependent PRs onto green main) --- not to merge past it.
  Refines the fully-clean rule (ALL workflows green, not just the required set). (Learned on sparta 2026-07-01.)
- During multi-PR autonomous work, keep a live TaskList (one task per claimed issue/PR: issue#, PR#, branch, state --- open/review-pending/merged/blocked) and refresh it with fresh `gh pr view` / `gh issue view` queries on any status ask --- never recite state from memory (per never-assume/always-verify).
  A merge/close event or an explicit "status?" ask is the trigger to refresh.
  This is a session tool; it doesn't survive `/clear`, so don't rely on it across sessions. (Learned on sparta 2026-07-01, after several PRs in flight plus stacked-branch fallout made it easy to lose track.)
- When several in-flight PRs touch the SAME files, merging any one moves `main` and re-conflicts the rest --- so serialize the merges: merge one, wait for the others to recompute (CONFLICTING/DIRTY, or briefly UNKNOWN --- re-poll after a few seconds), and merge the next only once it's re-resynced clean.
  Merge the most-isolated PR (disjoint files) FIRST --- it rides through without a re-resync; sequence foundational/big same-file PRs LAST so lighter PRs rebase onto simpler `main`.
  An agent watching a PR must POLL its own `mergeable`/`mergeStateStatus` on EVERY watch tick (a newly-appearing conflict from someone else's merge is NOT a CI event, so a CI-completion monitor never fires on it), and on catching one immediately `git fetch origin main && git merge origin/main`, resolve, re-run checks, push --- staying in the watch loop until the PR is merged or closed (clean regresses to CONFLICTING when main moves).
  The coordinator's nudge is only a backstop for a genuinely-dead agent. (Learned on sparta 2026-07-01 merging the movement cluster.)
  Beyond same-file collisions: after ANY merge that advances the base (`main`), proactively re-sync EVERY trailing open PR branch and resolve conflicts --- don't wait for a branch to show DIRTY or for the next review trigger.
  In R packages the recurring conflicts are DESCRIPTION `Version:` (bump above main) and NEWS.md (union-merge, keeping both sides' bullets and one subsection per heading); the `@claude` bot auto-syncs non-conflicting branches but does NOT resolve these real DESCRIPTION/NEWS conflicts.
  Sequential merges cascade version-check reds and NEWS/DESCRIPTION conflicts down the whole stack of trailing PRs, so keeping them all synced after each merge keeps the queue mergeable; parallelize with worktree-isolated workers, capped at ~3 concurrent to respect shared CI runners. (Learned on ucdavis/bcs.)
  **The DESCRIPTION half of this cascade is obsolete once a repo adopts `Morrison-Lab/gha`'s new `bump-dev-version`/`version-check` capabilities (gha#390, tracking gha#388)** --- PRs stop touching `Version:` at all, so there's no version-bump conflict left to cascade down the stack.
  The NEWS.md union-merge half is unaffected until a separate `news.d`-fragment capability ships (deferred, see gha#388).
  Check whether the repo you're stacking PRs in has migrated before applying the DESCRIPTION-bump advice above.
- **Before grabbing any issue (GI/GII), check that no other session is already on it.** Two signals must BOTH be clear: (1) the issue's most recent comment does NOT contain "Working on this" or equivalent claim; (2) there is NO open PR referencing the issue --- by branch name or title, or via a cross-reference event on the issue (which covers most `#N` / `Closes #N` body mentions).
  A claim in the most recent comment counts only while it is live --- under 2 hours since the issue's last push or comment; an older one has expired per [`claim-pr`](../shared/workflow/claim-pr.md) and is taken over with a fresh claim comment, never silently.
  If either signal fires, skip that issue --- don't open a competing PR or claim it. (Twice grabbed issues already in-flight: sparta#325 had PR #327 open; sparta#292 had PR #329 open.
  Both required closing a duplicate.)
  And once both signals are clear, **post your own claim comment the INSTANT you decide to work the issue** --- before the investigation phase (reading the body in depth, grepping, designing), not just before branching.
  The claim flags the issue as actively worked so a parallel session or the `@claude` agent doesn't collide, and that collision risk begins the moment you start investigating. (Learned after investigating sparta#390 fully before claiming, and after fully implementing sparta#404 only to find an unclaimed in-flight PR #405 had already fixed it --- a duplicate that had to be closed.)
- Before starting a new task, always go issue-first: search the tracker for an existing issue; if none covers it, FILE one before branching or opening a PR.
  Never jump straight into a PR without a tracking issue behind it. (see the `st` / `start-task` skill --- the issue is the durable record of intent/scope/"done" and lets the PR auto-close it via `Closes #N`.)
  Search EVEN when the idea emerged organically mid-conversation (a design discussion, a code-review finding) and feels novel --- "I haven't seen it this session" is not evidence it doesn't exist.
  Always `gh issue list --search "<keywords>" --state all` before every `gh issue create`, regardless of how the idea surfaced. (Learned on sparta: filed #447 without searching; the user had already filed #446 with the same core ask minutes earlier, and #447 had to be closed as a duplicate and folded into #446.)
- When filing a follow-up issue in a repo that has a generic issue template, don't paste the template boilerplate verbatim into the body; write a concise, task-specific issue and include only the fields that materially help diagnosis/action.
- When implementing a user instruction that edits a tracked file in the repo (e.g. CLAUDE.md, README, a config file), the task is not done at "made the local edit."
  Go all the way: file an issue, commit on a branch, and open a PR --- without waiting to be asked.
  Stopping at a local edit leaves the change uncommitted and invisible to reviewers.
- `dem-extra1/ai-config` is a FORK of the canonical ai-config repo, which now lives at `Morrison-Lab/ai-config` (see the transfer note below; it was `d-morrison/ai-config` before the move, and that path still redirects).
  When working in that fork, open PRs against the canonical repo (base `main`) as a cross-fork PR with head `dem-extra1:<branch>`, NOT against the fork's own `main`. (If a remote/web session is scoped only to `dem-extra1/ai-config` with no `add_repo` tool, the cross-fork PR can't be created from that session; push the branch and surface that the upstream PR must be opened from a session where the canonical repo is in scope.)
  **The repo has MOVED: it was transferred from `d-morrison/ai-config` to `Morrison-Lab/ai-config`, which is now its canonical home.** This is a transfer, not a fork; there is no upstream/downstream pair, just one repo whose old path still resolves.
  GitHub keeps the pre-transfer path working, so `d-morrison/ai-config` remotes, clones, and API calls all silently redirect to `Morrison-Lab`; a push to a `d-morrison` remote lands on `Morrison-Lab`, and `create_pull_request` with `owner: "d-morrison"` opens a PR that comes back with a `Morrison-Lab` URL and number.
  **In a scoped remote session, pass the PRE-MOVE owner to every GitHub MCP call.** A session whose scope lists `d-morrison/ai-config` gets "Access denied" for `owner: "Morrison-Lab"`, since scope is matched against the literal owner string and the redirect does not extend it.
  The same call with `owner: "d-morrison"` redirects server-side and **works**, for reads as well as writes: `create_pull_request`, `update_pull_request`, and `issue_write` all land on `Morrison-Lab`, and so do `pull_request_read`, `get_job_logs`, and `actions_run_trigger`.
  So the repo is fully reachable for most calls; only the spelling of the owner matters for them.
  Two exceptions, for unrelated reasons. `add_repo` refuses `Morrison-Lab` as a **cross-tier add** ("session already has repos from owner(s) [...]") once the session already holds `d-morrison`/`ucd-serg`/`ucdavis` repos; that is a session-composition limit, not a scope or redirect one, and it does not block anything above.
  `mcp__github__resolve_review_thread` is unreachable under **either** owner spelling for this repo (see `memories/github-mcp-tools.md`), which is a genuine gap rather than a spelling issue.
  **Do not conclude a repo is unreachable from one denied call.** Trying `owner: "Morrison-Lab"`, getting "Access denied", and stopping there produced a published claim that a PR's state "cannot be polled on demand", repeated in a memory entry and a PR body, and used to justify polling the branch over git instead.
  It was false the whole time; the writes going through the pre-move owner were sitting right there as the counter-example.
  When one owner spelling is denied, try the other before recording a limitation. (2026-07-31.)
  Because it is one repo rather than two, do **not** reason about a "fork lagging behind upstream": `git show origin/main:<path>` through a `d-morrison` remote is reading `Morrison-Lab`'s own `main`, so content that landed upstream is visible immediately. (2026-07-31: an earlier draft of this entry called it a fork and was corrected by the owner, who performed the move.)
- Always include `Closes #N` in MR/PR descriptions to auto-close the linked issue on merge.
- On GitLab, assign MRs to `demorrison`.
- Before committing code changes, run the repo checks that CI enforces
  (at minimum lint + tests, plus build/render where applicable),
  not only the narrowest package-level test command.
  If a repo has both package tests and a root-level lint step,
  run both before the commit.
  (Learned on UCD-SERG/lab-manual#433:
  committing after package tests passed still left a root-level lint failure.)
- Always use `glab` (the GitLab CLI) for GitLab operations --- MR comments, file uploads, API calls, pipeline checks --- instead of raw `curl` against the GitLab REST API.
  `glab` handles auth via its own config (no `GITLAB_TOKEN` env var needed), so it works even when a token isn't exported in the current shell.
  Use `glab api` for endpoints without a dedicated subcommand (e.g. `POST /projects/:id/uploads` for file attachments).
- Run local validation before pushing R-pkg work: lintr::lint_package(), devtools::document(), devtools::test(), devtools::check(), pkgdown::build_site() (per repo copilot-instructions).
- Before opening a PR, read the repo's own agent/contributor instructions (CLAUDE.md → the canonical reference it points to, e.g. `.github/copilot-instructions.md` / CONTRIBUTING) and front-load the required pre-PR housekeeping in the FIRST commit instead of discovering it via red CI.
  For R packages this means a NEWS.md entry AND a `usethis::use_version()` DESCRIPTION dev-version bump, even for a docs-only / vignette-only change --- see `r-quarto.md`'s "R-package PR CI gates" section for the full changelog-check / version-check / spellcheck / opt-out-label details.
  The concise, auto-loaded version of this rule now lives in
  [`shared/workflow/read-canonical-doc-before-starting.md`](../shared/workflow/read-canonical-doc-before-starting.md),
  wired into `CLAUDE.md` --- this bullet stays for its extra R-package specifics.
- Never commit directly to a shared/multi-project CI-infra repo's `main` --- even when confident and already validated the fix live.
  Push to a branch and open an MR for review first.
  This applies going forward; it does not retroactively require undoing an already-validated fix already on main unless the user asks.
- After an iterate loop completes, ALWAYS create follow-up issues for every deferred/acknowledged item before reporting done.
  Never leave deferred items untracked.
- When an MR/PR addresses multiple independent concerns, proactively offer to split it into separate MRs/PRs (one per concern).
  Simpler diffs = easier review, independent merge timelines, and less risk of one concern blocking another.
- When resolving a git merge/rebase/cherry-pick conflict, consolidate the best of BOTH branches --- read why each side changed the hunk and preserve both intents; never blind-pick `--ours`/`--theirs`, which silently discards the other side's work.
  Remove every marker (verify with `git diff --check`), run the repo's pre-commit checks (a merge clean on each side separately can break combined), then stage and finish the operation --- don't `--abort`/`--skip` a conflict you were asked to resolve.
  Note: "ours"/"theirs" are reversed in a rebase vs a merge.
  The `resolve-conflicts` skill (alias `rc`) operationalizes this; `sync-pr-branch`/`clean-branches`/`gii` delegate to it. (Distinct from `session-lock`/`deconflict-sessions`, which deconflicts AI *sessions*, not git content.)
- When deferring items to follow-up issues during a PR/MR review loop, always update the PR/MR description with a "Known Deferred Items" section listing each deferred issue (with link), description, and rationale.
  This gives automated reviewers context so they stop re-flagging the same items.
  Include a "Notes for Automated Reviewers" section for any recurring false positives.
- When noticing potential improvements to the codebase while working, proactively suggest them (don't wait to be asked).
  The user wants to hear about improvements as they come up.
- Always run /ums (Update Memories and Skills) after finishing a task --- don't wait to be asked.
- After a PR/MR merges, run the `post-merge` skill: verify the merge actually landed, tidy the local branch (checkout main, pull, `git branch -d`), confirm any deferred items are tracked, then run UMS to capture what the PR's review lifecycle taught --- mistakes corrected and guidance given along the way.
  A merge is the natural checkpoint to bank lessons before context is lost.
  Do all of this automatically --- including opening the follow-up branch and PR that records the lessons --- without asking permission first; opening that follow-up PR is a standing yes.
- **This applies per-merge, not once per session.** During a backlog-clearing run (many PRs merged back-to-back), it's easy to treat "run UMS after merging" as a one-off end-of-session step and batch it --- wrong: run it after EACH merge, before starting the next PR.
  Caught on sparta (2026-06-30): merged ~8 PRs in one session without running UMS once, until the user explicitly said "do ums after each merge; then keep going."
  The existing instruction already covered this; the gap was execution discipline in a fast multi-merge loop, not missing guidance --- re-read this bullet at the top of every "pick the next backlog item" cycle.
  In a multi-AGENT pipeline, UMS runs at BOTH levels: each subagent runs UMS once ITS PR merges (it stops after reporting CLEAN, so the coordinator resumes it post-merge with a "your PR merged, run UMS" nudge --- or the agent-launch spec bakes in a final UMS step), and the coordinator runs its own UMS for the cross-PR orchestration learnings no single subagent can see (merge-order sequencing, conflict-cascade handling, pipeline mechanics).
  Each agent writes its OWN memory file plus one MEMORY.md index line to keep the conflict surface small; avoid rewriting shared memory bodies concurrently. (Learned on sparta 2026-07-01.)
- Keep it simple.
  Don't over-explain or ask permission for straightforward fixes --- just do them.
- Don't re-ask a decision that's already settled and built.
  Once an answer is given and the work is implemented to match it (and CI-green), don't reopen it with a fresh AskUserQuestion --- that invites a contradictory answer you then have to reconcile, and discounts work already done.
  If you think the scope should change, say so explicitly with a recommendation instead of silently re-asking. (Learned on gha#110: re-asked content structure + deploy after the PR was built and green; the user had to reconcile the conflict with "keep what's built.")
- The reverse mistake: committing to a build on an ambiguous `config-ai`-style capability request instead of asking first, when the ambiguity is genuinely between two mechanisms that would build materially different artifacts (a passive standing rule vs. an active, invokable skill), not just two homes for the same content.
  `config-ai`'s "least mechanism" tiebreaker is for picking between forms that do the same thing more or less expensively --- it's not license to default to the cheaper reading of a verb-first request ("go through X one at a time", "sweep Y for Z"), which usually names a repeatable action (a Skill), not a preference to record.
  One clarifying question is far cheaper than a full build-and-PR cycle spent on the wrong mechanism. (ai-config#583 vs. #585, 2026-07-16: built a `CLAUDE.md` presentation rule first, then had to build the actually-requested issue-sweeping skill separately once the user said "no i meant...".)
- When finishing work on an MR/PR (clean review, ready to merge, etc.), always provide a clickable link to the MR/PR in the chat message.
- When discovering bugs in upstream/shared infrastructure (e.g., HACtions templates), always file an issue immediately --- don't ask first.
- More generally: always post a follow-up issue without asking first, in any repo we own or are a member of (a filed issue is cheap to close later if it turns out not to be helpful, so there's no real downside to erring toward filing).
  The opposite default applies to a repo we're NOT a member of --- never post there autonomously; draft it and ask the user for permission first, per the fuller upstream-contribution escalation path (`shared/workflow/upstream-issues.md`).
- Generalizing the bullets above: when a small, obvious, low-risk follow-up falls
  out of work already in progress (a two-line comment fix, a stale link, an
  accompanying NEWS bullet), just do it and report it, rather than describing it
  and asking "want me to?".
  The asking costs a round-trip per trivial change and makes me repeat the same
  answer.
  Keep asking when the choice is genuinely load-bearing: a tradeoff with no
  obviously right answer, a hard-to-reverse action, or something touching
  shared/outward-facing state.
  The test is "small and obvious", not "quick".
  (Given 2026-07-28 as "always yes", after a run of offers that were each
  accepted.)
- When I detect a concrete follow-up while working --- even outside a formal review/defer loop --- file the follow-up issue before reporting back, rather than just mentioning it in chat.
  Same owned/member-vs-external split as the bullet above: file directly in a repo we own or are a member of; in an external repo, draft it and ask the user first (`shared/workflow/upstream-issues.md`).
- Before acting on a request, review the relevant ai-config memories first so existing standing rules and prior lessons shape the response.
- When the user points out a mistake I made, fix that mistake immediately and then record the learning for future runs, without waiting for extra prompting.
- When a CI/review gate on your OWN PR keeps failing because of the repo owner's tooling (a flaky review workflow, a misfiring guard) and NOT your content, don't rabbit-hole opening fix-PR after fix-PR against their CI infra --- FIRST check whether the owner is already reworking that same infra in parallel (scan recent `main` commits and open PRs), since a fix landed under them collides with their work and is likely superseded; then verify the deliverable independently (render/lint/tests) and hand off/escalate to the owner sooner.
  Corollary --- bootstrap deadlock: you can't cleanly fix a review workflow via PRs that are themselves reviewed by that broken workflow, so such a fix lands by admin-merge, not self-certification. (Learned on rme#954: content was done+verified early, but I iterated several `gha` review-workflow PRs chasing a no-verdict gate that d-morrison was concurrently fixing via his own #201/#204.)
- Always check r-lib, tidyverse, and similar R ecosystem organizations for off-the-shelf solutions before building custom implementations.
  Prefer well-maintained upstream packages over hand-rolled code when they meet the requirements.
- When borrowing code or ideas from another repo, verify its license from the source FIRST (fetch its LICENSE file / `gh api repos/<o>/<r>/license`).
  MIT/BSD/Apache/ISC → may adapt WITH attribution recorded in a root `CREDITS.md` (keep copyright notices); no-license / "all rights reserved" → reimplement the *idea* clean-room, never copy text/code verbatim; copyleft (GPL/AGPL/MPL) → flag the compatibility consequence before copying.
  The `/scout-peers` skill encodes the full survey → license-gate → borrow-with-attribution loop.
- Before starting work on an issue/MR, always review the MR history (merged and closed) to ensure the proposed changes don't undo past progress or re-introduce previously fixed problems.
- Before building setup/infra/toolchain config in a repo, fetch origin/main and scan the repo's own reference material (e.g. `references/`, `docs/`) and recent main commits for an existing or just-merged solution --- build on / align with it rather than a parallel, possibly contradictory approach. (Learned after drafting a juliaup-based Julia install that conflicted with the repo's reviewed curl+tarball cloud-setup reference.)
- Always simplify code where feasible (without feature loss) --- prune dead code paths, remove unreachable branches, simplify variable assignments that can never take their fallback values given the current invocation context.
- When fixing a bug or a fragile/duplicated pattern, grep the WHOLE repo for sibling instances and fix them all in one pass --- don't patch only the occurrence you happened to notice.
  Otherwise a reviewer flags the missed copies as a separate finding, costing an extra round. (Learned on d-morrison/ai-config#45: the `git -C ~/.claude/skills` path fix was applied to `ums/SKILL.md` but the identical line in `skill-builder/SKILL.md` was missed until review caught it.)
- When renaming a variable or concept, grep for the old term in **both code and comments** (including section headers, file-level comments, and inline `# ---` banners).
  A variable rename that also appears in a section header (`# --- 2. Baseline covariates + Nelson-Aalen ---`) costs an extra ARDI round every time the header is missed.
  After changing the identifier, run `grep -r "old_name" .` before committing. (Learned on ucdavis/bcs#246: `nelson_aalen` → `cumhaz_baseline` fixed the variable and the file header but missed the section header --- caught two ARDI rounds later.)
- When removing decorative comment banners (e.g. `# ---...---` / `# Name #` blocks), scan for **every** occurrence in the file --- both file-scope banners and inner function-body banners.
  Removing only the outer ones leaves the inner ones, and a reviewer catches the inconsistency as a separate finding.
  Run `grep -n "^[[:space:]]*#[[:space:]]*[-=*_#]" file` to surface padded/decorated banner lines before committing. (Learned on d-morrison/ai-config#274: outer banners stripped in round 1, inner ones missed until round 2.)
- Do not commit scratch test files that are not wired into CI.
  A file like `test_fix.py` with a dead `sys.path.insert` at the top and no pytest/CI integration adds noise without value and costs an extra ARDI round.
  Delete it before the initial push, or as soon as a reviewer flags it. (Learned on d-morrison/ai-config#274.)
- In test code, express date intervals with lubridate rather than hardcoded day counts.
  Use `lubridate::years(N)` + date arithmetic for calendar-year intervals from a known start date, or `lubridate::dyears(N)` when an exact numeric duration (`N x 365.25 x 86400` seconds) is what the function under test expects --- `years()` returns a Period, `dyears()` returns a Duration; pick the one that matches the semantics.
  Only fall back to a raw day count when the function requires one; verify it via `365.25 x N`, not by counting leap years manually (e.g., "3 leap years in 2000-2003" is wrong --- only 2000 qualifies), and confirm with `lubridate::time_length(lubridate::ddays(days_exact), "years") == N` (`time_length()` requires a timespan object, not a bare numeric). (Learned on ucdavis/bcs#249: using lubridate directly avoids the error class entirely.)
- When writing documentation in a stacked PR (or any branch), only document features whose code is actually present on the CURRENT branch's ancestry --- `grep` for the symbol/constant first.
  A feature that lives in a sibling branch also targeting `main` is NOT in scope, even if conceptually related; documenting it reads as a hallucinated feature and a reviewer will flag it.
  Move those docs to the branch where the code lives. (A specific case of "NEVER assume; ALWAYS verify" above.)
- Reference material derived from a repo's own code constants --- tables of values, spawn layouts, file-format/API semantics --- belongs in THAT repo's docs next to the code, not in central `ai-config` memory.
  A memory copy rots silently when the constants change (nobody editing the game/library code thinks to update a memory in another repo) and isn't discoverable by human contributors.
  Keep the durable *lesson/gotcha* in memory and point at the in-repo docs for the tables. (Learned splitting a sparta scenario cheat-sheet: the lesson "team 0 is stationary by default" now lives in sparta's `CLAUDE.md`; the speed/UID/order-target tables live in sparta's `demos/README.md` + `REPLAY.md` --- ai-config#1 / lacaedemon/sparta#207.)
- Avoid nested function calls and nested function definitions where feasible --- prefer named intermediate variables (or a pipe, e.g. `|>` / `%>%` in R) over `f(g(h(x)))`, and prefer top-level function definitions over functions defined inside other functions.
  Keep the nesting only when flattening it would be more convoluted. (CLAUDE.md "Coding style" section has the full rationale.)
- Follow the SERG lab manual (https://ucd-serg.github.io/lab-manual/) for coding and collaboration conventions.
- When mentioning GitLab/GitHub pipelines, jobs, or commits in prose, always hyperlink them:
  - Pipelines: `[#3330](https://host/project/-/pipelines/3330)`
  - Jobs: `[job 11056](https://host/project/-/jobs/11056)`
  - Commits: `[320d7ad](https://host/project/-/commit/320d7ad)`
- When linking to MRs/PRs, link to the bottom of the page so the user doesn't have to scroll:
  - GitLab: use a specific note anchor (e.g., `#note_11437`); there is no symbolic "latest" anchor
  - GitHub: use a specific comment anchor (e.g., `#issuecomment-4739921085`); there is no symbolic "latest" anchor
- When stopping work on an MR/PR (end of conversation, pausing, handing off), always post the MR/PR link so the user can click through immediately.
- When the user provides general guidance or a new preference, always update BOTH the relevant skills AND `/memories/preferences.md`.
  Skills encode the behavior; preferences ensure it persists and is visible across all contexts.
  When the same rule lives in two copies (an expanded one in `CLAUDE.md`, a terse one in `preferences.md`), keep load-bearing qualifiers/caveats consistent across both --- the short copy is the one that most easily drops a qualifier and becomes misleading. (Learned on PR #43: the terse pipe-examples bullet dropped the "in R" qualifier that `CLAUDE.md` had, which a reviewer flagged as implying `|>` / `%>%` exist in Python/JS.)
- Before adding a bullet that redefines or narrows an existing term (fully clean, claim-pr, ARDI, etc.), grep the repo for that term's OTHER canonical definitions --- not just the twin preferences.md/CLAUDE.md copy above, but any `shared/*.md` fragment, skill doc, or other memory file that states the same rule.
  If the new rule is a genuine refinement, update the canonical doc itself in the same PR, not just a satellite copy; note in the PR description that the canonical file is touched and why. (Learned on sparta 2026-07-01, PR #318: a new `dont-merge-failing-workflows` bullet expanded "fully clean" CI to mean every workflow green, including non-gating checks --- but silently contradicted the canonical `shared/workflow/fully-clean.md` [`@`-included into `CLAUDE.md`], which still said "every required check."
  The `@claude` bot review caught the drift in round 1.)
- After adding or updating skills OR memory files in the ai-config repo, always commit and push everything to origin (on the current branch if a PR is already open, or create a new branch + PR if the change is out of scope).
  Never leave ANY changes in ai-config as local-only uncommitted edits --- including memory files.
- **AI memories, skills, and commands never stay local-only.**
  That covers session memory and auto-memory as well as local-only files:
  a scratchpad is not a home, so anything worth keeping must be committed and
  pushed.
  When I capture a durable learning, commit it to the right repo via PR --- GENERAL/cross-project learnings go to `Morrison-Lab/ai-config` (as bullets in the right `memories/*.md` topic file);
  PROJECT-SPECIFIC learnings go to that project's own repo (its `CLAUDE.md` / agent docs / `.claude/memories/`).
  A memory kept only under `~/.claude/projects/<path>/memory/` or `~/.codex/memories/` is invisible to other sessions, machines, and humans, and rots silently --- so migrate it.
  Capturing a learning isn't done until it's committed where the right audience will see it.
- **A migrate-then-delete cleanup (copy content into a repo, THEN delete the local source) must verify the copy is both COMPLETE and CURRENT before deleting --- not just that it exists.**
  A migration commits a point-in-time snapshot, but the local source keeps evolving, so a copy made days earlier can be missing later edits --- or carry a policy the source has since reversed.
  Diff each file against the merged target before deleting it.
  And fact-check the migrated CONTENT against current repo state, because copying preserves stale claims verbatim: a memory paragraph can describe a bug as still-open (naming a since-removed function) when a later PR already fixed it and closed the issue.
  (ucdavis/bcs#427, 2026-07-24: of 7 migrated memory files, 4 had newer local content the repo lacked --- one carried a superseded `--exclude=c1` policy --- and a "still-open #371" paragraph was wholly obsolete, since #377 had fixed it and closed #371. Diffed every file and checked the issue/code state before deleting the 15 local copies.)
- In Codex sessions, treat `Morrison-Lab/ai-config` as the canonical home for cross-project memories even if a local `~/.codex/memories/` store is present.
  The local store is not the durable source of truth; if ai-config access is missing from the environment, restore access first rather than writing the memory only locally.
- When committing, stage the SPECIFIC files you touched --- NEVER `git add -A`.
  The working tree often holds unrelated in-flight edits (the user's own UMS/skill commits, another draft); `git add -A` silently sweeps those into your commit and onto your PR, bloating the review and extending the cycle.
  List paths explicitly, and `git status` before committing to confirm only intended files are staged. (Learned the hard way: a `git add -A` swept the user's `scout-peers` skill into an unrelated `/prune` PR, adding several extra review rounds.)
- **Always use a worktree; never the primary checkout.**
  Every local session --- including gi/gii/ardia, simple single-file edits, and reads that will become writes --- starts by creating a dedicated worktree.
  **Do:** `git worktree add -b <branch> ../ai-config-worktrees/<branch> origin/main` (or per the `session-lock` skill's `ai-session.sh worktree <branch>`) before any read or write, and clean it up after merge with `git worktree remove`. (Learned when a concurrent session deleted a freshly-written, still-untracked skill file from the wd.)
  **Don't:** work directly in the shared/primary checkout, even for "just a quick read" or "just one file" --- reads often become writes, and the primary checkout is shared with concurrent sessions.
  This default holds for EVERY local session, not just substantial multi-file work or when the user flags the wd as "in use" / "do this in a separate repo", so parallel local AI agent sessions never step on or clobber each other's working directory or branch state.
  The ai-config working copy is often in use by CONCURRENT local AI agent sessions.
  Untracked or uncommitted files there can be silently wiped by another session (branch switch / `git clean`).
  Create it off `origin/main` (`git worktree add -b <branch> ../ai-config-worktrees/<branch> origin/main`), not the shared wd.
  Clean it up after merge with `git worktree remove`. (Learned when a concurrent session deleted a freshly-written, still-untracked skill file from the wd.)
  The `session-lock` skill (alias `deconflict-sessions`) tooling automates this: `ai-session.sh worktree <branch> [--base origin/main]` creates the isolated worktree, `register`/`check` surface collisions, and the registry under `.git/ai-sessions/` lets parallel sessions see each other before they clobber the shared checkout.
  This applies to EVERY repo, not just ai-config --- bcs and the other work repos are checked out as worktrees too, and a concurrent agent may rely on a given checkout staying on its current branch.
  Use ONE worktree per branch/PR: don't `git checkout` a *different* branch inside an existing worktree (or the shared checkout) to move between several in-flight PRs --- that silently changes the branch out from under any other session or task pointed at that path.
  Spin up a separate worktree per PR instead (`git worktree add`), even when you're already inside a worktree. (Learned on bcs, 2026-07-08: hopped a single worktree's branch across three open PRs and switched the ai-config checkout's branch mid-task --- both risk clobbering a concurrent agent.) (Reinforced as a correction, 2026-08-19: the user issued `\cai always use a worktree; never the primary checkout` after observing the primary checkout being used instead of a worktree.)
- **Don't touch anyone else's branch.**
  **Do:** only push to or modify branches I created in my own worktree.
  **Don't:** push commits, force-push, checkout, or edit branches belonging to another session or user --- even if the content looks worth keeping or the branch looks abandoned.
  If a branch needs work that isn't mine, flag it and let the owner handle it. (User directive, 2026-08-19.)
- **A delegated subagent runs in the parent session's working tree, so the "Use ONE worktree per branch/PR" rule above governs your own agents, not only other sessions.**
  The remedy is already written down: [`gip`](../skills/gip/SKILL.md) says to
  give every subagent `isolation: "worktree"`, and
  [`ultracode-merge-conflicts`](../shared/workflow/ultracode-merge-conflicts.md)
  assumes the same parameter.
  Both frame the hazard as agents colliding with **each other** across a
  fan-out, though, so the rule reads as inapplicable when you launch exactly
  one agent and it has no siblings to collide with.
  It is not.
  The parent is a colliding party too, and a lone agent is fully exposed to the
  parent's own `git checkout` or cherry-pick in the shared checkout.
  An agent you launched also reads as part of your session rather than as a
  separate consumer of that checkout, which is why switching branches
  underneath it does not feel like switching branches out from under anybody.
  Nothing errors when you do.
  Every read the agent resolves through `HEAD` --- the working tree, the index,
  and `git show HEAD:<file>` alike --- silently becomes an answer about your
  branch instead of its own.
  The symptom is the expensive part: `git show HEAD:<file>` returns the
  pre-edit text, which is indistinguishable from the agent's own commit having
  been reverted, so it may redo finished work or report the work as lost, and
  both readings are wrong.
  Note what that command is **not**, because the obvious remedy does not fix
  it: `git show HEAD:<file>` already reads a committed blob and never touches
  the working tree, so switching from the tree to a commit changes nothing.
  What moved is the **ref**.
  `HEAD` follows the parent's `git checkout` or cherry-pick; a branch name does
  not.
  So name the branch --- `git show <its-branch>:<file>` and
  `git ls-remote origin <its-branch>` are unaffected by whatever `HEAD` now
  points at.
  - **Do:** pass `isolation: "worktree"` for a single delegated agent that will
    commit or change branches, not only for a fan-out of several.
  - **Do:** answer a suspected revert from the branch ref and the remote.
  - **Don't:** change branches in a checkout one of your own subagents is
    using, on the grounds that it is your session.
  - **Don't:** read a working tree that disagrees with a commit you just made
    as evidence the commit did not happen.
  (2026-07-31, ai-config: a subagent committing in `/home/user/ai-config` had
  the parent cherry-pick onto a new branch in the same checkout mid-run.
  The agent then read `git show HEAD:<file>` as its edits reverted, while its
  commit `8cc7ae3` in fact carried both files it had touched and its branch ref
  and `origin` both pointed at it.
  No `isolation` argument had been passed, which is the whole cause.)
- **That remedy has a precondition nobody states: `isolation: "worktree"`
  needs the *session's own cwd* to be inside a git repository, so it errors in
  a session whose cwd merely holds repos as subdirectories.**
  The Agent tool refuses with `Cannot create agent worktree: not in a git
  repository and no WorktreeCreate hooks are configured.`
  Both clauses of that message are separate preconditions, and a harness can
  fail the first while providing nothing to satisfy the second.
  The rule is not wrong, it is stated without its precondition, in both places
  a reader meets it: the bullet directly above, and
  [`gip`](../skills/gip/SKILL.md)'s "give **every** subagent
  `isolation: "worktree"`".
  Read as written, each prescribes a parameter that errors here, which invites
  the reader to conclude isolation is unavailable and share the checkout after
  all -- the exact outcome the bullet above exists to prevent.
  The explicit fallback gives identical isolation for two commands, so reach
  for it rather than standing down:
  `git -C <repo> fetch origin <default-branch>`, then
  `git -C <repo> worktree add --detach <path> origin/<default-branch>`.
  Resolve `<default-branch>` from the repo rather than assuming `main`, the way
  [`gip`](../skills/gip/SKILL.md)'s step 0 and [`ums`](../skills/ums/SKILL.md)
  both already do: hard-coding it dies with
  `fatal: invalid reference: origin/main` wherever the default is `master` or
  `develop`, which is precisely where a fallback is worth having.
  Each part of that pair is load-bearing, and the naive spelling
  `worktree add <path> <default-branch>` is wrong in more than one way at once.
  Use `git -C` rather than `cd`, because Bash's cwd persists across separate
  calls in a session, so a `cd` here silently carries into later ones.
  Name `origin/<default-branch>` rather than the bare branch, because a branch
  is meant to live in one worktree: `add <path> <default-branch>` refuses
  whenever that branch is checked out anywhere, which is this corpus's own
  session-start state, and which after the first subagent is every later one in
  a fan-out.
  Worse, that guard is not atomic, so a genuinely concurrent fan-out can slip
  several worktrees onto that one branch at once and lose the isolation with no
  error at all -- the loud refusal is the good outcome here.
  That same substitution fixes the stale-base trap in one stroke, since
  `fetch origin <default-branch>` advances the remote-tracking ref while
  leaving the local branch where it was.
  And prefer `--detach` over a plain `-b <slug>`, because creating a branch
  *that tracks* a remote ref writes upstream config under a `.git/config` lock
  that concurrent subagents lose races on; the agent cuts its own branch inside
  the worktree afterward, which is what its brief already tells it to do.
  - **Do:** create the worktree explicitly with
    `git -C <repo> worktree add --detach <path> origin/<default-branch>` when
    `isolation: "worktree"` errors, and brief the agent with that path.
  - **Do:** base it on `origin/<default-branch>`, which sidesteps the
    already-checked-out refusal and the stale local base at the same time.
  - **Don't:** name the bare branch -- sequentially that refuses from the
    second agent onward, and concurrently it can silently share one branch
    across several worktrees instead.
  - **Don't:** hard-code `main` in either command, which dies outright on a
    repo whose default branch is named anything else.
  - **Don't:** read the isolation error as "isolation is unavailable here" and
    let the agent share the parent's checkout.
  - **Don't:** infer that the session's cwd is a repository from the fact that
    the work is in one -- a cwd holding several repos satisfies neither clause.
  (2026-08-01, this session: `git rev-parse --show-toplevel` in the default cwd
  `/home/user` returns `fatal: not a git repository`, with `ai-config`, `gha`,
  `qbt`, `qwt`, `rpt`, and `workflows` one level below it, and no
  `settings.json` exists at `~/.claude/` or `/root/.claude/` -- so both named
  preconditions are independently false here.
  The error text is quoted from the parent session's own attempt; this agent
  has no Agent tool and did not re-run it.
  The stale-`main` half was hit directly: `git worktree add /tmp/wt-ums main`
  checked out `a30a2e1` while `origin/main` was five commits ahead at
  `d0994c2`.
  The command shape was then measured on git 2.43.0, five worktrees per run
  against a throwaway repo whose local `main` sat five commits behind
  `origin/main`.
  `add <path> main` scored 0/5 with `main` checked out and 1/5 with it free,
  the rest refusing with
  `fatal: 'main' is already used by worktree at ...`.
  Run **concurrently**, as a fan-out actually launches, that guard races: three
  or four worktrees landed on `main` at once in every one of six rounds, a state
  the sequential path refuses outright.
  Nothing errors, and the isolation is gone -- one worktree committed, the next
  immediately read `main` at that new commit and stacked on top of it, which is
  the collision the parameter exists to prevent.
  `add -b <slug> <path> origin/main`, the form review suggested, scored 5/5
  sequentially but failed in four of five concurrent rounds with
  `error: could not lock config file .git/config: File exists` beside
  `unable to write upstream branch configuration`.
  `--detach` and `-b <slug> --no-track` each scored 5/5 in all five concurrent
  rounds, and the full flow -- detach, `checkout -b`, commit, five at once --
  scored 5/5 in three more, every worktree based on `origin/main` rather than
  the stale local ref.
  Those runs all used a repo whose default branch is literally `main`, which is
  why they are written that way here and why they did not surface the
  hard-coding: measured separately against one whose default is `develop`,
  `fetch origin main` returns `fatal: couldn't find remote ref main` and
  `worktree add --detach <path> origin/main` returns
  `fatal: invalid reference: origin/main`, while both succeed against
  `origin/develop`.)
- Bash's cwd PERSISTS across separate calls within a session (it does not silently reset between calls) --- so a `cd` in one call carries forward into the next unless a later call `cd`s elsewhere.
  This one mechanism causes two mirror-image mistakes depending on the session's layout:
  - **Session runs INSIDE a worktree:** do NOT prefix git commands with `cd <main-checkout>`.
    Because cwd persists, that `cd` doesn't just affect the current call --- any *later* call that omits its own `cd` stays in the main checkout too, silently working against a different branch (often another session's) instead of your worktree.
    Run git in the worktree with no `cd` at all; if you must touch another checkout, use `git -C <path>` instead of `cd`-ing into it.
    `gh` commands keyed by PR or issue number are cwd-agnostic, so only `git` breaks.
    Run `git branch --show-current` before committing or pushing to confirm.
    Learned on PR #62: a `cd`-prefixed push hit `main` and made my own worktree commits look missing.
  - **Session juggles several full (non-worktree) repo checkouts side by side:** a call with no `cd` silently runs against whichever repo an earlier call last `cd`'d into, not the repo you mean this time.
    Never omit an explicit `cd <repo>` in any Bash call when more than one repo checkout is in play, and re-verify with `pwd` or `git remote -v` after any call whose target repo matters.
    This bites hardest in back-to-back "same shape, different repo" calls (e.g. an identical empty claim-commit pushed to two sibling PRs one after another) --- the second call looks correct in isolation but silently repeats the first call's repo.
    Caught it by checking `mergeable_state` output afterward; recovery was a `git reset --hard` to the last-good local commit plus `git push --force-with-lease` to undo the wrong-repo push before redoing it with an explicit `cd`. (Learned on ai-config#454/gha#215: an empty commit meant for `gha` landed on `ai-config`'s branch instead.)
- Before pushing skill/memory changes to ai-config, run the local checks that `validate.yml` runs in CI --- at minimum `python3 scripts/validate-skills.py` and `python3 scripts/check-links.py`, for frontmatter and broken-relative-link errors --- before they cost an ARDI round.
  Derive the full list from `.github/workflows/validate.yml` rather than from this bullet, which named only those two while the job had grown well past them.
  The `scripts/test_*.py` steps are the half most easily skipped and the half that actually gates: several of them assert against the **live** corpus, so an edit elsewhere in the repo can turn one red without touching its subject.
  Running a production script is not running its test, and an "advisory" script can have a hard-gating twin in the same job --- see `memories/tools.md` on `check-context-closure.py` for the instance where editing `CLAUDE.md`'s `@`-import list is what trips it.
- When creating a new acronym/short-name skill (e.g., `gi`, `sup`, `ums`), always also create a spelled-out alias skill (e.g., `grab-issue`, `send-upstream`, `update-memories-and-skills`) that points to the canonical file.
- Some skills are platform/global --- present in the Claude Code skill registry but with NO local `skills/<name>/` directory (e.g. `deep-research`).
  Cross-references to them are valid.
  Automated reviewers (Copilot, the `@claude` bot) may wrongly flag such a reference as a "non-existent skill"; check the available-skills list presented to the agent (the Claude Code skill registry) before treating a skill cross-ref as a broken link, then rebut the false positive. (ai-config#120 flagged it 4x.)
- **Do not request Copilot code review on any PR, in any repo, until September 2026.**
  Standing maintainer directive, restated and widened to all repos on 2026-08-19.
  It outranks `hooks/no-unreviewed-pr.py` and `shared/workflow/pr-on-claim.md`'s request-the-reviewer step.
  State the directive as the reason when a PR ships without one, and re-verify at the expiry.
  Full statement, measurements, and Do/Don't pair: [`github.md`](github.md), "Restated and widened 2026-08-19".
- Per [`copilot-review-before-human.md`](../shared/vendored/copilot-review-before-human.md), request AI review (`@claude review` / `@agy review`) after completing code pushes, and do NOT request human review until after the AI review produces a clean/approved verdict (or an impasse/deadlock occurs).
- During ARDI loops: if a round has only Rebut/Defer dispositions (no code pushed), still explicitly re-request review --- the push won't auto-trigger the reviewer bot.
  BUT the converse: when a round DID push code, the push already triggers the review workflow --- do NOT also post "@claude review again".
  On workflows with `concurrency: cancel-in-progress` (d-morrison/gha) the two runs cancel each other, leaving the latest commit with a canceled, never-posted verdict.
  If a review ends up canceled with no comment, check first whether a newer run for the **same PR** is already in flight --- a retry cancels it, and it may be a review a human just requested --- and dispatch only when nothing is running: `gh workflow run claude-review.yml --ref <PR-branch> -f pr_number=<N>`.
  Attribute in-flight runs to a PR from each run's own `gather-context` log.
  `gh run list` reports `main` as the branch for every dispatched review.
  Always pass `--ref`: a dispatch without it runs against the default branch, so the run's check runs land on `main`'s tip rather than the PR head --- which leaves the PR's own review check stale and makes a check-runs query at that head a vacuous all-clear about whether a review is in flight.
  See [`review-verdict-pitfalls`](../shared/workflow/review-verdict-pitfalls.md)'s "A `cancelled` review is the one case where retrying is the cause rather than the remedy".
- During ARDI loops: when waiting for long-running review workflows (`claude-review.yml`, `@claude` review, or CI checks), set a background timer (`schedule` tool with `DurationSeconds=180` or `300`) before ending the turn so you automatically wake up to check for review completion rather than sitting idle until the next user message.
- During ARDI loops: always ANTICIPATE what the reviewer will flag next and fix those issues preemptively in the same commit.
  Don't wait for each round to surface issues one at a time --- read the code holistically, think about what patterns the reviewer has flagged in prior rounds (documentation gaps, coupling without cross-references, missing edge-case guards, inconsistent accounting), and fix analogous issues elsewhere in the same file before pushing.
  The goal is to minimize back-and-forth rounds.
- When a PR's own body states a blocking dependency ("draft, blocked on sibling-repo PR #N landing first"), that sentence is a claim about the PR's *actual* state, not just a note to the reader --- verify the PR really is in that state (draft, not marked ready) before moving on, don't just describe the constraint in prose and leave the PR ready/open regardless.
  Caught by the `@claude` reviewer (twice, once inline and once in the full verdict) after a companion PR was opened ready-for-review while its own body said "blocked, should stay draft" --- the citation it made to a sibling-repo file genuinely 404'd on that repo's `main` because the dependency hadn't merged yet.
  Fix pattern once caught: convert back to draft, reword any forward-looking citation to something that stays accurate regardless of merge timing (e.g. "proposed in #N --- once merged, lives at `path`" rather than asserting the path already resolves), then flip back to ready and re-verify the citation resolves once the dependency actually merges. (Learned on ai-config#454/gha#215.)
- During ARDI loops: only stop iterating (without consensus) if you're at a literal impasse --- going in circles, redoing and undoing the same changes.
  New nits each round is NOT an impasse; keep addressing them.
  **There is no round limit, and "asymptotic noise" is an anti-pattern rather than a signal.**
  Always request another review. Stop only on a totally clean review, on every remaining item being escalated to a human (nothing actionable left), or on me saying stop --- never on a round count, and never by asking whether to accept the current state.
  A deadlock on ONE item does not stop the loop: escalate that item and keep driving the rest.
  That question fires on how many rounds have passed rather than on what the findings are worth, and it reads as diligence, which is why it goes unexamined.
  (Purged from the corpus in ai-config#1030 after ai-config#1029 ran six rounds producing 23 real findings, with rounds 2-6 each finding bugs in earlier rounds' own fixes; the loop stopped to ask twice under the old guard, both times the answer was to keep going, and the next round found four more real bugs. Rationale and case record in `skills/ardi/SKILL.md`, "Stopping conditions".)
- **Every mistake owes a HOOK, not just a recorded learning.** When I get something wrong, ask whether a condition decidable from the transcript would have caught it, and write the hook if so.
  A prose rule is consulted at read time and broken at composition time, so re-reading it never reaches the moment it breaks --- every mistake in the 2026-08-02 session already had a rule covering it, and the rule is what failed.
  Model a message that is wrong to send on `hooks/no-offer-to-file.py` (a `Stop` block); model an obligation that follows a message which is right to send on `hooks/remind-ums-after-error.py` (a `UserPromptSubmit` injection).
  Never block an error admission --- admitting stays free and immediate, and only the follow-up is owed.
  Not every mistake is mechanizable: a one-off factual slip or a judgment call has no decidable condition, and a hook invented for one misfires and gets switched off, taking the real cases with it.
  Saying plainly that a mistake is not mechanizable, and why, discharges this.
  This is separate from the UMS pass an error already owes: that records the learning, the hook prevents the recurrence, and both can be owed at once. (`cai`, 2026-08-02; implemented as `hooks/no-mistake-without-a-hook.py`, which is the rule applied to itself.)
- **A new enforcement hook always ships with its test in the same change before pushing.**
  When authoring or modifying a hook in `hooks/`, create its companion regression suite `hooks/test-<name>.py` in the same commit and run `python3 scripts/test_hooks.py` before pushing.
  Shipping a hook without its test fails the runner's subject-to-test coverage check in CI and pre-commit; keeping the subject and test tightly coupled ensures new guards and their behavioral assertions land together. (ai-config#1616: `no-unshipped-commit.py` reached a PR before its test suite was written.)
- Keep the bot's `@`-mention trigger phrase OUT of PR/issue comment prose unless you actually intend to dispatch.
  The `issue_comment` trigger fires on the bare mention ANYWHERE in a comment --- even in a sentence saying you're NOT triggering a review (e.g. an ARD summary noting "not posting [the mention]").
  A stray mention spawns a run that cancels the push-triggered review on `cancel-in-progress` setups.
  On the d-morrison/gha mention bot it also starts a session whose residual-commit sweep can churn the branch.
  Refer to it obliquely ("re-request review", "the review-trigger mention") or split the tokens (e.g. `@ claude`, with a space). (Learned the hard way on ai-config#41; ardi/iterate/ard carry the warning.)
- Don't ping EXTERNAL people or repos from our OWN repo's PR/issue/commit/comment text.
  An `@username` for a non-team person (e.g. an upstream maintainer) sends them a GitHub notification, and the `owner/repo#number` shorthand for an external issue posts a cross-reference backlink onto THEIR issue.
  Both reach into a repo we shouldn't be touching.
  Refer to external people by plain name ("a Quarto collaborator") and external issues by a full URL link --- never `@name` or `owner/repo#num` --- reserving those forms for our own team and repos. (ai-config#246: the PR body `@`-mentioned `mcanouil` and the commit used `quarto-dev/quarto-cli#NNNNN`, both pinging the very upstream repo the PR was meant not to disturb.)
- When writing prose (a PR/issue comment, commit message, chat reply) that references an issue or PR in a DIFFERENT repo than the one you're posting in, always disambiguate with the full `owner/repo#N` form --- never a bare `#N`.
  GitHub silently resolves a bare `#N` to the CURRENT repo, so `#156` typed in an ai-config PR comment links to ai-config#156 even when you meant a different repo's #156.
  This is a correctness bug (a dead or misleading link), distinct from the notification-etiquette rule above (which governs whether `owner/repo#N` is appropriate to use AT ALL for a given repo, e.g. avoid it for external repos you shouldn't ping).
  Once you've established that a cross-repo reference is otherwise fine to make, still spell out `owner/repo#N` in full --- don't drop to the bare form just because it reads shorter. (ai-config#304: `fxtas#156`/`fxtas#157` written as bare `#156`/`#157` in an ai-config PR comment auto-linked to ai-config#156 instead of ucdavis/fxtas#156.)
- While I'm iterating a PR, the `@claude` bot (triggered by an `@claude` comment --- including one I or the user posts mid-loop) runs its OWN ARD and pushes fix commits to the SAME PR branch.
  Before every edit/push during a PR loop, `git fetch` and reconcile `origin/<branch>`: sync to the bot's commit and don't redo fixes it already landed.
  Two Claude sessions on one branch is the parallel-session collision `claim-pr`/`session-lock` warn about. (ai-config#120: the bot fixed 3 of 4 findings while I worked the same branch.)
- A *suggested fix* (a `suggestion` block or proposed code) from any reviewer --- human or bot --- can itself be wrong --- verify it before applying; don't paste it in blind.
  Check it handles the general case, not just the one flagged spot.
  If the correct fix differs, apply that and say so in the ARD reply so the reviewer sees why you diverged. (ai-config#94 round 2: a suggested regex `[>|][-+]?` would have blanked every inline `description:` --- the very round-1 bug under review; the right fix kept the block indicator optional, `[>|]?[-+]?`.)
- In R/Quarto/Rmd prose, prefer inline R expressions (`` `r ...`
  ``) over hard-coded numbers that came from the analysis (means, counts, p-values, sample sizes) so the text never goes stale on re-render.
  Hard-coded literals are fine for genuine constants (a chosen threshold, a year).
  Example: [ucdavis/bcs#191 review comment r3437005734](https://github.com/ucdavis/bcs/pull/191/changes#r3437005734).
- When adding or changing math (LaTeX/Quarto equations --- `$...$`, `$$...$$`, `\begin{equation}`, `\(...\)`), always verify it actually RENDERS --- open the rendered HTML page and confirm the equation displays, not just that the build succeeded.
  A typo in a macro can silently break MathJax while the build still passes.
  For rme, open your PR's preview page --- e.g. `https://d-morrison.github.io/rme/pr-preview/pr-<N>/chapters/proportional-hazards-models.html` (the `pr-<N>` previews are per-PR and get deleted when the PR closes, so `<N>` is a placeholder for your PR number). (An instance of never assume; always verify, applied to math.)
  - **In a remote/web sandbox the github.io preview may be unreachable** --- if the environment's network policy blocks `d-morrison.github.io` the proxy answers `403` to CONNECT (curl: `CONNECT tunnel failed, response 403`; Chromium: `ERR_TUNNEL_CONNECTION_FAILED`), so you can't load the preview to eyeball the math.
    Verify locally instead: `npm i mathjax` (npmjs is allowed through the proxy), then init MathJax **with the `[tex]/noundefined` extension loaded** (`init({tex:{packages:{'[+]':['noundefined']}}}).then(MJ => MJ.tex2mml(defs + expr))`) and check the output.
    With `noundefined` an undefined macro shows as `<mtext mathcolor="red">\cmd</mtext>` (NOT an `<merror>` or a thrown exception), so grep for `mathcolor="red"`.
  - **MathJax ignores `\providecommand`** --- only `\newcommand` / `\def` / `\renewcommand` define a macro.
    So `\providecommand{\X}{...}` is a *silent no-op* whenever `\X` shadows a LaTeX built-in (`\v` caron, `\b` bar, `\u`, `\c`, …): the built-in meaning survives and renders broken (rme's `\hat{\v{\mu}}` showed a red `\v`).
    Use `\vec` / `\vecf` (rme defines these with `\renewcommand{\vec}{...}`, which properly overrides the built-in), and fix upstream by switching `\providecommand` → `\def`/`\renewcommand` for built-in names.
- In Quarto, a cross-referenceable figure/table **div** (`::: {#fig-...}` / `::: {#tbl-...}`) uses its **last paragraph** as the caption --- the caption text must come AFTER the image / code chunk / table, not before it.
  A caption placed first renders as ordinary body prose and the float is left uncaptioned.
  Same rule for both `#fig-` and `#tbl-` divs; for a bare pipe/markdown table, put the caption below it with the `: Caption {#tbl-...}` syntax.
  Also: don't give the code chunk *inside* a `#fig-`/`#tbl-` div a `fig-`/`tbl-`-prefixed `#| label:` --- that registers a second, redundant cross-reference id.
  Give the enclosed chunk a plain label and let the div own the `@fig-`/`@tbl-` reference.
  Refs: <https://quarto.org/docs/authoring/figures.html#figure-divs>; ucdavis/bcs#220, #223.
- When a memory, skill, or doc entry points at a location in *another* file, don't cite a specific line number --- it goes stale the moment that file changes, and a later reader who looks it up comes up empty.
  Quote the section heading or symbol name (e.g. the `## Foo` heading) or use a vaguer reference instead.
  This shares the same root principle as the inline-R-expressions rule above: don't bake a volatile value into prose.
  The same goes for ephemeral example URLs --- PR-preview deploy links and PR numbers get deleted or superseded when the PR closes; parameterize the ephemeral part (`pr-<N>`) rather than hardcoding it. (ai-config#135 review: a `debugging.md` note cited `scout-peers/SKILL.md` lines 156/183, which #132's `bfc17ee` had already removed. ai-config#155 review: a hardcoded `pr-772` rme-preview URL was flagged --- ironically inside the new "verify math renders" rule, the very kind of stale-value-in-prose the rule warns against.)
- Always leave yourself handoff notes proactively when pausing --- don't wait to be asked --- especially while a long-running job is in flight (SLURM arrays, builds, CI, background tasks, remote agents).
  Snapshot branch/HEAD, unpushed commits, job IDs + how to check status, expected outputs + paths, backups, open decisions, and the exact pick-up steps into a project memory, and post a paused-state note on any active PR/MR.
  The flip side --- READ before takeover: when taking over an in-flight PR someone else (a colleague or another session) started, scan the PR's comments for a handoff note FIRST, before checking out, editing, or re-reviewing.
  The branch shows only pushed commits; a handoff note captures the out-of-band state (uncommitted files, env changes, "reran X locally but didn't commit renv.lock", "what remains is to render Y") that you'd otherwise miss and either redo or break.
  `gh pr view <N> --json comments`, look for a "Handoff note" / "State as of ..." comment (usually from the PR author), follow its "What remains" list, and respect its local-only caveats.
  See the `handoff` and `wait-for-results` skills.
- Cancel superseded or stale SLURM jobs proactively --- don't let a job that's been replaced keep running unused.
  When a job is superseded (a job-array approach replaces a single-node run, or a resubmit makes an earlier job redundant), `scancel <jobid>` the old one immediately rather than waiting for it to finish on its own.
  Whenever submitting a replacement or successor job, check `squeue -u $USER` for older runs covering the same workload and cancel them. (Learned on ucdavis/bcs: an old single-node true-effects run sat running 2+ hours unused before the user asked to cancel it.)
- Always look for opportunities to create new reusable skills from multi-step processes.
  When a workflow emerges that could be codified, proactively suggest creating a skill for it. (see the `spot-skill-opportunities` skill --- the continuous recognition step that hands off to `skill-builder`.)
- When asked to build/create a new skill, FIRST check whether an existing skill should be extended instead --- search `skills/` for an adjacent one AND scan ALL branches (`git ls-tree` over every remote branch) for in-flight similar work --- before scaffolding a new one.
  Prefer extending (a new alias/section/trigger) over a near-duplicate skill; if another branch is already building it, continue that work rather than opening a colliding branch. (see the `skill-builder` skill.)
- "slide <tag>" means force-move a floating Git tag to current main HEAD (delete + recreate + push).
  Common for repos with floating major-version tags that consumers reference.
- Use the `session-lock` skill (alias `deconflict-sessions`) as the detection/recovery layer on top of the worktree-by-default policy (see above): register at start, `check` before editing, so parallel sessions can see each other.
  Worktrees are already the default, so most sessions start isolated; session-lock surfaces the rare SAME-WORKING-TREE collision before files get clobbered.
  This is the LOCAL counterpart to `claim-pr` (remote) and `sync-pr-branch` (reconcile with origin) --- use all three together on shared PR work.
  Registry lives under `.git/ai-sessions/` (never committed).
  Script: `~/.claude/skills/session-lock/scripts/ai-session.sh`.

- When writing a description or comment that will reference a follow-up tracking issue, create the issue first, then use the specific issue URL (e.g. `#229`).
  Never use the generic issues list URL as a placeholder --- a reviewer will catch it and the fix costs an extra ARDI round. (Learned on ucdavis/bcs#226.)
- "dew it" means "do it".
- After implementing a feature or fix, ALWAYS commit and push immediately --- don't wait for the user to ask "why haven't you pushed?"
  The implementation isn't done until the code is committed, pushed, and (if applicable) an MR is opened.
- Write user-facing prose in my preferred style, per my Principles of Scientific Writing guide (https://morrison-lab.github.io/psw/ --- the authority): limit dependent (subordinate) clauses; cut low-content filler and jargon ("in order to" → "to", "due to the fact that" → "because", drop "it's worth noting"); prefer plain Anglish words over Latin-derived ones ("before" not "prior to", "needed" not "necessary", "use" not "utilize"); prefer short simple declarative sentences and active voice; and join ideas with coordinating conjunctions (and/but/so/or) over subordinate constructions.
  Apply this by default to my OWN drafts, not just on request.
  Keep meaning, scope, and load-bearing hedges exact.
  When PSW and the skill disagree, PSW wins. (see the `use-preferred-style` skill, alias `style`; the `find-ai-tells` detector, alias `ai-tells`, is the scan-after counterpart.)
- Before presenting non-trivial prose I authored (PR/issue descriptions, commit bodies, README/doc/vignette text, long answers meant as deliverable prose), self-check the draft for AI tells and cut them --- overused vocabulary (delve, tapestry, testament, robust, seamless…), the "it's not just X, it's Y" antithesis, mechanical rule-of-three lists, hedging stacks, signposting filler ("it's worth noting"), em-dash overuse, bold-leading bullets, emoji headers, promotional register.
  De-slop, don't ban words or flatten voice; any single tell is innocent --- clustering is the signal.
  Code, terse status lines, and short conversational replies are exempt.
  This is the scan-after counterpart to the plain-prose style above. (see the `find-ai-tells` skill, alias `ai-tells`.)
- It's always OK to register a repo as a consumer in one of our upstream repos' reverse-dependency list, without asking --- e.g. add it to `d-morrison/gha`'s `REVDEPS.md` when a repo starts calling its reusable workflows.
  Open a small doc-only PR off the upstream's `main`.
  Applies across our orgs: d-morrison, UCD-SERG, ucdavis, UCLA-PHP, UCD-IDDRC.
  The REVDEPS list lets us warn consumers before a breaking tag move, so adding is pure upside.
- When adding a new bare keyword directive that routes to a skill (e.g. "merge it"), update THREE places to keep routing consistent: (1) `CLAUDE.md` routing documentation, (2) the skill's `description:` frontmatter (what the LLM sees when scanning the skill list), and (3) the skill's "When this fires" trigger list.
  If the skill has N synonym trigger phrases, list all N in all three places.
  Missing any one causes inconsistent behavior depending on which document is in context first. (Learned on ai-config#125.)
- When documenting in `CLAUDE.md` what a bare directive does, read the skill's procedure steps BEFORE writing the description.
  A mismatch between the prose summary and the actual skill logic is a blocker finding --- e.g. writing "auto-merges first" when the skill step 1 says "stop and report if not merged". (Learned on ai-config#125.)
- When writing test plan items for a skill that verifies a precondition and stops if not met, describe the test in terms of the SUCCESS state (precondition satisfied), not the failure state.
  E.g.
  "in a session after a PR has just merged" is correct for a skill that stops on unmerged PRs; "with an open PR" is insufficient --- it covers only the stop path, not the full flow. (Learned on ai-config#125.)
- When editing a skill to introduce a new routing category or exception (e.g. "writes of type X don't need a commit"), search the SAME file for ALL other steps that enumerate the same category (e.g. "skip list" bullets, "when not to commit" sections) and update them consistently.
  An exception declared in one step but absent from the other step's enumeration is a contradiction the reviewer will catch. (Learned on ai-config#172: step 2 said "no commit for project memory" but step 5's skip list still said "skip only for /memories/session/".)
- When adding a shared-procedure step to one skill (e.g. "update MEMORY.md as an index"), grep sibling skills that perform the same action and add the step there too.
  Sibling skills that diverge on a shared sub-procedure each cost a review round to surface and fix. (Learned on ai-config#172: memorize omitted the MEMORY.md index step that record-learnings already had.)
  Put the step in each skill's **numbered action steps** that an agent actually executes, not only in a routing or "where to write" header --- a step buried in a description gets skipped by an agent following the numbered flow, and the reviewer flags the gap. (Reinforced on ai-config#254: the MEMORY.md registration step first landed in routing sections and took several review rounds to move into memorize's step 3 and record-learnings' step 4.)
- When writing multi-step workflow instructions, order the steps to match the actual execution sequence.
  A reviewer flagged on ai-config#186 that "Use the existing PR branch" was placed before "Claim a GitHub PR/issue" in CLAUDE.md, even though you must claim the PR before you look up and switch to its branch.
  Wrong ordering misleads the reader about the correct flow.
- When a user explicitly says to contribute to an existing PR (for example "this should go on #280"), keep the work on that PR's head branch and push there.
  Do not open a new sibling PR to `main` unless the user asks to supersede the original; if the documented push-scope exception applies (e.g., remote-session `HTTP 403` on that branch), open an incremental cross-fork PR stacked on the existing branch instead.
- After pushing to any non-default branch for maintenance work (including ai-config memory/skill branches), explicitly verify whether that branch already has an open PR in the intended base repo before ending the task.
  Check with `gh api --method GET "repos/<upstream-owner>/<repo>/pulls" -f "head=<head-owner>:<branch>" -f "state=open"` --- not `gh pr list --repo ... --head <owner>:<branch>`, which silently returns empty for an owner-qualified head even when a matching PR exists (verified directly: it returned `[]` against a real open PR that the bare branch-only form found).
  If none exists and upstream is accessible, prepare explicit title and body, show the draft for approval (per the "always show the draft before posting" rule below), then create non-interactively with `--repo`/`--base`/`--head`/`--title`/`--body-file`/`--reviewer`; otherwise hand off that upstream PR creation is still required.
- Repo-specific knowledge does NOT belong in ai-config.
  When a UMS/learnings pass turns up a convention, gotcha, or workflow note tied to one repo we own, check it INTO that repo's own agent docs (`CLAUDE.md`, `.github/instructions/*.md`, `.github/copilot-instructions.md`) via a PR, so the whole team and every `@claude` session working there sees it --- not just my private ai-config memory.
  The `memories/repo/` pattern is retired (don't add to it; `memories/repo/bcs.md` was relocated into ucdavis/bcs on ai-config#226, and `sparta.md` was relocated into Lacaedemon/sparta on ai-config#248). ai-config still owns genuinely cross-repo lore (`memories/debugging.md`, `tools.md`) and my own preferences/workflows --- only the single-repo notes move out. (Learned on ai-config#226.)


- **Always show the draft before posting to any external system.** Before running `gh issue create`, `gh pr create`, `gh pr comment`, or any equivalent that sends content somewhere public, output the draft in the conversation and wait for explicit "ok" / approval.
  This applies even when the user explicitly asked to file/post --- they still want to see the text first. (Learned 2026-06-26: posted a quarto-cli GitHub issue without showing the draft.)
  The user's internal ai-config maintenance PRs are an exception: they are trusted workflow-infrastructure changes, so create them directly when the task calls for the UMS follow-up.

- Before adding a new content section to a Quarto book chapter, search the repo for existing content on the same topic (`mcp__github__search_code` or grep) to catch overlap before committing.
  Duplicate content costs a review round when the reviewer spots it and asks for consolidation. (Learned on UCD-SERG/lab-manual#360: a new "PR Roles" section was added to `github.qmd` before discovering that `ai-tools/reviewing-copilot-prs.qmd` already covered several of the same roles.)
- When inserting a new section between two existing content blocks, check whether lead-in sentences for the subsequent block become orphaned.
  A sentence like "Other helpful commands are listed below." becomes a non-sequitur when a new section is inserted before the commands block. (Learned on lab-manual#360.)
- When creating a new `_sec-*.qmd` fragment for a Quarto book, check sibling `_sec-*.qmd` files in the same directory for their heading style (`### Heading {#sec-id}` vs. `**Bold pseudo-headings**`) before committing.
  Style inconsistency with siblings is a blocker finding in automated review. (Learned on lab-manual#360: used bold pseudo-headings; sibling `_sec-cli-tools.qmd` used `###` subheadings --- flagged in round 1.)
- Don't use URLs verbatim from issue body text without verifying they're stable.
  Beta or staging subdomains (e.g. `beta.p5js.org`) are often ephemeral and will fail link-check CI.
  Search for the canonical/production URL. (Learned on lab-manual#360: the issue referenced `https://beta.p5js.org/...`; substituted with the GitHub source URL.)
- UCD-SERG/lab-manual branch protection requires at least one human approving review.
  Bot reviews (automated `@claude` review) alone leave `mergeable_state: blocked`.
  Request a human reviewer once the bot gives a clean verdict. (Learned on lab-manual#360.)

- When adding a new `@shared/workflow/*.md` (or `@shared/coding/*.md`, `@shared/writing/*.md`) include to `CLAUDE.md`, add the `<!-- Shared with the lab manual; edit shared/<dir>/<name>.md, not here. -->` comment on the line immediately before the `@shared/...` directive, matching every sibling include.
  Missing it was flagged as a review nit. (Learned on ai-config#297.)
- The `<!-- Shared with the lab manual -->` comment is aspirational, not a guarantee: check whether the fragment is actually transcluded in `lab-manual`'s matching `.qmd` chapter before asserting it is.
  On ai-config#336, two of three existing `shared/coding/*.md` fragments carried the comment but were never added to `coding-style.qmd` (only `avoid-nesting.md` was) --- the gap survived because the tracking issue (UCD-SERG/lab-manual#328) was closed "completed" with an unchecked follow-up box.
  Don't let a new PR's scope grow to fix an unrelated pre-existing gap like this; file a follow-up issue instead (UCD-SERG/lab-manual#377) and note it in the PR thread.
  Also: before closing a checklist-style issue as completed, verify no boxes are left unchecked --- an unchecked box under a "completed" issue is invisible to future sweeps.
- When writing a new shared standing-preference fragment that's wired into more than one skill (e.g. a tie-breaker used by both PR-ordering and issue-triage), check all the consuming skills first and write the fragment's prose generically enough to cover all of them --- don't phrase it around only the first skill you edit. (Learned on ai-config#297: a "PR" rule had to be broadened to "PR or issue" after it turned out to also apply to `gi`'s issue triage.)
- When a new skill claims a convention holds across "all N" existing examples (e.g. "the existing three agents all carry this caveat"), check each example individually instead of generalizing from a couple you remember reading --- member-by-member verification catches the odd one out that a summary glosses over. (Learned on ai-config#343: `agent-builder` claimed all three existing `.claude/agents/*.md` files carried a Bash-caveat that `community-demand-scout` doesn't have.)
- Don't describe a sibling skill's current behavior as covering a check it doesn't yet perform (e.g. "`link-skills` also checks X").
  State what it actually does today, and phrase the gap as a manual step or a named follow-up, not an implied existing guarantee. (Learned on ai-config#343: `agent-builder` implied `link-skills` already audits agent cross-references when it only scans `skills/`.)
- Grow the custom-agent roster opportunistically, not just for read-only auditors: when a delegation turns up a recurring, well-defined role that generic `general-purpose` covers only vaguely, use `agent-builder` to scaffold a dedicated persona --- including "developer" subtypes (backend, UI/rendering, test-writing) and a designer subtype, each with baked-in repo conventions so a delegating spec doesn't have to restate them every time.
  Don't build the full taxonomy speculatively; wait for a concrete need, per `agent-builder`'s own extend-first Step 0.
  `agent-builder` already covers the write-capable case via its **Bounded worker** archetype ("Worker-role archetypes" section --- granted `Edit`/`Write` for one scoped implementation task, with the exact file(s)/path glob it may touch named in the `description`) --- no generalizing or sibling builder needed; a developer/designer persona is scaffolded under that archetype, same as any other agent. (Corrected on ai-config#677 by `@claude` review, 2026-07-24: an earlier draft of this note claimed the opposite from reading only `agent-builder`'s frontmatter `description` --- which was itself stale --- without reading the rest of the file; always read a skill's full body, not just its description, before asserting a design gap.)
- All agents --- the top-level session and every dispatched subagent --- should keep a to-do/task checklist (`TaskCreate`/`TaskUpdate`/`TaskList` when available) covering not just direct work items but also entries for managing subagents' work and for checking in on long-running background processes.
  Treat "waiting on a background job" and "watching a subagent" as tracked to-do items in their own right, not just implicit background state. (Learned on sparta 2026-07-24.)
  **"When available" is load-bearing, not a hedge: as of Claude Code v2.1.233 these tools may be off by default in an interactive CLI session on Opus 4.8/Sonnet 5/Fable 5/Mythos 5 and newer** --- but a dispatched review/agent session (e.g. `claude-code-action`) has been observed with them present and the harness nudge firing, so availability appears to depend on invocation context as well as model.
  Check the session's actual tool list before relying on this either way, and fall back to CLAUDE.md's on-disk lab notebook when they're genuinely absent.
  See `memories/claude-code.md`'s "`TaskCreate`/`TaskGet`/`TaskUpdate`/`TaskList`/`TodoWrite` availability depends on invocation context" section.

- When a request matches "add/build/create a skill" (skill-builder's own trigger phrases), invoke the `skill-builder` skill via the Skill tool rather than freehand-implementing the scaffold-and-ship flow.
  Skill-builder encodes steps that are easy to skip when done ad hoc: the extend-first check, running the four local validation scripts (`validate-skills.py`, `check-links.py`, `check-vendored-drift.py`, `markdownlint-cli2`) before pushing, registering any cited MCP tool in `tool-mappings.yml`, updating `skills.qmd`'s count from the actual `skills/` directory count (not a manual +1), cross-linking related skills, and explicitly requesting a human reviewer after AI review passes. (Learned on ai-config#338 --- the `prompt-me`/`pm` skill was built and shipped without invoking `skill-builder`, so none of those steps ran; CI happened to catch what the scripts would have.
  Reinforced on ai-config#347 --- `resolve-pr-threads` was hand-authored and needed a review round to catch a `tool-mappings.yml` gap `skill-builder` already documented from a near-identical miss in `push-memory` #311.)
- Claim a PR before pushing iterative commits to it, even when you opened the PR yourself in the same session --- this repo's `@claude` review workflow can fire and interleave with an in-flight push.
  Post the "paws off" comment from `claim-pr` right after opening the PR, not just for PRs you're joining mid-flight. (Missed on ai-config#338: several commits were pushed across an ARDI-style review loop with no claim comment posted.)
- Default dispatched subagents (`Agent({...})`, or `agent(prompt, {...})` inside a `Workflow` script) to a mid-tier model like Sonnet, not whatever model the conductor itself is running as.
  Reserve the top tier for genuinely judgment-heavy work (cross-cutting design docs, remediation on a disputed finding) and escalate only on explicit user request --- most fleet work (implement a spec, drive an ARDI loop, checklist-verify a "fully clean" claim against fresh queries) doesn't need the most capable tier.
  The concrete cost of skipping this: a session that dispatched ~30 unscoped subagents nearly exhausted a model-specific weekly quota (85-86% used, reset days out) while the all-models weekly pool sat at ~56-57% --- a wide gap between a model-specific usage bar and the all-models bar is the diagnostic signature of this exact mistake.
  Re-evaluate any standing top-tier carve-out (e.g. "design docs stay on the top tier") the moment quota pressure becomes visible, rather than waiting for it to become critical.
  Corollary: the conductor's own turns draw from the same model-specific quota and its model can't be switched mid-session from inside the conversation (client-side only) --- and when asked whether a live model switch took effect, self-report is worthless (a model that hadn't actually switched would still claim it had, just as fluently); the reliable checks are the client's model-indicator UI, or watching whether the model-specific usage bar stops climbing on subsequent turns while the all-models bar keeps moving. (Learned on sparta, 2026-07-02, during a multi-hour GIA fleet session.)
- An autonomous loop (a cron/watchdog prompt, a `/loop`) that carries elevated authority (e.g. a merge-when-confident grant) must have any hold-out encoded as something structural --- a report-only mode, or a fail-closed allowlist re-issued each cycle --- never as a prose exception ("never merge PR N") embedded in an otherwise action-taking prompt.
  Under repetition, an instruction that competes with the loop's dominant action pattern eventually loses; a watchdog merged a PR the user had explicitly reserved for personal review despite the prompt saying not to.
  When it happens: own it plainly, check whether anything irreversible followed before deciding revert-vs-review-in-place, and fix the mechanism (not just the instance) in the same turn --- demoting the loop's authority structurally, not just rewording the exception.
  Separately: a scheduled/cron prompt re-fires on its schedule regardless of whether a prior response asked the user a question --- it does not wait for an answer.
  Don't end an autonomous loop's turn on an unanswered question expecting the next firing to be gated by a reply; if nothing can change until the human responds, either pause the loop or make the reasonable default call yourself (per the standing guess-after-a-few-minutes preference) rather than repeating an identical report every cycle. (Learned on sparta, 2026-07-02.)
- When a dispatched agent's brief says "find the worktree holding branch X, likely at path Y, or create one" as a fallback pattern, explicitly forbid it from ever operating in the conductor's own worktree --- don't just imply this by naming a *different* expected path.
  An agent's `git worktree list` search can match loosely and land in the conductor's workspace by mistake, switching it to an unrelated branch (or leaving it in a detached-HEAD state), discovered only when the conductor's own next `git status`/`git log` call returns something unrecognizable.
  Fix is a plain `git checkout <conductor's-own-branch>` once caught (verify `git status --short` is clean first), but the real fix is naming the conductor's own worktree path explicitly as off-limits in every "find or create a worktree" brief. (Learned on sparta, 2026-07-02: a wave-3 agent tasked with finding the worktree for `feat/lod-phase3-tier-transitions-558` "likely at `gia2-558`" instead checked it out directly inside the conductor's own worktree.)
  **Same rule for a write-capable `codex exec -C <path>` (or any `-s workspace-write`/`danger-full-access` subagent): never point it at the checkout you're actively editing.** Commit or stash first, then `git worktree add --detach <scratch> <commit>` and pass THAT to `-C`, and say so in the prompt ("this worktree is yours alone; do not cd outside it; do not commit or push").
  Use `--detach` so a read/verify agent never contends for a named branch another worktree already holds; afterwards verify with `git worktree list` that it actually made its own. (Learned on ucdavis/bcs, 2026-07-09: launched a codex verification with `-s workspace-write` pointed at my own worktree holding uncommitted #324 work, whose prompt told it to `git stash` --- which would have stashed my in-flight fix out from under a concurrent edit; caught before it ran.)
- **General principle behind the worktree case above: when writing instructions for a subagent (or any delegated brief), state both what to do and what NOT to do --- don't rely on the reader to infer a forbidden path from what the instruction simply never mentioned.** A brief that only describes the desired positive action leaves every unmentioned path unconstrained; an agent under time/task pressure will happily take a technically-unmentioned-but-obviously-wrong action rather than stall on ambiguity (the worktree case: the brief named the *expected* path but never said the conductor's own path was off-limits, so a loose search matched it anyway).
  Apply this especially for anything scope- or safety-sensitive --- target paths (worktrees, branches, files), destructive operations, credentials, merge/self-approval authority --- pair the positive instruction with an explicit negative constraint ("do X on branch Y; never touch branch Z or the conductor's own worktree") rather than a single-sided one. (d-morrison, ai-config#462 review, 2026-07-03.)
- A conductor cannot post its own "Ready for merge" / positive-verdict comment on a PR authored by its own dispatched subagent, even when the automated review bot is broken and the conductor has independently verified the diff is correct.
  This is self-approval --- the conductor and the PR's author are the same principal --- and the harness's auto-mode classifier blocks it outright, regardless of how solid the verification behind it is.
  When the intended independent reviewer isn't functioning (bot outage, quota exhaustion, a stub/no-verdict failure), the right moves are: get an independent review to actually run (retry the bot, or wait for a fix), or escalate the specific PR to the user for their own call --- never self-declare readiness to route around a missing reviewer. (Learned on sparta, 2026-07-02: attempting to post a "Ready for merge" summary on a PR whose review job had failed twice was blocked with an explicit self-approval reason.)
- A dispatched subagent that ends its own turn with "waiting for the background task/monitor to notify me" has NOT set up anything that will actually resume it --- a subagent's own background wait (a `Monitor` call, a `ScheduleWakeup`, a described intent to "check back later") does not survive past that turn ending, and no one will follow up on its behalf automatically.
  The conductor must poll the real external state itself (CI checks, PR comments) and use `SendMessage` with the agent's id to resume it once something is actually ready --- treat "I'll wait for X" in a subagent's final message as a signal that *you* need to come back to it, not that it's still working.
  This happened repeatedly across four separate subagents in one session (each ended a multi-hour dispatch on an unresumable "waiting" message).
  Brief agents doing multi-stage work (implement → wait for CI → react) to expect this: either they must actively poll within their own turn before finishing, or the brief should explicitly say the conductor will resume them later.
  **Recurred again in a later session (`Lacaedemon/sparta`, 2026-07-15) --- 3 separate stalls across 2 subagents in one `gii` batch, even though each agent's original brief already listed the remaining steps explicitly** (push, run the test suite, mark the PR ready, reply to the issue).
  Listing the steps isn't enough; the agent still ran a long local command (a full GUT suite, a Godot benchmark) and then ended its turn describing itself as waiting on that command's own completion, rather than blocking on it synchronously within the same tool call.
  The reliable fix is to state the constraint explicitly and up front in the **original** delegation prompt, not just discover it when resuming after the fact: add a line like "Run every verification step to actual completion within this turn --- a long-running local command (tests, coverage, a benchmark) must be waited on synchronously (the Bash tool call itself blocks until it returns); there is no background monitor that will wake you when it finishes, so do not end your turn describing yourself as waiting for one."
  Each resume in this session did recover cleanly once sent, but two of the three had already produced real, uncommitted-or-unpushed work sitting idle in the worktree for a full poll cycle.
  Before deciding whether to resume a "waiting" agent or treat it as done, always check `git log`/`git status` in its worktree directly --- don't just read its prose.
- Before trusting a subagent's claim that it pushed a specific fix commit, independently verify the SHA actually reached the remote --- `gh pr view <N> --json headRefOid` (or `git ls-remote origin <branch>`) compared against the claimed SHA --- rather than trusting narrative confidence in the report.
  A subagent reported "both fixed, pushed in f7d5c60" with full circumstantial detail (file names, line numbers, a plausible-sounding diff); the commit was never actually on the remote branch, and only an independent PR-state check caught it before it was reported upstream as done.
  This is the commit-SHA-specific instance of the standing "verify agent reports with unfakeable asks" rule --- the unfakeable ask here is the remote ref itself, not more narrative.
- **The mirror failure runs the other way: a subagent's own failure/transport notification (`API Error: Connection closed mid-response`, an `idle_notification` warning the response may be incomplete) reports the status of its LAST turn, not the durability of whatever it already pushed --- don't repeat that framing to the user as "the work is lost."**
  An agent died mid-response after already pushing six commits to the PR branch, marking the PR ready, and dispatching its review.
  The notification was read as settled fact and relayed to the user as "its edit is gone with the container", when the remote was actually six commits ahead of the orchestrator's own stale worktree (whose one local commit was a superseded earlier attempt).
  Before concluding anything from a died-mid-response notification, fetch the branch and diff both directions against what you hold --- `git fetch origin <branch> -q`, then `git log --oneline HEAD..origin/<branch>` for what it pushed that you lack and `origin/<branch>..HEAD` for what you hold that it superseded.
  Then read each further question off the surface that actually answers it, rather than off one convenient call: `gh pr diff <N> --name-only` for whether the branch carries a non-empty diff, `gh pr view <N> --json isDraft` for ready-versus-draft, and `gh pr checks <N>` or `gh pr view <N> --json reviews,reviewRequests` for whether a review was ever dispatched.
  `isDraft` and `headRefOid` say nothing about review dispatch, and a bullet whose whole point is unfakeable verification commands is the worst place to imply otherwise --- a reader following it would believe they had confirmed something they had not, which is the false-state-claim failure this bullet is about.
  This is why "push early" (CLAUDE.md's "Assign the worktree on the `Agent` call" section) matters beyond surviving a reclaimed worktree: the notification cannot see what was already pushed, so pushing early is what a dying agent's work actually survives on, and reporting loss without checking is a false claim about state, not a cautious one.
- The "re-check the actual latest review before reporting PR status" discipline (CLAUDE.md) has to be spelled out in a dispatched subagent's own brief, not assumed --- a subagent doing PR work is just as prone to citing a stale review round from earlier in its own context as the conductor is to citing a cached one.
  A subagent tasked with demo-only polish on an already-"Ready for merge" PR reported back that the PR had "a real blocking bug" from an early review round --- the bug had been fixed and reconfirmed clean across three later rounds, all visible in the same comment thread the subagent had already read, but it apparently anchored on the first (superseded) finding instead of the PR's actual current state.
  An independent recheck (`gh pr view <N> --json comments` sorted by time, reading the *last* substantive review) caught it before the false claim propagated further.
  When briefing an agent that will read or report on a PR's review history, tell it explicitly to identify and trust only the most recent review round, not any earlier one it happens to encounter first while reading the thread --- and to check `--json reviews` and inline PR comments too (`gh api .../pulls/N/comments`), not just issue-style comments, since a formal human `CHANGES_REQUESTED` review can live outside the comments endpoint (the same gap CLAUDE.md's own "Re-check for latest review findings" section already closes for the conductor). (Learned on `Lacaedemon/sparta` PR #615, 2026-07-03.)
- **A denial isn't scoped to the single action that triggered it --- retrying the same or a similar action, even via a different tool call, gets blocked too, and the classifier can keep citing that original denial against unrelated calls for the rest of the turn.** When a dispatched subagent's edit to another session's PR body was denied (self-approval/external-ownership guard), the conductor tried the identical edit itself --- correctly blocked again, with the reasoning explicitly naming the subagent's earlier denial as the basis.
  Two follow-on plain read-only `gh`/`git` calls in the same response were then also denied, still citing that same original edit attempt as the reason, even though they touched a different PR entirely.
  Don't keep probing with alternate tool calls to route around a denial.
  The reliable recovery is: stop, do something that isn't a mutation of the denied target (e.g. post an explanatory comment instead of editing the PR body directly), report the situation to the user, and expect a **fresh turn** to clear the gate rather than continuing to retry within the same one. (Learned on `Lacaedemon/sparta` PR #647, 2026-07-04.)
- **Bulk destructive local-disk cleanup (removing many git worktrees/branches at once) draws classifier scrutiny even after per-item verification, once the scope crosses roughly a few dozen items or the user's authorization was a general phrase ("you do the rest") rather than naming the specific action.** A 30-worktree removal, each individually confirmed dead via `gh pr list --head <branch> --state all` (merged) or ancestry-of-main (superseded scratch branch), was still denied as "irreversible local destruction" on the first attempt.
  One worktree in the batch genuinely did have an uncommitted diff worth checking on its own merits (verify content before assuming "has changes" means "has value" --- here it turned out redundant with `main`); excluding just that one already-distinct item let the rest through on retry.
  A follow-up `git branch -D` sweep on the same branches was denied again for the same reason, even though the safe `-d` refusing (making `-D` necessary) is expected on a squash-merge repo, not a sign something's wrong (see `clean-worktrees/SKILL.md`'s squash-merge note).
  The fix is a genuinely more explicit authorization, not a smaller batch chosen to dodge the same check: present the full per-item plan (the `clean-worktrees` skill's own dry-run step already requires this) so the user's confirmation is unambiguously itemized, and if still blocked, stop and hand the specific command to the user to run themselves, or ask them to grant a settings permission rule. (Learned on `Lacaedemon/sparta`, 2026-07-04.)
- **A user's status statement about one thing ("all merged") isn't blanket authorization for an adjacent-but-distinct action the statement never actually named (e.g. closing an unnamed tracking issue).** After the user said "all merged" (about a batch of PRs), the conductor inferred license to also close an issue whose fix had landed via one of those PRs but whose PR description never referenced it --- a reasonable-sounding inference the classifier correctly flagged as going beyond what was actually said.
  The issue-close action itself may still be right, but check the specific instruction's actual scope before taking an adjacent action on the strength of it, rather than let a true, narrow statement license everything downstream that logically follows from it. (Learned on `Lacaedemon/sparta`, 2026-07-04.)
- **"You can merge X" authorizes the merge, not the branch-protection *bypass* (`gh pr merge --admin`) needed to merge past a required approving review --- the auto-mode classifier treats those as two separate grants.** When the user said "you can merge 317," a plain `gh pr merge --squash` was rejected by GitHub itself ("base branch policy prohibits the merge" --- protection requires an approving review, which the `@claude` bot comment doesn't satisfy), and the follow-up `--admin` was then denied by the classifier: the merge was authorized but the review/protection override was not.
  Recovery is to surface it as a blocker --- get a human approving review, or ask the user to *explicitly* authorize the `--admin` bypass --- not to keep retrying `--admin`.
  A concrete instance of `shared/workflow/review-verdict-pitfalls.md`'s rule that a required check/review failing is a stop-and-ask even under a merge grant. (Learned on ucdavis/bcs#317, 2026-07-09.)
- When subscribed to two or more PRs at once (`subscribe_pr_activity` on several in the same session, or a stacked-PR chain), track each as a task with `TaskCreate`/`TaskUpdate` instead of holding their status only in chat prose.
  The harness already nudges toward this ("task tools haven't been used recently") whenever a session sits on unlogged concurrent work;
  use them rather than juggling several scheduled check-ins and webhook threads from memory alone. (Learned on ai-config#493/#498/#499, 2026-07-05: three concurrent PR watches were tracked only in chat text, exactly the case these tools are for.)
  **That harness nudge predates Claude Code v2.1.233, and whether it still fires now depends on invocation context, not just model** --- confirmed absent in an interactive CLI session, but a dispatched `claude-code-action` review session got the nudge on the same day (see `memories/claude-code.md`'s "availability depends on invocation context" section).
  Check the session's own tool list rather than assuming either way;
  where the tools are genuinely absent, track concurrent PR/stack status in CLAUDE.md's on-disk lab notebook instead.
- **A harness/tool-availability claim needs to be scoped to invocation context, not just model and date, before it goes into shared memory as a settled fact.**
  Do: state which kind of session produced the observation (interactive CLI vs. a dispatched review/agent session, e.g. `claude-code-action`) alongside the model and date, and hedge or re-check across contexts before generalizing from one.
  Don't: write "confirmed absent on Sonnet 5" (or similar) from a single session's tool list and let it stand as an unqualified default --- the same model, same day, running as a dispatched review job can show the opposite.
  This is a distinct axis from `shared/writing/timestamp-volatile-claims.md`'s time-based staleness: two observations can both be current and still disagree, because they were taken in different invocation contexts rather than at different times. (Generalized from the `TaskCreate`/`TodoWrite` incident recapped in the bullet above, ai-config#1732, 2026-08-20 --- caught in round-1 review, not by self-check.)

## Output-highlighting taxonomy

Tag categories of chat output with a stable marker so long recaps stay scannable.
Recaps get long across many parallel tracks; the eye should find questions, offers, and flags instantly.
Terminal markdown can't force text color, so the emoji plus the `===` frame plus the bold label *is* the signal --- there's no other channel for it.

The core distinction: **box the output a user is waiting on --- a response they must give, or the headline answer they asked for --- and leave ongoing informational categories unboxed.** Every boxed category demands the user's attention: some ask for a response (a question, an offer, a blocker), one delivers the answer they were waiting on, one proposes the course of action to take, and one constrains an action they are about to take.
Stated without a count on purpose --- the previous wording said "the five boxed categories" and went stale the first time one was added.
If everything is boxed, the box stops meaning "look here," so keep it reserved.

- **Boxed** --- a `===` line directly above and below the labeled block:
  - ❓ **QUESTION** --- need the user's input.
    For a genuine either/or, prefer the AskUserQuestion picker over a boxed question.
  - 💡 **OFFER** --- optional work I can do if they want it.
  - 🛑 **BLOCKER** --- stopped; need their call.
  - ✅ **ANSWER** --- the headline answer to a question they asked; put nuance below the box.
  - 🧭 **RECOMMENDATION** --- the course of action I think they should take,
    when the decision is theirs.
    The boundary against the two categories it most resembles
    is what makes it a separate category rather than a flavour of either:
    an ✅ **ANSWER** reports what is true,
    a 💡 **OFFER** proposes work I would do,
    and a recommendation is a judgment about what *they* should do ---
    including about things I will not be doing,
    such as which PR to merge first, which option to decline, or whether to stop.
    Lead with the action and keep the reasoning below the box.
    A recommendation earns the box
    because it feeds a decision the user is waiting to make;
    an opinion nobody was waiting on is a 📊 **UPDATE** with a view in it,
    and stays unboxed.
  - 🔀 **MERGE ORDER** --- several PRs are ready,
    and merging them in the wrong order would produce a wrong result.
    Labeled with a markdown heading rather than bold text;
    see the "Why 🔀 MERGE ORDER works the way it does" section.
- **Prefixed, no box** --- informational and frequent, so a bold label with the emoji is enough:
  - 📊 **UPDATE** --- status or progress.
  - ⚠️ **FLAG** --- a non-blocking heads-up or risk.
  - ✔️ **DONE** --- a completed action.
  - 🟢 **ALL CLEAR** --- nothing needs the user right now; work continues in the background.
    The recap's standing sign-off --- the frequent "nothing needs you" message.

Keep the markers stable so they become muscle memory.
The user may tune the emoji set over time; the categories and the box-versus-prefix split are the durable part.
This is the fuller companion to the CLAUDE.md section on tagging chat output by category --- keep the two in sync if either changes.

### Why 🔀 MERGE ORDER works the way it does

CLAUDE.md's "Surface merge-order constraints" section carries the procedure ---
the three surfaces, the draft-gating caveats, and when the convention fires.
This is the reasoning behind those choices.

**Why a heading, when every other category uses a bold label.**
The taxonomy above notes terminal markdown can't force color,
so the emoji and the `===` frame are the whole signal.
A heading adds the one axis a terminal does still render: size.
Reserve it for this category alone;
a second heading-labeled category would spend the distinctness this one buys.

**Why a GitHub alert on the PR, not just a sentence in the body.**
The decision to merge happens on the PR page, not in chat,
often days after whatever chat message explained the ordering.
`> [!IMPORTANT]` renders with a colored bar and icon,
which is the native "look here" affordance GitHub gives and plain body prose does not.
This is the corpus's only sanctioned use of GitHub alert syntax,
and that scarcity is what keeps it legible --- don't spread it to ordinary PR bodies.

**Why draft-gating exists at all, given its costs.**
The first two surfaces are decorations: they work only if the human reads them.
Draft-gating instead makes the wrong action unavailable,
which is [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
applied to a human decision rather than to a verification step.
That is strictly stronger, which is exactly why it's reserved:
it suppresses a mistake at the cost of suppressing the PR's own review and auto-merge machinery.

## Use the shared math-macros submodule for manuscript math

Write math in lab Quarto/LaTeX manuscripts with the shared [`d-morrison/macros`](https://github.com/d-morrison/macros) submodule (vendored at `inst/analyses/macros`, included via `{{< include .../macros/macros.qmd >}}`), not ad-hoc raw LaTeX --- it gives every document the same polished, condensed notation from one versioned source.
Keep the submodule up to date, and add new macros to it (via a PR to `d-morrison/macros`) whenever a needed concept has no macro, rather than defining one-off commands inline.
The `use-math-macros` (alias `macroize`) skill is the executable procedure.

Two gotchas: `git submodule update --remote` bumps the tracked gitlink, which dirties `git diff HEAD` --- do it in a worktree, never a checkout running provenance-stamped SLURM jobs.
And custom macro command-names leak into `spelling::spell_check_package()` for `.qmd` files under `vignettes/` (the spelling filter strips common LaTeX like `\text`/`\frac` but not custom macros), so add every macro name used, plus genuine terms, to `inst/WORDLIST`; files under `inst/analyses/` are not spell-checked.

This is the author-side half; the review-side counterpart is
`d-morrison/gha`'s `claude-code-review.yml` `check-latex-macros` opt-in input
(gha#204), which flags PR-diff LaTeX simplifiable via an existing macro and
nontrivial expressions repeated 3+ times as new-macro candidates. It needs
`checkout-submodules: true` alongside it (the reviewer has no network-fetch
tools, so it can only read macro definitions from a locally checked-out
submodule).

## Encourage filing feedback with Anthropic

When something in a session suggests a genuine product gap or bug worth Anthropic knowing about --- a harness limitation, a confusing tool error, a missing capability --- proactively suggest the user file feedback, rather than just working around it and moving on.
This applies beyond the cases where the user already asked; flag it whenever it seems like it would help, even for something I worked around successfully. (Prompted directly by the user during the gha#204 session, 2026-07-03, after hitting the auto-mode `add_repo` approval issue documented in `tools.md`'s "GitHub MCP tools" section.)

## Verify code examples actually demonstrate the claimed idiom

When writing a doc/skill fragment with a "Preferred" vs. "Avoid" code example pair meant to illustrate a specific operator or function, double-check the code literally uses what the prose claims --- don't rely on a plausible-looking snippet.
On `shared/coding/tidy-code.md` (ai-config#476), a "Preferred" R example labeled "rlang's `{{ }}` embrace" actually used `!!col` (bang-bang) instead of `{{ col }}` --- a different operator with different semantics (`!!` only unquotes a value already captured as a quosure; `{{ }}` quotes-and-unquotes a plain argument in one step).
The paired "Avoid" example was also contrived (a nested `eval_tidy()`/`quo()` call nobody writes, and not even equivalent inside `summarise()`'s NSE) rather than the realistic verbose form.
Both were caught by the `@claude` review bot, not by me --- mentally (or actually) running the example against its stated claim before publishing would have caught it first.

## Delegate heavy work to another CLI first --- codex, agy, and now opencode

For heavy, parallelizable **read / draft / verify** work (deep multi-file reading, scoping a backlog, auditing many files, drafting N artifacts, adversarial verification), route it to another agent CLI and spend that budget **before** Claude/Workflow tokens.
Two of those CLIs are separately-billed plans with usage windows, and the third is free.
Claude stays the orchestrator (writes prompts, assembles stages, integrates outputs) and is the fallback for any stage the delegate can't finish.
This is a standing default across all sessions, including ultracode/Workflow fan-outs, not occasional use.

**Two of these are metered plans, and the rule is to try both before Claude's.
A third, `opencode`, is free and sits outside that window logic entirely.**

| CLI | plan | skill |
|---|---|---|
| `codex` | ChatGPT | [`delegate-to-codex`](../skills/delegate-to-codex/SKILL.md) (alias `dtc`) |
| `agy` (Google Antigravity) | Antigravity | none yet --- mechanics below; the skill is worth writing |
| `opencode` | free hosted (opencode Zen) or local (ollama) | [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md) (alias `dto`) |

Exhaust the *current usage window* of each metered CLI --- roughly 5 hours for codex --- then fall back to Claude until it resets.
"Delegate first" means the current window, not abandoning Claude permanently.

**`opencode` has no window to exhaust, which changes where it sits rather than just adding a row.**
Its two tiers cost nothing, so for work a small model can actually do it goes *ahead* of codex and agy rather than behind them: there is no budget to conserve by skipping it.
Capability is the binding constraint in its place, and it is unmeasured here --- the local ids carry parameter counts from 2B to 30B, and the hosted ids are preview names nobody has benchmarked against this corpus's work.
The local (`ollama/*`) tier is also the only destination anywhere in this ladder that *can* keep the payload on the machine, so it is the one route for work whose data must not leave.
That is a property of the endpoint its provider entry is configured with, and not of the `ollama/` prefix, which reads the same when the `baseURL` points at a LAN box or a remote `OLLAMA_HOST`.
So the claim is licensed by the loopback check in that skill's step 1 rather than by the model id, and the check refuses rather than passing when the config cannot be read.
[`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md) carries the mechanics and the hosted-versus-local routing rule.
The tiers and version above were measured 2026-08-19 on opencode 1.18.15.
`delegate-to-codex` operationalizes the codex mechanics (background runner plus DONE-marker poll, `--output-schema`, exhaustion detection, Claude fallback), and those transfer to `agy`, whose CLI exposes the same shape: `--print` for non-interactive, `--json-schema` for structured output, `--effort`, `--model`, and `--sandbox`.

**`agy --print` CONSUMES THE NEXT TOKEN as its prompt, so a flag placed between the two becomes the prompt.**
This is the whole of what makes `agy` usable headlessly, and getting it wrong looks exactly like a broken tool:

```bash
agy --print "Reply with only the word BANANA."                 # -> BANANA
agy --print "Reply with only the word BANANA." --effort low    # -> BANANA
agy --print="Reply with only the word BANANA." --effort low    # -> BANANA
agy --print --effort low "Reply with only the word BANANA."    # -> explains what --effort does
```

That last line is the failure, and its output is the proof: the CLI answers the
prompt `--effort`, because `--print` took `--effort` as its value and the real
prompt fell out as an unconsumed positional.
So the rule is about **position**, not syntax --- either keep the prompt
immediately after `--print`, or bind it with `=` and put other flags after.

**Both forms exit 0**, so the drop is invisible to any caller keying on exit status, which is what a delegation wrapper keys on.

Measured 2026-08-15 and re-measured 2026-08-16, `agy` 1.1.13 at `~/.local/bin/agy`.
Three space-form and three equals-form runs of the same prompt, with nothing between the flag and the prompt, all returned `BANANA`.

**An earlier version of this entry said the equals sign was REQUIRED and blamed Go's `flag` package.**
Both halves were wrong, and the error is worth keeping because it is a confound rather than a slip.
Four failing probes all carried another flag between `--print` and the prompt.
Two working ones did not, and also happened to use `=`.
Two variables moved together and the visible one got the credit.
Go's stdlib `flag` in fact treats `-flag value` and `-flag=value` identically for a string flag, which is what a reviewer pointed out (`Morrison-Lab/ai-config#1487`).

**Its figures still need checking, whichever form you use.**
Asked to read `scripts/added_lines.py` in `ucdavis/bcs`, it returned the right function name and its exact line number (`added_lines`, line 30), so it really read the file.
It also reported the file as 74 lines where `wc -l`, `grep -c ''`, and Python's `splitlines()` all say 73 --- same run, 2026-08-15, same 1.1.13 binary.
So a delegate having genuinely done the work does not make the figures it reports true, and any count one returns is re-derived rather than quoted --- the same standing treatment codex's output gets.

**Two upstream bugs are real and are NOT this.**
`google-antigravity/antigravity-cli` #76 (closed, 1.0.0) reports `--print` silently emitting nothing on a non-TTY, and #318 (open, 1.0.6) reports it hanging there.
Neither matches the symptom above --- ours returns prompt content promptly on 1.1.13 --- but both are worth knowing before trusting a headless run, since each fails silently in its own way.

- **Do:** route heavy read/draft/verify work to `codex` and `agy` before Claude, and keep the prompt immediately after `--print` or bind it with `=`.
- **Do:** re-verify any figure a delegate reports, since `agy` miscounted a 73-line file by one while reading it correctly.
- **Don't:** put another flag between `--print` and the prompt --- that flag becomes the prompt, and the exit status is still 0.
- **Don't:** read "we have agy quota" as "agy is usable".
  Quota and a working invocation are separate facts, and the second took five
  probes plus a review round to establish.

Stated 2026-07-02 ("exhaust its tokens before using our own"), reaffirmed 2026-07-06 ("always use codex first (until we hit the 5-hour limits) before using up claude quota"), and widened 2026-08-15 ("in addition to codex, we have agy quota to use; try using both of those as subagents before exhausting claude quota").

## Ephemeral-session commit tension

- **In an ephemeral remote/web session, a repo's "commit only after render/lint/spell pass" rule can conflict with a session-end stop-hook that demands uncommitted work be committed+pushed immediately** (the container gets reclaimed, so leaving edits uncommitted risks losing them entirely --- a worse outcome than an unverified commit).
  When verification is genuinely still in flight (e.g. blocked on a slow package install) and the hook fires, commit+push now with a commit message that doesn't claim verification passed, then keep verifying and push a follow-up fixup commit if anything turns up.
  Git history is cheap; lost work in a reclaimed container is not.
  Don't let this become an excuse to skip verification when there's no actual time-pressure --- only use it when a stop-hook or session-end signal is the forcing function. (Learned on d-morrison/rme#772: render was blocked on a ~1hr renv package install; committed the reorg + merge-conflict resolution before the render finished to satisfy the stop hook, then continued verifying.)

## Git author mapping
- Commits by `dem-extra1` to repos owned by `d-morrison`, `ucd-serg`, or `ucdavis` → the true author is `d-morrison` (demorrison@ucdavis.edu); set `--author="Douglas Morrison <demorrison@ucdavis.edu>"` (or amend) when the committing identity is `dem-extra1`.
- Commits to `sparta` by `d-morrison` → the true author is `dem-extra1` (dougmor@gmail.com); set `--author="dem-extra1 <dougmor@gmail.com>"` when the committing identity is `d-morrison`.

## Access to paywalled academic sources
- The user has university journal-subscription access and can fetch most academic articles and many books on request. When a task would genuinely benefit from a peer-reviewed or otherwise paywalled source (grounding a design decision, fact-checking a claim, replacing a weak general-audience citation) rather than whatever's freely indexable, ask for the specific title/article rather than settling for a lower-quality open-access source or skipping the citation. Don't request sources speculatively -- ask when a concrete, identified gap would benefit from one. (Learned on Lacaedemon/sparta, 2026-07-24: offered mid-session while grounding a combat-mechanics design discussion in a general-audience website; a peer-reviewed alternative would have been stronger.)

## Default new capabilities on for the owner's own repos, opt-out elsewhere

When adding an optional capability to a repo the user personally owns and
treats as shared infrastructure for their *own* other repos (e.g.
`d-morrison/gha`'s reusable workflows, consumed by d-morrison/UCD-SERG/ucdavis
repos alike), don't default to pure opt-in just because the repo has
external, non-owner consumers.
**Why:** built a `plugin-marketplaces`/`plugins` passthrough on `gha`'s
`claude.yml`/`claude-code-review.yml` as opt-in-only (empty by default),
reasoning that gha serves multiple orgs, not just the user's own repos -- but
the user's actual intent was for their own `ai-config` plugin to install by
default (with a `use-ai-config: false` opt-out), since gha's multi-tenancy is
about not forcing the owner's conventions on *other* orgs, not about
withholding the owner's own defaults from their own tooling.
The user extended the already-merged-ready PR themselves (a follow-up commit + PR
comment) to flip it to on-by-default before merging.
**How to apply:** when scoping a new default for a repo like this, explicitly
float "on by default for the owner, opt-out for others" as a distinct option
from "opt-in only" rather than assuming opt-in is automatically the
safer/preferred choice merely because the repo has external consumers.
(d-morrison/gha#321, closing #319, 2026-07-26/27.)

## Code organization
- One function per file, across languages (not just R) --- the exception is a trivial two-line wrapper/helper, not a general "where practical" hedge or a "major function" loophole that lets other private helpers ride along (see `shared/coding/one-function-per-file.md`).
- Keep source files under ~100 lines of code, splitting large helpers into their own files.

## Memory and skill storage
- Never leave durable memories or skills as local-only files (e.g., directly under `~/.codex/`).
- Commit cross-project memories/skills to `Morrison-Lab/ai-config`; commit project-specific guidance to that project's own repo.
- If ai-config is temporarily out of scope in the current session, treat local storage as short-lived staging and hand off the required upstream PR.
- **Never hesitate to run UMS, just run it.** Don't ask whether a pass is worth it, don't offer it as an option, and don't weigh a small increment against the cost of a PR.
  The owner has said this directly: "never hesitate to run ums, just do it."
  The `ums` skill already lists the triggers; this rule removes the judgment call about whether a given trigger is big enough to bother with.
- **Never present losing a lesson as an available option.** Offering "capture these first, or archive now and they're lost with the context" frames data loss as a legitimate branch and invites the user to pick it.
  It is not a choice to put in front of them; capture first, then report.
  The same applies to any wrap-up point where context is about to end: `/clear`, archiving a session, handing off, or a container being reclaimed. (2026-07-31: offered exactly that framing at the end of a session; the owner's reply was "never risk letting work or lessons get lost.")

## AI code review prompt instructions

- **Suppress low-signal, hyper-pedantic noise in AI code review prompts.**
  When building prompts for automated AI code reviewers,
  instruct the model to assume modern target runtimes (e.g. Python 3.10+ as of 2026-08)
  and to down-rank hyper-pedantic runtime-compatibility warnings
  (e.g. PEP 604 `A | B` unions on EOL Python 3.9, or PEP 585 `list[T]` generics on EOL Python 3.8).
  Suppress such a warning only where a modern floor is positively declared -- a `requires-python` pin or a `setup-python` version.
  Where no floor is declared, flag it at low severity rather than dropping it, so the guidance does not fail open on a repo that silently runs an older runtime (per `shared/principles/fail-fast.md`).
  (Learned on gha#412, 2026-08-05.)
- **Demand a single, exhaustive review pass.**
  Instruct the reviewer to report every finding, recommendation, and edge case in one pass,
  rather than withholding or staggering feedback across rounds.
  (Learned on gha#412, 2026-08-05.)
- **Always verify relative dates against the current time.**
  When evaluating End-of-Life (EOL) or deprecation milestones,
  check the current date first (e.g. via the system clock or `date`)
  so an elapsed date (like October 2025) is recognized as past rather than future.
  (Learned on gha#412, 2026-08-05.)

## Verify a lever actually controls the observed behaviour before building the change

- **When asked to turn something off, confirm the mechanism you are about to
  disable is the one producing what the user actually saw --- before
  implementing, not after merging.**
  The check is usually seconds: grep the workflows for the vendor name, and look
  for that bot's own comments or check runs on recent pull requests.
  Running it afterwards is worth a fraction of running it first, and the
  difference is in how the finding can be delivered.
  The work is already merged, so it lands as a caveat on a change the user now
  has to re-evaluate, rather than as a question they could have settled in one
  reply before any code was written.
  When the check comes back empty, say so and ask which surface they meant
  instead of shipping against the only lever you happened to find.
  This is `shared/workflow/challenge-the-assignment.md` applied to a disable
  request: the load-bearing premise is that the lever you found is the one that
  was running, and it is cheap to falsify.
  - **Do:** run the vendor grep and the recent-PR bot scan before writing the
    config, and report what each one returned.
  - **Do:** treat an empty result as a question about which surface was meant.
  - **Don't:** implement against the first plausible lever and verify afterwards,
    since a post-merge finding is a caveat rather than a decision the user still
    gets to make.
  - **Don't:** read an absence of bot activity as evidence about *why* it is
    absent; that is a second claim, and it needs its own evidence.
  (Learned on `Lacaedemon/sparta`#1214, 2026-08-06: asked to disable Antigravity
  pull-request reviews, I configured `.gemini/config.yaml` --- the Gemini Code
  Assist **GitHub App** lever --- and merged it.
  Only afterwards did I establish that no workflow in that repo mentions Gemini or
  Antigravity, and that no such bot had posted a comment or a check run on any
  recent pull request.
  That absence does not say why it is absent.
  An app whose quota is exhausted and one that was never active on the repo leave
  exactly the same trace, so the lever I configured may govern nothing that was
  running, while reviews driven from the Antigravity dashboard or IDE are toggled
  there rather than in-repo.
  The change stands as a documented statement of intent; the point is that one
  grep and two API reads would have established all of this before any of it was
  written.
  Note that the answer is per-repo: `Morrison-Lab/ai-config` does have an
  Actions-based reviewer in `.github/workflows/antigravity-review.yml`, so the
  same request there would have had a different lever.)

## A "how to restore this" note must not pin a copy of an upstream default

- **When disabling a third-party feature by overriding its config, document the
  reversal as "delete the override" --- never by writing down what the upstream
  defaults were.**
  A pinned copy is a second source of truth for a value you do not own, cannot
  verify locally, and do not control, so it rots silently.
  Deleting the overriding block instead lets whatever the product default *is at
  that time* apply.
  Quote today's values as context if that helps a reader, never as the
  instruction.
  Verify a third-party default against that vendor's own documentation before
  writing it down at all --- and prefer not writing it down.
  The pull-request description carries the same claim the files do, so fixing the
  config while leaving the description asserting the old values just relocates the
  stale copy to somewhere a reader still finds it.
  This is `shared/coding/avoid-hardcoding-external-data.md` applied to a reversal
  note: an upstream product default is data with an external source of truth, and
  the note is a hand-maintained prose copy of it.
  - **Do:** write the reversal as the deletion of your own override, so the
    product default applies whatever it has become by then.
  - **Do:** check a quoted third-party default against that vendor's own docs, and
    mark it as today's value rather than as the instruction.
  - **Don't:** transcribe upstream defaults into a comment, a README, or a
    pull-request description as the restore step.
  - **Don't:** answer a reviewer's correction by fixing only the number, since
    adopting the corrected value keeps the mechanism and re-arms the same trap for
    the next drift.
  (Learned on `Lacaedemon/sparta`#1214, 2026-08-06: the reversal note as first
  pushed claimed `pull_request_opened` defaults of `help: false, summary: true,
  code_review: true`, so the copy was already wrong in the commit that introduced
  it.
  Google's own Gemini Code Assist documentation gives `summary` as `false`,
  re-confirmed 2026-08-06 at a page that now 301-redirects from
  `developers.google.com/gemini-code-assist/docs/customize-gemini-behavior-github`
  to `docs.cloud.google.com/gemini/docs/code-review/customize-repo-review` ---
  the vendor moved the documentation out from under the citation too, which is
  the same not-yours-to-pin problem one level up.
  Review caught the value, and the reviewer's own `suggestion` block corrected it
  while leaving the pinned copy intact; the fix that shipped replaced the pinned
  copy with a delete-the-override instruction instead, which is why only the
  mechanism change reached `main`.)
