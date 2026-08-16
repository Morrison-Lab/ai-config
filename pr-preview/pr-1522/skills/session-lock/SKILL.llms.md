# session-lock — deconflict parallel local AI sessions

`claim-pr` stops two sessions from colliding on the **remote** (a GitHub/GitLab PR or issue). This skill stops them from colliding on the **local filesystem** — when two or more agent sessions (Claude Code CLI tabs, a CLI + the IDE extension, two cloned terminals) have the *same working tree* open at once and silently step on each other:

- one `git checkout`s a branch out from under another’s uncommitted edits;
- two edit the same file and the later write wins;
- two push to the same branch and one rejects / force-overwrites the other;
- two kick off the same expensive render/build/test in the same dir.

The system is one script — **`~/.claude/skills/session-lock/scripts/ai-session.sh`** — backed by a registry of live sessions under the repo’s shared git common dir (`$(git rev-parse --git-common-dir)/ai-sessions/`). That location is machine-local (git never tracks anything under `.git/`, so it is never committed or pushed), repo-scoped, and **shared across every `git worktree`** of the repo — so sessions in different worktrees still see each other.

> Throughout, `ai-session.sh` means `~/.claude/skills/session-lock/scripts/ai-session.sh` (symlinked there by `bootstrap.sh`). Use the full path, or alias it for the session.

## When this fires

- **Before a write session** on a repo that another local session might also have open — fix/implement/refactor/commit/push work.
- When asked to “deconflict sessions”, “don’t step on the other session”, “lock the worktree”, “am I going to collide with my other tab?”, or to set up parallel-session safety.

It does **not** fire for a quick read-only look, and it is about *local* sessions — for PR/issue-level claims across machines and the `@claude` CI bot, use **`claim-pr`** instead. The two are complementary: `claim-pr` for the remote, `session-lock` for the local checkout.

## Identity

Every command keys off a **session id**, resolved in this order:

1.  `--id <id>` flag (recommended — pick a short stable label at session start, e.g. `cli-$(whoami)-fix-auth`, and pass it on every call);
2.  `$AI_SESSION_ID`;
3.  `$CLAUDE_SESSION_ID`.

Because each Bash invocation is a fresh shell (no persisted env), the durable way to stay consistent is to **choose one label when the session starts and reuse it** for `register` / `heartbeat` / `check` / `release`.

## The workflow

### 1. Register at the start of a write session

``` bash
ai-session.sh register --id <id> --task "<one line: what you're doing>"
```

`register` prunes dead records first, writes this session’s record (branch, worktree, host, agent PID, timestamps), and **immediately reports any collision** with another live session. If it reports a `SAME WORKING TREE` conflict, go to step 3 before editing anything.

### 2. Check before you touch the working tree

``` bash
ai-session.sh check --id <id>
```

Exit codes let you gate work:

| exit | meaning | what to do |
|----|----|----|
| `0` | clear — no other live session in this worktree/branch | proceed |
| `3` | **same working tree** — another live session shares this exact checkout | isolate (step 3) **before editing** |
| `4` | same branch in a *different* worktree — pushes may race | coordinate pushes, or use a distinct branch |

If both apply at once, `check` prints **both** warning blocks but exits `3` — the more severe code wins. That’s intentional: a shared working tree subsumes the push race, and isolating into your own worktree (step 3) resolves both. A caller scripting on the exit code should treat `3` as “isolate first,” which also clears any latent `4`.

`check` also refreshes your own heartbeat (when run with a `--id` that is already registered), so calling it as you work keeps your session marked live. Run without a registered id it is purely **read-only** — it still reports conflicts, but can’t refresh a heartbeat, so register first for a normal session.

### 3. Isolate into your own worktree on a `SAME WORKING TREE` conflict

The clean fix for two sessions in one checkout is to give each its own **git worktree** — a separate working directory that shares the same `.git`, so there is no shared-edit contention at all:

``` bash
ai-session.sh worktree <new-branch> [--base <ref>]   # default base: HEAD
```

This creates `…/<repo>.worktrees/<new-branch>/` on `<new-branch>` (override the parent dir with `$AI_WORKTREE_DIR`). Then move your session there and re-register:

``` bash
cd <printed path>
ai-session.sh register --id <id> --task "<…>"
```

Do all subsequent edits/commits/pushes from that path. When finished:

``` bash
git worktree remove <path>     # add --force if it has untracked files you don't need
```

(Note: this is the same isolation the `Agent` tool offers via `isolation: "worktree"` for *sub*-agents; `ai-session.sh worktree` is for *independent top-level* sessions that the Agent tool can’t reach.)

### 4. Release at the end of the session

``` bash
ai-session.sh release --id <id>
```

Removes your record so you stop showing as a live session. If you forget, staleness handling (below) reclaims it automatically.

## Seeing the whole picture

``` bash
ai-session.sh list          # live sessions + a CONTENTION summary
ai-session.sh list --all    # include stale/dead records (not pruned)
ai-session.sh prune         # drop stale records now
```

`list` flags any worktree or branch held by ≥2 live sessions — a quick dashboard of who is working where.

## Staleness & crash recovery (no daemon, no heartbeat babysitting)

A session that crashes or is closed must not block others forever. A record is **stale** (and auto-pruned by `register` / `check` / `list` / `prune`) when:

1.  its PID is on **this host** and the process is **gone** (`kill -0` fails) — the strong, immediate signal for a closed local CLI; **or**
2.  its host is unknown/different (no usable PID) and its **heartbeat is older than `$AI_SESSION_STALE_SECONDS`** (default `1800` = 30 min).

So on a single machine you rarely need heartbeats at all — a dead process is detected at once. Heartbeats (`heartbeat` / `check`) are the fallback for cross-host or container cases where the PID can’t be probed.

## Optional: auto-register via a hook

For hands-off registration, wire `hooks/session-start-register.sh` into a repo’s `SessionStart` (and optionally `UserPromptSubmit`) hook — it registers the session using the real `session_id` from the hook payload and prints any conflict. See `docs/local-session-deconfliction.md` for the exact `settings.json` snippet and design notes.

## Notes

- The registry never leaves the machine: it lives under `.git/`, which git does not track. Nothing to `.gitignore`, nothing to commit.
- Works for any agent that can run the script — it is not Claude-specific.
- This guards *local* contention only. Still use `claim-pr` for the PR/issue and `sync-pr-branch` before pushing, so remote and local stay in sync.
- This skill *creates* worktrees (step 3) and removes your own at session end. For the bulk sweep of dead worktrees left behind by ended sessions, use **`clean-worktrees`** (`cw`) — it consults this registry so it never removes a worktree a live session still holds.

Back to top
