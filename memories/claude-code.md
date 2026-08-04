# Claude Code harness & agent tooling

## Copilot tool availability can change mid-session

- Honor `tools_changed_notice` events literally. If a notice says a tool is no
  longer available (e.g., `create`, `edit`), switch immediately to still-listed
  alternatives (typically `apply_patch` + `view` + `bash`) instead of retrying
  the removed tool.
- For UMS/maintenance passes this matters because stale muscle memory ("use
  create/edit") can fail repeatedly after the tool list changes.

## WebFetch 403 on a rendered docs site -> raw.githubusercontent.com; WebSearch to find the exact source path
- A GitHub-Pages/Quarto-rendered docs site (e.g. `jarl.etiennebacher.com`,
  `ucd-serg.github.io/lab-manual/...`) can reject `WebFetch` outright (403 —
  likely anti-scraping), even though the plain-text/markdown **source** it was
  built from is a public file in a public repo and fetches fine via
  `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`. This
  isn't `d-morrison/gha`-specific (that repo's own `CLAUDE.md` documents it
  for the lab manual) — it generalizes to any Quarto/Docusaurus-style site,
  including third-party tool docs with no relation to our own repos.
- **When the exact source path isn't obvious** (unlike the lab-manual case
  where `foo.html` predictably maps to `foo.qmd`), guessing candidate paths
  one `curl -o /dev/null -w "%{http_code}"` at a time is slow and often wrong.
  `WebSearch` for `<repo-or-tool-name> <topic> site:github.com` (or just
  `<tool> <config-file> github`) surfaces the actual repo file path (e.g.
  `jarl/docs/reference/config-file.md`) from its indexed GitHub listing —
  faster than blind guessing, and the found path fetches cleanly via
  `raw.githubusercontent.com` immediately after. (Confirmed on jarl's docs
  site: `jarl.etiennebacher.com/reference/config-file` 403'd, but
  `WebSearch` surfaced `docs/reference/config-file.md` as the underlying
  file, which raw-fetched with the full field-by-field config reference.)
- **A 404 from `raw.githubusercontent.com` is often a filename-case mismatch, not a missing file.**
  The rendered URL's slug is lowercased by the site generator while the source file's own name may not be.
  Advanced R serves `function-operators.html` from `Function-operators.Rmd`, so the obvious raw URL 404s and the capitalized one returns the chapter.
  Retry with the repo's own capitalization before concluding the source lives at some other path.
  (ai-config#760, 2026-07-28: `adv-r.hadley.nz` 403'd through the proxy, and the first raw attempt 404'd purely on the leading capital.)
- **`docs.github.com` itself can be blocked outright by a remote session's
  network policy** (proxy 403 on every page, and `api.github.com` too —
  both at the curl/WebFetch level; the GitHub MCP tools route through
  their own server and keep working), not
  just anti-scraping — but `raw.githubusercontent.com` stays reachable, and
  GitHub's docs are built from the public `github/docs` repo. Verify a docs
  claim or URL against that source instead: page content lives under
  `content/<area>/.../<slug>.md`, but live-URL paths do NOT map 1:1 to
  source paths (the docs get reorganized; e.g.
  `/billing/managing-billing-for-your-products/...` now lives at
  `content/billing/concepts/product-billing/github-actions.md`). If a page
  was moved, its frontmatter carries a `redirect_from:` list — an old URL
  appearing there means it still works for readers via redirect — and
  shared text is factored into `data/reusables/<area>/<name>.md` includes,
  so grep for a `{% data reusables.<area>.<name> %}` tag and fetch that
  file when a section's body looks like one include line. Version-gated
  (`{% ifversion <flag> %}`) passages resolve via `data/features/<flag>.yml`:
  its `versions:` block (e.g. `fpt: '*'`) says which plans the gated text
  applies to: `fpt` = Free/Pro/Team on github.com, `ghec` = GitHub Enterprise
  Cloud (also github.com-hosted), `ghes` = GitHub Enterprise Server
  (self-hosted). (Used on
  ai-config#601 to verify the GitHub Actions billing and `jobs.<job_id>.if`
  citations offline, and on gha#272 to confirm the approval-required
  `pull_request`-runs exception applies to github.com.)

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

## ai-config's three context pools -- only one of them is worth splitting

Not all of this corpus costs the same per session, and the cheapest way to
waste effort is to "reduce context" by shrinking the wrong layer:

- **Always-loaded** -- `CLAUDE.md` plus every `@shared/...` fragment it
  references, plus *every* skill's `description` frontmatter. Paid on every
  session regardless of task. Splitting a file here saves **nothing**: each
  piece still loads. The only levers are pruning, consolidating, or
  demoting a fragment to on-demand.
- **On-demand** -- `memories/*.md` and skill bodies. Paid only when read, so
  file length is a real per-use cost and splitting genuinely helps.
- **Generated** -- `codex-skills/` and other derived trees. Costs CI time
  and merge conflicts, not context.

Measure before acting: as of 2026-07-24 the always-loaded set was ~48.5k
tokens (`CLAUDE.md` + 47 fragments) plus ~15.2k tokens of skill
descriptions, against `memories/tools.md` at ~48k tokens paid only on a
whole-file read. That is why ai-config#696 split `tools.md` (on-demand, so
the split pays) while ai-config#700 attacked the description budget by
removing duplication rather than by splitting anything (always-loaded, so
splitting would not have paid).

**That "splitting saves nothing" claim is Claude Code's documented behaviour,
not an inference, and the docs name a lever this section omits.**
Verified against <https://code.claude.com/docs/en/memory> on 2026-07-31.
Imported files "are expanded and loaded into context at launch alongside the
CLAUDE.md that references them"; "Splitting into `@path` imports helps
organization but doesn't reduce context, since imported files load at launch";
imports recurse to "a maximum depth of four hops"; and "CLAUDE.md files are
loaded in full regardless of length, though shorter files produce better
adherence".
Two details worth adding to the pools above.
Import parsing skips Markdown code spans and fenced code blocks, so a
backticked `@README` stays literal text rather than becoming an import.
And the docs' own recommended lever for a large instruction set is
**path-scoped rules**, which load only when Claude works with matching files
--- effectively a fourth pool, and one this corpus does not currently use.

**Re-measure before arguing from a number: the always-loaded closure has
roughly tripled since the 2026-07-24 figure above.**
The instrument is a recursive walk summing `os.path.getsize` over
whole-line `@path` matches, seeded at `CLAUDE.md`:

```python
import os, re
IMPORT = re.compile(r"^@([\w./-]+)$", re.M)
def closure(root, start="CLAUDE.md"):
    seen, stack = {}, [os.path.join(root, start)]
    while stack:
        p = os.path.normpath(stack.pop())
        if p in seen or not os.path.isfile(p):
            continue
        seen[p] = os.path.getsize(p)
        text = open(p, encoding="utf-8", errors="replace").read()
        stack += [os.path.join(root, m) for m in IMPORT.findall(text)]
    return len(seen), sum(seen.values())
```

Measured 2026-07-31: ai-config's closure is **66 files, 661,750 bytes** ---
roughly 165k tokens at a 4-bytes-per-token rule of thumb --- with all 65
imports at depth 1, so the corpus uses one of the four available hops.
`Morrison-Lab/gha`'s closure is 1 file, 104,462 bytes, which is the
comparison worth holding onto: a repo with no imports at all pays about a
sixth as much.

**A CI review bot pays that closure too, so it is not only an interactive-
session cost.**
`claude-code-action` defaults `settingSources` to
`["user", "project", "local"]` in `base-action/src/parse-sdk-options.ts`, and
`"project"` is what loads the repo's own `CLAUDE.md`.
The default is overridden only by passing `--setting-sources` in
`claude_args`, which `Morrison-Lab/gha` does at none of `main`, `v1`, or `v2`
(`git grep -c setting-sources <ref> -- '*.yml' '*.yaml'` returns no hits at
any of the three).
So every `@claude` run in a gha-consuming repo loads that repo's whole
always-loaded set before it reads a line of the diff.

**That closure has now overflowed the context limit for at least one workflow
in this repo, so the cost is a measured failure rather than a projected one.**
`Morrison-Lab/ai-config#986` carries a comment posted at 2026-07-31T20:47:04Z
whose body is the API's context-length error verbatim, `Prompt is too long`,
emitted by `claude.yml@v1`'s post-step from workflow run 30664135897.
The agent had loaded the always-loaded set and done no work of its own: its
`Run Claude Code` step ran 36 seconds, and the job concluded `success` with no
step failing.
So the figure above is not merely large; it exceeds what at least one consumer
of it can accept.

The second-order effect is the part to plan around.
An agent that cannot run in this repo cannot be asked to help shrink it, so
the corpus's size now blocks the tool that would reduce the corpus's size.
That argues for treating the levers above as urgent rather than tidy, and for
preferring the ones a human or a plain script can apply without an agent.

**The reviewer half of the same afternoon is inference, and is labelled that
way deliberately.**
`claude-review` failed at two heads with `is_error: true` alongside
`subtype: "success"`, and has **not** been shown to hit the same limit.
The shapes do fit: the agent died before its first call, while the reviewer
ran 43 seconds and spent $0.97 across 2 turns, which is what a prompt sitting
just under the line and then pushed over by tool results would look like.
A fitting shape is not evidence, so treat the reviewer failure as an open
question rather than as a second instance, until something reads its own error
string.

- **Do:** re-run the closure walk before making a context-budget argument ---
  the figure moves fast, and a stale one argues for the wrong lever.
- **Do:** reach for pruning, consolidating, demoting to on-demand, or
  path-scoped rules, which are the levers that change the number.
- **Do:** treat the closure as a ceiling already reached rather than a budget
  still being spent, since one workflow here has now failed on it outright.
- **Don't:** propose splitting a large `CLAUDE.md` into `@path` imports as a
  context saving; it buys organization and nothing else.
- **Don't:** assume the always-loaded cost is paid only by interactive
  sessions.
- **Don't:** report the `claude-review` failures as the same overflow --- that
  is a shape match, and no error string has been read for them.

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

## ScheduleWakeup is scoped to `/loop` dynamic mode --- use `send_later` for ad-hoc waits

`ScheduleWakeup` requires a `prompt` param and is meant to re-arm a `/loop`
session's next firing (its own docs say to pass the same `/loop` input back,
or the `<<autonomous-loop-dynamic>>` sentinel). Calling it outside a `/loop`
context --- e.g. to arm a plain "check back on this PR in 5 minutes" wait ---
throws `InputValidationError: prompt is missing`, since there's no `/loop`
input to hand it. Use `mcp__Claude_Code_Remote__send_later` (or the harness's
plain wakeup tool, if present) for a one-off self check-in instead; reserve
`ScheduleWakeup` for actual `/loop` iterations. See `send_later` mid-session
availability above for the fallback (`CronCreate`) if it disappears.
(ai-config#455/gha#216, 2026-07-03.)

**Correction: the validation error is about a missing `prompt`, not about
being outside `/loop` per se.** In a remote/web session, calling
`ScheduleWakeup` with an explicit, self-written `prompt` string (not the
`/loop` sentinel) for a plain ad-hoc check-in did **not** throw
`InputValidationError` --- it accepted the call, returned a confirmed clock
time, and the wakeup fired as scheduled. This is a workable fallback when
`send_later` itself is unavailable or repeatedly failing (e.g. an MCP server
mid-reconnect) --- supply your own full prompt text rather than assuming the
tool rejects non-`/loop` calls outright. (ai-config#583/#585 session,
2026-07-16: `mcp__Claude_Code_Remote__send_later` failed three times in a row
with "Tool permission stream closed before response received"; `ScheduleWakeup`
with a custom prompt worked immediately both times it was tried as a fallback.)

## In a plain local Claude Code session, `ScheduleWakeup` can accept an ad-hoc call but silently fail to fire

This is a DIFFERENT harness/observation from the entry above (that one is the `Claude Code Remote`
MCP server's `ScheduleWakeup`; the "rejects non-`/loop` calls with a validation error" characterization
was corrected by the block above it --- the error is about a missing `prompt`, not the non-`/loop`
context, and a supplied `prompt` works fine there).
In a plain local Claude Code CLI session, `ScheduleWakeup` accepted an arbitrary one-off
`{delaySeconds, prompt, reason}` call with no error and returned a confirmed clock time (e.g.
"Next wakeup scheduled for 08:27:00") -- but the scheduled re-invocation never actually fired.
Observed twice in a row in the same session: the user had to send a message directly each time
before work resumed, well past the confirmed time. Root cause unconfirmed from inside the
conversation (no introspection into harness wakeup-delivery internals) -- plausible candidates are
a genuine at-least-once delivery gap for ad-hoc (non-`/loop`) wakeups in this session type, or the
pending wakeup being silently superseded/dropped when a real user message arrives first rather than
double-delivering. Either way: don't treat a confirmed `ScheduleWakeup` result as a guarantee of
resumption in a plain local session -- prefer a `Monitor`/background-Bash wait (which reports back
via the harness's own task-completion notification, not a separately-scheduled wakeup) when the
condition being waited on is itself observable via a command, and treat `ScheduleWakeup` as
best-effort. (Sparta gii-ffdb93 session, 2026-07-14.)

## `CronCreate`'s job store can silently lose a scheduled job mid-session, so it is a weak fallback for a check-in you have promised a time for

The `send_later`-can-become-unavailable-mid-session bullet in
[`memories/github-mcp-tools.md`](github-mcp-tools.md) recommends
`CronCreate` as the fallback when `send_later` disappears.
It works, but its jobs are in-memory and session-only by design, and they can
vanish **before their fire time** with no error and no notification.

Observed twice in one remote/web session (gha#318 / ai-config#733,
2026-07-26).
A job created at 14:15 PDT to fire at 15:22 was already absent at 15:35 ---
`CronDelete` returned `No scheduled job with id`, and `CronList` returned
`No scheduled jobs`.
A second job created at 15:35 to fire at 16:38 was likewise gone by 15:50,
well before it could have fired.
Creation itself is fine: a probe job created immediately afterward appeared in
`CronList` at once, so this is loss after the fact, not a failed write.
The cause is not confirmable from inside the conversation.
The strongest correlate is that the session's MCP servers disconnected and
reconnected several times in between, which fits an in-memory store being
reset, but that is inference, not something the tools report.

What makes this worse than an ordinary flaky tool: both jobs had already been
reported to the user as a specific clock time, per `CLAUDE.md`'s "State the
actual time when reporting a scheduled check-in" rule.
Stating a time implies a commitment the mechanism silently dropped, and
nothing surfaces the loss --- the check-in simply never arrives.

So:

- Prefer `mcp__Claude_Code_Remote__send_later` whenever its server is
  reachable.
  The two tools' own descriptions say opposite things about durability:
  `send_later`'s reads "Delivery survives container restarts", while
  `CronCreate`'s has a "Session-only" section saying jobs live only in the
  current session, nothing is written to disk, and "the job is gone when
  Claude exits".
  Read them in the tool schemas themselves rather than inferring durability
  from this corpus.
- When you do fall back to `CronCreate`, say so in the same breath as the
  time: name it as a session-only, best-effort check-in rather than letting
  "I'll check back at 16:38" read as a guarantee.
- Re-verify with `CronList` before relying on a job you armed earlier ---
  a one-call check that decides it exactly, rather than trusting the
  creation receipt.
  This is [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
  applied to your own scheduling: the store either lists the job or it does
  not.
- Where the thing being waited on is observable by a command, a
  `Monitor`/background-Bash wait is sturdier than any scheduler, for the same
  reason the `ScheduleWakeup` entry above gives --- it reports through the
  harness's own task-completion path instead of a separate delivery
  mechanism.

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
`claude`/`claude-code-review` bots (running via `d-morrison/gha`'s reusable
workflows and `anthropics/claude-code-action`) get nothing from it. The
pattern that worked, with no workflow changes needed, on `d-morrison/rme#982`
and `ucdavis/epi204#360`:

1. `git submodule add https://github.com/d-morrison/ai-config.git .ai-config`
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

## A plugin ref resolves by the marketplace's *declared* name, not by its URL

The section above covers the submodule-plus-symlink path.
The other way a repo consumes ai-config is the **plugin marketplace** ---
`.claude/settings.json`'s `extraKnownMarketplaces` / `enabledPlugins` for a
web/cloud session, and gha's `use-ai-config` input for the bots.
That path has a failure mode the submodule path does not, and it is worth
knowing because the obvious diagnosis is the wrong one.

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
Adding marketplace: https://github.com/d-morrison/ai-config.git
✔ Successfully added marketplace: Morrison-Lab (declared in user settings)
Installing plugin: ai-config@d-morrison
✘ Failed to install plugin "ai-config@d-morrison": Plugin "ai-config" not
  found in marketplace "d-morrison".
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

(2026-07-29: ai-config renamed its declared marketplace from `d-morrison` to
`Morrison-Lab`.
Both consumers broke; the gha fix shipped when `v2` was slid to `c50e847`.)

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

`bootstrap.sh` symlinks this repo into `~/.claude`, so a `git pull` normally
refreshes what the Skill tool loads.
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
