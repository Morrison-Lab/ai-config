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

**Historical as of the symlink-install removal ([ai-config#2229](https://github.com/Morrison-Lab/ai-config/pull/2229)):** `bootstrap.sh` no longer links `~/.claude/skills`, `~/.cursor/skills`, or `~/.cursor/rules` at all --- the Cursor plugin is now the only supported route for Cursor.
Read the rest of this section as describing a machine installed before that change.

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
Name the checkout whose `git push` follows
(the isolated worktree, not the conductor's cwd).
Brief the child with that checkout path.
Run every git command in this section in that checkout
(`git -C <checkout> ...`, or after `cd` to it).
A `git -C` on the push that names a different directory
than the gates is the wrong-repository bypass
`iter_pushes` already grades
(chained `-C`, `cd`/`pushd`, `REDIRECTED`; ai-config#1977).
Record `git rev-parse HEAD` and `git rev-parse --abbrev-ref HEAD`
in that checkout
before the dispatch,
and run `git status --short` there.
If that status is not empty, do not dispatch: commit or stash first.
After the child returns, recover the report from
cursor-cloud `batch-fetch-details`
with `bcIds: [<cloudAgentBcId>]` and `includeTranscripts: true`.
That transcript is the admissible source for `parse_report()`
and the HEAD fingerprint check.
`scripts/cursor-self-review-check.py` is the interim instrument for
both halves --- `verdict --transcript <file> --expect-head <sha>` runs
`parse_report()` and the fingerprint comparison, and
`gates --recorded-head <sha> --recorded-branch <name> -C <checkout>`
runs the git-decidable refusal gates below --- so neither is re-derived
by hand (ai-config#2299, #2310; retired when #2241 restores the hook).
The dry-run tip check and the source-ref check take no input
from the transcript:
they come from the same-argv
`git push --dry-run` in the checkout whose push follows.
A harness paste of the child's own assistant message may corroborate
the recovered body;
an author-composed block with those headings does not.
Measured 2026-08-26 PDT on Cursor Cloud:
`json.load` of `transcript.json` already yields the markdown
string in the assistant `text` field.
Do not `json.loads` that field's value a second time.
The file stores the body as a JSON string
(newlines appear as escaped `\n` on disk).
The parser resolves that.
Records carry a `role` the decoder must filter on.
`json.load` of `transcript.json` returns a dict
with a `messages` key (measured 2026-08-26 PDT on Cursor Cloud);
iterate that list, not the dict.
Take the last assistant record whose `text` is a non-empty string.
Thinking and `tool_calls` records usually omit the `text` key
(measured 2026-08-26 PDT: the key is absent, not null and not empty).
Read it with `.get("text")`.
A missing, null, or empty value is not a candidate.
That last non-empty assistant `text` must itself carry
Summary / Findings / Verdict / Reviewed-Commit.
The decoder decides that; `parse_report()` does not
(`parse_report` matches only the verdict line and the fingerprint).
If that last non-empty text lacks those headings, there is no report.
Do not call `parse_report()` on a body that failed the heading check.
The role filter is load-bearing.
The user brief also carries those headings
(it specifies the required report shape).
A decoder that takes the last matching `text`
without filtering `role == assistant`
grades the brief when the child produced no report.
A decoder that skips a later non-empty assistant text
grades a draft when the child errored after quoting the shape.
The recovered transcript file is the instrument.
A decoder reads `transcript.json` whose path contains
the `cloudAgentBcId`, writes that last non-empty assistant `text`
to a file outside the checkout (under `/tmp`),
and calls `parse_report()` on the file contents
in one process.
The `parse_report()` tuple always comes from that file,
never from an unverified subagent return.
Fetch only the `cloudAgentBcId` from a `Task` dispatch whose
`subagent_type` was `adversarial-reviewer`.
Do not fetch a sibling child's transcript.
The posted body is that recovered file,
then the agent-authorship disclosure marker
after a blank line
(see [`disclose-agent-authorship`](../shared/workflow/disclose-agent-authorship.md)).
The child does not write the marker.
Do not re-emit the markdown through a shell command string.
A backtick span inside a double-quoted body runs as
command substitution and vanishes.
A doubled backslash can collapse even inside a quoted heredoc.
Write the recovered file plus the marker to a comment file
under `/tmp`, and post that file
with `--body-file` / `-F body=@<file>`.
The recovered file is both the `parse_report()` input
and the posted comment body (then the disclosure marker).
The tuple is only the push gate.
Call `parse_report()` from the **worktree's**
[`hooks/no-push-without-self-review.py`](../hooks/no-push-without-self-review.py)
on the file contents
(`importlib.util.spec_from_file_location`;
the module loads with no side effects)
when the worktree hook script exists in the pushing checkout.
Measured 2026-08-26 PDT on this VM, whose primary checkout
is ai-config:
`~/.claude/hooks -> /workspace/hooks`,
and `~/.claude/hooks/no-push-without-self-review.py`
shares an inode with
`/workspace/hooks/no-push-without-self-review.py`
(`/workspace` was `main` at `21a2e2aa`).
That measurement does not say what the path is
when the primary checkout is not ai-config.
If `hooks/no-push-without-self-review.py` is missing
from the pushing checkout, obtain a CLI review
([`adversarial-self-review`](../shared/workflow/adversarial-self-review.md)).
Do not import `~/.claude/hooks/`:
it is a different revision from the branch under review,
and in some install shapes a real copy a `git pull` does not refresh.
When the three-dot diff includes
`hooks/no-push-without-self-review.py`,
also call `parse_report()` from `origin/<default-branch>`'s copy
(`git show origin/<default-branch>:hooks/no-push-without-self-review.py`
written under `/tmp`).
Do not push unless both copies return `clean`
with a fingerprint that prefix-matches HEAD.
If that path is missing on the default branch, obtain a CLI review.
Do not import `~/.claude/hooks/` for that copy either.
Do not paste a report body the conductor composed.
Do not read the transcript file into the conductor's context.
The recovered report file under `/tmp` is what the author reads
to Address, Rebut, or Defer each finding.
The transcript prohibition does not cover that file.
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
Address, Rebut, or Defer each finding from the recovered report file,
then re-dispatch.
A push that carries nothing to review
is the empty [`pr-on-claim`](../shared/workflow/pr-on-claim.md)
branch, created with `--allow-empty`.
The positive test is two commands in that checkout:
`git rev-list --count origin/<default-branch>..HEAD` equals 1,
and `git diff --quiet HEAD^ HEAD` exits 0.
Exit 1 means a diff; exit 128 means the command failed.
Neither is the carve-out.
Both conditions passing is the `--allow-empty` pr-on-claim commit.
`git diff origin/<default-branch>...HEAD` empty
in that checkout is tree equality against the merge-base,
not "this branch carries nothing".
An add-then-delete pair, a revert pair, or a branch
whose only commits are `main` merges
also produce an empty three-dot diff and still ship commits.
Those are not the carve-out: obtain a review.
For the `--allow-empty` case, do not invent a report,
do not refuse that push for lack of a verdict,
and say in the reply that the carve-out was used.
Re-read `git rev-parse HEAD` in that checkout after the child returns.
If HEAD is not the recorded sha, the child wrote or HEAD moved:
do not push; re-dispatch on the new HEAD.
The fingerprint must prefix-match HEAD
(`c.startswith(reviewed_commit)` in `verify_review`).
`parse_report` already lowercases the fingerprint.
If the fingerprint does not prefix-match HEAD, do not push.
[#2299](https://github.com/Morrison-Lab/ai-config/issues/2299)
tracks a CLI wrapper over that Cursor Cloud `parse_report()` call.
The recovered transcript file is what supplies the report
on Cursor Cloud;
Claude Code reads the same report from the `Agent` call's `tool_result`.
Until that wrapper lands, the import is the instrument
for recovering a Cursor Cloud `Task` child's report.
[#2255](https://github.com/Morrison-Lab/ai-config/pull/2255)
landed `scripts/pre-push-review.py` on `main` (measured 2026-08-26 PDT):
a separate local-engine dispatcher with its own report contract
(`parse_review_verdict`), not a wrapper over `parse_report()`
and not this recovery path.
Tracked as [#2309](https://github.com/Morrison-Lab/ai-config/issues/2309).
The remaining git-decidable refusal gates
(`git status`, HEAD still recorded, dry-run tip, source ref,
empty-diff carve-out) are tracked as
[#2310](https://github.com/Morrison-Lab/ai-config/issues/2310).
Run `git push --dry-run` in that checkout
with the same arguments as the push
that follows, including the refspec
(the guard exempts dry-run from review).
This recipe's push is `git push -u origin <branch>`
without `--porcelain`.
A `--porcelain` push is not this procedure.
Do not treat a line without `->` as a deletion under porcelain:
porcelain writes those lines to stdout
and emits no `->` on any line
(git v2.43.0 `transport.c` `print_ref_status`).
Read stdout and stderr (`2>&1`).
Without `--porcelain`, the summary lines this section names
write to stderr.
If that command fails,
or you cannot tell from its output which commits would ship,
or any reported new tip does not prefix-match HEAD,
or the dry-run listed other refs,
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
A `--verbose` or `--porcelain` run can also emit per-ref
`= [up to date]`; this recipe does not use those flags.
A new branch's dry-run line is `[new branch]` with no sha.
That line is not a mismatch.
It also does not confirm the shipped tip:
the first push of a `cursor/<name>` branch is this case,
so the dry-run only confirms the command would create that ref.
A `-u` dry-run also prints
`Would set upstream of '<branch>' to '<branch>' of 'origin'`
on stdout, including when the upstream is already set
(git 2.43.0 `set_upstreams()` pretend branch).
That line is not a mismatch and is not "other refs".
It does not confirm the shipped tip.
The source-ref rule and the HEAD comparison remain.
A deletion line (`- [deleted]`) has no `->`,
so it has no source ref for the source-ref check.
`--delete` / `-d` is not this procedure.
`_argv_push` excludes those flags,
so the guard never sees the push.
Treat a `--delete` / `-d` push as an ordinary git push,
not as a reviewed feature-branch push.
`git push origin :branch` is also not this procedure.
On Claude Code it still needs a clean verdict
to reach `verify_review`'s `if not commits` exit
(the guard's own docstring).
On this Cursor-adapter path it is not a source-ref miss
of the feature-branch recipe;
it is a different command.
If the source ref (left of `->`) is `HEAD`, the recorded sha covers it.
If it is a branch name, that name must match the recorded branch.
Any other source ref (a tag, `FETCH_HEAD`, a raw sha) is not covered:
do not push.
Re-run `git status --short` in that checkout.
If it is not empty, do not push:
uncommitted child edits (or leftover dirty files) are not in the
fingerprint.
This repo's Cursor adapter skips `no-push-without-self-review.py`
(`SKIP_WITHOUT_TOOL_RESULT`) until
[#2241](https://github.com/Morrison-Lab/ai-config/issues/2241),
so a failed or skipped dispatch is not caught before the push.
The posted PR comment is the record, not a gate.
If the dispatch errored, produced no report,
or produced a report whose fingerprint cannot be recovered
(including a stale-registered persona),
obtain a review via the CLI fallback in
[`adversarial-self-review`](../shared/workflow/adversarial-self-review.md),
write that reviewer's report to a file under `/tmp`,
and call `parse_report()` on that file.
On a session whose pushes go through this repo's Cursor adapter,
default: do not prefix `ALLOW_UNREVIEWED_PUSH=1`.
The adapter skip makes it inert for the adapter
(measured 2026-08-25 PDT on Cursor Cloud).
If the pushing command is denied by a native
`PreToolUse` `no-push-without-self-review` hook,
that deny is the measurement that the native runner fired;
then prefix for that native guard.
Home Claude settings can exist on Cloud
(measured 2026-08-26 PDT: `/home/ubuntu/.claude/settings.json`
binds `no-push-without-self-review` under `PreToolUse`).
That measurement does not say how this VM's copy got there.
The in-tree writer of that path is `scripts/install-hooks.py`.
Those settings do not make the Cursor adapter run Claude's hook runner.
Whether Claude Code's native hook runner also fires on Cloud
is unmeasured as of 2026-08-26 PDT.
Settings existing is not the measurement that it fired.
The prefix stays inert for the adapter either way.
On a desktop session, do not pair the project adapter
with native Claude hooks (leave one path enabled).
On Cursor Cloud both can be present:
the adapter skip is the Cursor path,
and a native deny of the unprefixed push is the
observable that the native runner fired.

If Claude Code's native guard is also running ---
desktop third-party Claude hooks, or a Claude Code process on the
same VM --- a native deny of the unprefixed push is the
observable that the prefix is that native guard's escape,
because Cursor JSONL omits `tool_result` and the native guard
otherwise denies every push
(desktop path measured against Cursor's third-party hook docs on
2026-08-25).

When [#2241](https://github.com/Morrison-Lab/ai-config/issues/2241)
lands, sweep every site this section names
(`AGENTS.md`,
`CLAUDE.md`,
[`adversarial-self-review`](../shared/workflow/adversarial-self-review.md),
[`skills/push/SKILL.md`](../skills/push/SKILL.md),
[`pr-on-claim`](../shared/workflow/pr-on-claim.md),
both persona copies,
[`docs/cursor-hook-mapping.md`](../docs/cursor-hook-mapping.md),
`README.md` (the hook table describes the script,
not a harness skip),
and this file)
so the adapter-skip claim does not outlive the skip.
Compact copies stay until that landing.

Refusal gates, in order.
This is a Read-Do checklist.
Item 1's pre-dispatch recording must precede the dispatch,
or item 4 has nothing to compare against.
Gate 3 consumes the tuple gate 2 produces.
Reordering 5 with 6 does not change the answer.
Details in the procedure above.
Pause points:
before the `Task` dispatch (item 1's first half),
and before `git push` of the reviewed branch
(item 1's second half through item 6).
The git commands among the six run in the checkout whose push follows.
Gate 2 writes the report under `/tmp`.
The empty `pr-on-claim` `--allow-empty` carve-out
exempts item 1's first half, item 2,
item 3's verdict/fingerprint clause, and item 4
(no dispatch, so no report and no pre-dispatch sha).
It does not exempt item 1's second half, item 5, or item 6.
The positive test is the two-command test in the procedure above.
Say in the reply that the carve-out was used.

1. Confirm `git status --short` is empty before dispatch,
   and still empty after.
   **Killer item:** skipped before dispatch, the fingerprint
   excludes the uncommitted work.
   Carve-out: skip the before-dispatch half
   (there is no dispatch); still confirm empty after.
2. Confirm the `cloudAgentBcId` came from a `Task` whose
   `subagent_type` was `adversarial-reviewer`.
   Take the last assistant record whose `text` is a non-empty string
   (thinking and `tool_calls` usually omit `text`; use `.get`;
   they are not candidates);
   that text must itself carry the headings
   (the decoder refuses here; `parse_report` does not check
   Summary or Findings).
   If the headings are missing, there is no report;
   do not call `parse_report`.
   Write that text to a file outside the checkout (under `/tmp`)
   and call `parse_report()` on that file.
   **Killer item:** an author-assembled body is not a report,
   and `parse_report` then grades the wrong text.
   A real report from the wrong dispatch also fails this gate.
   Skipping a later non-empty assistant text
   to reach an earlier matching one also fails this gate.
   Carve-out: skip (no report to parse;
   do not refuse for lack of a verdict).
3. Confirm the verdict is `clean` and the fingerprint
   prefix-matches HEAD.
   Carve-out: skip (no fingerprint;
   the two-command test above is what decides).
4. Confirm HEAD is still the recorded sha.
   Carve-out: skip (no sha was recorded before a dispatch).
5. Run the same-argv dry-run; confirm every reported new tip
   prefix-matches HEAD
   (`Everything up-to-date` is not a mismatch;
   a new-branch line with no sha is not a mismatch
   and also does not confirm the shipped tip;
   `Would set upstream of ...` on stdout is not a mismatch
   and is not "other refs").
   If the dry-run listed other refs (`[new tag]`,
   `push.followTags`), do not push.
6. Confirm every source ref is `HEAD` or the recorded branch.
   A deletion line (`- [deleted]`) is a different command
   (`_argv_push` excludes `--delete` / `-d`,
   so the guard never sees that push;
   `:branch` is not this feature-branch recipe),
   not a source-ref miss.
   This recipe does not use `--porcelain`.

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
  Name the checkout whose push follows.
  Brief the child with that checkout path.
  Record `HEAD`, the branch name, and `git status --short`
  in that checkout
  before the dispatch.
  After it returns, recover the report from `batch-fetch-details`
  with `bcIds` and `includeTranscripts: true`
  (a harness paste of the child may corroborate; name the route).
  Write the last non-empty assistant `text`
  (thinking and `tool_calls` usually omit `text`; use `.get`;
  they are not candidates).
  That text must itself carry
  Summary / Findings / Verdict / Reviewed-Commit.
  Write it to a file outside the checkout (under `/tmp`;
  role filter is load-bearing;
  the user brief also carries those headings),
  and call `parse_report()` on that file
  from the worktree's `hooks/no-push-without-self-review.py`
  (see the import rule in the procedure above).
  If you cannot obtain a `clean` verdict and fingerprint,
  or HEAD is not still the recorded sha,
  or the fingerprint does not prefix-match HEAD,
  or `git status --short` is not empty,
  or the same-argv dry-run fails,
  or any reported new tip does not prefix-match HEAD
  (`Everything up-to-date` is not a mismatch;
  a new-branch line with no sha is not a mismatch
  and also does not confirm the shipped tip),
  or any source ref is not `HEAD` and is not the recorded branch,
  or the dry-run listed other refs,
  do not push.
  The empty [`pr-on-claim`](../shared/workflow/pr-on-claim.md)
  `--allow-empty` branch is the carve-out.
  The positive test is the two-command test in the procedure above.
  A net-zero tree of other commits is not the carve-out:
  obtain a review.
  The `--allow-empty` case has no report,
  that is not a reason to refuse the push,
  and the reply must say the carve-out was used.
- **Don't:** treat a skipped GitHub `claude-review` as "no
  Claude reviewer is reachable in this session".
- **Don't:** omit `model` on that dispatch when Claude is
  listed and the conductor is not Claude.
- **Don't:** prefix `ALLOW_UNREVIEWED_PUSH=1` on a Cursor-adapter
  push by default: the skip makes it inert for the adapter.
  Prefix only after a native `PreToolUse`
  `no-push-without-self-review` deny of the unprefixed push.
  On a desktop session, do not pair the project adapter
  with native Claude hooks.
  On Cursor Cloud both can be present
  (see the pairing rule in the procedure above).
  If the dispatch errored, produced no report,
  or produced a report whose fingerprint cannot be recovered
  (including a stale-registered persona),
  obtain a CLI review,
  write that reviewer's report to a file under `/tmp`,
  and call `parse_report()` on that file.
- **Don't:** record HEAD, status, or the dry-run in a different
  checkout than the push's `-C` or cwd.
- **Don't:** re-emit the recovered markdown through a shell
  command string; write it to a file outside the checkout
  (under `/tmp`) and parse and post from that file.
- **Don't:** treat a matching HEAD sha as covering a dry-run
  that used different arguments, failed, or listed other refs.
- **Don't:** treat a fingerprint that matches only the
  pre-dispatch recorded sha as covering a new HEAD.
- **Don't:** treat a clean `git status` as proof the child did
  not commit.
- **Don't:** compose the fallback PR comment in the authoring
  session; post the dispatched reviewer's report verbatim
  from the recovered file, then the disclosure marker.

## Cursor Cloud Task `tool_result` is identity-only

A Cursor Cloud `Task` JSON `tool_result` (harness logs may show `task_v2`)
carries identity fields (including `cloudAgentBcId`) and no review body,
even when the child ran in the foreground.
That JSON is not the report to post as a fallback comment.
The harness may still paste a child assistant message into the parent
transcript.
A paste may corroborate the recovered body;
do not post the paste.
Fetch the child transcript and post the recovered file.
Do not treat a thinking paraphrase or an empty paste as the report.

The adapter skip of `no-push-without-self-review.py` until
[#2241](https://github.com/Morrison-Lab/ai-config/issues/2241)
is in the dispatch section of this file;
this lesson is about the posted PR comment, not about satisfying the
pre-push guard.

- **Do:** recover the report from
  cursor-cloud `batch-fetch-details` with `bcIds: [<cloudAgentBcId>]` and
  `includeTranscripts: true`, then write the last non-empty assistant `text`
  (thinking and `tool_calls` usually omit `text`; use `.get`;
  they are not candidates).
  That text must itself carry
  Summary / Findings / Verdict / Reviewed-Commit.
  Write it to a file outside the checkout
  (under `/tmp`) and post from that file ---
  not a harness paste (a paste may corroborate; do not post it),
  not an earlier matching assistant text reached by skipping
  a later non-empty one, not the user brief
  (the brief also carries those headings; the role filter is load-bearing),
  and not the whole file.
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

## Jules allowlist skips `cursor[bot]` outside OWNER/MEMBER/COLLABORATOR

[`.github/workflows/jules-review.yml`](../.github/workflows/jules-review.yml)
requires `author_association` in OWNER/MEMBER/COLLABORATOR.
Comments from a Cursor Cloud run post as `cursor[bot]`.
A 2026-08-25 memory recorded that identity as `NONE` on
[#2234](https://github.com/Morrison-Lab/ai-config/pull/2234).
A live REST re-read on 2026-08-26 of the same `@jules review` comment
([5415839558](https://github.com/Morrison-Lab/ai-config/pull/2234#issuecomment-5415839558))
returns `CONTRIBUTOR`, as do `cursor[bot]` comments on
[#2290](https://github.com/Morrison-Lab/ai-config/pull/2290).
`CONTRIBUTOR` is still outside the allowlist, so an `@jules review`
comment from that identity is skipped either way.
Prefer the live association over the stored `NONE`.

This is the same class as
[`self-review-fallback.cases.md`](../shared/workflow/self-review-fallback.cases.md)
"A session that could reach none of four working reviewers"
([#1417](https://github.com/Morrison-Lab/ai-config/pull/1417) /
[#1433](https://github.com/Morrison-Lab/ai-config/issues/1433), 2026-08-12:
`claude[bot]` / `CONTRIBUTOR`).
2nd occurrence, 2026-08-25, #2234 (the skip is real; the stored
`NONE` is not what that comment shows on 2026-08-26).

`jules-review.yml` also starts a skipped run on every PR comment, because
`on: issue_comment` fires before the job `if:`.
That skip is the `@jules` substring pre-filter, not this allowlist.
[#2290](https://github.com/Morrison-Lab/ai-config/pull/2290) had zero
`@jules` comments; its skipped Jules runs do not count as a recurrence.

- **Do:** have a human OWNER/MEMBER/COLLABORATOR post `@jules review`
  (the workflow trigger is a trusted comment containing that mention).
- **Do:** re-read `author_association` on the comment you care about
  rather than inheriting a stored Cursor Cloud value.
- **Don't:** re-post the same request from a session whose comments post
  as `cursor[bot]` outside OWNER/MEMBER/COLLABORATOR --- the gate that
  skipped it skips the retry.
- **Don't:** count a skipped `jules-review.yml` run as this allowlist
  miss unless the triggering comment actually contained `@jules`.

(Allowlist skip measured 2026-08-25 on
[ai-config#2234](https://github.com/Morrison-Lab/ai-config/pull/2234);
association on that `@jules` comment re-read 2026-08-26 as
`CONTRIBUTOR`. #2290 had no `@jules` mention.)

## Cursor Cloud `gh` writes can 403 while the PR-comment tool still posts

Measured 2026-08-26 on a Cursor Cloud run driving
[#2290](https://github.com/Morrison-Lab/ai-config/pull/2290):
`gh issue comment` and a Copilot review-request POST returned
`403 Resource not accessible by integration`.
`gh api user` returned the same 403.
`gh issue create` and `gh pr view` succeeded in the same session.
PR conversation comments posted through Cursor's `ManagePullRequest`
`post_comment` action (example:
[comment 5423368708](https://github.com/Morrison-Lab/ai-config/pull/2290#issuecomment-5423368708)).

This is a session-token measurement, not a standing GitHub outage.
Re-attempt `gh` writes before reporting them blocked, per
[`github-mcp-tools.md`](github-mcp-tools.md)'s 403-as-measurement note.

- **Do:** fall back to Cursor's `ManagePullRequest` `post_comment` when
  `gh pr comment` 403s in a Cursor Cloud session, and disclose agent
  authorship in the body.
- **Don't:** treat a 403 on one write surface as covering every `gh`
  write --- `gh issue create` worked in the same run that could not
  comment.

## Cursor CLI requires `--trust` for non-interactive execution

When running `cursor-agent` or the Cursor CLI non-interactively (without a TTY, such as in a subprocess or automated script),
the `--trust` flag is strictly required even in `plan` mode.

If `--trust` is omitted, the agent will prompt for workspace trust confirmation and hang indefinitely waiting for standard input,
leading to silent timeouts in automated tools.
Do not remove this flag in the name of tighter sandboxing for automated review scripts.

(Measured 2026-08-26 on Morrison-Lab/ai-config#2255 during adversarial review script integration).

## Auto-review push blocks are not a stop

Cursor Auto-review may refuse `git push` / `gh pr comment` until a smart-mode
approval card is shown.
That is a client gate, not a missing user grant.
Standing permission already covers push and PR updates
(`AGENTS.md` "Default to action"; preferences "always push and PR").

- **Do:** retry the push/comment with the approval path the client requires,
  or ask once for that card when the harness cannot show it --- then push.
- **Don't:** end the turn with commits ahead of origin and
  "say if you want those pushed" (ai-config#2277, 2026-08-26).

