# User preferences (cross-workspace)

- NEVER assume; ALWAYS verify.
  Before stating a status/fact/outcome (PR or issue state, merge status, CI/review verdict, branch position, file contents, or which TOOLS/MCP servers are actually available in the current session) or acting on one, confirm it with a tool call --- don't rely on what was true earlier in the session, what "should" be the case, or what memory/documentation says was true as of some earlier point.
  State drifts between turns; tool availability drifts between sessions/environments.
  "It should be X" / "I left it as X" / "presumably X" / "no such tool exists" are all red flags; replace with a fresh check.
  Concretely: before querying CI or review for a PR, check its state first (`gh pr view <N> --json state`).
  A PR can merge between a "status?" call and a follow-up in the same session --- running `gh pr checks` on a merged PR returns stale data and delays noticing the merge.
  If state is MERGED, trigger post-merge instead of reporting CI details.
  (Learned on ucdavis/bcs#266;
  recurred on Morrison-Lab/ai-config#2876, 2026-09-01,
  when a cached pre-merge PR status was reported after the PR had merged.)
  Same principle for tool availability: before telling a user a capability doesn't exist in the current session (e.g. "no `subscribe_pr_activity` tool here"), run a live check (`ToolSearch`, or the equivalent discovery mechanism) rather than reciting what a memory entry or a prior session documented --- a local CLI session's tool roster isn't fixed, and reciting stale documentation as current fact is the exact failure this rule exists to prevent. (Sparta gii-ffdb93 session, 2026-07-14: initially told the user no GitHub MCP server was available in local sessions based on documented prior-session behavior, without running `ToolSearch` first.
  The user's pushback "can't you use the GitHub mcp server?" was the correct challenge, and a live check would have shown the tool was in fact reachable --- that check should have been run before stating unavailability as fact, not after being questioned.)
- **A PR is not ready for merge without an up-to-date code review**:
  Never declare a PR ready for merge solely on passing CI checks or self-review;
  an up-to-date review covering the current HEAD commit with zero unaddressed findings is required.
  See [`shared/workflow/fully-clean.md`](../shared/workflow/fully-clean.md) and [`memories/mistake-patterns.md`](mistake-patterns.md) Pattern 5f. (User directive / CAI, 2026-08-31.)
- **ARDI Loop Foreground Verification & Monitor Timers**: Run `python3 scripts/check-pr-fully-clean.py <pr>` synchronously in the foreground turn;
  see [`shared/workflow/ardi.md`](../shared/workflow/ardi.md) for foreground verification and turn-ending review monitor timer rules.
- **Never pause without an armed wake mechanism**:
  Whenever yielding a turn while tasks, tests, CI, or review checks remain incomplete, arm a timer (`schedule`, `ScheduleWakeup`, `CronCreate`, or background monitor) to resume the next concrete step.
  Never yield a turn claiming to wait on background tasks or external results without an armed wake mechanism;
  report the clock time in local time (Pacific Time) when the timer will fire.
  See [`shared/workflow/flag-session-boundaries.md`](../shared/workflow/flag-session-boundaries.md).
  (User directive, 2026-09-22).
- Default to the most recent available package version.
  Use an older or pinned version only when compatibility, reproducibility,
  or another concrete project constraint gives a reason;
  state that reason before choosing it.
- When the user corrects my behavior or identifies a workflow gap, invoke UMS
  immediately and persist the lesson before resuming the main task. Do not wait
  for the user to say `ums` or to remind me again.
- When redundant prose is identified or removed, decide explicitly whether it
  shows that the existing text needs a hook or other algorithmic safeguard;
  record either the mechanism or why the condition is not mechanizable.
- **Treat user profanity and frustration as an urgent defect signal**:
  Profanity, exasperation, or intense frustration from the user is almost always a signal that an agent made a severe mistake, regressed behavior, dropped context, violated a preference, or gave a cop-out offer.
  Never tone-police, scold the user, debate politeness, emit canned corporate apologies, or offer defensive excuses.
  Immediately halt, inspect recent actions/state to diagnose the root cause, remediate the defect completely in that same turn, trigger an urgent UMS pass, and implement mechanical enforcement.
  See [`shared/workflow/user-profanity-signal.md`](../shared/workflow/user-profanity-signal.md). (User directive / Issue #2644, 2026-08-31.)
- **Do:** use hosted/cloud models for delegated work and adversarial review; if
  hosted quota is unavailable, report the blocker or use deterministic checks instead.
- **Don't:** run Ollama, LM Studio, llama.cpp, or any other local/on-device model.
  Local inference can crash the user's computer. (User directive, 2026-08-30.)
- **Never use LLMs for algorithmic thinking --- use validated algorithmic software**:
  Do not rely on probabilistic language model reasoning in-context for arithmetic, counting, algebra, derivatives, integrals, linear algebra, sorting, or mathematical proof verification.
  Use validated deterministic tools (e.g. `wc -l`, `grep -c`, Python `len()`/`math`, SymPy, NumPy, R, Computer Algebra Systems, or formal proof assistants).
  When no off-the-shelf software exists, write and validate the algorithmic software yourself before consuming its output.
  See [`shared/principles/no-llm-algorithmic-thinking.md`](../shared/principles/no-llm-algorithmic-thinking.md). (Issue #2745 / user directive, 2026-08-31.)
- Treat a request to disable AI review as narrowly repository-scoped: it applies only to the repositories the user explicitly names in that request.
  The invariant is organization-independent --- don't widen a named-repository request into a sibling repository, into the rest of that organization, or into later unrelated PRs, and don't remove review automation anywhere that wasn't named.
  Verify each named repository independently rather than inferring one from another, since App installation is a per-repository fact.
  (User directive / CAI, 2026-08-21: the request named specific `ucdavis` repositories.
  Read `ucdavis` as the incident rather than as the rule's boundary --- as of 2026-08-21, review still ran everywhere else, `ucdavis/bcs` had the Claude app installed, and no `Morrison-Lab` repository was ever in scope.
  See [`github-consumer-ci.md`](github-consumer-ci.md)'s
  "Verify GitHub App installation per repository" for how to check a given
  repository.)
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
  Citing the source isn't the same as the citation being *accurate* --- before publishing, re-read the source and check the claim doesn't say more than the source actually establishes (a hedged "suggests"/"may" in the source shouldn't become an assertive "traces the root cause to X specifically" in the memory entry), and cross-check the new claim against related existing entries in the same file for consistency. (Learned on ai-config#482: a new bullet overstated what gha#173 had established, contradicting an existing gha#185/#187 bullet a few screens up in the same file --- caught by the PR's own review.
  Recurred on ai-config#1779, 2026-08-20: a new bullet recorded a PR-authorization lesson from ucdavis/bcs, phrased as conditional on a repo-level grant.
  That conditional phrasing restated --- and inadvertently narrowed --- three already-unconditional "always open the PR after pushing" bullets a few screens up in the same file.
  A PR review caught it, and the fix folded the case record into the existing unconditional bullet as a citation rather than keeping a separate conditional one.)
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
- **ALWAYS run UMS IMMEDIATELY upon any user correction, incorrect claim, missed item, scrutiny of the work, or pause to wait on something external.**
  The moment the user corrects your behavior, you realize you made an incorrect claim or missed something, you read a review of your work, you receive critical feedback, a questioned claim ("are you sure about that?") turns out to be wrong, or you are about to end a turn to wait on CI, a review round, or an answer from the user (at the first pause, and again only once new learnings accumulate, rather than once per wait or per re-arm of a monitoring timer), run UMS right then --- do not wait for the task to finish, Address, a clean verdict, a first-person admission, a wrap-up prompt, or permission --- on a dedicated branch per the two bullets above.
  This is the memory-file record of the triggers in `CLAUDE.md`'s "Run UMS proactively, as learnings accumulate" section --- a corrected understanding, a false claim about state, a questioned claim that was wrong, and a pause before an external wait all fire immediately, and that section holds the rationale and case records (User directive / CAI, 2026-08-05, 2026-08-25, and 2026-09-01, [ai-config#2261](https://github.com/Morrison-Lab/ai-config/issues/2261) and [ai-config#2905](https://github.com/Morrison-Lab/ai-config/issues/2905)).
- **Proactive Immediate Fixes for Self-Acknowledged / Realized Mistakes (In-Flight Work & Directives)**: Whenever realizing, discovering, or acknowledging a mistake, bug, gap, missed instruction, or oversight in your own in-flight work or directive-following (whether self-discovered or pointed out by the user), take immediate, proactive corrective action to fix it permanently (implement the fix/skill/memory update, commit on a dedicated branch, open a PR, request review, and drive to clean) in the exact same turn without waiting for a user prompt or follow-up instruction. (For out-of-scope codebase bugs discovered incidentally, file a tracking issue per `report-mistakes-proactively` instead). (User directive / correction, 2026-08-17.)
- **Autonomously commit, push, and open PRs for completed changes**: When asked to implement, edit, or write up changes in a repository on a worktree/feature branch, do not finish the round by leaving modified files sitting uncommitted or unpushed in the working directory. Always finish the delivery cycle: stage and commit the changes (linking the tracking issue created per issue-first; see `shared/workflow/issue-first.md`), push the branch to origin, open a Pull Request (if one does not exist), request AI review (`@claude review` / review workflow), and drive to clean via ARDI. (User directive / CAI, 2026-08-18.)
  Reaffirmed 2026-08-26 as bare "always push and PR" on ai-config#2277 after a turn left four commits ahead of origin and ended with "say if you want those pushed".
  - **Do:** push and open/update the PR in the same turn as the commits.
    Report the PR URL in the past tense.
  - **Don't:** leave `ahead N` commits local,
    park on a client approval-card failure,
    or close with an offer to push ---
    standing grant already covers push and PR (not merge).
- When opening a GitHub PR, trigger AI review (`@claude review`) when done pushing, and request human review (`<reviewer>`) only after AI review passes cleanly or on deadlock (see request-pr-review skill).
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
- **External repository communication requires membership or specific approval.**
  Before sending any outward communication to a repository, positively verify that the user is a member of that specific repository.
  Outward communication includes PRs/MRs, issues, comments, reviews, review requests, discussions, bot/workflow messages, and indirect actions that notify or mutate the repository, such as mentions, cross-reference backlinks, and transfers.
  - **Do:** unless membership in the specific repository is positively verified, obtain explicit approval that names the repository and the specific communication before sending it.
    This includes both unknown membership and verified non-membership.
    Draft locally while approval is pending.
  - **Do:** still follow any stricter repository contribution or AI-agent policy after membership or approval is established.
  - **Don't:** treat a public repository, organization membership, technical write access, available credentials, `/daytb`, `away`, the general default-to-action rule, or standing authorization to open PRs/file issues as permission to communicate with a non-member repository.
  - **Don't:** infer repository membership from prior contributions, a fork, collaborator access elsewhere, or the ability to post.
    Verify it for the specific repository.
  This rule applies across agents, workspaces, forges, and all communication mechanisms.
  (User directive / CAI, 2026-08-27; [ai-config#2468](https://github.com/Morrison-Lab/ai-config/issues/2468).)
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
  - **Exception (the class the user carved out):** an irreversible or destructive action still gates on explicit approval.
    An outward-facing action also gates until repository-specific membership or approval is established under the external-repository communication rule above.
    After that gate is satisfied, outward-facing status alone does not add another approval step for standing-authorized PRs, issues, or other communication.
    The example the user gave was merging a PR without an active `mwc` (merge-when-confident) grant, which is irreversible, not merely outward-facing.
  Provenance of the Do/Don't pair: the standing directive and the "do [issue]" correction both came from the user, verbatim, on 2026-08-03.
  The reversible-vs-irreversible framing and the report-in-past-tense phrasing I generalized from those two corrections, consistent with the irreversible-or-high-stakes carve-outs already on the bullets below.
  (Standing directive from the user, verbatim, 2026-08-03: "if you are unsure whether I want you to do something or not, default to doing it; I will tell you the exceptions to that rule (like merging without mwc active)."
  Recurred 2026-08-23 --- the user answered "always yes --- remember that" to yet another offer-to-ask, and the grant is now encoded agent-universally in `AGENTS.md`'s "Default to action without asking".
  Recurred 2026-08-30 on Lacaedemon/sparta: session prompted confirmation for code review and track cleanup rather than deciding directly.
  User corrected "/daytb; don't ask so many questions".)
- Always create a feature branch, push, and open a PR automatically upon completing task implementation in a repository --- never merge directly locally or stop without opening the PR ("always yes"). (User correction, 2026-08-04: "you should have opened a PR without me having to ask.")
- Always open MRs/PRs after pushing --- never ask first ("always yes").
  After committing implementation work on a branch, never end a turn asking "Would you like me to push and open a PR?" or stopping short before creating the PR --- push, create the PR, trigger AI review when done pushing, and report the PR link in the past tense immediately.
  (Recurred on ucdavis/bcs, 2026-08-20, even with an explicit repo-level "Pull requests: standing authorization" section in that repo's own `CLAUDE.md`.
  After finishing a manuscript edit, the session still asked whether more changes were coming before opening the PR ---
  "cai: don't ask whether more changes are coming;
  just open the PR immediately."
  The repo-level grant was redundant with this already-unconditional rule;
  the miss was not applying the existing rule, not a gap in its scope ---
  so this generalizes to any repo/session carrying a standing "just do X" grant, not only one with its own explicit PR-authorization section.)
  (Reconfirmed 2026-08-20 on Lacaedemon/sparta:
  agent asked "Want me to push and open a draft PR?";
  user replied "always yes".)
  - **Do:** put a markdown-linked `[#NNN](https://github.com/<owner>/<repo>/pull/NNN)` in the same turn's user-visible recap whenever you open, update, or hand off a PR --- lead with it when the user asked for status, a link, or whether work landed.
  - **Don't:** report only a branch name, a bare PR number, or prose like "PR is open" without the clickable URL, and don't make the user ask a second time for a link you already had. (User correction, 2026-08-20: status recap on [#1707](https://github.com/Morrison-Lab/ai-config/pull/1707) omitted the link until prompted.)
- **Mark review-ready PRs ready before ending a delivery turn**, even when the harness opened them as drafts.
  The up-front empty-PR pattern opens a draft deliberately, and a PR-creation tool may default to draft on its own;
  `AGENTS.md` overrides both defaults once implementation is on the branch head and checks pass.
  - **Do:** before ending a turn that delivered completed work, query live PR state and flip draft to ready (`gh pr ready "<N>"` / `mcp__github__update_pull_request` with `draft=false`, per `tool-mappings.md`'s `MARK_PR_READY`) once the branch head carries the work and validate (or equivalent) is green --- then report the linked PR in past tense.
  - **Don't:** end a delivery recap with a review-ready PR still in draft because the tool default was draft or because you opened early for CI and forgot the final un-draft step. (User correction, 2026-08-20: [#1707](https://github.com/Morrison-Lab/ai-config/pull/1707) stayed draft after checks passed.)
  - **Don't:** un-draft a **deliberately draft-gated** dependent PR.
    That PR is review-ready by construction and sits in draft only to block the wrong merge order until its prerequisite merges, so `AGENTS.md`'s draft-status carve-out and this file's own blocking-dependency entry both reserve it --- this rule does not reach it.
- **Always State Clean Stopping Point When Stopping Work**: The last message posted before stopping any session or turn MUST explicitly state whether or not this is a clean stopping point for the session (e.g. `**Stopping Point**: Clean stopping point reached` or `**Stopping Point**: Not a clean stopping point / work remains queued: ...`).
  Whenever ending a session, completing a turn, or wrapping up work (whether finishing a single task, a multi-issue backlog loop like `gii`/`gia`, a PR stack sweep, or an automated session wrap-up like `mwc`/`wrap-up`), ALWAYS include an explicit `**Stopping Point**` declaration.
  Never finish or stop without stating whether or not a clean stopping point has been reached.
  If you opened PRs and haven't driven them to clean (and merged them if `mwc` is active), it is NOT a clean stopping point --- explicitly state that the PR remains in flight and unmerged.
  (User corrections / directives, 2026-08-17, 2026-08-18, 2026-08-30.)

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
  That second half is every reviewer's latest verdict, not the globally last
  comment (ai-config#2274).
  A later all-clear from one reviewer does not clear another reviewer's
  standing not-clean, even with mwc.
  A rebuttal the reviewer still disputes does NOT count as clean.
  **`mergeable_state: clean` is NOT Fully Clean**: GitHub `CLEAN` is conflict-free (GitHub `mergeable`) plus passing commit status, not a review verdict (only `dirty` means conflicts).
  It does NOT mean a review has approved the PR, or that the PR may be described as merge-ready.
  NEVER merge --- and never describe as merge-ready --- a PR that lacks an authentic clean review verdict evaluating the HEAD SHA, even when GitHub reports `CLEAN` (user correction, 2026-08-17, restated 2026-08-25).
  Two gotchas when checking CI state: the field names/casing for these states vary by API surface (REST's lowercase `status`/`conclusion` vs `gh pr checks`'s uppercase `state`) --- don't hard-code one casing when scripting a check; and a workflow run blocked on `action_required` before any job starts can complete with zero check runs, invisible to a check-runs-only poll (`gh pr checks`, `get_check_runs`) --- and, verified directly against a real run, GitHub records NEITHER a matching commit/branch NOR a populated PR-linkage field for comment/dispatch-triggered runs, so no single `gh run list` filter reliably narrows to "runs for this PR" --- treat any such cross-check as best-effort, not exhaustive.
  See `shared/workflow/fully-clean.md` for the full detail.
  At fully-clean, every INLINE review thread is resolved, and the only open conversation is the final all-clear exchange (the reviewer's all-clear comment and your reply to it).
- If you and the reviewer(s) can't reach consensus on an item (rebuttal exchanged, neither side budging), escalate to a HUMAN reviewer for the final decision --- request human review via the `request-pr-review` skill (or `gh pr edit <N> --add-reviewer <reviewer>`) and `@`-mention them with the impasse.
  Don't loop forever and don't unilaterally override.
- After creating, pushing to, or being handed a PR, immediately arm a persistent monitoring loop using whatever wake this session has, without asking first.
  A PR-activity subscription is not a loop.
  Treat a "are you monitoring?" question as a status check that starts the loop if it is not running.
- **Always Keep a Scheduled Monitor Timer Running for In-Flight Work**: Whenever ending a turn after code pushes or while background CI, `@claude review`, or async jobs are executing on active PRs under `mwc` / `ARDI`, ALWAYS launch a `schedule` timer (e.g. 120s) before ending the turn.
  If no review has arrived when the timer expires, verify that review workflow runs are still active in CI (via `gh run list` / `gh pr view --json statusCheckRollup`).
  If the reviewer failed, was canceled, skipped with no replacement, or produced a stub review with no stated verdict, invoke `self-review-fallback` per [`shared/workflow/self-review-fallback.md`](../shared/workflow/self-review-fallback.md).
  Otherwise fix any dispatch/workflow failures discovered along the way and schedule another timer to maintain continuous monitoring until a review lands, self-review fallback triggers, or CI completes.
  Never finish a turn leaving in-flight PRs unmonitored without an active scheduled timer.
  (User directive / CAI, 2026-08-17.)

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
- **Always provide an explicit recommendation with every question or choice presented to the user.**
  See [`AGENTS.md`](../AGENTS.md) § Always give recommendations with questions (User directive / CAI, 2026-08-29).
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
  ESPECIALLY when the bot review self-skipped:
  a PR editing the review workflow itself --- the reusable `claude-code-review`
  workflow in `Morrison-Lab/gha`, or the repo's own caller that invokes it,
  whatever it's named in that repo --- makes the `@claude` bot self-skip
  (it 401s from a PR ref and only runs after merge),
  and a quota skip has the same effect.
  Then my own diff read is a necessary check --- and never the merge gate;
  since 2026-08-25 the author's inline diff read clears no merge grant.
  Autonomous merging under `mwc` stays blocked,
  and human approval is the only path to landing such a PR,
  with any available cross-model, cross-harness adversarial review
  recorded alongside, never substituted for, that sign-off.
  In status recaps, name the venue as well as the verdict.
  A subagent transcript is a "private/local pre-push adversarial check",
  never a statement that the PR "has a clean review";
  reserve that wording for a genuine verdict posted in the forge review record,
  and link the posted verdict when citing it.
  If the private artifact has no user-visible URL, say that plainly rather than
  letting "independent review" imply an externally visible review.
  (User correction, 2026-08-27, ucdavis/rampp#153.)
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
  Beyond same-file collisions: after ANY merge that advances the base (`main`), proactively re-sync EVERY trailing open PR branch that passes `memories/reviewing-prs.md`'s scope test and resolve conflicts (an out-of-scope branch is reported to the user and left untouched) --- don't wait for a branch to show DIRTY or for the next review trigger.
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