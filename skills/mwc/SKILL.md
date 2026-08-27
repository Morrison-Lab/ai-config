---
name: mwc
description: "Session merge grant with confidence gate."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Merge-When-Confident (MWC) Session Grant

`mwc` ("merge when confident") is an explicit, session-scoped user grant
that authorizes the AI assistant to merge fully-clean pull requests autonomously
for the duration of the current session,
without asking confirmation before every merge.

## Standing Scope & Policy

- **Baseline Prohibition**: AI assistants MUST NOT merge PRs/MRs
  without explicit user instruction for that specific PR.
  Pushing, building, or driving a PR to 100% clean CI
  DOES NOT grant permission to merge.
  One repository is exempted standing --- see "The standing per-repository
  grant" below --- and the Scope Limit binds that exemption too.
- **MWC Override Scope**: When the user explicitly issues `/mwc`,
  "merge when confident", "merge at will", or "maw",
  that baseline prohibition is suspended for the current session only.
- **Scope Limit**: An MWC grant applies ONLY to PRs that are 100% clean
  (all CI checks passing, automated Claude review verdict clean, no unresolved comments, no open block labels).
  It NEVER authorizes merging a PR with failing CI, unresolved findings, pending reviews, or a missing/skipped Claude review.
  A clean automated Claude review evaluating the current HEAD commit is strictly required for autonomous merge under MWC;
  a reviewer skip notice (e.g. for quota exhaustion or workflow edits) or a fallback self-review does NOT waive this requirement, grant merge authority under MWC, or clear missing external review.
  **A disagreement among reviews is unresolved findings.**
  If one review is all-clear and another raises blocking issues, nits, or any
  other flagged items, MWC does not authorize a merge.
  ARD every item from every review, then request fresh reviews.
  `check-pr-fully-clean.py` fails that state (ai-config#2274).
  A later all-clear from a different reviewer does not supersede a standing
  not-clean; only a later clean from the same reviewer does.
- **Session Duration**: The grant expires automatically when the session ends
  or when explicitly revoked via `/mwc revoke` or `disable-mwc`.

## The standing per-repository grant

One repository carries the grant **standing**, with no session step at all:
PRs targeting `Morrison-Lab/ai-config` (ai-config#1352).
`no-unauthorized-merge.py` reads the merge's target repository off the command
itself, so there is nothing to enable, nothing to expire, and no marker to go
stale.

The two grants differ on every axis except the Scope Limit, which binds both:

| | session grant (`/mwc`) | standing grant |
| :--- | :--- | :--- |
| scope | this session, every repo | `Morrison-Lab/ai-config`, forever |
| keyed on | a `.mwc` marker in the **current** repo's git dir | the **target** repo named in the command |
| enabling step | `enable-mwc`, then `check-mwc` | none |
| covers | any merge command run from that checkout | `gh pr merge` / `gh api .../pulls/N/merge` only |
| requires a fully clean PR | yes | yes |

Read the second row carefully, since it is the one that surprises.
The session grant is keyed on **where you are** and the standing grant on
**what you are merging**, so the standing one is the tighter of the two: an
active `/mwc` in an ai-config checkout authorizes `gh pr merge -R other/repo`,
and the standing grant never does.

Three things the standing grant deliberately does not cover, each of which
keeps the baseline prohibition:

- **A merge with no repo named in the command.**
  The target is read from the command text only, never from the working
  directory --- `offending` splits on `&&`, so `cd ../other && gh pr merge 1`
  would otherwise resolve to ai-config.
  `hooks/require-gh-repo-flag.py` already refuses a `gh pr merge` without `-R`,
  so this costs nothing in practice.
- **A repository branch merge** (`gh api -X POST repos/<owner>/<name>/merges`).
  That writes to the default branch with no PR, no review and no required
  check, and the grant is for PRs.
- **A GraphQL `mergePullRequest` mutation**, which names its target by node id,
  so no repository is derivable from the command at all.

Those last two are excluded by **every** interpretation the segment matches,
not by the first one.
The merge patterns are unanchored scans over the whole segment, so one command
line can satisfy several at once --- and the `pulls/N/merge` forms are tried
before the `repos/<owner>/<name>/merges` ones.
A real branch merge carrying a forged `pulls/1/merge` substring in an unmasked
flag (`-H`, `--jq`) is therefore *labelled* a PR merge, and both the forged and
the real `repos/<owner>/<name>/` path name the same granted repo, so a
first-label reading grants a direct push to the default branch.
Reported and reproduced on ai-config#1353.

So the guard runs the same ambiguity test on two axes --- **what kind** of
merge this is, and **which repository** it lands in --- and either one coming
back undetermined denies.

What the standing grant removes is the need to **ask**, not the judgment about
whether the PR is done.
[`ardi`](../../shared/workflow/ardi.md)'s loop still terminates by reporting the
PR ready, so the grant changes what happens at that moment and not what has to
be true before you get there.

Adding a repository to the grant is a one-line diff to
`STANDING_MERGE_GRANT_REPOS` in the hook.
It is deliberately not settable from the environment: `ALLOW_MERGE=1` already
covers the one-off case from inside the command text, and an env-settable
allowlist would widen a security guard from ambient state a reader of the
command cannot see.

### A bare `gh pr merge <N>` refuses, and the refusal may diagnose the wrong thing

The uncovered case named above as "a merge with no repo named in the command" closes with "so this costs nothing in practice".
That claim is about **design cost** --- requiring an explicit target adds no burden the corpus was not already imposing --- and it is correct.
What it does not say is what the *operator* sees, which is where the real cost lands.

With no session grant in play, both guards deny the bare form, with different messages, and the one surfaced is not necessarily the one that names the fix.
Measured 2026-08-17, feeding each hook the exact payload for fully-clean PR #1598:

| command | `require-gh-repo-flag.py` | `no-unauthorized-merge.py` |
| :--- | :--- | :--- |
| `gh pr merge 1598 --squash --delete-branch` | deny --- names the missing `-R`, gives the fix | deny --- names permission and `STANDING_MERGE_GRANT_REPOS` |
| `gh pr merge 1598 -R Morrison-Lab/ai-config --squash --delete-branch` | allow (has `-R`) | allow (exit 0) |

Nothing about the two commands differs except the explicit `-R`.

The session that hit this saw `no-unauthorized-merge.py`'s message, which talks about permission and the standing grant and says nothing about a missing flag.
So the natural readings are "the grant lapsed", "this PR does not qualify", or "the hook is broken" --- and each sends you somewhere useless: re-reading the grant, re-running `check-pr-fully-clean.py`, or inspecting the hook.
The fix is one flag.

Which of the two messages a session sees is harness behaviour rather than anything these hooks decide, so treat the observation above as one reading and not as a rule about ordering.
Either message is possible; only one of them is self-diagnosing.

It is worst exactly where it is most likely.
A session working *in* the ai-config checkout has the least reason to name the repo, because every other `gh` command in that directory infers it correctly --- so the habit that works everywhere else is the one that fails here.

- **Do:** write `-R Morrison-Lab/ai-config` into the merge command, since the grant attaches to the target named in the command text and to nothing else.
- **Do:** re-issue with `-R` as the first response to any merge refusal in a repo that carries a grant, before investigating anything.
- **Don't:** read the refusal as the grant not applying, the PR not qualifying, or the hook being broken --- the commonest cause is an underspecified command, and none of those three readings is checkable against it.
- **Don't:** infer the target from the working directory the way the rest of `gh` does; that is precisely the inference the guard refuses to make.

## Session Lock & Hook Integration

`no-unauthorized-merge.py` enforces the baseline merge prohibition at the `PreToolUse` hook level,
blocking `gh pr merge`, `glab mr merge`, `gh api .../merge`, and `glab api .../merge`.

When MWC is enabled for a session:
1. `ai-session.sh enable-mwc` creates a `<sanitized-session-id>.mwc` marker file
   in the repository's git common directory (`$(git rev-parse --git-common-dir)/ai-sessions/`).
2. `no-unauthorized-merge.py` checks for the active session's `.mwc` marker file
   and validates that the session is alive (`is_session_alive()`).
3. If an active `.mwc` marker exists for the current session, `no-unauthorized-merge.py` allows merge tool executions.
4. `ai-session.sh disable-mwc` removes the `.mwc` marker file, restoring the strict prohibition immediately.

**The session id has to match on both sides, and that is the part that breaks.**
The guard resolves which session it is running under from the hook payload's own
`session_id` field, then the transcript filename stem, then `AI_SESSION_ID` /
`CLAUDE_SESSION_ID`.
It used to read only the two environment variables, and the hook process inherits
neither, so a grant made the sanctioned way was invisible to it and every merge was
blocked no matter what the user had granted (ai-config#1279).
Pass the harness session id explicitly when granting, since the shell script has no
payload to read.

`check-mwc` distinguishes three outcomes rather than reporting one sentence for all
of them, because "never granted" and "granted but the session reads dead" want
opposite responses:

| Exit | Meaning | What to do |
| :--- | :--- | :--- |
| 0 | active | nothing; the guard will honour it |
| 1 | no grant recorded | `enable-mwc --id <id>` |
| 2 | granted, but not currently honourable | the message names which case and the fix |

It is a **query**: it never prunes and never deletes the marker, so a stale read
cannot silently revoke a grant, and a `heartbeat` restores one.
Use `disable-mwc`, `release`, or `prune` to actually remove a grant.

## Procedure for Agents Handling `/mwc`

When the user gives an MWC grant (e.g. `/mwc` or "merge when confident"):

1. **Run the enabling step first, and confirm it took.**
   `skills/session-lock/scripts/ai-session.sh enable-mwc --id "<session id>"`
   (or `~/.claude/skills/session-lock/scripts/ai-session.sh enable-mwc --id "<session id>"`)
   sets the session merge-permission flag `no-unauthorized-merge.py` reads.
   This step is what makes the grant real: without the `.mwc` marker it creates,
   `no-unauthorized-merge.py` cannot see the grant and correctly keeps blocking.
   **A grant acknowledged only in prose is not a grant the machinery can see**,
   so skipping this step leaves you believing you hold a permission that does not
   exist --- and then reading the resulting block as an obstacle rather than as
   the accurate answer it is.
   Only then acknowledge the grant in one sentence,
   so the user knows it's active for the session,
   and what it does and doesn't cover.
   Pass `--id` explicitly unless `AI_SESSION_ID` or `CLAUDE_SESSION_ID` is set in
   the shell: without one the script cannot resolve an id and dies with
   "no session id".
   Its value is the harness session id, which is the transcript filename stem.
   Then confirm with `check-mwc --id "<session id>"`,
   which exits 0 only when the guard will actually honour the grant.
   Do not skip that confirmation:
   an `enable-mwc` that reports success still leaves the guard blocking if the
   two sides resolved different ids, which is exactly what ai-config#1279 was.
2. Proceed with the task (e.g. driving PRs to clean via `ardi`).
3. When a PR reaches 100% clean state, merge it immediately
   (default: squash merge via `gh pr merge <number> --squash --delete-branch`),
   verify the merge landed on GitHub/GitLab,
   and run the post-merge skill (`post-merge` / `ums`).
4. If the user revokes the grant, run `skills/session-lock/scripts/ai-session.sh disable-mwc` immediately.

## What a re-grant does NOT mean

The grant is **conditional**, and the condition is the Scope Limit above.
Re-issuing a conditional permission does not make its condition true.
That distinction collapses in one specific situation, so it is worth naming
mechanically rather than trusting judgment in the moment:
a merge command is blocked, you ask whether to retry, and the user answers with
the keyword.

Read as an answer to "should I retry?", the keyword looks like "yes, merge that
PR."
It is not.
It re-states a standing, conditional policy, and the PR in front of you is
precisely the one that failed the condition --- otherwise nothing would have
blocked.
The framing of your own question is what makes the keyword look like an
instruction about one specific PR.

Three rules follow, and they hold whatever the block turned out to be:

- **A conditional grant re-issued in response to a blocked action is not
  authorization for that action.**
  Re-check the condition before acting, and say which specific PR you are
  claiming the grant for and why it qualifies --- naming it forces the check
  that the keyword bypassed.
- **A permission whose enforcement is mechanized has an enabling step.**
  Run it when the grant is given.
  If you did not, a block is evidence the grant is **not active** --- not an
  obstacle to retry.
- **Never retry a denied merge on the strength of a keyword.**
  The denial and the grant are about different things: one is a guard's state,
  the other is the user's intent, and only the guard's state gates the action.

## Four properties of the guard worth knowing before you trust it

**The denial you hit may not be this guard.**
`no-unauthorized-merge.py` is a `PreToolUse` hook, and a hook only runs if it is
**registered** --- which is a separate question from whether its file exists.
Claude Code's own auto-mode permission classifier blocks merge commands too, and
the two are independent mechanisms.
They differ in exactly the way that matters here: the hook reads a **marker
file**, so re-asking cannot move it, while the classifier reads the
**conversation**, so re-stating intent can.
So a denial that clears on a retry was, by that fact, probably not this guard.
Check registration rather than assuming, per `CLAUDE.md`'s
"Keep ai-config and repo checkouts fresh":

```bash
python3 <ai-config-checkout>/scripts/install-hooks.py   # report only; --fix binds
```

Measured on one machine, 2026-08-07: `registered=0 missing=15`, with
`enabledPlugins` unset in `~/.claude/settings.json` --- so every guard in
`hooks/hooks.json`, this one included, was placed but unbound.
The guard's own logic was fine: fed a `gh pr merge` payload directly it returned
`permissionDecision: deny`, and with a valid marker it allowed.
It simply never ran.

**The marker is per-repository, so a grant in one repo authorizes nothing in
another.**
`check_mwc_active()` looks for `<git-common-dir>/ai-sessions/<session>.mwc`,
resolved from the current working directory and `CLAUDE_PROJECT_DIR`.
Enabling MWC while working in repo A therefore leaves a merge in repo B blocked,
which is correct and easy to misread as the guard malfunctioning.
It also requires `AI_SESSION_ID` or `CLAUDE_SESSION_ID` to be set; with neither
set the function returns `False` and the guard denies even with a valid marker.
Run `check-mwc` from the repo you intend to merge in, not merely once per session.

**The grant does not expire, but its LIVENESS PROOF does, and a long session loses merge authority mid-session because of it.**
This is the property most likely to bite, because the two facts that produce it are individually reassuring.

The marker file is durable: `check-mwc` never prunes it, and the section above says a stale read "cannot silently revoke a grant".
Both true.
What neither says is that the guard consults **session liveness** as well as the marker, and liveness goes stale after **1800 seconds** without a `heartbeat`.
So a session that grants MWC, merges happily for twenty minutes, then works on something else for an hour, finds its next merge refused --- with the marker still sitting on disk exactly where it was written.

Measured 2026-08-22 on `Lacaedemon/sparta`.
The grant was made at 19:16 and four PRs merged between 19:17 and 19:20 without incident.
At 20:25 the fifth merge was refused, and `check-mwc` reported it precisely:

```
mwc is NOT active for session <id>: grant recorded, but the session reads unknown.
  Marker: <git-common-dir>/ai-sessions/<id>.mwc
  Last heartbeat 2026-08-22 19:16; a session goes stale after 1800s.
  If the session IS live:  ai-session.sh heartbeat --id '<id>'
```

One `heartbeat --id <id>` restored it and the merge went through unchanged.

The refusal is easy to misread, and every natural reading sends you somewhere useless.
It looks like the grant lapsing (it did not), like the PR failing the Scope Limit (it did not), or like the guard being broken (it is working exactly as designed).
The section on re-grants above is the relevant discipline here: a block is evidence the grant is not **active**, and the fix is to find out why rather than to retry.
`check-mwc` answers that question in one read and names the remedy in its own output, which is why it is worth running before diagnosing anything else.

- **Do:** run `check-mwc` first on any merge refusal in a session that has been running a while --- its message distinguishes "never granted" from "granted but stale".
- **Do:** `heartbeat` on a long session that will merge later, rather than waiting for the refusal.
- **Don't:** read a refusal after a successful earlier merge as the grant having been revoked --- nothing revoked it, and the marker is still there.
- **Don't:** re-run `enable-mwc` to fix this.
  It is not what is missing, and it obscures which of the two states you were in.

**Read `check-mwc`'s exit status from the script, not from the end of a pipe.**
Its three-way status (0 active, 1 no grant, 2 granted-but-not-honourable) is the whole point of the command.
Piping it through `tail` and echoing `$?` reports **`tail`'s** status instead, which is `0` whatever the script said.
That is how the stale grant above first read as "active" when the script had actually exited 2, and the misreading survived until the merge was refused a second time.

- **Do:** run the bare invocation and branch on `$?`, or redirect its output to a file and echo `$?` from the unpiped command.
- **Don't:** read `$?` after a pipe --- it belongs to the last stage, so every three-way status collapses to whatever `tail`, `head` or `grep` returned.

## Quick Reference

| Command | Effect |
| :--- | :--- |
| `skills/session-lock/scripts/ai-session.sh enable-mwc --id "<id>"` | Enables session-wide merge grant |
| `skills/session-lock/scripts/ai-session.sh disable-mwc --id "<id>"` | Revokes session-wide merge grant |
| `skills/session-lock/scripts/ai-session.sh check-mwc --id "<id>"` | Checks the grant, exiting 0 / 1 / 2 (see above) |

`--id` is optional only when `AI_SESSION_ID` or `CLAUDE_SESSION_ID` is set in the
shell, which in a Claude Code session it generally is not.
