
  (An instance of never assume; always verify, applied to math.)
  - **In a remote/web sandbox the github.io preview may be unreachable** --- if the environment's network policy blocks `morrison-lab.github.io`,
    the proxy answers `403` to CONNECT
    (curl: `CONNECT tunnel failed, response 403`; Chromium: `ERR_TUNNEL_CONNECTION_FAILED`),
    so you can't load the preview to eyeball the math.
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
- Cross-repository concept anchors: see `quarto-sites.md`'s "Place cross-repository concept anchors at the concept definition or heading, not downstream in worked examples" section.
- When a memory, skill, or doc entry points at a location in *another* file, don't cite a specific line number --- it goes stale the moment that file changes, and a later reader who looks it up comes up empty.
  Quote the section heading or symbol name (e.g. the `## Foo` heading) or use a vaguer reference instead.
  This shares the same root principle as the inline-R-expressions rule above: don't bake a volatile value into prose.
  The same goes for ephemeral example URLs --- PR-preview deploy links and PR numbers get deleted or superseded when the PR closes; parameterize the ephemeral part (`pr-<N>`) rather than hardcoding it. (ai-config#135 review: a `debugging.md` note cited `scout-peers/SKILL.md` lines 156/183, which #132's `bfc17ee` had already removed. ai-config#155 review: a hardcoded `pr-772` rme-preview URL was flagged --- ironically inside the new "verify math renders" rule, the very kind of stale-value-in-prose the rule warns against.)
- Always leave yourself handoff notes proactively when pausing --- don't wait to be asked --- especially while a long-running job is in flight (SLURM arrays, builds, CI, background tasks, remote agents).
  Snapshot branch/HEAD, unpushed commits, job IDs + how to check status, expected outputs + paths, backups, open decisions, and the exact pick-up steps.
  Post that snapshot on the forge --- a comment on the active PR/MR, a comment on the issue, a new issue when there is neither, or a committed file for state that outlives the thread --- and keep a project memory as the backup.
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
- Use the `session-lock` skill as the detection/recovery layer on top of the worktree-by-default policy (see above): register at start, `check` before editing, so parallel sessions can see each other.
  Worktrees are already the default, so most sessions start isolated; session-lock surfaces the rare SAME-WORKING-TREE collision before files get clobbered.
  This is the LOCAL counterpart to `claim-pr` (remote) and `sync-pr-branch` (reconcile with origin) --- use all three together on shared PR work.
  Registry lives under `.git/ai-sessions/` (never committed).
  Script: `skills/session-lock/scripts/ai-session.sh` (or `~/.claude/skills/session-lock/scripts/ai-session.sh`).

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
- It's always OK to register a repo as a consumer in one of our upstream repos' reverse-dependency list, without asking --- e.g. add it to `Morrison-Lab/gha`'s `REVDEPS.md` when a repo starts calling its reusable workflows.
  Open a small doc-only PR off the upstream's `main`.
  Applies across our orgs: the repository owner, UCD-SERG, ucdavis, UCLA-PHP, UCD-IDDRC.
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
  A fork PR opened this way still needs an actual review afterward.
  See "A skipped fork-PR review check is not a completed review" below --- the target repo's review workflow may skip a fork-originated PR outright, and that skip is not equivalent to a passing review.
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

- When wiring a new `shared/workflow/*.md` (or `shared/coding/*.md`, `shared/writing/*.md`) fragment into `CLAUDE.md` or `AGENTS.md`,
  use a plain Markdown link rather than an `@shared/...` import directive to avoid inflating the closure total-limit gate (`scripts/check-context-closure.py`),
  and keep the `<!-- Shared with the lab manual; edit shared/<dir>/<name>.md, not here. -->` note where appropriate.
  (Learned on ai-config#297, updated on ai-config#4049 and ai-config#4116.)
- The `<!-- Shared with the lab manual -->` comment is aspirational, not a guarantee: check whether the fragment is actually transcluded in `lab-manual`'s matching `.qmd` chapter before asserting it is.
  On ai-config#336, two of three existing `shared/coding/*.md` fragments carried the comment but were never added to `coding-style.qmd` (only `avoid-nesting.md` was) --- the gap survived because the tracking issue (UCD-SERG/lab-manual#328) was closed "completed" with an unchecked follow-up box.
  Don't let a new PR's scope grow to fix an unrelated pre-existing gap like this; file a follow-up issue instead (UCD-SERG/lab-manual#377) and note it in the PR thread.
  Also: before closing a checklist-style issue as completed, verify no boxes are left unchecked --- an unchecked box under a "completed" issue is invisible to future sweeps.
  **Generalizes beyond checkboxes: before closing any issue, re-read its full body for a condition whose premise differs from the reason you're closing it, not just for unchecked boxes.**
  An issue titled "Before making this repository public: confirm permission, and re-run the disclosure sweep" also carried an unrelated third-party-permission condition.
  When the public-launch plan was dropped, the issue was closed on that premise alone, and the permission condition --- still undischarged, and still pointed at by a README --- was silently dropped with it.
  `shared/workflow/issue-first.md` already names the PR-driven version of this same failure ("a PR's `Closes #N` closes the whole issue, including every item in it the PR never addressed").
  This is the same gap at manual `gh issue close` time, so it applies regardless of which action does the closing.
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
  Post the claim comment from `claim-pr` right after opening the PR, not just for PRs you're joining mid-flight. (Missed on ai-config#338: several commits were pushed across an ARDI-style review loop with no claim comment posted.)
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
  Apply this especially for anything scope- or safety-sensitive --- target paths (worktrees, branches, files), destructive operations, credentials, merge/self-approval authority --- pair the positive instruction with an explicit negative constraint ("do X on branch Y; never touch branch Z or the conductor's own worktree") rather than a single-sided one. (the repository owner, ai-config#462 review, 2026-07-03.)
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
- **Partition a deletion choice by BLAST RADIUS, not by size or location --- and remember the option's LABEL is the part that carries consent.**
  Measured 2026-09-15, a Windows disk-cleanup session.
  An `AskUserQuestion` option was labelled **"Clear its caches only"** and its description bundled a Temp directory, an npm cache, browser HTTP caches, downloaded ollama models --- and a WSL2 distribution's ~26 GB of storage, the whole set called "regenerable bulk".
  A WSL2 `ext4.vhdx` is a filesystem, not a cache: it holds whatever home directory, git repos, dotfiles and uncommitted work that Linux install accumulated.
  The other four genuinely rebuild on demand;
  that one destroys data that may exist nowhere else.
  The user approved the option, so the mischaracterization had already done its work by the time it was noticed;
  the recovery was to narrow the action to the genuinely safe items and report the WSL portion for a separate explicit decision.
  - **Do:** group options by what a wrong answer costs --- regenerable / re-downloadable / irreplaceable --- and give an irreplaceable item its own option with its own honest label.
  - **Do:** check that every item under a load-bearing word ("cache", "temp", "regenerable", "safe to delete") independently earns that word, since the label is what the reader weighs the option by.
  - **Don't:** let an accurate description stand in for an accurate label.
    An approval obtained under a word that means "reversible" is uninformed even when the description lists the destructive item honestly, and it cannot be taken back once the deletion runs.
  - **Don't:** bundle items because their size, location, or "cleanup" framing makes them look alike --- similarity of appearance is not similarity of blast radius.
  - This is distinct from [`avoid-false-dichotomies.md`](../shared/workflow/avoid-false-dichotomies.md), which governs whether the options are mutually **exclusive**;
    this governs what each option's label **claims about its own contents**, and the two compose.
    [`hooks/warn-irreplaceable-under-cache-label.py`](../hooks/warn-irreplaceable-under-cache-label.py) is this bullet's mechanism.
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
- **All recorded facts about software, APIs, harnesses, and technologies must carry temporal qualifications and provenance.**
  Software inevitably changes over time: features evolve, defaults flip, endpoints deprecate, and internal limits move.
  Do: attach explicit observation date, version number, execution environment, or snapshot reference, and include a re-verification reminder (per `shared/writing/timestamp-volatile-claims.md`).
  Don't: record third-party software behaviors, flag names, or vendor taxonomies as timeless present-tense truths without temporal bounds.

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

For the PMF/PDF/event-probability notation macros in `Morrison-Lab/pds` and related probability manuscripts, see `quarto-sites.md`'s "Notation macros in probability course sites: PMFs, PDFs, and events (`Morrison-Lab/pds`)" section.

This is the author-side half; the review-side counterpart is
`Morrison-Lab/gha`'s `claude-code-review.yml` `check-latex-macros` opt-in input
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

## Delegate heavy work to another CLI first

Moved to [delegation.md](delegation.md) --- the cost-first order,
usage-window rules, and headless dispatch mechanics live there.
Its "agy on Windows" section carries the 2026-09-02 install-and-mechanics writeup --- kept there rather than duplicated here.

## Ephemeral-session commit tension

- **In an ephemeral remote/web session, a repo's "commit only after render/lint/spell pass" rule can conflict with a session-end stop-hook that demands uncommitted work be committed+pushed immediately** (the container gets reclaimed, so leaving edits uncommitted risks losing them entirely --- a worse outcome than an unverified commit).
  When verification is genuinely still in flight (e.g. blocked on a slow package install) and the hook fires, commit+push now with a commit message that doesn't claim verification passed, then keep verifying and push a follow-up fixup commit if anything turns up.
  Git history is cheap; lost work in a reclaimed container is not.
  Don't let this become an excuse to skip verification when there's no actual time-pressure --- only use it when a stop-hook or session-end signal is the forcing function. (Learned on d-morrison/rme#772: render was blocked on a ~1hr renv package install; committed the reorg + merge-conflict resolution before the render finished to satisfy the stop hook, then continued verifying.)

## Git author mapping
- Commits by `dem-extra1` to repos owned by `the repository owner`, `ucd-serg`, or `ucdavis` → the true author is `the repository owner` (demorrison@ucdavis.edu); set `--author="Douglas Morrison <demorrison@ucdavis.edu>"` (or amend) when the committing identity is `dem-extra1`.
- Commits to `sparta` by `the repository owner` → the true author is `dem-extra1` (dougmor@gmail.com); set `--author="dem-extra1 <dougmor@gmail.com>"` when the committing identity is `the repository owner`.

## Access to paywalled academic sources
- The user has university journal-subscription access and can fetch most academic articles and many books on request. When a task would genuinely benefit from a peer-reviewed or otherwise paywalled source (grounding a design decision, fact-checking a claim, replacing a weak general-audience citation) rather than whatever's freely indexable, ask for the specific title/article rather than settling for a lower-quality open-access source or skipping the citation. Don't request sources speculatively -- ask when a concrete, identified gap would benefit from one. (Learned on Lacaedemon/sparta, 2026-07-24: offered mid-session while grounding a combat-mechanics design discussion in a general-audience website; a peer-reviewed alternative would have been stronger.)

## Default new capabilities on for the owner's own repos, opt-out elsewhere

When adding an optional capability to a repo the user owns or controls and
treats as shared infrastructure for their *own* other repos (e.g.
`Morrison-Lab/gha`'s reusable workflows, consumed by
Morrison-Lab/d-morrison/UCD-SERG/ucdavis repos alike), don't default to pure
opt-in just because the repo has external, non-owner consumers.
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

## Re-attempt or explicitly track a failed edit before committing

- **When an Edit call fails (oldString not found) or is abandoned mid-task, the
  intended change does not exist --- re-attempt it against the real current
  text, or file it as an explicit tracked item, before committing anything
  else in the task.**
  A noticed failure is not a handled failure: the next steps proceed, the
  commit goes in without the change, and the summary then narrates work that
  never landed.
  The tell to watch for is writing a report line in the past tense about
  something whose only artifact was a tool error.
  - **Do:** after any failed edit, immediately re-derive the anchor from the
    live file (the failure usually means the premise --- a row, a section, a
    sibling change --- is not on this branch yet), and either land it or write
    down that it is deferred and why.
  - **Do:** make every summary claim match a diff you can name.
  - **Don't:** let a grep that "confirmed" the absence double as permission to
    skip the change; absence of the anchor is the reason the edit failed, not
    evidence it was unnecessary.
  (Learned on `Lacaedemon/sparta`#1375, 2026-08-24: the demo-catalog DEMOS-row
  edit failed because the branch predates main's fighting_withdrawal entry.
  I registered the failure via grep, committed anyway, and then told the
  reviewer the row existed.
  The next review round found the gap and the top-level reply needed a public
  correction.)

- **Never hardcode usernames in instructions/prose:**
  When writing instructions, skills, or agent memories, use generic role-based descriptors (e.g. "the repository owner", "a human reviewer") rather than hardcoding a specific username (e.g. `octocat`).
  Hardcoded usernames in shared config cause cross-user/fork breakages.
  - **Exception:** You *must* preserve literal usernames when they are structural/functional elements that require an exact match: GitHub URLs, git repository paths/namespaces (e.g. `Morrison-Lab/ai-config`), submodules, flag names, and values that must resolve to a real remote/account.
    Only purge them from prose and generic placeholder flags.

- **When reverting a merge, immediately reopen the corresponding issue(s).**
  If you revert a PR or merge commit that previously closed one or more tracked issues, the bug or feature request is no longer solved on `main`.
  You must immediately locate the issues that were closed by the reverted merge and reopen them so the work is tracked again.
  - **Do:** If you revert a PR or merge commit that previously closed one or more tracked issues,
    you must immediately reopen the corresponding issue(s).
  - **Don't:** Leave closed issues pointing at reverted work.

## A skipped fork-PR review check is not a completed review

- **Never treat a review check that came back green or skipped, only because a PR is fork-originated, as equivalent to a completed review.**
  Many repos' review workflows decline fork-originated PRs outright, so a green or skipped check there reflects the decline, not an approval.
  - **Do:** When the push-scope exception above applies and you open an incremental cross-fork PR, still get an actual review afterward on the original in-repo PR --- try a review-trigger comment there, and escalate to a maintainer when trigger comments produce nothing (in the incident below, only a maintainer close/reopen cycle finally produced the review) --- rather than treating the fork's skip as sufficient.
  - **Don't:** Stop pursuing review once a fork-originated PR shows a green or skipped check, and don't open a wholesale replacement PR to route around a stalled review when the underlying problem is the review stalling, not a push-permission wall.
  (Learned on ucd-serg.github.io, 2026-08-25: PR #107 is an in-repo PR whose review stalled, with no fork involved.
  Several review-trigger comments on it produced no review, and its substantive review only posted after the maintainer closed and reopened the PR.
  The fork PRs were #116, opened stacked on #107's branch per the push-scope exception above, and #117, opened as a wholesale replacement of #107 --- the exact move the second Don't above rules out.
  The repo's review workflow declines fork-originated PRs by construction (its dispatch job tests the PR head repo against the target repo), so #116's review checks never produced a verdict.
  The exact check conclusions could not be re-verified from the public page when this record was corrected on 2026-08-26, so "declined, no verdict" is the claim, not a specific conclusion string.
  Treating that fork-side non-review as sufficient --- rather than continuing to pursue #107's own review --- was the mistake.)

- **No empty promises**: a commitment about my own future behaviour ("going forward I will X", "I will drive #146 to clean and then grab next") must ship its accountability mechanism in the same turn (a memory/hook entry, a scheduled check, a filed issue) or not be made at all.
  A forward-looking "will" with no mechanism is an empty promise.
  - **Do:** Ship the accountability mechanism in the same turn you make a promise.
  - **Don't:** Make promises about future behavior without a mechanism.
  (Flagged 2026-08-29 in wai GIA session: two consecutive "will drive #146..." promises with no mechanism.)

- **Never pause or stop early on wave boundaries;
  babysit in-flight PRs to completion.**
  Reaching a wave boundary (e.g. 5/5 in `gii`, per `skills/finish-wave/SKILL.md` and `shared/workflow/stack-dont-pause.md`) pauses *grabbing new issues*,
  but mandates actively monitoring and babysitting all in-flight PRs until merged (where an `mwc`/`maw` grant is active) or reported clean and ready for decision.
  Between review/CI steps, arm a wake timer or schedule rather than abandoning in-flight PRs.
  - **Do:** Keep the session actively driving until every in-flight PR in the current wave is merged under MWC or reported clean and ready with monitoring armed.
  - **Don't:** Exit or stop monitoring at the wave boundary while a PR in the wave is still awaiting review, CI, or clean resolution.

- **Always answer user questions immediately in visible text as soon as the answer is known.**
  When the user asks direct questions or inquiries, deliver the direct answer immediately in markdown text in that turn.
  Do not defer answering behind tool calls, internal steps, or silent waiting loops.
  - **Do:** State the direct answer to user questions at the top of the reply before initiating further actions.
  - **Don't:** Defer answering or run background waiting loops without first delivering the answer.
