# skill-builder — author a new skill (extend-first)

Create — or, preferably, *extend* — an ai-config skill following the repo’s conventions. The prime directive: **don’t create a new skill until you’ve confirmed no existing one should be extended instead**, and that no other branch is already building it.

## When this fires

- “build a skill”, “create a skill”, “make a new skill”, “add a skill”, “skill-builder”
- Creating an **alias** for an existing skill — “add an alias for X”, “make X an alias for Y”, “should this be an alias for Y” — is a skill-builder task too, not a raw `Write` of a stub file. Hand-writing an alias `SKILL.md` skips the codex-wrapper regeneration (the required step below) and trips the `validate` CI check, and skips the self-review pass that catches errors in the stub’s own prose. (ai-config#569: a hand-written `giardia`→`gia` alias stub failed `validate` on the missing wrapper and needed a review round to fix a reversed phase-order description — both avoidable by routing here.)
- Any time a repeatable multi-step workflow emerges that’s worth codifying — proactively suggest capturing it as a skill.

## Step 0 — Extend before you create (do this FIRST, always)

Rule out extending an existing skill *before* scaffolding anything:

1.  **Search the whole corpus, not only `skills/`**, for something that already owns (or is adjacent to) this concern:

    ``` bash
    cd "$(git -C ~/.claude/skills/skill-builder rev-parse --show-toplevel)"   # the ai-config repo
    ls skills/ scripts/ hooks/
    grep -ril "<keywords>" skills/ scripts/ hooks/ shared/ memories/ CLAUDE.md
    ```

    If a skill already covers it, **extend that skill** (a new alias, a new section, an extra trigger phrase) rather than adding a near-duplicate. If a **script or hook** already performs it, the skill you were about to author is a wrapper around that instrument, so document the instrument instead of restating its procedure as prose.

    **`scripts/` and `hooks/` are the paths most often left out of this search, and they are where prior art for a procedural skill is likeliest to sit.** A skill describing a procedure is frequently a wrapper around an instrument that already exists, because [`deterministic-tools`](../../shared/principles/deterministic-tools.md) pushes every recurring judgment task toward a script. So an instrument in `scripts/` is prior art for a skill exactly as another skill is. A search confined to `skills/*/SKILL.md` answers the narrower question “does a skill exist”, rather than the one actually being asked, “does this capability exist”.

    Omitting them produces the failure shape [`grep-is-not-coverage`](../../shared/workflow/grep-is-not-coverage.md) describes: a real command, a real null result, and a conclusion wider than the paths that were searched. So report the paths you covered alongside the step 4 decision below, rather than reporting the decision alone.

    - **Do:** search `scripts/` and `hooks/` alongside `skills/` before concluding that a capability does not already exist.
    - **Do:** name the paths the search covered when stating the extend-or-create decision.
    - **Don’t:** read a clean grep over `skills/*/SKILL.md` as evidence that the capability is absent; it answers a narrower question.
    - **Don’t:** author a skill describing a procedure without first checking whether an instrument already performs it.

    (Morrison-Lab/ai-config#1055 and \#1056, 2026-08-02: a Step 0 pass ran `ls skills/`, the `skills/*/SKILL.md` grep, and the branch, worktree, and open-PR scans below, plus a wider grep over `skills/`, `shared/`, `memories/`, and `CLAUDE.md`. Every one came back clean, so the session filed \#1055 and opened \#1056 to author a new `refresh-claude-token` skill. `scripts/rotate-claude-token.py` had been on `main` since commit `18173c88`, merged as \#953 under issue \#952, at 312 lines with a 329-line test file beside it. It already discovers its target repos rather than hardcoding them, previews by default, reads the token from stdin or the environment so it never reaches `argv`, and re-reads each secret’s `updated_at` to verify the write. It surfaced only incidentally, from a `gh search code 'CLAUDE_CODE_OAUTH_TOKEN'` run made for an unrelated reason. `scripts/` was in none of the searched paths.)

2.  **Scan EVERY branch AND every local worktree for in-flight work — the whole tree, not only `skills/`.** You, another CLI session, or the `@claude` bot may already be adding it, and a growing share of contributions are edits to `shared/`, `CLAUDE.md`, `memories/`, or `scripts/` rather than a new `skills/<name>/` directory, so a `skills/`-scoped scan is blind to exactly the kind of parallel work most likely to collide (Morrison-Lab/ai-config#776). A parallel CLI session usually builds its skill in an **unpushed local worktree**, so a remote-only `git branch -r` scan misses it entirely (this hit PR \#67 — a sibling skill was caught only by a stray system-reminder, not the scan). Scan local refs *and* the worktree working trees too:

    ``` bash
    git fetch origin --prune
    # local + remote branches --- NOT just -r; unpushed local branches count.
    # Whole-tree filename match, not skills/[^/]*<keyword> --- a colliding edit
    # to shared/ or CLAUDE.md has no skills/ path to match:
    for b in $(git branch -a --format='%(refname:short)' | grep -v HEAD); do
      git ls-tree -r --name-only "$b" | grep -iE "<keyword>" | sed "s|^|$b: |"
    done
    # uncommitted, ref-less work in sibling worktrees — list only UNTRACKED
    # files (whole tree, not just skills/), so shipped skills (committed in the
    # main worktree) don't false-match.
    # Read paths via sed + `while read` (not $(...)/awk $2) so paths with spaces
    # survive:
    git worktree list --porcelain | sed -n 's/^worktree //p' | while IFS= read -r wt; do
      git -C "$wt" ls-files --others --exclude-standard 2>/dev/null \
        | grep -iE "<keyword>" | sed "s|^|$wt: |"
    done
    # A filename match still misses an EDIT to an existing shared/ or CLAUDE.md
    # file that introduces the concept with no new path to catch --- pickaxe by
    # content instead, recent-window scoped so it doesn't drown in unrelated
    # history:
    git log --all --oneline --since=14.days -S'<keyword>' -- shared/ memories/ scripts/ hooks/ CLAUDE.md
    ```

    If a branch or worktree is already building it, **continue that work** (check it out / extend its PR) instead of opening a colliding parallel branch.

3.  **Check open PRs too** — a branch scan misses work already pushed and opened as a PR if you never fetched it. See [`check-open-prs-before-duplicating`](../../shared/workflow/check-open-prs-before-duplicating.md).

4.  **Decide explicitly: extend (preferred) or new.** State which and why before writing a line. A new alias or section almost always beats a whole new skill.

## Anatomy of a skill

One directory per skill, `name` matching the directory:

    skills/<name>/SKILL.md

``` yaml
---
name: <name>                 # MUST equal the directory name
description: "<what it does>. Use when asked to '<trigger>', '<trigger>', …"
user-invocable: true
allowed-tools:               # real skill: list its tools. alias: mirror the canonical's list
  - Bash
  - Read
  - Edit
  - Write
---
```

- **`description` is how the skill gets discovered.** Pack it with *what it does* AND the natural-language triggers (`Use when asked to '…'`). The matcher reads this — be generous with trigger phrasings.
- Body shape: `# <name> — <tagline>`, then `## When this fires`, `## Procedure`, `## Relationship to other skills`, `## Anti-patterns`. Concrete commands beat prose.

## Conventions (match the existing family)

- **Decide checklist fit explicitly.** Before adding a checklist section to a skill (new or extended), apply [`shared/workflow/skill-checklists.md`](../../shared/workflow/skill-checklists.md): add one only for repeatable, high-cost, mechanically verifiable failure modes. If the skill is mostly judgment/exploration, skip checklist boilerplate.

- **Include reusable, copy-pasteable shell commands where useful.** Instead of leaving procedural steps as abstract prose (“grep for X”, “check CI logs”, “query PRs”), provide concrete, tested shell command snippets with realistic placeholders (e.g. `gh pr list ...`, `rg -niE ...`). This ensures agents and users don’t have to reformulate or debug command pipelines every time they execute the skill.

- **Pair short names with spelled-out aliases.** When the canonical skill has an acronym/short name (`gi`, `sup`, `ums`, `dc`), also create the spelled-out alias dir (`grab-issue`, `send-upstream`, `update-memories-and-skills`) — and give a memorable short alias to a spelled-out canonical where it helps. The alias file is thin and only redirects:

  ``` markdown
  ---
  name: <alias>
  description: "Alias for `<canonical>`. <one-line>. Use when asked to '<trigger>'."
  user-invocable: true
  allowed-tools:        # mirror the canonical's allowed-tools exactly
    - Bash
    - Read
    - Edit
    - Write
  ---

  # <alias> (alias for `<canonical>`)

  This is a spelled-out alias. Read and follow the canonical skill:

  → **[<canonical>](../<canonical>/SKILL.md)**
  ```

  Keep the real content in **one** canonical file; aliases never duplicate it. The alias’s `allowed-tools` is the one exception: copy the canonical’s list verbatim so invoking the alias permits exactly what the canonical needs (an alias redirects, so it must not be more restrictive than its target).

- **Cross-link** related skills under `## Relationship to other skills`.

- **No registry to update.** Skills are auto-discovered from `skills/` (the bootstrap symlink and the plugin root both read the directory) — adding the directory is enough.

- **List it in `skills.qmd` if it belongs in one of the category tables**, and bump the “All N+ canonical skills” count at the bottom to the **actual** directory count (`ls -d skills/*/ | wc -l`), not a manual +1 — `main` often gains other skills while your PR is in review, so a hand-incremented count drifts and reads as stale by the time you merge (ai-config#347).

- **Register any new tool the skill names.** Discovery needs no registry, but tool *references* do. If the procedure names a **GitHub MCP tool or `gh`/`git` operation not already in `tool-mappings.yml`** (grep it to check), verify the tool is real first (`ToolSearch` for it in a live session), then add it there — `id`, `description`, `cli` (the CLI fallback), and `github_mcp` (the MCP tool) — and rerun `scripts/sync-codex-skill-wrappers.py` so the Codex wrappers can translate it. Skip this and the `@claude` reviewer flags the unregistered name as a *possible hallucination* — it can’t tell a real-but-undocumented tool from an invented one. (`push-memory` \#311 hit this: `mcp__github__create_branch` and `mcp__github__push_files` were real but unregistered, and the first review round flagged both.)

- **Grep-verify any citation to `CLAUDE.md`, a `shared/` fragment, or an “existing convention/scale” before writing it into new skill prose** — not only when auditing someone else’s text. A skill being authored is new content too, and the same failure `purge-hallucinations` catches in other authors’ text (a citation that reads as authoritative but doesn’t resolve) is just as easy to introduce while writing your own. `grep -rn "<exact phrase>" CLAUDE.md shared/` before the sentence ships, especially for “mirrors the scale already used” / “per CLAUDE.md’s …” phrasing — that pattern claims unverified precedent. (`check-info-quality` \#349 shipped both: a `CLAUDE.md` section citation that didn’t exist, and a claimed “blocking/nit/optional” severity scale the cited doc never defined — both caught by the `@claude` reviewer, not by the skill’s author.)

- **Test any regex/grep detection heuristic against the skill’s own cited canonical examples before shipping — don’t just reason about it abstractly.** When a skill’s description or fragment names specific example phrases it’s supposed to catch, actually run the pattern against those exact strings. A heuristic that doesn’t match its own advertised examples is broken, not just incomplete, and a reviewer checking prose for accuracy (`fact-check-prose`) will catch the mismatch even if you don’t. (`fix-forward-references` / ai-config#507: the first version of `forward-references.md`’s heuristic required a paired reference-cue alongside the directional word, but every one of its own cited examples — “see below”, “as discussed below”, “we’ll cover this later” — has no such cue, so none of them actually matched; caught in review, not before pushing.)

- **After testing a heuristic against multiple canonical examples, verify every pattern you tested actually landed in the shipped fragment — passing the test isn’t the same as writing the result down.** Testing two patterns and confirming each catches a different example, then only transcribing one of them into the file, ships a fragment that contradicts its own skill’s procedure description (which still says to run both). `diff` or re-read the fragment against your test notes before committing, not just your terminal scrollback. (`ai-config#524`: both regexes were verified working in a scratch test file, but only the first was written into `informal-definitions.md` — caught by the `@claude` reviewer, not before pushing.)

- **Write example commands and claims so a literal, mechanical reader gets the right answer — intent-correct isn’t enough.** A verification command whose comment says “the base PR *adds* it” must actually constrain to added lines (`grep "^+.*<symbol>"` on a diff — unanchored, it also matches deletions and context, inverting the answer), and an absolute claim (“guarantees a conflict”) is a review finding when a plain counterexample exists (identical edits to the same passage merge cleanly — write “almost always conflicts”). (`stack-prs` \#577: two of the review round’s three findings were this one class, both caught by the reviewer rather than the author’s own self-review.)

- **Use `<angle-bracket>` placeholders in command blocks — never bare ALLCAPS.** Identifiers like `PATH`, `URL`, `TARGET` look like shell env vars; bare `PATH` looks like the `$PATH` env var, and `path` is a zsh special that mirrors `$PATH`. A reader who copies the command without substituting the placeholder runs something wrong. Use `<path>`, `<url>`, `<target>` instead. (See `memories/claude-code.md` → “Skill command blocks”.)

- **Every procedural step needs a runnable command, not just prose.** If sibling steps in the same skill show a bash snippet, a step that only describes the action in prose (“rebase to drop the commits”) reads as incomplete and invites a reviewer finding. This matters most for a destructive or history-rewriting step that already requires explicit user approval — the user needs to see exactly what they’re approving, not infer it. (`stack-prs` \#359 round 1: the one step without a concrete command was the abandoned-base-PR rebase.)

- **Verify a cross-skill claim against the referenced skill’s actual mechanics before writing it — don’t infer from what would be plausible.** A claim like “skill X uses signal Y to detect Z” needs to be checked against X’s real procedure, not assumed from what sounds reasonable. (`stack-prs` \#359 round 1: claimed `ardia`’s stacked-PR detection reads the PR body, when `ardia/SKILL.md` actually matches `baseRefName` against `headRefName` — the body note only helps a human scanning the list.)

## If the skill fans out to subagents

When a skill’s procedure spawns subagents (to parallelize per-item work, e.g. `pr-status-all` runs one subagent per PR), write the **subagent prompt as if the skill file doesn’t exist** — because for the subagent it doesn’t. A spawned subagent starts fresh: it sees only the prompt the orchestrator hands it, not this skill’s text. Any discipline the work depends on (the exact query, the bot-login wording, how to resolve owner/repo, “read the LATEST review”) has to be restated inside the subagent prompt, not assumed inherited. Keep the cheap, once-per-run setup in the orchestrator — enumerate the work items there, and pass down the per-item data the orchestrator already holds so each subagent doesn’t re-fetch it. `pr-status-all` is the worked example.

If the same worker persona would be spawned by more than one call site, or the fan-out step needs a harness-enforced tool boundary an inline prompt can’t guarantee (e.g. a detection pass that must never be able to write), promote it to a **persistent** `.claude/agents/<name>.md` subagent instead of an inline prompt — hand off to `agent-builder` for that. `dependency-auditor`, `hallucination-detector`, and `community-demand-scout` are the worked examples.

## If the skill encodes a standing rule

When the skill codifies general guidance or a preference (not just a one-off procedure), **also** update `memories/preferences.md`, and for top-level workflow policy add a `CLAUDE.md` section. Standing rule: update **BOTH** the skill AND preferences — the skill encodes the behavior, preferences make it persist and fire across all contexts even when the skill isn’t invoked.

## Ship it

Skills and memories all live in the ai-config repo — never leave changes local-only. Commit via a **branch + PR** (not direct to main), request `the repository owner` as reviewer, then **ARDI to clean**.

> **In a worktree session, the repo toplevel below is the MAIN checkout, not your worktree.** `~/.claude/skills` symlinks into the main `ai-config` checkout, so `git -C ~/.claude/skills … rev-parse --show-toplevel` returns the main repo root — often on another session’s branch. Don’t `cd` there and don’t pass that path to Write/Edit: the skill files (and git commits) would land in the main checkout, clobbering another session’s working tree. Instead author the files in your **worktree’s own** `skills/<name>/` dir and run git from the worktree (it’s a full checkout of the same repo). Confirm with `git branch --show-current` before committing.

``` bash
cd "$(git -C ~/.claude/skills/skill-builder rev-parse --show-toplevel)"   # ai-config root — NOTE: the MAIN checkout, NOT your worktree (see caveat above)
git fetch origin main && git checkout -b add-<name>-skill origin/main   # FETCH, CREATE_BRANCH
# write skills/<name>/SKILL.md (+ alias dir, + preferences/CLAUDE.md if it's a rule)
python3 scripts/sync-codex-skill-wrappers.py   # regenerate codex-skills/ wrappers — REQUIRED for every new/renamed skill
python3 scripts/semantic-line-breaks.py skills/<name>/SKILL.md   # preview only; --write to apply (see caveat below)
# The `validate` CI job runs these four — run all four locally before pushing:
python3 scripts/validate-skills.py             # frontmatter + wrapper-sync + manifest checks + the 8000-char skill-listing budget
python3 scripts/check-links.py                 # relative markdown links resolve
python3 scripts/check-vendored-drift.py        # shared-fragment vendored-content drift check
npx --yes markdownlint-cli2@0.22.1             # markdown style (config in .markdownlint-cli2.jsonc)
git add skills/<name>/SKILL.md codex-skills/<name> \
        skills/<alias>/SKILL.md codex-skills/<alias> \
        memories/preferences.md                             # stage the files you
                                                            # touched (incl. the
                                                            # generated wrappers, and
                                                            # the alias dir if you made
                                                            # one) — NOT `-A`, which
                                                            # sweeps in unrelated edits
git commit -m "skills: add <name> — <summary>"   # COMMIT
git push -u origin HEAD && gh pr create --fill   # PUSH, CREATE_PR
```

**Regenerate the Codex wrappers — every new or renamed skill needs them.** `codex-skills/` is a generated tree of thin Codex-compatible wrappers, one per `skills/<name>/`, and the `validate` CI job fails if it’s out of sync (the red log reads `Codex skill wrappers are out of sync:`). After writing the skill (and any alias dir), run `python3 scripts/sync-codex-skill-wrappers.py`, then `git add` the new `codex-skills/<name>/` (and `codex-skills/<alias>/`) alongside the source. The `validate` CI job runs four checks — `scripts/validate-skills.py` (frontmatter + wrapper sync + manifests), `scripts/check-links.py` (relative markdown links), `scripts/check-vendored-drift.py` (shared-fragment drift), and `markdownlint-cli2` (markdown style). Run all four before pushing to catch a stale wrapper, broken link, drift, or lint violation without a red-CI round-trip. Markdownlint lints every `SKILL.md`; the corpus disabled the rules its legacy files already violate (see `.markdownlint-cli2.jsonc`), so a new skill still has to pass the rest — e.g. unique headings (MD024) and blank lines around tables (MD058).

**A fifth CI gate isn’t among those four, and it fires on the new file’s own prose: `check-new-line-breaks`, a separate workflow that rejects a line you add which packs more than one sentence, or which reaches 80 characters and carries a mid-line semicolon.** Its scope is **Markdown only** (`globs: '*.md'`), minus the `paths-ignore` set — `codex-skills/**`, `docs/**`, `_site/**`, `.quarto/**`. So it scans every `.md` the skill touches, and it never scans the generated wrappers, which must not be hand-edited to satisfy a gate that does not read them.

`scripts/semantic-line-breaks.py` is **not** that gate. As of ai-config#2085 it loads the same checker the gate pins, so `--write` splits a mid-line semicolon the gate would flag rather than manufacturing one. The script is still a reformatter of named files, not the diff-scoped job: take the verdict from the real check, whose runnable command is in [`semantic-line-breaks`](../../shared/writing/semantic-line-breaks.md). The gate only flags **lines this branch actually changed against `origin/main`**, so run the reformatter against every file the skill touches, not just the new `SKILL.md`. Add `--write` to apply once you’ve confirmed the diff is what you expect. **Don’t reach for `--all` by default** — it widens the reformat to the whole file, and on a file with pre-existing hard-wrapped (but otherwise CI-clean) prose it can rewrite hundreds of untouched lines into a large, unrelated-looking diff. Prefer the scoped mode, and if it under-fixes a paragraph (a same-sentence line shows up as “still would change” on a second scoped run even though `git diff origin/main` shows that region untouched), just fix that one paragraph by hand instead of widening scope.

**The 8000-char skill-listing budget lives inside `validate-skills.py`, not a separate script.** Adding a skill grows two catalogs at once — `skills/` (this repo’s own routing prompt) and `codex-skills/` (the Codex-wrapper mirror) — and `validate-skills.py` reports both totals even when neither is over budget, so a passing run still tells you your margin. If either is over, shorten **this skill’s own** `description` field rather than editing an unrelated skill’s frontmatter to make room. Re-run `sync-codex-skill-wrappers.py` after any frontmatter edit, since the Codex listing is derived from it.

Then, as their own explicit steps (don’t leave them buried in a comment):

1.  **Request the reviewer:** `gh pr edit --add-reviewer <reviewer>` (`EDIT_PR`; see `request-pr-review`).
2.  **Drive to clean:** run the `ardi` skill on the new PR until the verdict has zero findings.

> Why `git -C … rev-parse --show-toplevel` over `dirname "$(readlink …)"`: bare `readlink` (no `-f`) resolves only a single hop and behaves inconsistently across macOS/Linux; `rev-parse --show-toplevel` returns the repo root directly regardless of how the symlink chain is set up.

## Relationship to other skills

- **`spot-skill-opportunities`** — the recognition step that runs before this one: it notices, continuously and in the moment, that a pattern is skill-shaped and hands off here to build it. `ums` / `record-learnings` route through it too rather than judging recurrence themselves.
- **`ums` / `record-learnings`** — when a session reveals a workflow worth codifying, they hand off to this skill to build it.
- **`memorize` / `remember`** — for a one-line fact or preference (not a procedure), write a memory instead of a skill.
- **`request-pr-review`, `ardi`** — used to ship and clean the new skill’s PR.
- **`simplify` / `tidy`** — when extending, prefer collapsing into an existing skill over proliferating near-duplicates.
- **`consolidate-skills`** — when you discover a near-duplicate that already shipped (two real skills for one workflow), hand the cleanup there: it merges them into one canonical skill plus alias stubs.
- **`decompose-skill`** — when Step 0 finds the closest existing skill to extend is actually two concerns wearing one name, hand the cleanup there instead of bolting a third concern on.
- **`heal-skill`** — the repair counterpart: this skill authors a skill, `heal-skill` fixes one that misfired after it shipped.
- **`agent-builder`** — the subagent-file counterpart: this skill authors user-invocable workflows in `skills/`; `agent-builder` authors the persistent, read-only fan-out worker personas a heavy skill’s subagent step can promote to `.claude/agents/<name>.md`.
- **`link-skills`** — this skill cross-links the one skill it authors; `link-skills` is the corpus-wide audit that catches cross-reference gaps a single authoring pass missed.
- **`config-ai`** — the broader router this skill is one destination for: when a request names a capability but not a mechanism, `config-ai` decides whether it’s a skill (→ here), a subagent, a memory, a hook, or a `gha` capability, then hands off accordingly.

## Anti-patterns

- ❌ Creating a new skill when an existing one should be extended (skipping step 0).
- ❌ Searching only `skills/` in step 0 – `scripts/` and `hooks/` hold the instruments a procedural skill is likeliest to duplicate, so a clean grep over `skills/*/SKILL.md` alone is not evidence the capability is missing (#1055/#1056).
- ❌ Not scanning other branches → colliding parallel work / duplicate skills.
- ❌ Not checking open PRs → building a second draft of a skill someone already pushed and opened a PR for, instead of redirecting to it.
- ❌ Duplicating canonical content across alias files (aliases must only redirect).
- ❌ Hand-writing an alias `SKILL.md` directly (raw `Write`) instead of routing through skill-builder — skips codex-wrapper regeneration (trips `validate`) and the self-review pass (`giardia`→`gia`, \#569).
- ❌ A thin description with no trigger phrases — the skill never gets discovered.
- ❌ In a subagent-fanning skill, writing the subagent prompt as if it inherits this skill’s text — it doesn’t; restate every needed discipline in the prompt.
- ❌ `name:` not matching the directory name.
- ❌ Encoding a standing rule in the skill but not in `preferences.md`.
- ❌ Naming a GitHub MCP tool (or `gh`/`git` operation) the skill uses without registering it in `tool-mappings.yml` — the reviewer flags the unregistered name as a possible hallucination (`push-memory` \#311, `resolve-pr-threads` \#347).
- ❌ Bumping `skills.qmd`’s skill count by a manual +1 instead of re-deriving it from `ls -d skills/*/ | wc -l` — it drifts whenever `main` gains other skills mid-review (`resolve-pr-threads` \#347).
- ❌ Citing a `CLAUDE.md` section or an “existing scale/convention” in new skill prose without grepping to confirm it actually exists first (`check-info-quality` \#349).
- ❌ Leaving the new skill as a local-only uncommitted file (or pushing direct to main).
- ❌ In a worktree session, writing the skill files to the `rev-parse --show-toplevel` path — it resolves to the main checkout (via the `~/.claude/skills` symlink), not your worktree, so the files land on another session’s branch. Author in the worktree’s own `skills/` dir.

Back to top
