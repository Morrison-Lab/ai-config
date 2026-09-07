# OpenCode hook mapping

Claude Code loads enforcement guards from [`hooks/hooks.json`](../hooks/hooks.json).
Cursor Cloud loads that catalog through a schema adapter (see
[Cursor hook mapping](cursor-hook-mapping.md)).
OpenCode reads neither.
It still runs the catalog where both halves of this chain are present:

1. `~/.claude/settings.json` carries the catalog through the non-plugin
   install path (`scripts/install-hooks.py --fix`),
   with commands pointing at `~/.claude/hooks/<script>`.
2. The [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)
   OpenCode plugin ships a Claude-hooks compatibility layer
   (`dist/hooks/claude-code-hooks/`) that reads those settings --- the
   user file plus the project's `.claude/settings.json` and
   `.claude/settings.local.json` --- and runs each matching catalog command
   inside OpenCode sessions.

Measured against oh-my-openagent 4.19.4 and opencode 1.18.20 on 2026-09-03
(PDT), by reading the plugin's bundle and by live observation inside an
OpenCode session.
The bridge is third-party and versioned independently;
re-verify on a harness bump, the way the Cursor mapping doc does.

## Activation

No OpenCode-side configuration is needed beyond having OMO installed
and the non-plugin Claude install on the machine.
OMO reads the settings files per session cwd, so the catalog follows the
project the session is opened in, exactly as it does for Claude Code.
A deny from a `PreToolUse` guard aborts the tool call and surfaces as the
call's error plus a TUI toast, so blocking works without any OpenCode-side
wiring.

The bridge only works with the non-plugin command form.
A settings file carrying plugin-path commands (`${CLAUDE_PLUGIN_ROOT}/hooks/...`)
would run unexpanded, because OpenCode does not set that variable;
how the bridge then fails is unmeasured (2026-09-03).
This machine's install is the non-plugin form.

## Event mapping

| Claude Code event | OpenCode surface | Fires | Notes |
|---|---|---|---|
| `PreToolUse` | plugin hook `tool.execute.before` | yes | OMO transforms the tool name and snake-cases `tool_input`, then runs every matcher-matching catalog command with a Claude-shaped payload. A deny aborts the call. |
| `PostToolUse` | plugin hook `tool.execute.after` | yes | OMO builds a temporary Claude-shaped transcript from the session API (assistant `tool_use` entries only) and passes its path. |
| `UserPromptSubmit` | plugin hook `chat.message` | yes | The payload carries `prompt` and `session_id` but no `transcript_path`. Hook `additionalContext` is injected into the message parts the model sees. |
| `Stop` | bus event `session.idle` | yes | `decision: block` re-prompts the session with the reason (OMO's `injectPrompt`), the analogue of Cursor's `followup_message`. Subagent sessions are skipped (`parentSessionId` guard). `stop_hook_active` state is tracked per session. |
| `SessionStart` / `SessionEnd` / `PreCompact` | in OMO's event list | unmeasured | The catalog registers none of these. The project-level `.claude/settings.json` `SessionStart` (`session-start.sh`) is a no-op outside remote sessions. |

## Tool-name mapping

OMO Pascal-cases the OpenCode tool name before matching
(`bash` to `Bash`, `task` to `Task`, `webfetch` to `WebFetch`,
and any name containing `-` or `_` to PascalCase).
Its matcher semantics are narrower than Claude Code's:
pipe-split patterns, `*` becoming a case-insensitive `.*` regex,
everything else an exact case-insensitive compare.
There is no JS-regex matcher form.

| OpenCode tool | Transformed | Reachable matchers |
|---|---|---|
| `bash` | `Bash` | `Bash` rows work. |
| `task` | `Task` | `Task` rows work; the `Agent`-matcher slice (e.g. `flag-unassigned-worktree.py`) never fires. |
| `github_add_issue_comment` | `GithubAddIssueComment` | `mcp__github__.*` patterns never match, so the MCP-matcher slices (`require-agent-disclosure.py`, `no-unauthorized-merge.py`, `warn-pr-create-without-dupe-check.py`, the MCP slice of `flag-unmeasured-timestamp.py`) are inert for MCP calls. Their Bash siblings still cover the CLI paths. |

## Transcript

OMO maintains one JSONL per OpenCode session under
`$CLAUDE_CONFIG_DIR/transcripts/` (default `~/.claude/transcripts/`),
appending as the session runs.
Three flat record shapes, none of them Claude's:

```json
{"type": "user", "timestamp": "...", "content": "<prompt>"}
{"type": "tool_use", "timestamp": "...", "tool_name": "task", "tool_input": {}}
{"type": "tool_result", "timestamp": "...", "tool_name": "task",
 "tool_input": {}, "tool_output": "<result text>"}
```

What is missing compared with a Claude-native transcript:
message nesting (`message.content` blocks),
call IDs (`tool_use_id` pairing),
`is_error` flags,
and all assistant reply text.

The missing `is_error` has a consequence worth stating rather than leaving to
be discovered.
`no-push-without-self-review.py` keeps its `is_error` exclusion on this path,
but the flag never arrives, so the clause is inert here and the guard authorizes
on the report's content alone.
An errored reviewer dispatch whose output happens to carry a complete,
correctly-fingerprinted report will therefore authorize a push, where the
Claude-native path would have excluded it.
The fingerprint requirement is what limits this: a truncated failure rarely
carries both a verdict line and a `Reviewed-Commit:` naming a commit the push
ships.
Pinned by two cases in `hooks/test-no-push-without-self-review.py`, so the
caveat cannot quietly stop being true.

Payload-side gaps:

- `PreToolUse` carries no `transcript_path` at all
  (OMO's hook context omits the field).
- `UserPromptSubmit` carries no `transcript_path`.
- `Stop` carries the session file's path.

The guard-side repairs in this repo, as of #3168:
[`no-push-without-self-review.py`](../hooks/no-push-without-self-review.py)
resolves the fallback transcript from the payload's `session_id` when the
primary path is absent,
reads OMO's flat shapes,
and pairs `tool_use`/`tool_result` positionally per tool name.
Everything else that reads a transcript still expects Claude-native shapes
and degrades per its own design.

## Per-guard status

Representative classes, after #3168:

| Guard class | Status in OpenCode |
|---|---|
| `PreToolUse` Bash guards (`require-gh-repo-flag.py`, `no-clobbering-push.py`, `no-commit-chained-to-push.py`, ...) | work |
| `no-push-without-self-review.py` | works (fallback transcript + OMO shapes); before #3168 it denied every push in an OpenCode session |
| `Write`/`Edit` guards (`no-whole-file-punct-replace.py`, `warn-stale-issue-edit.py`) | work (`file_path` reaches `tool_input`) |
| `UserPromptSubmit` injectors (`inject-local-time.sh`, ...) | work (`additionalContext` reaches the model as injected parts) |
| `UserPromptSubmit` transcript readers (`remind-ums-after-error.py`, ...) | their transcript half no-ops (no `transcript_path` in the payload) |
| `Stop` git-state guards (`no-unshipped-commit.py`) | work |
| `Stop` reply-text guards (`require-stopping-point.py`, `flag-cop-out-offer.py`, `no-placeholder-reply.py`, `no-empty-promise.py`) | silent: the OMO transcript carries no assistant text, so nothing to scan |
| `Agent`-matcher guard (`flag-unassigned-worktree.py`) | inert (no `Agent` tool name) |
| MCP-matcher guards | inert (see tool-name mapping) |
| `SendMessage`-matcher slice of `remind-brief-premises.py` | inert |

Measured-by-absence, 2026-09-03:
an OpenCode session that ran the bridge live for dozens of turns
observed zero `Stop` blocks and correct `PreToolUse` denies.
Whether the silent reply-text guards pass or no-op is not distinguished
by that observation; an instrument for it is a follow-up.

## What this file is not

It is not a second catalog.
New guards still land in `hooks/` with a `hooks/hooks.json` row,
a README row, and a `test-<name>.py`.
The bridge reads whatever Claude settings carry;
this doc describes how the existing catalog behaves there.
Do not add a parallel list of script names here.

## Follow-ups

- `UserPromptSubmit` transcript fallback for the `remind-*` hooks
  (the payload has `session_id`, so the same fallback `no-push-without-self-review.py`
  uses would apply).
- Assistant reply text absence in OMO transcripts and its effect on the
  `Stop` reply-text guards.
- `Agent` and `mcp__github__.*` matcher gaps under OMO's tool-name transform
  (upstream OMO is the candidate fix).
- An instrument that distinguishes `Stop` silent-pass from silent-no-op.
