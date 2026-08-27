# Claude Code harness & agent tooling

## Copilot tool availability can change mid-session

- Honor `tools_changed_notice` events literally. If a notice says a tool is no
  longer available (e.g., `create`, `edit`), switch immediately to still-listed
  alternatives (typically `apply_patch` + `view` + `bash`) instead of retrying
  the removed tool.
- For UMS/maintenance passes this matters because stale muscle memory ("use
  create/edit") can fail repeatedly after the tool list changes.

## Web fetching lives in its own file
- `WebFetch`, `raw.githubusercontent.com` fallbacks, and what a fetch
  actually returns are in
  [`claude-code-webfetch.md`](claude-code-webfetch.md).

## Claude Code on the web: CI monitoring toggles have no default setting
- The per-PR "CI monitoring" panel (web session sidebar) shows two toggles,
  **Auto-fix CI & address comments** and **Auto-merge when ready**. There is
  **no account-, org-, repo-, or environment-level setting to default these on**
  — confirmed against https://code.claude.com/docs/en/claude-code-on-the-web.
  Each new PR/session starts with both off and they must be toggled manually.
- Closest workaround: run `/autofix-pr` from the CLI on a PR's branch — it
  spawns a web session with **Auto-fix CI & address comments** already on for
  that PR. There's no CLI shortcut for **Auto-merge when ready**; that one
  always needs a manual toggle. A true default would require a feature
  request via `/feedback`.
- **No tool on the agent's side can toggle this itself.**
  Checked the full available toolset (Bash, every loaded MCP tool, and
  `update-config`, a skill rather than an MCP tool) for a client-side
  settings lever and found none: the panel is client-UI-only state, not
  something `update-config`'s `settings.json` surface reaches.
  If the user reports the checkbox changed, that's their action, not
  something to claim credit or responsibility for.
- **What actually fires once "Auto-fix CI & address comments" is on:**
  the harness starts pushing `<ci-monitor-event>` messages mid-turn
  (arriving alongside the next tool result, same delivery mechanism as a
  background task notification) whenever the PR gets new activity ---
  a formal review (via the reviews API) or a plain issue/PR comment,
  observed firing on both.
  Each event quotes the comment(s) verbatim and appends a **fixed
  instruction template**: "address the feedback and push a fix... post
  a one-line reply on the thread... end with
  `_🤖 Addressed by Claude Code_`... resolve the thread... skip replies
  for comments you didn't act on."
- **That template is boilerplate applied to every new comment, not
  gated on whether the comment is a real finding.**
  Observed firing on: a Copilot quota-refusal ("unable to review...
  reached their quota limit"), a Copilot "wasn't able to review any
  files" refusal, and a sticky PR-preview-deploy comment
  (`rossjrw/pr-preview-action`) that just posts a preview URL and
  updates in place on every push.
  None of those carry an actionable finding.
  Treat every `<ci-monitor-event>` as a prompt to go verify the PR's
  actual state via the API (`gh api .../issues/.../comments`,
  `gh pr checks`) rather than complying with "push a fix" reflexively:
  the template's own trailing clause ("skip replies for comments you
  didn't act on") is the license to do nothing when there's nothing to
  do, and it's worth reading, not just the imperative sentence before
  it.

## AskUserQuestion (Claude Code harness tool)
- Each entry in `questions[]` **requires a `question` field** (the full question
  text) — `header` + `options` alone fail with `InputValidationError: required
  parameter questions[0].question is missing`. Easy to omit when you build the
  call from options first; include the `question` string every time.
- **`Tool permission request failed: Error: Tool permission stream closed before
  response received`** is a **transient** harness glitch, not a user denial —
  **retry the same call.** Hit AskUserQuestion twice and `ExitPlanMode` twice in
  one web session; every retry went through. Applies to any permission-gated
  harness tool (AskUserQuestion, ExitPlanMode, …), so don't abandon the
  interactive flow or fall back to a workaround on the first failure. (A genuine
  denial reads differently — the user declining the specific action.)
  **But don't retry indefinitely if it keeps failing.** In a different web
  session, the same error hit AskUserQuestion twice in a row with no successful
  retry in between. Rather than looping a third time, asking the same question
  in plain chat text worked fine and got an answer. One or two retries is
  reasonable; past that, fall back to a plain-text question rather than
  blocking the turn on a tool that isn't recovering. (ai-config#493 fix-up
  session, 2026-07-05.)

## Bash tool runs under zsh — avoid bash-isms & reserved variable names
- The Bash tool's shell is zsh-initialized, where some names are **read-only
  special variables**: `status`, `path`, `pipestatus`, `argv`, `options`, `?`.
  Assigning to them (e.g. `status=$(...)` in a poll loop) fails with
  `read-only variable: status` and aborts the command.
- Use neutral names instead — `st`, `rc`, `out`, `p`. Bit a `gh run view`
  status-poll loop once; renaming `status`→`st` fixed it.
- **No bash-only builtins.** `mapfile`/`readarray` are undefined in zsh —
  `mapfile -t arr < <(cmd)` fails with `command not found: mapfile`. Iterate the
  glob/list directly instead, e.g. `for d in skills/*/; do s=$(basename "$d");
  …; done`, rather than slurping into an array first. This matters double for
  **skill command blocks**: the user's local shell is zsh too, so a command
  block I write into a skill gets run under zsh — keep it bash/zsh-portable.
  (A `mapfile` loop in the link-skills draft failed this way; PR #71.)
- **Process substitution breaks in a pipeline.**
  `diff <(a) <(b)` works alone but fails under zsh once it feeds a pipe, with `/proc/self/fd/N: No such file or directory` --- and a downstream `grep -c` then reports a false `0`.
  Bash runs the same line fine, so it survives review.
  Use temp files instead.
  See [`memories/zsh.md`](zsh.md), "A process substitution feeding a pipeline fails under zsh".

## Skill command blocks — resolve the ai-config repo root with the per-skill symlink
- To `cd` to the repo root from inside a skill, use the **per-skill** form
  `git -C ~/.claude/skills/<this-skill> rev-parse --show-toplevel`, never the
  bare-parent `git -C ~/.claude/skills rev-parse --show-toplevel`. `bootstrap.sh`
  may symlink skills
  *per-child* into a real `~/.claude/skills` directory, so the parent isn't a
  symlink into the repo and `git -C` there fails with "not a git repository".
  The `@claude` reviewer enforces the per-skill form on new skills (it flagged
  the bare-parent form on PR #71); `skill-builder` and `ums` already use it.
- Issue #36 originally proposed the bare-parent `git -C ~/.claude/skills
  rev-parse --show-toplevel` — but that example is the unreliable one (it can
  error with "not a git repository", not a security risk). #36 was closed by
  PR #110, which standardized on the **per-skill** form for `record-learnings`
  and `memorize`; PR #109 swept the last straggler #110 missed (`find-overlap`).
- **Worktree caveat:** the resolved toplevel is the **MAIN** checkout, often on
  another session's branch — don't author files there. Work in your own
  worktree's `skills/<name>/` dir (full rationale in `skill-builder`'s Ship-it
  caveat).
- **Use `<angle-bracket>` placeholders in command blocks — never bare ALLCAPS.**
  `PATH`, `URL`, `TARGET`, etc. look like shell env vars: bare `PATH` looks like
  the `$PATH` env var, and `path` is a zsh special that mirrors `$PATH`. A reader
  who copies the command without substituting the placeholder runs something wrong.
  Use `<path>`, `<url>`, `<target>` instead. (PR #99 fixed `test -e PATH` →
  `test -e <path>` and `curl … URL` → `curl … <url>` in purge-hallucinations.)
- **A trailing `# TOKEN` annotation on a `\`-continued line swallows the
  continuation.** When annotating a command with an inline marker comment
  (e.g. the `tool-mappings.yml` abstract-operation-token pilot, #195/#415),
  putting `# TOKEN` on a line that ends in a line-continuation `\` breaks the
  command: bash's `#` starts a comment that runs to the end of the line,
  consuming the `\` along with it, so the next line's flags are no longer
  part of the same command. Put the annotation on the **last** line of a
  multi-line command (after the final flag/filter), never on an intermediate
  `\`-continued line. The `@claude` reviewer caught this on PR #415's first
  pass (`skills/ardi/SKILL.md`'s `gh pr list \` / `--jq ...` block) — worth
  checking for on every subsequent skill in #416's token-rollout.
- **Verify a brand-new `tool-mappings.yml` `github_mcp` tool name with
  `ToolSearch` before adding the operation, not after.** When #416's
  token-rollout needs a new operation whose GitHub MCP form hasn't been used
  in this repo yet, the tool name is easy to *guess* correctly by pattern
  (e.g. `mcp__github__search_issues` from the existing
  `mcp__github__search_pull_requests`) but still worth confirming live —
  `ToolSearch({query: "select:mcp__github__<name>"})` returns the real schema
  if it exists, or no match if it doesn't. Doing this before adding the row
  avoids a review round-trip flagging the name as unverified (batch 2, PR
  #419): the reviewer couldn't confirm the tool from a static read and had to
  ask for a live check, which a rebuttal citing the schema then resolved
  anyway. Front-load that ToolSearch call and note in the row's PR
  description (or commit message) that it was verified, so the review can
  skip straight past it.
- **`PUSH` was an imperfect fit for remote ref/tag *deletion* — resolved.**
  Flagged as a non-blocking observation by the `@claude` reviewer on batch 3
  (PR #423, `skills/slide-tag/SKILL.md` and `skills/ts/SKILL.md`'s
  `git push origin :refs/tags/<tag>`): the registry's `PUSH` operation is
  documented as "push commits to a branch," and a colon-prefix ref-delete
  pushes nothing and isn't a branch. Initially left as `PUSH` (two instances,
  not the rollout's main surface) with a note to revisit if the pattern
  recurred. It did, a third time, in batch 4 (`clean-branches`'s
  `git push origin --delete <branch>`) — past the self-set threshold — so
  batch 4 added a dedicated `DELETE_REF` operation to `tool-mappings.yml` and
  retro-fitted all three sites (including the two already-merged ones) from
  `PUSH` to `DELETE_REF`.

## ai-config memory file structure
- Memory files (`memories/*.md`) **may** carry YAML frontmatter (`name`,
  `description`, `metadata`) — while older ones
  start directly with a `#` heading. Don't assume either form: `grep -rn "^name:"
  memories/` finds the frontmatter'd files, and a file without it is still valid.
  Preserve whatever frontmatter a file already has rather than stripping it.
- `[[link]]` cross-links in skills and memories resolve to **skill directories**
  (`skills/<target>/`), not to named entries in memory files. To verify a
  `[[target]]` link: `ls skills/<target>/`. If no skill dir exists, fall back to
  searching memory headings: `grep -rn "^# .*<target>" memories/`.
- System skills (e.g. `claude-api`) may be globally available but have no local
  `skills/<name>/` directory. An absent local dir means ❓ Unverifiable, not
  ❌ Fabricated — check the session's available-skills list before classifying.
- **Editing one frontmatter field programmatically: replace that field's text,
  don't re-serialize the mapping.** Parsing a `SKILL.md`'s frontmatter with
  `yaml.safe_load`, changing one key, and writing it back with
  `yaml.safe_dump` reformats every *other* key too -- most visibly, an
  `allowed-tools` block goes from block-sequence style (`  - Bash`) to
  flush style (`- Bash`). Both are valid YAML and nothing errors, so the
  churn only shows up in the diff size. Do a targeted regex replacement of
  the `description:` entry through to the next top-level key instead, and
  emit the value via `json.dumps` (a valid YAML double-quoted scalar, and
  the style several skills already use). Pass the replacement as a **lambda**
  rather than a string: `re.sub` parses a string replacement as a template
  and interprets its backslash escapes, and `\u` is not one of the escapes
  that template accepts, so a `json.dumps` result containing `\uXXXX` raises
  `re.error: bad escape \u`. (Distinct from a group-reference failure, which
  reports `invalid group reference` instead -- `\1` and `\q` produce
  different errors, confirming `\u` fails as an unrecognized escape, not as
  a mis-parsed group.) A lambda skips template parsing entirely, so its
  return value is used verbatim. This only bites when the value actually
  contains non-ASCII -- `json.dumps` defaults to `ensure_ascii=True` and
  emits `\uXXXX` only then -- but the lambda costs nothing and removes the
  conditional. (ai-config#700: the safe_dump
  approach turned a 63-line change into 427 insertions across 63 files
  before being reverted and redone surgically.)

## Custom subagents (`.claude/agents/*.md`) — Bash is a write-access loophole

The `tools:` frontmatter field (comma-separated, e.g. `tools: Bash, Read,
Grep, Glob`) is the correct, harness-enforced way to restrict a custom
subagent — confirmed against the real docs
(<https://code.claude.com/docs/en/sub-agents>). But blocking `Edit` and
`Write` does **not** make an agent read-only if it still has `Bash`: shell
commands (`sed -i`, `echo >`, `git commit`, `renv::update()` without
`check = TRUE`) write to the filesystem regardless of which Claude tools are
in the allowlist. Only an agent with *no* `Bash` (e.g. `WebSearch, WebFetch,
Read, Grep, Glob`) gets a genuine harness-enforced read-only guarantee.
When an agent needs `Bash` for read-only shell checks (`grep`, `gh api`,
`git status`), describe the isolation honestly as "no Edit/Write tool use;
avoiding write-capable shell commands is instruction-level discipline" —
don't claim an unconditional "nothing can be modified" guarantee. (Caught
across three review rounds on ai-config#341, `hallucination-detector` and
`dependency-auditor`.)

## Monitor scripts: don't pipe a `grep -q` into another `grep` -- `-q` suppresses stdout too

`grep -q` is silent by design -- it exits 0/1 and prints nothing, even on a match (unlike `-l`,
which prints the matched filename, or `-c`, which prints a count -- only `-q` produces zero
stdout). Piping its (empty) stdout into a second `grep -qi "..."` therefore ALWAYS sees an empty
input and ALWAYS fails to match, regardless of the actual content -- e.g.
`gh pr checks N | grep -qv "pending" | grep -qi "^check-name.*(pass|fail)"` silently never fires,
looping until the `Monitor` call's own timeout kills it, with no error to signal the mistake (the
loop just runs quietly and "times out" looking like slow CI rather than a broken filter). Test the
condition directly against the ORIGINAL command's output instead of chaining greps:
`line=$(gh pr checks N | grep "^check-name"); ! echo "$line" | grep -qi pending && echo "$line"`.
More generally: before arming a `Monitor` loop, mentally trace what each pipe stage's STDOUT
actually contains -- a `-q` flag upstream of a later stage that reads stdout (or `-l`/`-c`
replacing the original content with just a filename or count) is
the tell. (Sparta gii-ffdb93 session, 2026-07-14: caught only by comparing the monitor's silence
against a manual `gh pr checks` call showing the check had already resolved.)

## Wiring ai-config skills/memories into a consumer repo's `claude` bots

`bootstrap.sh` only reaches local CLI sessions --- a consumer repo's
`claude`/`claude-code-review` bots (running via `Morrison-Lab/gha`'s reusable
workflows and `anthropics/claude-code-action`) get nothing from it. The
pattern that worked, with no workflow changes needed, on `d-morrison/rme#982`
and `ucdavis/epi204#360`:

1. `git submodule add https://github.com/Morrison-Lab/ai-config.git .ai-config`
   in the consumer repo.
2. Replace any hand-copied `.claude/skills/<name>/SKILL.md` (these drift ---
   confirmed via `diff` against ai-config's canonical copy before removing)
   with a **committed symlink** `.claude/skills -> ../.ai-config/skills`, so
   all of ai-config's skills become discoverable, not just the one that was
   hand-copied. `.claude/commands/` was left as-is in both repos --- those
   were genuinely project-specific, not ai-config duplicates.
3. Check `.gitignore` for a blanket `.claude/*` ignore (rme had one, with an
   existing `!.claude/commands` exception already carved out for the same
   reason). If it's there, add `!.claude/skills` alongside it, or `git add`
   silently skips the new symlink as ignored. If `.claude/skills/` was
   already tracked as a real directory, also run
   `git rm -r --cached .claude/skills` first, to clear it from the index
   before the symlink can be staged in its place.
4. Confirm `checkout-submodules: true` (or an unconditional
   `git submodule update --init --recursive`, as in rme's bespoke `claude.yml`)
   is already set on both bot workflows --- both repos already had it, so no
   workflow edit was needed.

The committed symlink survives `claude-code-action`'s `restoreConfigFromBase`
(which wipes/restores `.claude/` from the base branch on PR-triggered runs)
because it's part of that committed base --- this is the same technique
ai-config's own repo already uses for its own `@claude` bot. `memories/` and
`shared/` get no equivalent auto-load mechanism (Claude Code doesn't scan a
project memories folder the way it does skills), so they're just readable
on disk, not injected into context automatically --- unless the consumer's
own `CLAUDE.md` explicitly pulls specific files in with Claude Code's
`@path` include syntax, e.g. `@.ai-config/memories/tools.md` or
`@.ai-config/shared/workflow/ardi.md` (the path is `.ai-config/`-prefixed
in a consumer repo, unlike ai-config's own `@claude` bot, which resolves
`@shared/...` straight from the repo root --- see this repo's own
`README.md`, "Shared content (`shared/`)").

Two caveats a reviewer raised are worth pre-empting rather than leaving as
open questions.

A pinned submodule SHA that isn't `ai-config`'s current tip is still
fetchable with `git fetch --depth 1 origin <sha>` --- GitHub's shallow-clone
protocol supports fetching any reachable commit, not just branch tips.

**A `--depth 1` shallow clone gives a bogus merge-base, so a `git log A..B`
/ `git diff A..B` range against another branch shows the *entire* repo as
added.** In a shallow clone the histories of two branches share no common
ancestor git can see (it's truncated), so `origin/main` and a feature branch
appear fully disjoint --- `git log <branch>..origin/main --stat` reports
hundreds of files / thousands of insertions that aren't real, and a real
`git merge origin/main` produces spurious mass conflicts. Don't run
merge/diff-vs-main operations on a shallow clone. What *is* reliable on a
shallow clone: single-tree reads (`git show origin/main:<file>`,
`git cat-file`) --- they read the fetched tip's tree directly, no merge-base
needed.

**The same truncation degrades classifiers built on file history, and how
badly depends on which question you ask -- so test the query rather than
assuming either that it works or that it doesn't.**
A bogus merge-base announces itself, with thousands of phantom insertions or a
merge that explodes into conflicts.
A history *query* just comes back empty, and empty is also a legitimate answer,
so it cannot be told apart from a real negative by looking at it.

Two questions that appear interchangeable behave very differently on a
shallow clone of this corpus:

- `git log --diff-filter=D -- <path>` ("was this ever deleted?") returned
  **zero for every candidate**, ours and foreign alike, at depth 50.
  A deletion that happened before the shallow window is simply not in it, so
  this question is unanswerable here while appearing answered.
- `git log --all -- <path>` ("has the repo ever touched this?") **did**
  discriminate, on the same clone at depth 55: zero for all seven Anthropic
  built-ins, against 6 for `ums`, 3 for `ardi` and 1 for `config-ai`.
  An actively maintained file gets touched inside almost any window, which is
  what makes the weaker question survive truncation.

The five commits gained between those two measurements are not what produced
the discrimination, which is the obvious objection and worth foreclosing:
none of them touches `skills/ums`, `skills/ardi` or `skills/config-ai`, and
every commit behind those three counts predates all five.
The second form would have separated the two classes at depth 50 as well.

The residual risk in the second form is a file that is genuinely ours but has
not been touched within the window, which reports as never-ours.
So the rule is not "history is useless when shallow" but: check
`git rev-parse --is-shallow-repository`, then **run the query against known
controls of both classes** before trusting it, and prefer a signal carried by
the file itself when one exists.
Note what "both classes" costs here, because this corpus could not supply it:
there was no deleted-but-still-installed skill to test against, so the
observed separation only shows the query telling *never ours* from *ours and
actively maintained*, never the class it claims to catch.
That is the same gap the residual risk above names, arrived at from the other
direction, and it is why the query is worth reporting to a human rather than
trusting.
[`ardi.md`](../shared/workflow/ardi.md)'s "test the class it distinguishes"
bullet is the review-time counterpart to this entry: this one says why a
history query fails on a truncated clone, that one says to confirm a true
positive of the class exists in what you tested before claiming the mechanism
separates the cases at all.
(ai-config#765/#770, 2026-07-28: separating our own deleted skills from
Anthropic-provided built-ins under `~/.claude/skills/`.
The `--diff-filter=D` form was measured first and its blanket zero suggested
history was unusable here; a bare `git log --all` over the same candidates in
the same shallow clone separated the two cleanly.
The file-borne signal that needs no history at all: the built-ins carry
`license: Proprietary. LICENSE.txt has complete terms`.)

`git fetch --depth N origin <branch>` deepens enough history to make
a real merge-base available if you must merge. (Hit resolving
UCD-SERG/serocalculator#503's altdoc chain, 2026-07: a `--depth 1` altdoc
clone made `recursive-qmd-search..origin/main` show 272 files / 14k
insertions, all an artifact; the `git show origin/main:R/utils.R` tree reads
in the same session were accurate.)

A fine-grained `SUBMODULES_TOKEN` scoped to a private submodule (e.g. rme's
`latex-macros`) also authenticates a newly-added *public* submodule, since
public repos need no authentication --- confirmed empirically by the PR's
own `claude-review` check (which runs with submodule checkout on) completing
successfully. (rme#982, epi204#359/#360, 2026-07-04.)

## A `PreToolUse` hook denies on stdout and still exits 0, so an exit-code check reads a denial as an allow

A hook blocks a tool call by printing its decision to stdout and returning
success:

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "..."}}
```

The process exits 0 while doing it.
So a harness that classifies by exit status --- `rc != 0` meaning blocked,
`rc == 0` meaning allowed --- reports a correctly-denying hook as having
permitted the call.
That is a false negative on the one question such a harness exists to answer,
and it is the [`fail-fast`](../shared/principles/fail-fast.md) shape where the
pass path and the failure path print the same thing: denying and permitting
both exit 0, so the exit status cannot separate them.

Read the decision out of stdout instead, and keep a non-zero exit meaning what
it actually means --- the hook crashed:

```python
if p.returncode != 0:
    sys.exit(f"FATAL: hook exited {p.returncode}")   # a bug, not a block
blocked = '"permissionDecision": "deny"' in p.stdout
```

Exiting 2 is a genuine blocking mechanism in Claude Code, and
[`permission-check`](../skills/permission-check/SKILL.md) documents it --- but it
is not the one this repo uses.
Every hook here signals on stdout and returns 0
(`grep -rn 'sys.exit(2)' hooks/` returns nothing, measured 2026-08-04), so an
exit-code classifier would read **every** blocking hook in `hooks/` as allowing
its call.
Knowing only the exit-2 path is therefore enough to build exactly this bug.

Absence of a `permissionDecision` key is a third state, and it is not an allow:
it defers to the normal permission flow, which is what an inject-only hook
wants.
Naming `"allow"` there would suppress a prompt the user would otherwise have
seen.

- **Do:** decide blocked-versus-allowed from the stdout JSON, and treat a
  non-zero exit as a crash to fail loudly on.
- **Don't:** label a hook result from its exit code --- a denial and an allow
  are both 0.

(Verified 2026-08-04 against `hooks/require-gh-repo-flag.py`, whose deny branch
is a `print(json.dumps(...))` at lines 103--109 followed by `return 0` at line
110.
The harness that surfaced this was exercising a different hook, one proposed in
ai-config#1139 and so not on `main` while that PR stays open; the mechanism is
identical, so this entry cites the merged instance instead.
That harness labelled its rows `rc != 0 -> BLOCKED`, and so reported the hook as
allowing a command it had correctly denied.)

## A plugin ref resolves by the marketplace's *declared* name, not by its URL

The section above covers the submodule-plus-symlink path.
The other way a repo consumes ai-config is the **plugin marketplace** ---
`.claude/settings.json`'s `extraKnownMarketplaces` / `enabledPlugins` for a
web/cloud session, and gha's `use-ai-config` input for the bots.
That path has a failure mode the submodule path does not, and it is worth
knowing because the obvious diagnosis is the wrong one.

For how an `enabledPlugins` entry resolves when more than one settings scope
names the same plugin, see
[`claude-code-settings.md`](claude-code-settings.md).

A plugin is installed as `<plugin>@<marketplace>`, and `<marketplace>` must
match the `name` field the marketplace declares in its own
`.claude-plugin/marketplace.json`.
It is **not** derived from the URL you registered, and the two can disagree
--- most easily when a repo moves orgs and renames the marketplace with it.

The clone URL keeps working throughout, which is what makes this hard to
read.
Git and `gh` both follow GitHub's transfer redirect, so the old URL clones
fine and the marketplace registers itself under its *new* declared name.
The log then says both things on adjacent lines:

```
Adding marketplace: https://github.com/Morrison-Lab/ai-config.git
✔ Successfully added marketplace: Morrison-Lab (declared in user settings)
Installing plugin: ai-config@the repository owner
✘ Failed to install plugin "ai-config@the repository owner": Plugin "ai-config" not
  found in marketplace "the repository owner".
```

Only the name lookup fails, and it fails hard: `claude-code-action` aborts
the whole job, so every `@claude` run in the repo goes red at once.

Read the marketplace's own manifest rather than inferring the name from the
URL or the org: `git show origin/main:.claude-plugin/marketplace.json` gives
the authoritative `name` and the plugin list in one call.

Two consumers to fix, not one --- they are configured independently and a
fix to either leaves the other broken.
gha's reusable workflows carry the built-in ref (`gha#359` retargeted
`claude.yml` and `claude-code-review.yml`), while each consuming repo's own
`.claude/settings.json` carries its own copy for web/cloud sessions
(`UCD-SERG/serodynamics#280`).
Grep for the old `<plugin>@<marketplace>` string across both layers.

- **Do:** read the declared `name` from `.claude-plugin/marketplace.json`
  when writing or fixing a plugin ref.
- **Do:** fix the reusable-workflow default and every consumer's
  `.claude/settings.json` in the same sweep.
- **Don't:** infer the marketplace name from the clone URL or the GitHub
  org.
- **Don't:** read a working clone, or a successful "added marketplace" line,
  as evidence the plugin ref is right --- the redirect makes both succeed
  while the install still fails.
- **Don't:** treat a change to the declared `name` as a safe drive-by just
  because it looks like a stylistic nit (a casing fix, "matching
  convention").
  The field is a hardcoded string other repos and reusable workflows depend
  on byte-for-byte, so any edit to it needs every consumer grepped first,
  not just an org move.

(2026-07-29: ai-config renamed its declared marketplace from `the repository owner` to
`Morrison-Lab`.
Both consumers broke; the gha fix shipped when `v2` was slid to `c50e847`.)

(2026-08-06/07: the same failure recurred from the opposite direction.
`Morrison-Lab/ai-config#1238` lowercased `name` from `Morrison-Lab` to
`morrison-lab` as a one-line drive-by inside an unrelated marketplace-sync
fix, described in its own commit message as "matching convention".
`Morrison-Lab/gha`'s `claude-code-review.yml@v2` still hardcodes
`ai-config@Morrison-Lab`, so every dispatched review broke again, tracked
as `#1246` and fixed on `main` by `#1247`.
Nothing about #1238's own CI exercised the plugin-install path, so a
one-character casing change rode through green and merged clean.)

## A marketplace-name fix pushed to the reviewed PR's own branch cannot make that PR's own review pass

The natural next move once #1246 was diagnosed was to push the identical
one-line restore directly onto the *broken* PR's own branch (PR #1244) and
re-request review, expecting the dispatched review to go green on its own
fix.
It failed identically, with the same
`Plugin "ai-config" not found in marketplace "Morrison-Lab"` error --- the
diagnostic names the *requested* marketplace (from the hardcoded
`ai-config@Morrison-Lab` reference), not the one actually registered.

The reason is a property of `claude-code-action`'s `plugin_marketplaces`
input, not of anything wrong with the fix.
That input is a bare git URL with no ref attached, so the marketplace is
always cloned from ai-config's **default branch**, never from whatever ref
the calling workflow itself is running against.
A `workflow_dispatch`-triggered review job (this repo's caller declares
only `workflow_dispatch`; run 31151198279 records that event) still checks
out the *reviewed* repo's selected PR to do its work, but the plugin it
installs comes from a completely separate clone of ai-config's `main` ---
so a fix that lives only on a PR branch is invisible to that PR's own CI by
construction, however correct the fix is.

This generalizes past this one input: any CI mechanism that reads a
dependency's default branch unconditionally, rather than pinning to a ref
or reading the consumer's own checkout, cannot be exercised by a fix
committed to the very branch under review.
The tell is a fix that reproduces the identical failure after being pushed
to the affected PR, with no diagnostic difference from before the fix.
Before assuming a re-push should have worked, check whether the failing
step reads its input from a fixed ref rather than from the PR's own
checkout.

- **Do:** land a fix to a shared, ref-less dependency (a marketplace, a
  pinned action's default-branch input) on `main` first, then re-dispatch
  the review that depends on it --- don't expect a same-PR push to prove it.
- **Do:** check an input's own ref-resolution behavior (a bare URL vs. a
  pinned SHA/tag) before treating a same-PR retest as a valid verification
  step.
- **Don't:** read an unchanged failure after a same-PR push as evidence the
  fix is wrong --- it can mean the mechanism under test never saw the fix
  at all.

(`Morrison-Lab/ai-config#1244`, 2026-08-07: the restore commit
(`6f4dec8d`) was pushed straight to #1244's own branch first, "so this
PR's own CI doesn't have to wait on [#1247] merging" --- and still failed,
because the dispatched review's plugin install cloned `main`, which did not
yet carry the fix.
The real fix landed via `#1247` -> `main`, at which point #1244's review
could pass.)

## Bash tool cwd persists across calls — an easy trap when juggling sibling repo checkouts

The Bash tool's working directory carries over from one tool call to the
next within a session (per its own tool description), not just within a
single multi-line script. When a task touches several sibling repo
checkouts in the same session (e.g. `rme`, `epi204`, and their shared
`macros` submodule, each at its own path), a command issued without an
explicit `cd` silently runs wherever the *previous* call left off — not in
the repo the command's own text implies. This produced several
wrong-directory mistakes in one session: a `git log --oneline -1` meant for
`epi204/macros` instead reported `epi204`'s own root HEAD, and a `git push`
meant for `epi204` silently ran again in `rme` and printed
"Everything up-to-date" (which reads like a real, if uninteresting, result —
not an obvious error — so the mistake wasn't visually distinct from success).
When issuing single-line Bash calls across multiple repo checkouts in the
same session, either prefix every command with an explicit `cd
/path/to/repo &&`, or use `git -C /path/to/repo <command>` for read-only
checks — don't rely on remembering which directory the last call left you
in. (Session sliding the `macros` submodule pin in `d-morrison/rme` and
`ucdavis/epi204`, 2026-07-04.)

**A parallel batch is the same trap in its sharpest form.**
Two Bash calls composed into one message read as independent,
but they share the one persistent shell and run serially,
so the first call's `cd` decides the second call's repo.
A verification command labeled for repo B, batched after a sibling that
`cd`'d to repo A, returns repo A's clean status and HEAD under repo B's
label --- plausible output, wrong subject.
(Post-compaction verification batch, 2026-08-12: an ai-config
`git status` check ran in the sparta checkout this way, and its output was
initially read as the ai-config answer.)

**In an AGENT / subagent thread the cwd behavior INVERTS -- it RESETS to the
project root between Bash calls, so a `cd` does NOT persist.**
The main-session persistence above is a property of that tool;
an Agent thread's Bash tool resets the working directory to the project root
before every command (the harness states this outright: "Agent threads always
have their cwd reset between bash calls ... please only use absolute file
paths").
The danger is a compound command like `cd /some/dir && <destructive cmds>`
where the `cd` target is wrong: without `set -e`, a failed `cd` does NOT abort
the command -- the shell prints its error and the remaining commands run in the
RESET cwd (the project repo), so file overwrites, commits, and pushes silently
execute in the WRONG repository.

- **Do:** open every directory-dependent multi-step Bash command with `set -e`
  and use absolute paths, so a bad `cd` aborts the chain instead of running
  elsewhere.
- **Don't:** chain `cd /x && <writes>` in an agent thread without `set -e` --
  a failed `cd` leaves the writes running in the project repo rather than
  stopping.

**A main session has been measured RESETTING**, so don't infer persistence
from being in a main session.
Read the printed `Shell cwd was reset` line, per [`git-worktrees.md`](git-worktrees.md).
That line is not guaranteed: an MCP disconnect and reconnect can reset a main
session's cwd with nothing printed, leaving a failing relative-path command as
the only tell --- worded differently by each tool.
`sed`'s `No such file or directory` names a file, so it reads as the file being
missing rather than the directory being wrong --- re-run under `cd` first.
(2026-08-16, ai-config: `sed -n '393p' memories/github.md` produced exactly that
message, `git diff origin/main...HEAD` a different one, and both worked under `cd`.)

(2026-08-03: `cd /tmp/rpt-test && cat > .github/workflows/... && git commit &&
git push` ran in the `gha` repo -- clobbering a workflow file on a stray branch
-- because the `cd` target was wrong and there was no `set -e` to stop the
chain.)

## Workflow `agent()` — schema validates shape, not substance

A `Workflow`-tool agent can pass its `schema` validation while returning
content that's substantively worthless — schema validation only checks
shape (does the JSON have the right fields/types), never substance (is
the content real analysis or a placeholder).
Don't trust a synthesis-stage `agent()` result at face value just because
it validated — skim the actual content before building on it, the same as
any other agent's report. If it looks wrong or too trivial for the input
it was given, read `<transcriptDir>/journal.jsonl` (each earlier agent's
real return value is recorded there — a directly-observed path from the
transcript directory during the incident below, and the primary artifact
per the Workflow tool's own spec; `agent-<id>.jsonl` files are that spec's
documented fallback for when no journal is available, not a competing
name for the same file) and redo the synthesis by hand from those results
rather than trusting the degenerate output.
(Learned on `ai-config#554`, 2026-07-14: a Design-phase agent, handed
genuine, detailed findings from four parallel survey agents, returned
`{"summary":"test","changes":[{"gap":"test",...}]}` — a literal
placeholder that still matched the schema. Caught before treating it as
"no changes needed"; the actual gap analysis and PR content were
synthesized by hand from the survey agents' real `journal.jsonl` results
instead. This is also why `shared/workflow/when-to-orchestrate.md` now
carries a "schema checks shape, not substance" reminder in its
model/effort-routing section — this incident is the concrete case behind
that addition.)

## Workflow phase persistence --- an embedded-JSON persist prompt hits the request ceiling

A Workflow script has no filesystem API, so the tempting checkpoint move is a cheap `agent()` whose prompt embeds the phase output verbatim ("Write this JSON to `<path>`").
That prompt scales with the output, and the fan-in phases are exactly the ones that outgrow the request limit: a Scout-phase blob (106 findings from 10 scouts) made the persist agent's request ~202,713 tokens against a 200,000 limit, failing with `Prompt is too long`, while the smaller later phases (consolidated ideas, overlap assessments, synthesis) persisted fine --- so the failure arrives as a lost checkpoint at the phase you most wanted saved.
Nothing was actually lost: the run's journal (`subagents/workflows/<run-id>/journal.jsonl`, the same artifact the entry above reads for degenerate synthesis output) records every completed `agent()` result as a `{"type":"result",...}` line, and the file was reconstructed from it afterwards in a few lines of Python.
(Measured 2026-08-23, Windows 11 local Claude Code session.)

- **Do:** persist large workflow intermediates by extracting from the run's `journal.jsonl` (during or after the run), or hand the persist agent a path to read from rather than the content itself;
  reserve embedded-JSON persist prompts for small blobs, well under ~100k tokens.
- **Don't:** embed an unbounded phase output verbatim in a persist agent's prompt --- the scout/fan-in phases are the ones that outgrow the request limit, and nothing warns before the oversized call fails.

## Edit two-step move — delete-only silently drops content

Relocating a block of text with `Edit` (an `old_string` that spans the
block plus its surroundings, a `new_string` that omits the block,
intending to re-insert it via a *second*, separate `Edit` at the new
location) silently drops the content if that second `Edit` never actually
gets issued — the diff then shows a pure deletion, and nothing errors to
flag the gap.
This is a different failure from the "restoring/reconstructing a full
file's content" bullet in `preferences.md` (that one is about transcription
fidelity — accidentally omitting, altering, or inventing content while
intending a faithful reproduction from memory); here the exact right
content is known throughout, but a two-step move degrades to a one-step
delete when the second step is skipped. The same fix applies either way —
diff the result against the base branch — but check specifically that the
moved content is **present** at its new location, not just that the old
location no longer has it.
(Learned on `ai-config#554`, 2026-07-14: a fix instructed as "move this
3-line bullet to after paragraph Y" was executed as delete-the-bullet
only, leaving the file's net diff against `origin/main` empty for that
bullet entirely. Caught by a bot review reading the actual diff, then
independently reconfirmed with `git diff origin/main -- <path>` before
trusting the follow-up fix.)

## Scripted block move --- a marker-delimited range carries its neighbours

The mirror of the two-step-move entry above.
That one loses content; this one takes content nobody asked it to take.
Neither half of that entry's fix is sufficient here, and they fail
differently.
Its "check specifically that the moved content is **present** at its new
location" passes outright, because the block *did* arrive intact --- what
came along with it is the problem.
Its "diff the result against the base branch" does surface the evidence, but
does not flag it, for the reason this entry is about: the change renders as
one moved region rather than as a removal and an addition.

Moving a region by script --- extract from marker A to marker B, re-insert
elsewhere --- takes everything between the two markers, including whatever
happens to sit just before marker B.
A comment above the step you chose as the end boundary is the common one,
since a comment is *attached* to what follows it by convention and *adjacent*
to it by text, and only the second is visible to a range extraction.

Two things make it hard to see afterwards.
The diff renders as one moved region rather than a delete here and an add
there, so nothing in it reads as "this comment changed owner".
And the result is well-formed --- the comment is still a comment, still above
a step --- so a syntax check, a linter, and a YAML parse all pass.

The check is to diff for what *else* moved: after a scripted relocation,
confirm the block's first and last lines are the ones you intended, and read
the lines immediately outside both boundaries at the source and destination.

- **Do:** choose boundaries that exclude a preceding comment, or re-read both
  edges of the extracted range before writing.
- **Don't:** treat "the moved block is intact at its destination" as
  sufficient --- that is the other entry's check, and it is silent here.

(Learned on `Morrison-Lab/gha#547`, 2026-08-21: a step was relocated with a
Python extraction whose end boundary was the *next* step's `- name:` line, so
the comment between them travelled too.
It ended up describing an unrelated step, while the step it documented lost
its explanation.
Every check passed; caught by a bot review reading the diff.)

## `codex exec`: the auto-mode classifier denies `--sandbox danger-full-access`

Claude Code's auto-mode permission classifier **denies** a `codex exec` invoked
with `--sandbox danger-full-access` (reason: "[Create Unsafe Agents] ... runs an
autonomous agent with sandbox isolation and approval gates disabled", plus
"[Safety Bypass Flag]"). A user grant to *use* codex — even a standing one, e.g.
"use codex whenever examining the actual data" — does **not** extend to running
it with the sandbox disabled; that's a separate permission the user never named.

Use `--sandbox workspace-write` instead. It reads/writes inside the repo and
runs local interpreters, which covers essentially every delegation case
(inspecting a large data file, running an `Rscript`/`python` analysis, drafting
into a scratch file). Don't reach for full-access as the reflex — reach for it
never, and re-scope the task if it seems to need it.

`--sandbox read-only` also exists but blocks writing the temp script most
analysis delegations need, so `workspace-write` is the practical default.

## `codex` is NOT a read-only tool — `-s read-only` still executes commands

`codex exec -s <mode>` (long form `--sandbox`) takes `read-only`,
`workspace-write`, or `danger-full-access`. "Read-only" is a sandbox flag you
choose, not a property of codex — so don't treat codex as a read/analyze-only
delegate:

- **codex can write and execute.** `-s workspace-write` lets it create files and
  run builds, so it can take execution-heavy implementation work, not just
  reading and analysis.
- **Even `-s read-only` runs model-generated shell commands** — the mode
  restricts *filesystem writes*, not command execution. A `-s read-only` codex
  can still invoke `Rscript`, run a test, and read the result; it just can't
  modify files. (This is why the `workspace-write` default in the section above
  matters for *writing* a temp script, not for running one.)

So when deciding whether codex can take a task, ask what sandbox mode it needs,
not whether codex "can write." (Corrected on `ucdavis/bcs`, 2026-07-09:
over-generalized a "`-s read-only` for read/analyze" default into a capability
limit when asked why a delegation wasn't happening.)

## `codex` can report "logged in" while every `codex exec` fails on auth

`codex login status` prints "Logged in using ChatGPT" and yet `codex exec` dies
with:

> Your access token could not be refreshed because your refresh token was
> already used.

The status check reads the stored credential; it does not exercise the refresh.
So a stale/consumed refresh token looks healthy right up until you actually run
something. Re-running `codex exec` just reproduces it — this does not
self-resolve.

Fix: a **full re-login**, which is interactive and therefore the user's to run:

```
codex logout && codex login
```

Ask the user to run it with the `! ` prefix so the output lands in the session.
Verify with a real round-trip (`codex exec --skip-git-repo-check "Reply with
exactly: CODEX_OK"`), **not** with `codex login status` — which is what misled
you in the first place. (Hit on `ucdavis/bcs`, 2026-07-13: the auth failure
blocked a data-examination step for an entire session under the user's standing
"use codex whenever examining the actual data" rule, until they reset it.)

## `claude setup-token` opens a browser first, then blocks on a stdin read an agent session cannot satisfy

Never run `claude setup-token` from an agent session, under any guard.
Two separate facts, and the first one is why no guard helps.

**It opens a browser on the user's machine as its very first act.**
The command is an OAuth flow, so running it launches a real browser window on
whatever profile that machine's default browser happens to be on, in the
middle of whatever the user was doing.
That lands immediately, so a `timeout`, an `alarm`, a `< /dev/null`, or a
subshell does not prevent it.
The general rule is
[`growth-mindset`](../shared/workflow/growth-mindset.md)'s
"A timeout bounds how long you wait, not what the command already did".

**It then blocks reading an authorization code from stdin, after the user has
authorized.**
The hang is not a startup capability check and not a refusal to run
non-interactively.
The process reaches the browser step, waits for the authorization to complete,
and only then reads the code back from stdin.
In an agent-spawned process fd 0 is a unix socket rather than a terminal, so
that read can never be satisfied and the process sits there indefinitely.

That second half generalizes past this one command: any process an agent
spawns has a socket on fd 0, so anything that reads a terminal for input
blocks forever rather than failing.
It is the same shape as the `codex logout && codex login` case above, where
the fix is likewise the user's to run.

So the token has to be minted by the user, in their own terminal, and handed
back.
`scripts/rotate-claude-token.py` is written for exactly that -- it reads a
token on stdin, so the user runs
`claude setup-token | python3 scripts/rotate-claude-token.py --apply`
themselves.

- **Do:** ask the user to run `claude setup-token` in their own terminal, with
  the `! ` prefix when its output should land in the session.
- **Don't:** run it from an agent session behind a timeout, an `alarm`, a
  closed stdin, or a subshell -- none of those stop the browser.
- **Don't:** read a bounded probe's empty output as evidence it did nothing.

(2026-08-02, while verifying a claim written into
[ai-config#1056](https://github.com/Morrison-Lab/ai-config/pull/1056), the
skill filed against
[#1055](https://github.com/Morrison-Lab/ai-config/issues/1055):
`perl -e 'alarm 8; exec "claude","setup-token"' < /dev/null` returned exit 142
with no output, having already opened a browser window on the user's machine
on the wrong browser profile.
An unbounded run then measured the mechanism: `ps -o pid=,stat= -p <pid>`
reported `S`, alive and blocked, *after* the browser authorization completed,
and `lsof -p <pid> -a -d 0` showed fd 0 as a unix socket.)

## Resuming a subagent mid-run tends to restart its long check, not resume it — verify the process directly before nudging it again

When a background subagent pauses its own turn while a long-running local
check (a full test/coverage suite, a build) is still executing in the
background, sending it a follow-up message to "check the result" does NOT
reliably make it poll the existing run — in practice it tends to just
launch a FRESH invocation of the same check and wait on that one instead,
discarding the earlier run's progress. This repeated three times in a row
in one session (each resume costing ~4-6 minutes of the agent's own
reasoning plus a full ~15-20 minute check re-run) before switching
strategy. The subagent isn't lying about "waiting for the background run"
— it genuinely doesn't have a reliable way to reattach to a shell command
it started in an earlier turn, so a fresh nudge reads as "go check" and it
takes the simplest interpretation: run it again.

**Fix: verify the actual process state yourself before resuming, and when
you do resume, hand the agent unambiguous evidence so it doesn't restart
anything.** From the orchestrating session (not the subagent), check for a
live process directly (`tasklist | grep -i <binary>` in Git Bash/Cygwin,
`findstr /I <binary>` in native Windows CMD, `Get-Process -Name "..."` for
start-time/age via PowerShell, or `pgrep`/`ps` elsewhere) and wait on it
directly (`Wait-Process -Id <pid> -Timeout <seconds>` on Windows, or a bash
poll loop) rather than just re-pinging the
subagent and hoping. Once the process has genuinely exited (confirm via a
fresh process check, not just elapsed time), resume the subagent with the
specific evidence in hand ("I've confirmed no such process is running as
of `<timestamp>`; the run already finished — do NOT start a new one, read
its output and report") — this stops the same restart loop from recurring
on the next resume. This is strictly better than either blindly trusting
"still waiting" messages (which can repeat indefinitely) or arbitrarily
capping the number of resumes (which risks cutting off a genuinely
long-running check before it finishes).

This generalizes beyond any one tool: the same pattern applies to any
subagent orchestration where a delegated agent's own background command
outlives its turn — verify state from the outside, don't just ask again.
(Sparta `gii-mwc` session, 2026-07-19: hit on two independent subagents in
the same session, one implementing a casualty-reflow feature and one a
maneuver feature, each running the project's own `tools/check.sh` full
suite — direct process verification via PowerShell resolved both.)

## A harness pass can replace `~/.claude` skill symlinks with stale copies AFTER `SessionStart`

**Historical as of the symlink-install removal ([ai-config#2229](https://github.com/Morrison-Lab/ai-config/pull/2229)):** `bootstrap.sh` no longer symlinks into `~/.claude`, `check-install.py` is deleted, and the `UserPromptSubmit` hook that ran it is removed.
Keep this section as a record of the incident and its ordering lesson, and read its present-tense instructions as historical.

`bootstrap.sh` symlinked this repo into `~/.claude`, so a `git pull` normally
refreshed what the Skill tool loaded.
In a web container a later provisioning pass can overwrite a subset of
`~/.claude/skills/*` with real directories holding older content, and those
copies then shadow the repo for the rest of the session.

The ordering is the part worth remembering, because it decides where a repair
can live.
The clobber lands *after* the `SessionStart` hook, so a check wired there runs
before the damage and reports a clean install every single time.
Run it from `UserPromptSubmit` instead, guarded to once per session on the
payload's `session_id`, which is late enough that startup has settled.

Upstream, the copies are stale because `upload_skills.sh` is idempotent by
**skipping** any skill already present in the workspace rather than adding a
version, so a workspace copy stays frozen at whatever revision was first
uploaded (ai-config#769).
That also predicts the shape of the drift: the stale set is exactly the
long-standing skills, while anything added since the last upload is still a
working symlink.

Detect and repair it with `python3 ~/.claude/scripts/check-install.py --fix`
rather than by hand; ai-config#765 added it, and the repo's own
`UserPromptSubmit` hook runs it.
(ai-config#755/#765, 2026-07-28: 42 of 172 skills were stale in one container,
`ardi` at 80 lines against 403 and `ums` at 94 against 365, so the session was
running materially older versions of its own review procedures.)

## Custom slash commands have been merged into skills

`.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both create
`/deploy`, and they work the same way.
Existing `commands/` files keep working, so nothing breaks and nothing signals
the change.

Verbatim from
[Extend Claude with skills](https://code.claude.com/docs/en/skills), fetched
2026-08-04 (its inline doc link flattened to plain text):

> **Custom commands have been merged into skills.**
> A file at `.claude/commands/deploy.md` and a skill at
> `.claude/skills/deploy/SKILL.md` both create `/deploy` and work the same way.
> Your existing `.claude/commands/` files keep working.
> Skills add optional features: a directory for supporting files, frontmatter
> to control whether you or Claude invokes them, and the ability for Claude to
> load them automatically when relevant.

Three further facts from that page, all as of 2026-08-04:

- `https://code.claude.com/docs/en/slash-commands` and
  `https://code.claude.com/docs/en/skills` serve the **same document**, titled
  "Extend Claude with skills".
  So an old bookmark does not land you on an older, still-accurate page.
- When a skill and a command share a name, the skill takes precedence.
- Invocation is carried by **frontmatter**, not by directory.
  `disable-model-invocation: true` makes a skill user-only,
  `user-invocable: false` makes it model-only, and the default is that both can
  invoke it.
  Note the second field is narrower than it reads: `user-invocable` controls
  visibility in the `/` menu, not access through the Skill tool, so
  `disable-model-invocation` is the one that actually blocks programmatic
  invocation.

**The belief this corrects.**
That commands and skills are two mechanisms, told apart by file type, a command
being user-invoked-only and unable to bundle supporting files.
There is one mechanism, and the invocation contract is a frontmatter switch.
A supporting-file directory is an optional skill feature rather than the thing
separating two kinds.

This corpus is a live instance of the state that makes the retired distinction
feel current: 177 skill directories and exactly one `commands/` file
(`commands/release-pr.md`), counted 2026-08-04.

- **Do:** describe a `/name` invocation as a skill, and reach for frontmatter
  when the question is who may invoke it.
- **Do:** read a surviving `commands/*.md` file as a still-supported older
  spelling of a skill.
- **Don't:** infer from a file's directory whether a user or the model can
  invoke it.
- **Don't:** cite "a command cannot bundle supporting files" as a distinction
  between two mechanisms.

## `kill -0` reports an unreaped zombie as alive, so a "wait until it is gone" loop spins

When a test or a helper needs a **reliably dead PID** --- to exercise a
liveness check's dead branch, say --- the obvious construction is to spawn a
process, kill it, and poll `kill -0` until it fails.
That poll does not measure whether the process is dead.
It measures whether the process has been **reaped**, and those are different
events separated by however long the parent takes to collect the exit status.
A killed child that nobody has waited on is a zombie, and `kill -0` succeeds
on a zombie.

The gap is set by who the parent is.
Orphan the child first --- spawn it from a shell that then exits --- and it is
reparented to PID 1, so the reap latency becomes a property of whatever PID 1
happens to be in this container rather than of your code.

Measured 2026-08-12, `uname -sr` = `Linux 6.18.5-fc-v20`, PID 1 =
`process_api` (a Firecracker init, per `ps -o comm= -p 1`):

| construction | result |
|---|---|
| orphan, kill, observe immediately | `stat=Z`, `ppid=1`, and `kill -0` returns **0** |
| orphan, kill, poll `kill -0` until it fails | 151 to 161 polls, **1.79s to 1.95s** (3 trials) |
| `wait <pid>` from a shell that never owned it | `wait: pid N is not a child of this shell`, rc **127**, zombie unreaped |
| spawn, kill, and `wait` in **one** shell | `wait` returns 143, `kill -0` fails immediately, ~3ms (3 trials) |

Read the second row as the correction to the intuition, in both directions.
PID 1 here **does** reap, so the loop terminates rather than hanging forever ---
but it burns roughly two seconds doing nothing, and during that window every
`kill -0` answers "alive" about a process that has already died.
A helper that treats that answer as authoritative reports a dead process as
live, which is exactly backwards for a staleness check.

The third row is the trap worth knowing separately, because `wait` looks like
the fix and is not: it fails outright on a non-child, and reaps nothing.
The last row is the working form --- spawn, kill, and `wait` inside a single
shell, so that shell is the parent and the reap is synchronous.

Treat PID 1's identity and its reap latency as volatile, per
[`timestamp-volatile-claims`](../shared/writing/timestamp-volatile-claims.md):
both are properties of this container image rather than of Linux, and a
subreaper or a different init changes the second row's numbers or removes the
reap entirely.
Re-run `ps -o comm= -p 1` before relying on any of it.

- **Do:** spawn, kill, and `wait` in one shell when a test needs a PID that is
  reliably gone.
- **Do:** bound any `kill -0` poll and treat exhausting the bound as a result,
  not as a hang, per
  [`fail-fast`](../shared/principles/fail-fast.md).
- **Don't:** read `kill -0` succeeding as the process being alive --- it
  succeeds on a zombie, which is the one state a liveness check most needs to
  tell apart from alive.
- **Don't:** `wait` on a PID this shell did not spawn; it exits 127 and leaves
  the zombie in place.

## `TaskCreate`/`TaskGet`/`TaskUpdate`/`TaskList`/`TodoWrite` availability depends on invocation context, not just model (Claude Code v2.1.233+)

Claude Code v2.1.233's release notes (2026-08-14) state the built-in todo/task-tracking tool family (`TaskCreate`, `TaskGet`, `TaskUpdate`, `TaskList`, `TodoWrite`) is "no longer available on Opus 4.8, Sonnet 5, Fable 5, Mythos 5, and newer models" by default (`CLAUDE_CODE_ENABLE_TODO_TOOLS=1` restores them), and this was confirmed empirically in an **interactive CLI session** on Sonnet 5, 2026-08-20: neither name appeared in the top-level tool list nor in the deferred-tools `ToolSearch` catalog.

**But the absence does not generalize to every session on that model --- it may be scoped to invocation mode.**
A `claude-review.yml` dispatch reviewing this very entry (also Sonnet 5, same date, via `claude-code-action`) reported the opposite: `TaskCreate`/`TaskGet`/`TaskList`/`TaskUpdate` appeared in *its* deferred-tools catalog, and the harness's own "task tools haven't been used recently" nudge fired mid-session.
Same model family, same day, opposite result --- so the discriminator observed so far is invocation context (interactive CLI vs. a dispatched GitHub Actions review/agent session), not the model alone, and this has not been checked across enough contexts to state as a settled cross-context default.
`TaskOutput`/`TaskStop` are a different, still-present family (background **agent/job** management, not a personal to-do list) and don't substitute, in either context observed so far.

This complicates an assumption baked into two `memories/preferences.md` bullets written before the change: "keep a live TaskList" and "the harness already nudges toward this" both describe a default that may no longer hold in an interactive CLI session, but has NOT been shown absent in a dispatched review/agent session.
Neither bullet is wrong for a session where the tools *are* present (an older model, the env var, or apparently a dispatched review/agent context);
check the session's own tool list before assuming either way, rather than generalizing from one session's finding.

- **Do:** check whether `TaskCreate`/`TodoWrite` actually appear in *this specific session's* tool list before relying on --- or dismissing --- the "keep a live TaskList" guidance.
- **Do:** fall back to `CLAUDE.md`'s on-disk session lab notebook, or a plain scratchpad markdown checklist, for tracking multi-PR/subagent state when the task tools are genuinely absent in this session.
- **Don't:** brief a dispatched subagent to use `TaskCreate`/`TaskUpdate` without first confirming those tools are actually in *its* tool list --- availability appears to depend on invocation context, not just model family, so don't assume a subagent inherits the conductor's own tool-list state.
- **Don't:** treat this entry's absence-finding as a settled cross-context default;
  it is confirmed only for an interactive CLI session, and contradicted by at least one dispatched review session on the same day.

See [Claude Code v2.1.233 release notes](https://github.com/anthropics/claude-code/releases/tag/v2.1.233), and the [Claude review on Morrison-Lab/ai-config#1732](https://github.com/Morrison-Lab/ai-config/pull/1732) that caught the overgeneralization above.

## The scratchpad directory path's trailing UUID is a usable stand-in for the harness session id

`skills/mwc/SKILL.md`'s `enable-mwc`/`check-mwc` need a `--id` unless
`AI_SESSION_ID` or `CLAUDE_SESSION_ID` is set in the shell, which in an
ordinary Claude Code session it usually is not.
The system prompt's "Scratchpad Directory" section names a path of the form
`/private/tmp/claude-<pid>/<sanitized-cwd>/<uuid>/scratchpad` --- that trailing
`<uuid>` is the session id `check-mwc` reports as active when passed to it.

Treat this as a working fallback, not a guaranteed match:
`check-mwc` itself only ever resolves its id from `--id`, `$AI_SESSION_ID`/
`$CLAUDE_SESSION_ID`, or a single-live-session fallback (`ai-session.sh`'s
`resolve_id_or_single_live()`) --- it never reads a hook payload at all, since
it's a plain bash script with no such input.
The `PreToolUse` hook payload resolution (`session_id`/`sessionId`, then
`conversation_id`/`conversationId`, then the transcript-path stem) belongs to
a separate component: `resolve_session_id()` in `hooks/no-unauthorized-merge.py`,
the guard that actually gates the merge tool call.
That is a different resolution path than the scratchpad directory name, and
the two are not documented as sourced from the same value --- `check-mwc`'s
own help text names this explicitly when the env vars are unset ("The
pre-tool-use merge guard resolves session id from the harness hook
payload..."), attributing it to the guard rather than to itself.
Confirm with `check-mwc --id "<uuid>"` returning exit 0 before relying on it,
and if a merge is still blocked after that, re-derive the id from a live
merge attempt's own denial message rather than trusting the scratchpad guess
a second time.

## Claude Code MCP tool search is default-on

Measured 2026-08-23 on Claude Code 2.1.221 against the docs page [code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp) ("Scale with MCP tool search").

- **MCP tool definitions load deferred by default on Claude 4.5-generation models**, so Reddit-style advice to "enable tool search" (`ENABLE_TOOL_SEARCH=true`) to save session-start context is already satisfied here.
  Only tool names and server instructions load upfront;
  bodies arrive via a `ToolSearch` call when first needed.
  Re-verify before relying on this: run `/context` in a live session and read the MCP tools line instead of recalling this bullet.
- **Knobs:** `ENABLE_TOOL_SEARCH` values are `(unset)` (all tools deferred), `auto` (defer only once tool definitions reach 10% of the context window, below which they load upfront), `auto:N` (the same threshold mode with a custom percentage, N is 0--100, e.g. `auto:5` for 5%), `true` (force deferral everywhere it can work), and `false` (all tools upfront).
- **What silently turns it off:** a custom `ANTHROPIC_BASE_URL` pointing at a non-first-party host (most proxies drop `tool_reference` blocks), `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`, Google Cloud's Agent Platform models earlier than the Claude 4.5 generation, and Microsoft Foundry deployments hosted on Azure (their serving stack rejects it server-side, which no `ENABLE_TOOL_SEARCH` value overrides).
- **Local setup:** `github-local` (toolsets `default,actions`, dozens of tools) plus `local-llm` are user-scoped in `~/.claude.json`.
  Corpus rules route local GitHub work through the `gh` CLI, so scoping `github-local` out of local sessions remains an open option even with search on;
  it would also remove tool-selection noise, not just tokens.
  Tracked in ai-config#2066.

## An UNQUOTED Bash-tool heredoc delimiter executes backtick spans inside the body

Writing a markdown file through `python3 - <<PY` (unquoted delimiter, chosen so a shell variable would interpolate) lets the shell run command substitution INSIDE the Python source: a markdown code span (a filename in backticks) inside a Python string literal was executed as a shell command (`command not found` on stderr) and replaced with its empty output, so the written file carried an empty link text --- `[](reddit-access.md)` --- with no error in the file itself.
The corruption was caught only by grepping the emitted file.
(Measured 2026-08-23, Windows 11 / Git Bash local Claude Code session.)

Same backtick-hazard family as `CLAUDE.md`'s "PowerShell CLI Command Safety" section (double-quoted command arguments), and the sibling of its "Tool transport collapses doubled backslashes" entry (QUOTED heredocs);
the unquoted-delimiter case was written down nowhere.

- **Do:** use a quoted heredoc delimiter (`<<'PY'`) whenever the body carries backticks or dollar signs, pass dynamic values in via a separately-exported environment variable or a placeholder substitution, and grep the emitted file for the expected spans afterwards.
- **Don't:** choose an unquoted delimiter for the convenience of variable interpolation when the body carries markdown code spans --- each backtick span becomes a command substitution and vanishes silently on success.

## Tool result persistence & disk spillover threshold

Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236):

- **Default size threshold**:
  Tool outputs exceeding `DEFAULT_MAX_RESULT_SIZE_CHARS = 50_000` characters (or 100,000 tokens)
  are written to disk under `~/.claude/projects/<project>/<session_id>/tool-results/<tool_use_id>`.
- **Model preview**:
  When persisted to disk, the model receives a preview wrapped in `<persisted-output>` XML tags
  with the exact disk path for subsequent `FileRead` retrieval.
- **Batch limit**:
  Combined tool outputs across parallel tool executions in a single turn are capped at `MAX_TOOL_RESULTS_PER_MESSAGE_CHARS = 200_000` characters.
  Thresholds are subject to harness configuration and release changes.

## Token budgeting directives

Measured 2026-08 against Claude Code v2.1 CLI runtime (v2.1.236):

- Shorthand forms (`+500k`, `+2m`, `+1b`) and verbose phrases (`spend 2M tokens`, `use 100k tokens`)
  are parsed into session token budgets.
- When an active budget is detected, the harness injects budget-monitoring instructions
  into dynamic system prompt sections and issues continuation prompts if the model finishes before expending the requested effort.

## `check-install.py --consumer-dir` retargets the Claude manifest, not one file

**Historical as of the symlink-install removal ([ai-config#2229](https://github.com/Morrison-Lab/ai-config/pull/2229)):** `check-install.py`, `link_one_claude`, and `scripts/test_bootstrap_link_hints.py` (linked below) no longer exist --- `bootstrap.sh` does not symlink into consumer directories at all any more.
This whole section describes a bug in, and the fix to, a mechanism that has since been removed;
keep it only as a record of the incident.

`--consumer-dir` retargets `collect()`, the whole Claude-shaped install
list (`AGENTS.md`, `CLAUDE.md`, `skills/`, `commands/`, `memories/`, and
the rest of that manifest).
It is not a single-file repair, and it is not an arbitrary-consumer
repair.

Pointing it at a Copilot memory directory or a Gemini skills directory
enumerates missing Claude-layout entries.
`--fix` would create those as unrelated top-level links there.
Measured 2026-08-26 on
[ai-config#2286](https://github.com/Morrison-Lab/ai-config/issues/2286):
`--consumer-dir` aimed at the Copilot memory dir listed 15 `missing`
Claude-layout entries.
`main()` only skips `--fix` when the consumer dir is absent; a live
Copilot or Gemini directory is present, so that guard does not save it.

`bootstrap.sh` therefore must not export the Claude-only hint
`run scripts/check-install.py --fix` via file-scope `LINK_ONE_FIX_HINT`.
Claude collisions pass that hint per call (`link_one_claude`).
Codex, Gemini, Copilot, and Cursor inherit
[`scripts/lib/link-one.sh`](../scripts/lib/link-one.sh)'s default
(`remove it or replace it with a link manually`).
Dotfiles/shiva is a third class:
[`dotfiles/shiva/install.sh`](../dotfiles/shiva/install.sh) sets
`LINK_ONE_FIX_HINT` to its `--adopt` message.
Sharing the never-clobber helper is not sharing a hint.

The default is not a backup instruction.
`--fix` is the path that backs up
(confirmed in `check-install.py --help`).

A first-push review on
[#2290](https://github.com/Morrison-Lab/ai-config/pull/2290)
(`ee2980bb`) flagged comments that grouped
"Codex, Gemini, Copilot, Cursor, and the dotfiles installers" as keeping
one backup/link instruction.
That sentence was false for shiva and misnamed the default.
Addressed in `adffe825` and `848539b7`.
`scripts/test_bootstrap_link_hints.py` was the instrument (removed along
with `check-install.py`): it ran real `bootstrap.sh` against colliding
paths and asserted the Claude-only `--fix` string did not leak into other
consumers, and that comments did not regroup dotfiles with the default
inheriters.

- **Do:** pass the `--fix` hint only on Claude `link_one` calls.
- **Do:** name shiva's `--adopt` override separately from callers that
  inherit the default.
- **Don't:** assign Claude-only `LINK_ONE_FIX_HINT` at bootstrap file
  scope.
- **Don't:** point `--consumer-dir` at a Copilot, Gemini, Codex, or
  Cursor path and run `--fix`.
- **Don't:** write comments that group default-inheriters with callers
  that override the hint, or call the default a backup/link instruction.

## A blocked compound `cmd1 && cmd2` Bash call blocks BOTH halves, not just the flagged one

A PreToolUse hook (`no-push-without-self-review.py` here) fires on the
**whole** Bash tool invocation before any of it runs, not per `&&`-joined
segment. `git commit --allow-empty -m "..." && git push ...` blocked by
the push guard therefore never ran the commit either -- the harness
reported the call as blocked, and nothing executed at all.

The trap is the natural recovery move: retry with the guard's override
prefix on a NEW call containing only the flagged command
(`ALLOW_UNREVIEWED_PUSH=1 git push -u origin HEAD`). That push succeeds
--- but pushes whatever HEAD already was, since the commit from the
blocked call never happened. On an empty-commit branch-claim flow this
is silent: the push reports `[new branch]` either way, and only a
downstream symptom (here, `gh pr create` refusing with "No commits
between main and \<branch\>") surfaces the gap. `git log -1`/`git
reflog` on the target worktree settles it immediately.

- **Do:** verify state (`git log -1 --format=%H`, `git status`) after
  any compound command a hook blocks, before assuming the unblocked
  half already ran.
- **Do:** re-run the FULL original command after fixing whatever the
  guard flagged, rather than splicing an override onto just the
  flagged segment.
- **Don't:** assume a compound command's earlier stages executed just
  because a later stage is what the guard's message named.

(2026-08-27, `Morrison-Lab/ai-config#2412`: an empty claim commit for
a hook-registration PR silently never happened this way; caught only
because `gh pr create` refused on a zero-commit diff.)

## Nesting your own `&` inside a `run_in_background: true` Bash call reports "done" the instant the wrapper shell returns, not when the backgrounded work finishes

`command > file 2>&1 &` inside a Bash-tool call already passed
`run_in_background: true` double-backgrounds: the tool's own
backgrounding waits for the SHELL invocation to exit, and a trailing
`&` makes that shell exit immediately (having detached the real work),
so the completion notification and the captured output file both land
long before the actual command has produced more than its first few
lines. The output file is not stale or buffered --- it is complete for
what the tool considered the finished job, which was the near-instant
`echo $!` after the ampersand, not the process it backgrounded.

The tell is a "completed, exit code 0" notification whose captured
output looks implausibly short for the work described, especially
right after the identical command WITHOUT the trailing `&` was still
running minutes later with no output at all (that one was not
double-backgrounded, just slow/quiet until its first flush -- a
different, non-bug explanation for a differently-shaped symptom, which
is why comparing the two side by side is what exposed this).

- **Do:** pass a plain foreground command (no trailing `&`) to a Bash
  call with `run_in_background: true` --- the tool's own backgrounding
  is sufficient and is what keeps the completion notification honest.
- **Don't:** add your own `&` (or `nohup ... &`, `disown`, etc.) on top
  of `run_in_background: true` --- the two backgrounding mechanisms
  don't compose, they race, and the tool's own wins.

(2026-08-27, same session: `python3 -u scripts/test_hooks.py > log 2>&1
&` reported complete in seconds with a 3-line log; the identical
command without the trailing `&` ran to a real completion minutes
later with the full ~45-suite output.)

(2026-08-26,
[#2286](https://github.com/Morrison-Lab/ai-config/issues/2286) /
[#2290](https://github.com/Morrison-Lab/ai-config/pull/2290).)
