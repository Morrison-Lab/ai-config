# Cursor

Cursor-specific agent and plugin behavior, split out of
[`tools.md`](tools.md) so that file stays under the 1200-line memory-file
gate (ai-config#694 / #2003).
General local-tool notes stay in `tools.md`.
GitHub PR review via Bugbot is in [`cursor-bugbot.md`](cursor-bugbot.md),
not this file.

## Cursor agent cannot write `.cursorignore` from the sandbox

The Write/StrReplace tools, and a sandboxed Shell, refuse a file named
`.cursorignore` with `operation not permitted`, including a tempfile of that
name under `/tmp`.
The filename is the trigger, not the destination.

- **Do:** write `.cursorignore` with Shell `required_permissions: ["all"]`.
- **Don't:** retry Write or StrReplace after that denial, or conclude the
  path is unwritable.

(Measured 2026-08-18 on Morrison-Lab/ai-config#1642.)

## Cursor hides `.cursorignore` paths from the agent, including worktrees

Cursor's Read/Grep/Glob/Write tools cannot see paths that match
`.cursorignore`.
This repo's `.cursorignore` lists `.claude/worktrees/`, so a
`session-lock` worktree placed there is invisible to Cursor even though
`git worktree list` and the filesystem still show it.

- **Do:** put a Cursor session's worktree outside `.claude/worktrees/`
  (a sibling directory, or another path Cursor can see).
- **Do:** check `git worktree list` before treating an empty Glob/Read of
  `.claude/worktrees/<name>` as "the worktree was never created".
- **Don't:** abandon isolation and edit the primary checkout just because
  Cursor cannot see the worktree; move the worktree to a visible path
  instead.

(Measured 2026-08-23 on Morrison-Lab/ai-config#1928: the first worktree at
`.claude/worktrees/cursor-first-class` was removed after `.cursorignore`
hid it, and work continued on the main checkout.)

## Cursor plugin, `~/.cursor/skills`, and `~/.claude/skills` are alternatives

A live Cursor plugin (`~/.cursor/plugins/local/ai-config` or
`~/.cursor/plugins/cache/<org>/ai-config`) **or** `~/.claude/skills`
already serving this repo is a skip, not a second install.
Do not `rglob` `~/.cursor/plugins/marketplaces`: a catalog clone plus this
repo's Antigravity `plugins/ai-config` is a false positive.
Leftover `ok` symlinks under `~/.cursor/skills` whose target is this
checkout or a sibling worktree are **stacked**, not healthy.

The plugin also ships `cursor-rules/` as user-global rules
(`.cursor-plugin/plugin.json` `"rules": "cursor-rules"`).
A live plugin is a skip for `~/.cursor/rules` too, not a second install.
A Claude skill catalog does not ship those rules, so it is not a skip
there.
Leftover `ok` symlinks under `~/.cursor/rules` whose target is this
checkout or a sibling worktree are **stacked**, not healthy.

Full `bootstrap.sh` installs `~/.claude/skills` first, so the
`~/.cursor/skills` link path almost never runs.
Do not "fix" tests to expect `~/.cursor/skills/ardi` after a full
bootstrap.

Do not point the Cursor plugin `hooks` field at Claude `hooks/hooks.json`;
that is Morrison-Lab/ai-config#1934, out of #1927 by design.

Cursor Cloud loads project hooks from [`.cursor/hooks.json`](../.cursor/hooks.json)
(native `version: 1` schema), not the Claude catalog.
[`.cursor/hooks/adapt-claude-hooks.py`](../.cursor/hooks/adapt-claude-hooks.py)
translates Cursor events into the payload the existing `hooks/` scripts
already consume.
The event mapping is [docs/cursor-hook-mapping.md](../docs/cursor-hook-mapping.md).
Cursor JSONL omitted `tool_result` as of 2026-04-13 (Cursor staff);
three fail-closed Stop/PreToolUse scripts are skipped until that changes
([#2241](https://github.com/Morrison-Lab/ai-config/issues/2241)).
Warn-only Claude Stop `systemMessage` maps to Cursor `followup_message`
because `stop` has no warn-only field.
`postToolUse.additional_context` is emitted; Cloud consumption is
unmeasured as of 2026-08-25 (desktop through 3.7.x discarded it).
Stop scanners still read JSONL, not that field
([#2245](https://github.com/Morrison-Lab/ai-config/issues/2245)).

User-level `~/.cursor/hooks.json` is not available to cloud agents.
`sessionStart` injection is desktop-only.
Cloud agents emit `UserPromptSubmit` context on the first `postToolUse`
of a generation; whether the model sees it is unmeasured on Cloud.
A tool-less cloud turn drops that context rather than delaying it,
because `beforeSubmitPrompt` cannot inject.
Desktop Cursor with third-party Claude hooks enabled also loads
`~/.claude/settings.json`; do not pair that with this project adapter
(both sources run; measured against Cursor's third-party hook docs on
2026-08-25).

## Cursor Cloud `Task` dispatches `adversarial-reviewer`

Measured 2026-08-25 PDT: a Cursor Cloud session can dispatch the
`adversarial-reviewer` persona through `Task`
(`subagent_type: adversarial-reviewer`).
Morrison-Lab/ai-config ships that persona under both `.claude/agents/`
and `.opencode/agents/`.
Which path Cursor Cloud reads was not isolated.

The dispatch this corpus requires is foreground
(`run_in_background` false).
Measured 2026-08-25 PDT on a Cursor Cloud Grok conductor in this repo:
that conductor's `Task` schema listed `run_in_background`
and did not list `isolation`.
`flag-unassigned-worktree.py` emits a warning on every such dispatch
because the Cursor adapter maps `Task` to `Agent`
when `subagent_type` is not explore/plan/shell
([`.cursor/hooks/adapt-claude-hooks.py`](../.cursor/hooks/adapt-claude-hooks.py)),
and [`hooks/flag-unassigned-worktree.py`](../hooks/flag-unassigned-worktree.py)'s
`READ_ONLY` set is Explore/Plan.
Deciding the child needs no worktree is fine;
the schema has no `isolation` field to mark that decision.
Tracked as [#2276](https://github.com/Morrison-Lab/ai-config/issues/2276).

Commit first.
A review of uncommitted work names a commit that does not exist yet
(`hooks/no-push-without-self-review.py`).
Record `git rev-parse HEAD` and `git rev-parse --abbrev-ref HEAD`
before the dispatch,
and run `git status --short`.
If that status is not empty, do not dispatch: commit or stash first.
After the child returns, recover the report from
cursor-cloud `batch-fetch-details`
with `bcIds: [<cloudAgentBcId>]` and `includeTranscripts: true`.
That transcript is the admissible source for `parse_report()`,
the HEAD fingerprint check, the dry-run tip check,
and the source-ref check below.
It is not a substitute for those checks.
A harness paste of the child's own assistant message may corroborate it;
an author-composed block with those headings does not.
Name which route produced the verdict.
JSON-decode the assistant `text` field
(`transcript.json` stores the body as a JSON string,
so newlines arrive as escaped `\n`).
`batch-fetch-details` can write a large `transcript.json`.
Extract the last assistant `text` that carries Summary / Findings /
Verdict / Reviewed-Commit
(same selector as the identity-only section below).
Two legal routes, and both must produce the report body
(the last matching assistant `text`) as well as the
`parse_report()` tuple:
(a) a decoder reads `transcript.json` whose path contains
the `cloudAgentBcId`, prints that last matching `text`,
and calls `parse_report()` on it in one process;
(b) a subagent returns that last matching assistant `text`
verbatim and the conductor calls `parse_report()` on that
return without editing it.
Do not require the same invocation for route (b).
Route (a)'s printed text is the body to post.
Route (b)'s provenance is the subagent's verbatim return
of the same selector.
The `parse_report()` tuple is the push gate, not the comment.
Do not treat route (a) as returning only the tuple.
Call `parse_report()` from
[`hooks/no-push-without-self-review.py`](../hooks/no-push-without-self-review.py)
on that recovered text
(`importlib.util.spec_from_file_location`;
the module loads with no side effects).
Do not paste a report body the conductor composed.
Do not read the transcript file into the conductor's context.
`cloudAgentBcId` is a field on the Task JSON `tool_result`;
`bcIds` is the tool parameter.
How to retrieve that paste or transcript is
[Cursor Cloud Task `tool_result` is identity-only](#cursor-cloud-task-tool_result-is-identity-only).
The `Task` JSON `tool_result` has no review body.
Do not re-derive `VERDICT_LINE` or fence-blanking by hand.
`parse_report` returns `(verdict, reviewed_commit)`:
`clean` is Ready for merge,
`needs_work` is Needs more work or Needs work,
and `(None, None)` is no verdict, including an unclosed fence.
If the verdict is not `clean`, or there is no fingerprint, do not push.
A push that carries nothing to review
(the empty [`pr-on-claim`](../shared/workflow/pr-on-claim.md) branch)
has no report to parse: do not invent one,
and do not refuse that push for lack of a verdict.
Re-read `git rev-parse HEAD` after the child returns.
If HEAD is not the recorded sha, the child wrote or HEAD moved:
do not push; re-dispatch on the new HEAD.
The fingerprint must prefix-match HEAD
(`c.startswith(reviewed_commit)` in `verify_review`).
`parse_report` already lowercases the fingerprint.
If the fingerprint does not prefix-match HEAD, do not push.
[#2299](https://github.com/Morrison-Lab/ai-config/issues/2299)
tracks a CLI wrapper over that Cursor Cloud `parse_report()` call.
Provenance (which file was parsed) is in that issue's scope too.
Until that wrapper lands, the import is the instrument
for recovering a Cursor Cloud `Task` child's report.
[#2255](https://github.com/Morrison-Lab/ai-config/pull/2255)
landed `scripts/pre-push-review.py` on `main` (measured 2026-08-26 PDT):
a separate local-engine dispatcher with its own report contract
(`parse_review_verdict`), not a wrapper over `parse_report()`
and not this recovery path.
Tracked as [#2309](https://github.com/Morrison-Lab/ai-config/issues/2309).
Run `git push --dry-run` with the same arguments as the push
that follows, including the refspec
(the guard exempts dry-run from review).
Read stdout and stderr (`2>&1`).
The summary lines this section names write to stderr.
If that command fails,
or you cannot tell from its output which commits would ship,
or a reported new tip does not prefix-match HEAD,
do not push.
Git's dry-run summary is `old..new` for a fast-forward,
and `old...new` for a forced non-fast-forward
(git-push OUTPUT; this worktree's git is 2.43.0).
Compare only the new tip:
the hex to the right of the two-or-three-dot range.
A split on the two-dot string is not that extraction,
because `...` contains `..`.
The left sha is the remote's current tip, not a commit this push adds.
`Everything up-to-date` means the push would ship nothing;
that is not a fingerprint mismatch.
A new branch's dry-run line is `[new branch]` with no sha.
That line is not a mismatch.
It also does not confirm the shipped tip:
the first push of a `cursor/<name>` branch is this case,
so the dry-run only confirms the command would create that ref.
The source-ref rule and the HEAD comparison remain.
If the source ref (left of `->`) is `HEAD`, the recorded sha covers it.
If it is a branch name, that name must match the recorded branch.
Any other source ref (a tag, `FETCH_HEAD`, a raw sha) is not covered:
do not push.
Re-run `git status --short`.
If it is not empty, do not push:
uncommitted child edits (or leftover dirty files) are not in the
fingerprint.
This repo's Cursor adapter skips `no-push-without-self-review.py`
(`SKIP_WITHOUT_TOOL_RESULT`) until
[#2241](https://github.com/Morrison-Lab/ai-config/issues/2241),
so a failed or skipped dispatch is not caught before the push.
The posted PR comment is the record, not a gate.
If the dispatch errored or produced no report,
obtain a review via the CLI fallback in
[`adversarial-self-review`](../shared/workflow/adversarial-self-review.md)
and still call `parse_report()` on the recovered report.
On a session whose pushes go through this repo's Cursor adapter,
the adapter skip makes `ALLOW_UNREVIEWED_PUSH=1` inert
for the adapter
(measured 2026-08-25 PDT on Cursor Cloud).
Do not prefix it for the adapter's sake.
Home Claude settings can exist on Cloud
(measured 2026-08-26 PDT: `/home/ubuntu/.claude/settings.json`
binds `no-push-without-self-review` under `PreToolUse`).
That measurement does not say how this VM's copy got there.
The in-tree writer of that path is `scripts/install-hooks.py`.
Those settings do not make the Cursor adapter run Claude's hook runner.
Whether Claude Code's native hook runner also fires on Cloud
is unmeasured as of 2026-08-26 PDT.
If it does, the prefix is that native guard's escape.
If it does not, the prefix stays inert for the adapter.
If Claude Code's native guard is also running ---
desktop third-party Claude hooks, or a Claude Code process on the
same VM --- the prefix is that native guard's escape,
because Cursor JSONL omits `tool_result` and the native guard
otherwise denies every push
(desktop path measured against Cursor's third-party hook docs on
2026-08-25).
Do not pair the project adapter with native Claude hooks.
If they are already paired, the prefix is required for the native
guard even though it is inert for the adapter.

Refusal gates, in order (Do-Confirm; details in the procedure above):

1. `git status --short` empty before dispatch, and still empty after.
2. Recover the last heading-bearing assistant `text`; call `parse_report()`.
3. Verdict is `clean` and the fingerprint prefix-matches HEAD,
   unless the push carries nothing to review.
4. HEAD is still the recorded sha.
5. Same-argv dry-run succeeds; a reported new tip prefix-matches HEAD
   (`Everything up-to-date` is not a mismatch;
   a new-branch line with no sha is not a mismatch
   and also does not confirm the shipped tip).
6. Source ref is `HEAD` or the recorded branch.

When the conductor is not Claude, pass a listed Claude slug on `model`
(that 2026-08-25 PDT conductor listed `claude-opus-5-thinking-high`
on its `Task` model list).
The `Task` schema documents that omitting `model` inherits the parent.
That inherit path was not separately observed on a live omit.
A separate context buys independence of intent even if `model` is omitted
([`adversarial-self-review`](../shared/workflow/adversarial-self-review.md)).
Passing a listed Claude slug when the conductor is not Claude also buys
independence of vendor from the author, which inherit does not.
That is the [#2270](https://github.com/Morrison-Lab/ai-config/issues/2270)
instruction, not the floor.
Independence from a Claude primary is the second-reviewer pairing,
not this dispatch
([`self-review-fallback`](../shared/workflow/self-review-fallback.md)).

Measured 2026-08-25 PDT: neither the `.claude/agents/` copy
nor the `.opencode/agents/` copy's declared restriction
filtered the child's schemas.
The `.claude/agents/` copy carries a `tools:` field;
the `.opencode/` copy uses `permission: edit: deny` instead.
The Cursor Grok dispatch measured that day on
[#2265](https://github.com/Morrison-Lab/ai-config/pull/2265) and
[#2266](https://github.com/Morrison-Lab/ai-config/pull/2266)
still received Write schemas.
State read-only in the brief.
Tracked as [#2281](https://github.com/Morrison-Lab/ai-config/issues/2281).
GitHub `claude-review` skipping for a missing
`CLAUDE_CODE_OAUTH_TOKEN` or quota does not mean Claude is
unreachable on that conductor's `Task` tool.

[#2270](https://github.com/Morrison-Lab/ai-config/issues/2270)
is the instruction to use this route.

- **Do:** dispatch `Task` `adversarial-reviewer` in the foreground
  (`run_in_background` false) for every self-review in a Cursor
  session whose `Task` tool lists `adversarial-reviewer`,
  including when GitHub
  `claude-review` skipped a run.
- **Do:** when the conductor is not Claude and a Claude model is
  listed for `Task`, pass that Claude model on `model`.
- **Do:** commit first, then brief the child not to edit.
  Record `HEAD`, the branch name, and `git status --short`
  before the dispatch.
  After it returns, recover the report from `batch-fetch-details`
  with `bcIds` and `includeTranscripts: true`
  (a harness paste of the child may corroborate; name the route).
  Call `parse_report()` on the last assistant `text` that
  carries Summary / Findings / Verdict / Reviewed-Commit.
  If you cannot obtain a `clean` verdict and fingerprint,
  or HEAD is not still the recorded sha,
  or the fingerprint does not prefix-match HEAD,
  or `git status --short` is not empty,
  or the same-argv dry-run fails,
  or a reported new tip does not prefix-match HEAD
  (`Everything up-to-date` is not a mismatch;
  a new-branch line with no sha is not a mismatch
  and also does not confirm the shipped tip),
  or the source ref is not `HEAD` and is not the recorded branch,
  do not push.
  The empty [`pr-on-claim`](../shared/workflow/pr-on-claim.md) branch
  is the carve-out: it has no report,
  and that is not a reason to refuse the push.
- **Don't:** treat a skipped GitHub `claude-review` as "no
  Claude reviewer is reachable in this session".
- **Don't:** omit `model` on that dispatch when Claude is
  listed and the conductor is not Claude.
- **Don't:** prefix `ALLOW_UNREVIEWED_PUSH=1` on a Cursor-adapter
  push for the adapter's sake: the skip makes it inert there.
  If Claude Code's native guard is also running, that prefix
  is the native guard's escape, not an inert flag.
  Do not pair the project adapter with native Claude hooks.
  If they are already paired, the prefix is required for the
  native guard even though it is inert for the adapter.
  If the dispatch errored or produced no report,
  obtain a CLI review and still call `parse_report()`.
- **Don't:** treat a matching HEAD sha as covering a dry-run
  that used different arguments, failed, or listed other refs.
- **Don't:** treat a fingerprint that matches only the
  pre-dispatch recorded sha as covering a new HEAD.
- **Don't:** treat a clean `git status` as proof the child did
  not commit.
- **Don't:** compose the fallback PR comment in the authoring
  session; post the dispatched reviewer's report verbatim.

## Cursor Cloud Task `tool_result` is identity-only

A Cursor Cloud `Task` JSON `tool_result` (harness logs may show `task_v2`)
carries identity fields (including `cloudAgentBcId`) and no review body,
even when the child ran in the foreground.
That JSON is not the report to post as a fallback comment.
The harness may still paste a child assistant message into the parent
transcript.
Quote that paste only when it already carries Summary / Findings / Verdict.
Otherwise fetch the child transcript.
Do not treat a thinking paraphrase or an empty paste as the report.

The adapter skip of `no-push-without-self-review.py` until
[#2241](https://github.com/Morrison-Lab/ai-config/issues/2241)
is in the dispatch section of this file;
this lesson is about the posted PR comment, not about satisfying the
pre-push guard.

- **Do:** quote a harness paste of the child's report when that paste
  already carries Summary / Findings / Verdict / Reviewed-Commit;
  otherwise call
  cursor-cloud `batch-fetch-details` with `bcIds: [<cloudAgentBcId>]` and
  `includeTranscripts: true`, then quote the last assistant `text` that
  carries those same sections --- not the last assistant message (which
  may be thinking or `tool_calls` with empty `text`), and not the whole
  file.
  `cloudAgentBcId` is a field on the Task JSON `tool_result`; `bcIds` is
  the tool parameter.
- **Don't:** treat the parent thinking "the reviewer approved" as the
  report, post the identity-only JSON `tool_result` as the review, quote
  a harness paste of thinking or empty `text`, quote the whole
  `transcript.json`, or paraphrase a missing body as Ready for merge.

(Measured 2026-08-25.
The wrap is
[ai-config#2234 comment 5415839535](https://github.com/Morrison-Lab/ai-config/pull/2234#issuecomment-5415839535).
The identity-only JSON is the parent `Task` `tool_result` for child
`bc-61fbadd0-7970-5b2d-8775-4924a28e09a1`.
That comment does not contain the JSON.)

## Jules allowlist skips `cursor[bot]` / `author_association: NONE`

[`.github/workflows/jules-review.yml`](../.github/workflows/jules-review.yml)
requires `author_association` in OWNER/MEMBER/COLLABORATOR.
Comments from a Cursor Cloud run post as `cursor[bot]` / `NONE`, so
an `@jules review` comment from that identity is skipped.

This is the same class as
[`self-review-fallback.cases.md`](../shared/workflow/self-review-fallback.cases.md)
"A session that could reach none of four working reviewers"
([#1417](https://github.com/Morrison-Lab/ai-config/pull/1417) /
[#1433](https://github.com/Morrison-Lab/ai-config/issues/1433), 2026-08-12:
`claude[bot]` / `CONTRIBUTOR`).
2nd occurrence, 2026-08-25, #2234; the association this time is `NONE`.

- **Do:** have a human OWNER/MEMBER/COLLABORATOR post `@jules review`
  (the workflow trigger is a trusted comment containing that mention).
- **Don't:** re-post the same request from a session whose comments post
  as `cursor[bot]` / `NONE` --- the gate that skipped it skips the retry.

(Measured 2026-08-25 on
[ai-config#2234](https://github.com/Morrison-Lab/ai-config/pull/2234).)

