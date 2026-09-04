---
name: ums
description: "Update memories and skills."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# UMS — Update Memories and Skills

Actively review recent session context and update all relevant memory files
and skill definitions to capture what was learned. Unlike `record-learnings`
(which records individual facts in place as they arise), UMS is a reflective
checkpoint: survey what accumulated, categorize it, and persist it all in one
committed pass.

## When this fires

- **As soon as a learning worth saving shows up** — a corrected mistake, a
  new preference, a tool quirk, a workflow gap. This is the primary trigger:
  run UMS right then, interleaved with the main work, instead of batching
  learnings for a wrap-up step at the end. Don't wait for the task to finish
  or for `/clear` to accumulate a backlog — and don't gate it on approval or
  on a PR merging: capture the learning the moment it appears, even while the
  PR that taught it is still open and unreviewed.
  **A user correction is a mandatory immediate trigger.** Persist the lesson
  before resuming the main task; never wait for the user to invoke UMS or
  remind you a second time.
  **User profanity or frustration is an urgent trigger.**
  It signals a severe mistake, broken assumption, or dropped preference
  requiring immediate diagnosis, repair, and learning
  (see [`user-profanity-signal`](../../shared/workflow/user-profanity-signal.md)).
- **When you read a review of your work, receive critical feedback on it,
  or a questioned claim turns out to be wrong.**
  The trigger is the scrutiny, not Address, not a clean verdict, and not
  a first-person admission.
  "Are you sure about that?" is the questioning case: check the claim, and
  if it was wrong, run UMS --- answering with the corrected fact is not
  the pass.
  Questioning alone does not owe a pass when the claim holds.
  See
  [`run-ums-proactively`](../../shared/workflow/run-ums-proactively.md).
- **When a PR reaches a clean review verdict** -- the checkpoint the
  `ardi` loop exits on, and the backstop if the user-correction trigger
  or the scrutiny trigger above was skipped.
  Run the pass there rather than at the merge: the merge is human-gated and
  may land long after this session ends, while the verdict is the moment the
  review lifecycle has finished teaching.
- **Even when a new request arrives at that same moment** -- the mechanism
  that actually skips the user-correction trigger, the scrutiny trigger,
  and the clean-verdict checkpoint.
  A merge or clean verdict is when you report back, so it is also when the
  next instruction lands, and that instruction reads as the live task while
  the owed pass quietly evaporates: never refused, never deferred out loud,
  just never performed.
  A new request does not cancel a checkpoint.
  Run the pass first (it is short), or say in the same reply that it is owed
  and when it will run.
  Deferring out loud is fine; dropping it silently is the failure.
  Watch for it too when a skill *ends* in a UMS step (`post-merge`, `ardi`,
  `wrap-up`): reporting that skill complete asserts its final step ran, so
  confirm the pass happened rather than only the steps before it.
- User says "ums", "update memories and skills", "record what we learned"
- **At the start of `/clear`** — a backstop, not the primary trigger: catch
  anything accumulated since the last proactive pass before context is lost
- After a workflow reveals a gap (e.g., a skill was followed but missed a
  step, or a preference wasn't encoded)
- When the user says "did you update memories?" (the answer should be "let
  me do that now")
- **While paused waiting on a subagent or a long-running background process
  to complete.** That idle stretch is exactly when there's time to survey
  what's accumulated so far and persist it, rather than only running UMS at
  a hard stop. Don't let a real wait sit fully idle when a useful pass is
  available to run alongside it.

## Procedure

1. **Scan recent context.** Review the conversation for:
   - Mistakes made and corrected (skill gaps)
   - New preferences expressed by the user
   - Tool quirks discovered
   - Workflow steps that were missing or unclear in existing skills
   - Debugging insights
   - Codebase conventions discovered

   *(When delegating UMS to a subagent, prefer **conversation-inheriting dispatch**
   (Agent `subagent_type: "fork"` or `/subtask` in Claude Code, or providing the transcript log path in clean-slate harnesses)
   so the subagent surveys conversation history directly without manual serialization;
   see [`use-subagents`](../../shared/workflow/use-subagents.md).)*

2. **Categorize each learning.** For each item, decide:
   - Is it a **skill update**? (workflow step missing, procedure unclear)
   - Is it a **memory note**? (tool quirk, preference, debugging insight)
   - Is it **both**? (general guidance → update skill AND preferences)
   - Is it already recorded? (grep before writing -- avoid duplicates)
   - Is it **cross-project or project-specific**? (`memories/preferences.md`'s
     "Memory and skill storage" rule: cross-project lessons commit to
     `Morrison-Lab/ai-config`; a convention/gotcha tied to one repo we own
     commits to *that* repo's own agent docs instead — see the checklist
     item below for where. This changes step 4's target, not just the
     content.)

3. **Apply updates.** For each item:
   - Read the target file first (skill or memory) to understand current state
   - **Grep the corpus for the item's specific subject** -- the tool name, the
     API call, the error string -- before appending anything.
     Reading the region you're editing is not enough: a topical memory file
     runs to hundreds or a thousand-plus lines, so an existing entry on the
     same subject can sit far away in an unrelated cluster and never enter
     your view.
     Grep [`skill-builder`](../skill-builder/SKILL.md) step 0's path list
     rather than one file, and rather than only `memories/`:
     ```bash
     (
       repo="${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/ums rev-parse --show-toplevel 2>/dev/null || pwd)}"
       test -f "$repo/CLAUDE.md" && test -d "$repo/shared" || { echo "not an ai-config checkout: $repo" >&2; exit 1; }
       cd "$repo" && grep -rilI "<keywords>" skills/ scripts/ hooks/ shared/ memories/ CLAUDE.md
     )
     ```
     The query runs over the files on disk,
     so an entry that exists only on a branch not checked out there is out of reach
     (see the unmerged-PR section of [`grep-is-not-coverage`](../../shared/workflow/grep-is-not-coverage.md)).
     `-I` skips binary files, bytecode caches included,
     which a plain `grep -r` would otherwise report as hits.
     A rule can be owned by a `shared/` fragment or a skill as easily as by a memory,
     and a `memories/`-only grep stays outside those paths.
     When the grep finds an existing entry on the subject, extend that entry in place;
     don't add a second bullet.
     (ai-config#689: a `list_workflow_runs` cost bullet went in next to the
     related `get_check_runs` guidance while an entry on the same tool already
     sat ~2000 lines below in the write-access cluster -- caught by the review
     bot, not by the author.)
   - **When the target memory file is already at the 1200-line cap**,
     recover lines (re-wrap or drop) or split the file.
     A fold has two shapes and neither escapes every gate: a new source
     line trips `scripts/test_check_memory_file_size.py`, while folding
     the sentence into an existing line leaves the count flat but makes
     that line a changed line the new-line-breaks gate can flag.
     A net-positive append fails
     `scripts/test_check_memory_file_size.py`
     even when every new sentence is a real lesson
     (3rd occurrence, 2026-08-25 on `memories/preferences.md` in
     ai-config#2262: `origin/main` was exactly 1200 lines, and a
     +5-line append reddened `validate`.
     Prior: `shared/writing/semantic-line-breaks.md` ai-config#1291;
     `shared/workflow/review-verdict-pitfalls.md` ai-config#811).
   - **When step 2 routed the item to a repo other than ai-config, grep both
     corpora.**
     The query above searches an ai-config checkout,
     so run a second pass in the destination repo, over that repo's own doc paths ---
     a repo-local entry can otherwise duplicate or contradict a fragment
     nobody thought to search from that repo.
     See
     [`grep-is-not-coverage`](../../shared/workflow/grep-is-not-coverage.md)'s
     "Searching the wrong corpus is the same error with no grep in it".
   - **When that grep finds the corpus already covers this class, record the
     recurrence on the existing entry, not just the new fact.**
     The grep bullet above already says to extend in place rather than add a
     sibling; what is missing is the count.
     Write it on the entry -- "3rd occurrence, 2026-08-16", with a pointer to
     each prior record -- so the entry carries evidence about whether the
     written rule is actually holding.

     The count has a consumer that already exists and currently has nothing to
     read.
     [`deterministic-tools`](../../shared/principles/deterministic-tools.md)
     names the third occurrence as the moment a recurring judgment task becomes
     a tool, and
     [`learn-from-review-findings`](../../shared/workflow/learn-from-review-findings.md)
     asks of every accepted finding whether it is algorithmatizable -- but
     nothing in the corpus counts, so that trigger fires on recollection or not
     at all.
     A rule on its third recurrence is a rule demonstrably not holding, which
     is the argument for a hook or a check rather than for a sharper sentence.

     A recurrence note is also a duplication signal for
     [`find-overlap`](../find-overlap/SKILL.md) and
     [`consolidate-memory`](../consolidate-memory/SKILL.md), since one class
     recorded twice under different wording is exactly the near-duplicate a
     phrase-similarity pass under-detects.
     The reverse reading -- an entry that has never recurred and is never cited
     is a retirement candidate -- has **no** consumer today, so treat it as a
     property the count makes available rather than as a step anything runs.
   - Make the edit — concise bullet points, not prose
   - If updating a skill: the change should be specific enough that following
     the skill next time would avoid the mistake

4. **Commit and push — via a branch + PR, not direct to `main`, in whichever
   repo step 2 routed the item to.**

   If the work will dispatch an expensive external action from a pinned commit
   (such as a release, deployment, or batch computation), create, push, and
   open the PR **before** dispatching it. The PR is the reviewable record of the
   exact SHA that performed the action; opening it afterward is too late.

   **Do this in an isolated `git worktree`, not the shared ai-config checkout
   directly** -- `memories/preferences.md`'s "Run a local session in an
   isolated git worktree by DEFAULT" rule applies here too.
   The shared checkout is routinely in concurrent use by other sessions also
   running UMS; a `git checkout <branch>` from another session mid-command
   can silently redirect *your* `git commit`/`git push` onto *their* branch
   (and vice versa), and a local `git status`/`git log` read moments later
   can already reflect a third session's activity, not your own.
   Every code block below creates (or reuses) a worktree first, then runs
   every `git add`/`commit`/`push` from inside it -- never `cd` straight
   into the shared checkout itself to make a change.

   **Run the repo's own gates on the files you touched before the commit**,
   since a UMS PR fails CI on the same checks as any other:
   `python3 scripts/check-memory-file-size.py --strict` (a memory file over
   1250 lines fails; split it, as `memories/markdownlint.md` was split from
   `tools.md` on 2026-09-01 when a UMS append crossed the budget),
   `NLB_BASE_REF=origin/main python3 scripts/vendor/gha-check-new-line-breaks.py`,
   `python3 scripts/check-links.py`, and `markdownlint` on the changed files.

   **If a push is rejected non-fast-forward:** fetch first and diff before
   assuming a real conflict -- the branch may have picked up another
   session's commit that needs separating out (`git revert <their-commit>`)
   rather than force-pushing over it.
   Verify the PR's real, current content via `gh api
   repos/<owner>/<repo>/pulls/<N>/files` or `git ls-remote`/`git show
   origin/<branch>:<path>` (the GitHub-side truth), not the local checkout,
   which may have already moved again.
   (ai-config#748: a UMS commit collided with another concurrent session's
   UMS commit on a shared branch name this way -- both sessions' content
   ended up interleaved on one branch before separating back out, resolved
   without data loss only because both sides fetched-before-pushing and
   diffed before force-acting.)

   **Cross-project items** (skills, cross-project memory notes): both live in
   the ai-config repo. Discover its path with
   `${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/ums rev-parse --show-toplevel 2>/dev/null || pwd)}` — point
   `-C` at a **skill subdir** (any one), not the `~/.claude/skills` parent.
   `bootstrap.sh` may symlink skills *per-child* into a real `~/.claude/skills`
   directory (cloud/web sessions pre-populate it), so the parent itself isn't a
   symlink into the repo and `git -C` there fails with "not a git repository";
   a child like `…/skills/ums` follows the symlink into the repo. (Both beat the
   older `dirname "$(readlink …)"`, which resolves only one symlink hop.) Never
   leave ANY changes (skills, memories, etc.) as local-only uncommitted edits.
   Run **one** of the two paths below — not both:

   **Stage only the files you actually edited — NEVER `git add -A`.** The
   working tree often holds unrelated in-flight edits (the user's own UMS
   commits, another skill being drafted); `git add -A` sweeps those into your
   commit and onto your PR, where they bloat the review and extend the cycle.
   List the specific paths instead. Then **`git status` to confirm only your
   intended files are staged** — if something unexpected is there, the working
   tree had in-flight work; unstage it rather than bundling it. (Avoid
   `git add -p` here: it needs a terminal and hangs in non-interactive sessions.)

   Every path below starts by resolving `$repo`, the shared checkout's path
   (read-only -- discovering the path doesn't touch the shared working
   directory), then creates or reuses a **worktree** off it and does every
   write from inside that worktree instead.

   *Already on the open PR's branch* (e.g. mid-ARDI): reuse a worktree for
   it, creating one if this is the first push in the worktree-ified flow.
   ```bash
   repo="${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/ums rev-parse --show-toplevel 2>/dev/null || pwd)}"
   wt="../ai-config-worktrees/<branch>"
   git -C "$repo" worktree add "$wt" "<branch>" 2>/dev/null || true   # no-op if it already exists
   cd "$wt"
   git add "skills/<name>/SKILL.md" "memories/<file>.md"   # the files you touched
   git commit -m "ums: <brief summary>"   # COMMIT
   git push origin HEAD                   # PUSH
   ```

   *No PR yet:* branch off main first — a direct-to-main push is denied by
   auto-mode and bypasses review.

   *Same-repo case* (this checkout's `origin` IS the repo you're targeting):
   ```bash
   repo="${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/ums rev-parse --show-toplevel 2>/dev/null || pwd)}"
   git -C "$repo" fetch origin main   # FETCH
   git -C "$repo" worktree add -b "ums-<topic>" "../ai-config-worktrees/ums-<topic>" origin/main   # CREATE_BRANCH
   cd "../ai-config-worktrees/ums-<topic>"
   git add "skills/<name>/SKILL.md" "memories/<file>.md"   # the files you touched
   git commit -m "ums: <brief summary>"   # COMMIT
   git push -u origin HEAD   # PUSH — PR creation is handled by the post-push verification step below
   ```

   *Cross-fork case* (this checkout's `origin` is your own fork, not the
   upstream repo you're targeting): don't branch from a bare `origin/main`
   here -- the fork's `main` can be stale relative to upstream's default
   branch. Fetch the intended **upstream** repo explicitly (not just look up
   its default-branch name) and branch the worktree from that fetched ref:
   ```bash
   repo="${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/ums rev-parse --show-toplevel 2>/dev/null || pwd)}"
   base="$(gh repo view "<upstream-owner>/<repo>" --json defaultBranchRef -q .defaultBranchRef.name)" \
     && git -C "$repo" fetch "https://github.com/<upstream-owner>/<repo>.git" "$base" \
     && git -C "$repo" worktree add -b "ums-<topic>" "../ai-config-worktrees/ums-<topic>" FETCH_HEAD
   # chained with && on purpose -- a failed lookup or fetch must stop the
   # worktree creation, or it silently reuses an older FETCH_HEAD from a
   # prior fetch, recreating the stale-base problem this block exists to prevent
   cd "../ai-config-worktrees/ums-<topic>"
   git add "skills/<name>/SKILL.md" "memories/<file>.md"   # the files you touched
   git commit -m "ums: <brief summary>"   # COMMIT
   git push -u origin HEAD   # PUSH -- to your fork; PR creation is handled by the post-push verification step below
   ```
   **CAUTION:** if a compound `add && commit && push` is **denied**, *nothing*
   was committed — verify with `git status` / `git log` before any `git reset
   --hard`, or you'll silently discard the still-uncommitted edits.

   **After the PR merges**, remove the worktree so it doesn't accumulate:
   `git -C "$repo" worktree remove "../ai-config-worktrees/<branch>"` (the
   `post-merge` skill's own tidy step does this automatically).

   **After every push in UMS, verify PR state for the current branch in the intended base repo.**
   `gh pr list --head <owner>:<branch>` silently returns empty for an owner-qualified head ---
   it only matches a bare branch name, even when a matching PR genuinely exists
   (verified directly: `gh pr list --head <owner>:ums-pr635-lessons` returned `[]` against a real open PR on that exact branch,
   while `gh pr list --head ums-pr635-lessons` found it).
   Query the REST API instead, whose `head` filter does honor the owner-qualified form:
   `gh api --method GET "repos/<upstream-owner>/<repo>/pulls" -f "head=<head-owner>:<current-branch>" -f "state=open" --jq '.[] | {number, url, state}'`
   (for `dem-extra1/ai-config`, that is `gh api --method GET "repos/Morrison-Lab/ai-config/pulls" -f "head=dem-extra1:<current-branch>" -f "state=open" ...`).
   If no open PR exists and upstream is accessible,
   open it as a cross-fork PR immediately with an explicit title and body.
   Do not pause for draft approval:
   UMS updates are the durable record of a completed learning,
   and the PR supplies the reviewable handoff.
   Bare `gh pr create` without `--fill`/`--title`/`--body` prompts interactively and can hang a headless session:

   ```bash
   gh repo view "<upstream-owner>/<repo>" --json defaultBranchRef \
     -q .defaultBranchRef.name   # discover the base -- don't hard-code main
   gh pr create --repo "<upstream-owner>/<repo>" --base "<discovered-default-branch>" \
     --head "<head-owner>:<current-branch>" \
     --title "ums: <summary>" --body-file /tmp/ums-pr-body.md \
     --reviewer <reviewer>
   ```

   If upstream is not accessible in-session, push and explicitly hand off that
   upstream PR creation is still required.

   **Project-specific items** (a convention or gotcha tied to one repo we
   own): commit to *that* repo's own agent docs (`CLAUDE.md`,
   `.github/agents/*.md`, `.github/instructions/*.md`,
   `.github/copilot-instructions.md`, or checked-in `.claude/memories/`) via a branch + PR in
   that repo --- not ai-config.
   Discover its path the same way,
   `cd`-ing into that repo's own checkout instead of the ai-config one,
   then follow the same branch/commit/push/PR steps above,
   substituting that repo's own default branch for every `main`/`origin main` reference above
   (don't hard-code `main` --- a project routed here may default to `master` or another name;
   discover it the same way:
   `gh repo view "<owner>/<repo>" --json defaultBranchRef -q .defaultBranchRef.name`).
   If that repo has no agent-doc infrastructure yet,
   write to its local Claude project memory
   (`~/.claude/projects/<project-path>/memory/`) as short-lived staging
   only --- this is not a durable destination;
   hand off that the project repo still needs agent-doc infrastructure added (via a PR)
   and the staged memory migrated there.
   See the checklist item below.

   **Operational checklist (run in order):**

   - [ ] **Preflight:** confirm branch + cleanliness (`git branch --show-current` / `git status --short`)
   - [ ] **Safe write form:** for any external post with markdown/backticks, use file-backed bodies (`--body-file` or `-F "body=@<file>"`), never inline double-quoted body strings
   - [ ] **Postcondition:** after push, verify open PR exists in the intended base repo for the head owner/branch (`gh api --method GET "repos/<upstream-owner>/<repo>/pulls" -f "head=<head-owner>:<branch>" -f "state=open" --jq '.[] | {number, url, state}'` --- not `gh pr list --head <owner>:<branch>`, which silently returns empty for an owner-qualified head)
   - [ ] **Recovery signature:** if shell logs `command not found` during a comment/create command,
     check whichever CLI the failing command actually invoked (`which gh` or `which glab` --- not always `gh`).
     If `gh` is unavailable in this session (expected in remote/web sessions),
     fall back to the MCP tool mapping in `tool-mappings.md` instead of retrying the CLI ---
     `tool-mappings.yml` has no `glab` operations, so a missing `glab` has no MCP fallback;
     hand off or block instead of retrying.
     If the CLI that failed *is* installed, the likely cause is backtick substitution mangling the body;
     re-run using a file-backed body and re-check posted content

5. **Report what was updated.** Provide a brief summary table:

   | What | Where | Change |
   |------|-------|--------|
   | Poll for new reviews | `iterate/SKILL.md` | Added explicit polling procedure |
   | glab has no --state flag | `/memories/gitlab.md` | New bullet |

## What to look for (checklist)

- [ ] Did I follow a skill but miss a step? → Update the skill
- [ ] Did the user correct my behavior? → Encode as preference + skill update
- [ ] Did I discover a tool quirk? → the matching topical file under
  `/memories/` (`memories/MEMORY.md` lists the current set; `tools.md` when
  it fits none of them)
- [ ] Did I learn a debugging pattern? → `/memories/debugging.md`
- [ ] Did I create a *new* file under `/memories/`? → register it in
  `memories/MEMORY.md` as an index entry

- [ ] Did I discover a repo convention for a repo **we own** that has checked-in
  agent docs? → put it IN that repo (its `CLAUDE.md`, `.github/agents/*.md`,
  `.github/instructions/*.md`, `.github/copilot-instructions.md`, or checked-in
  `.claude/memories/`),
  via a PR, so the whole team and every `@claude` session there sees it. Do NOT
  keep repo-specific notes in ai-config (`memories/repo/` is retired). For a repo
  without agent-doc infrastructure yet, write to this session's own local
  project-memory mechanism (Claude Code: `~/.claude/projects/<project-path>/memory/`
  — a non-Claude session should use whatever the equivalent local staging
  location is for its own agent) as short-lived staging only — hand off that a
  PR adding agent docs to that repo is still required.
- [ ] Did the user express a new preference? → `/memories/preferences.md`
- [ ] Did a workflow emerge that could be a new skill? → run `spot-skill-opportunities`
  to judge whether it's genuinely recurring, then `skill-builder` to create it
- [ ] Did a heavy skill's fan-out step need a dedicated read-only worker persona
  (like `dependency-auditor` / `hallucination-detector` / `community-demand-scout`),
  rather than just a new skill? → run `agent-builder` to scaffold
  `.claude/agents/<name>.md`
- [ ] Are there existing skills that reference outdated info? → Fix them
- [ ] Has `learn-staging.md` accumulated entries since the last
  `promote-memory` run? → fold in a `promote-memory` pass now.
- [ ] Did I edit one step's scope without updating sibling steps in the same file? →
  Search the file for all enumerations of the changed category and make them consistent.
- [ ] Did I add a shared-procedure step to one skill but not to sibling skills? →
  Grep sibling skills for the same action and add the step there too.
- [ ] Did I change how a skill describes its relationship/contrast to a sibling
  skill (e.g. "X is passive, Y is explicit")? → Grep the sibling skill for its
  own mirrored description of that same relationship and update it too — a
  one-directional fix leaves the sibling's docs contradicting the new
  behavior. (Caught by `@claude` review on ai-config#439: `ums/SKILL.md`'s
  passive-vs-active contrast with `record-learnings` was fixed, but
  `record-learnings/SKILL.md`'s own mirrored line describing `ums` as "the
  explicit ... counterpart" was missed until review flagged it as a
  follow-on.)

## Relationship to record-learnings and staged capture

- `record-learnings` = records individual facts in place, in the moment they arise
- `ums` = a reflective, full-context sweep — survey what accumulated, categorize it, and persist it all in one committed pass

Both write to the same destinations. `ums` fires proactively, as soon as a
learning worth saving shows up, rather than waiting to catch up later; the
`/clear` trigger is only a backstop for anything that slipped through.

`spot-skill-opportunities` is the standing, continuous version of this
skill's "did a workflow emerge that could be a new skill?" checklist item —
it runs the recognition judgment call live, in the moment, instead of only
at this checkpoint. `agent-builder` is the sibling construction step for the
other checklist item above — a recurring fan-out worker persona rather than a
new user-invocable skill.

`learn`/`promote-memory` are a staged alternative for the uncertain case:
`record-learnings` and this skill both write directly to committed memory
the moment something looks worth remembering, which is right when you're
confident. When you're not — a candidate whose generality or evidence isn't
solid yet — `learn` stages it instead, and a `promote-memory` pass (which a
`ums` run can fold in, or run standalone) reviews staged candidates before
they land in committed memory. Neither replaces the direct-write path; they
add a review gate for the cases that need one.

## Anti-patterns

- ❌ Saying "I'll remember that" without actually writing it down
- ❌ Updating memories but not pushing skill changes to origin
- ❌ Recording vague lessons ("be more careful") instead of specific ones
  ("always poll for new review after pushing --- check commit SHA matches")
- ❌ Skipping step 3's dupe check and creating duplicates --
  specifically, reading only the region you're appending to instead of
  grepping the corpus for the subject
- ❌ Updating only preferences when a skill also needs the fix
- ❌ `git add -A` --- it sweeps unrelated in-flight edits (the user's work, other
  draft skills) into your commit/PR. Stage the specific files you touched.
- ❌ Creating `memories/repo/<repo>.md` for any repo --- this pattern is retired.
  Put repo-specific lore in the repo's own agent docs (`.github/agents/`,
  `CLAUDE.md`, `.github/instructions/`, `.github/copilot-instructions.md`, or
  checked-in `.claude/memories/`) via a PR;
  if the repo has no agent-doc infrastructure yet, this session's own local
  project-memory mechanism (Claude Code: `~/.claude/projects/<project-path>/memory/`
  --- substitute the equivalent for a non-Claude agent) is short-lived staging
  only --- hand off that a PR adding those agent docs is still required.
  See the checklist item above and `memories/preferences.md` for the full rule.
- ❌ Naming a tool, flag, or API identifier that appears **nowhere else in the
  corpus** without anchoring it somewhere checkable. A lone mention reads
  identically whether it is correct or hallucinated, so a later session has
  nothing to verify it against --- and the guidance is only actionable if the
  name is right. When the identifier is a cross-model tool, add it to
  `tool-mappings.yml` (then regenerate) rather than leaving the memory bullet
  as its only home; otherwise cite where you confirmed it. Having *used* it
  successfully in the session you're writing up is good evidence, but that
  evidence dies with the session. (ai-config#727: `mcp__github__list_commits`
  was flagged in review as unanchored; it was genuinely verified by use, and
  the fix was registering it as the `LIST_COMMITS` operation.)
- ❌ Writing up an incident from **recall** rather than re-deriving its
  figures and its mechanism from the artifacts.
  The artifacts are still there --- that they are still there is exactly why
  the entry is worth writing now.
  The bullet above covers an identifier that appears nowhere else;
  this covers an entry whose identifiers are all real,
  and whose *quantities* and *causal claim* are invented.
  It is the harder case, because having **witnessed** the incident feels like
  evidence,
  so nothing about composing the entry resembles guessing.
  Re-read the commit, re-run the command, re-open the issue,
  and quote what they say ---
  [`verify-the-right-artifact.md`](../../shared/workflow/verify-the-right-artifact.md)
  states the general form, that a figure a reader can re-derive beats one you
  assert.
  (ai-config#2637: a 37-line entry recording a reformatter incident from
  earlier the same session drew eight blocking findings from an adversarial
  self-review --- a count worth attributing, since the PR's own bot review
  raised one.
  Nearly every factual claim in the entry was false.
  "Three pre-existing paragraphs" was one,
  "200 to 350 characters" measured 178--268,
  and "from 1 to 11" was 0 to 11.
  The mechanism was wrong too:
  the entry blamed `--write` for reflowing whole files,
  when `--write` has been diff-scoped since #951 and `--all` is what widens
  it, so the prescribed remedy would not have prevented the churn the entry
  was written about.
  The passage was withdrawn rather than patched.
  The same PR's other half, which survived, carried the matching error in its
  citations: "#1373 recorded 47% over" was 487%, read off that issue's title
  while its own console block sat below it ---
  and the passage citing it was citing #2626, whose subject is reading a
  summary in place of its source.)
- ❌ Inserting a new bullet into any memory file with nested lists (including
  `github-actions.md`, `preferences.md`) without checking the surrounding indentation
  first. These files mix 0-indent top-level bullets with 2-/4-indent sub-bullets and
  multi-paragraph continuations; a new top-level bullet dropped in the middle
  of an existing parent's sub-list re-parents whatever follows it in Markdown
  (a sibling sub-bullet silently becomes this new bullet's child). Before
  committing an insertion, re-read the few lines immediately above and below
  the insertion point and confirm the indentation still matches what it did
  before — or place the new bullet after the complete enclosing list instead
  of inside it. (Caught by `@claude` review on ai-config#335: a new 0-indent
  bullet landed between two sibling sub-bullets of an existing parent,
  breaking the nesting.)

## Proactive hook compliance

- **`remind-ums-after-error.py`**: Prompt-injection hook that fires
  when an admitted mistake has no subsequent memory or skill modification.
  Satisfy it by executing `ums` immediately upon acknowledging an error.
- **`remind-ums-on-scrutiny.py`**: Injects a reminder when a review was read
  or a questioned claim was corrected without a recorded UMS pass.
- **`remind-learn-from-review.py`**: Reminds when an accepted reviewer finding
  has no accompanying learning or guard recorded.
- **`no-mistake-without-a-hook.py`**: Stop guard and reminder that blocks after an admitted,
  mechanizable mistake until a hook (`hooks/<name>.py`), test (`hooks/test-<name>.py`),
  and manifest binding (`hooks/hooks.json`) are authored.
