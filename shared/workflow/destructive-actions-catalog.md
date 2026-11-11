# Catalog of destructive agent actions, and the guard for each

Ezra, 2026-11-11, after a session nearly deleted `lds` branches it had misread from a shallow clone: "search online for common failure patterns and build guards against them, VERY CAREFULLY" ([ai-config#5317](https://github.com/Morrison-Lab/ai-config/issues/5317)).
This fragment lists the reported ways coding agents have destroyed data, with a source for each, and names the ai-config hook that covers each one.
A "none" in the guard column marks a gap that #5317 tracks.

## Test a guard only where it cannot do damage

Ezra, 2026-11-11: "use test repos to test everything" and "go very slowly and carefully, even on test repos".

- **Do:** test a destructive-command guard by feeding its hook a JSON payload, or inside a throwaway repository made with `mktemp -d` for that test.
  Check each result before running the next case.
- **Don't:** run a destructive command in a real checkout, a home directory or a shared mount, even one you expect a hook to refuse.
  A guard that fails open lets the test itself do the damage.

## Reported failure patterns

Bare issue numbers below are in [`anthropics/claude-code`](https://github.com/anthropics/claude-code/issues).
Each of those issues and the Docker post was read on 2026-11-11;
a row says so where its source was not.

| Pattern | Reported incident | ai-config guard (2026-11-11) |
| --- | --- | --- |
| `rm -rf` with a stray home target | `rm -rf tests/ patches/ plan/ ~/` wiped a Mac home directory ([Docker, 2026-06-01](https://www.docker.com/blog/coding-agent-horror-stories-the-rm-rf-incident/)) | none |
| `rm -rf "$VAR"` where the variable was set in an earlier Bash call | `rm -rf "$HOME"` ran against the real home directory after a temporary `$HOME` did not persist between tool calls ([#75859](https://github.com/anthropics/claude-code/issues/75859)) | none |
| `git reset --hard` over uncommitted work | [#7232](https://github.com/anthropics/claude-code/issues/7232), [#17190](https://github.com/anthropics/claude-code/issues/17190), [#33850](https://github.com/anthropics/claude-code/issues/33850), and twice at session start in [#34327](https://github.com/anthropics/claude-code/issues/34327) | `flag-reset-hard-uncommitted-work.py` (warns) |
| `git checkout -- .` or `git restore <path>` over uncommitted work | `git checkout HEAD -- .` ([#11821](https://github.com/anthropics/claude-code/issues/11821)); `git restore lib/` across 40 files ([#43591](https://github.com/anthropics/claude-code/issues/43591)) | `flag-reset-hard-uncommitted-work.py` (warns) |
| `git clean -fd` deleting untracked or ignored files | [#45974](https://github.com/anthropics/claude-code/issues/45974); after `git rm -rf .` on a new orphan branch ([#29179](https://github.com/anthropics/claude-code/issues/29179)) | none outside render intermediates (`no-rm-live-render-intermediate.py`) |
| Concurrent sessions resetting, stashing or cleaning one shared worktree | [#53819](https://github.com/anthropics/claude-code/issues/53819) | none; the worktree-isolation rule in `AGENTS.md` is prose |
| Plain `--force` push after `--force-with-lease` was refused | [#70378](https://github.com/anthropics/claude-code/issues/70378) | `no-clobbering-push.py` (denies a bare force push) |
| Force push to a branch with an open PR | `git reset --hard HEAD~1` then `--force-with-lease` ([#85450](https://github.com/anthropics/claude-code/issues/85450)) | `no-clobbering-push.py` warns when the remote tip has diverged, without checking for an open PR |
| Branch deleted with unmerged commits | worktree cleanup deleted the branch ([#38287](https://github.com/anthropics/claude-code/issues/38287)); branches misread from a shallow clone (`lds`, 2026-11-11) | none; a shallow-clone guard is in progress in another thread, and `no-delete-branch-under-stacked-pr.py` covers only a stacked PR's base deleted on merge |
| Worktree force-removed with uncommitted work | blanket `git worktree remove --force` fallback (ai-config, 2026-09-10) | `warn-blanket-worktree-force-remove.py` (warns) |
| Gitignored render intermediate deleted under a live render | ai-config, 2026-09-24 | `no-rm-live-render-intermediate.py` (denies) |
| Live config deleted as "orphaned" | [ai-config#3096](https://github.com/Morrison-Lab/ai-config/issues/3096) | `flag-config-deletion-without-ref-check.py` warns at `Stop` on a reply that recommends the deletion; nothing intercepts the command |
| `chown -R` or `chmod -R` on system directories | `sudo chown -R $USER:$(id -gn) /usr && sudo chmod -R u+w /usr` broke `sudo` ([#168](https://github.com/anthropics/claude-code/issues/168)); a background agent with `sudo` left `/etc` owned by UID 100000, then ran `chown -R root:root /usr/` and `/etc/` as a repair, clearing setuid bits on `sudo` and `su` ([#39283](https://github.com/anthropics/claude-code/issues/39283)) | none |
| Moving files into a directory that a failed `mkdir` never made | Gemini CLI, July 2025, per [Ars Technica](https://arstechnica.com/information-technology/2025/07/ai-coding-assistants-chase-phantoms-destroy-real-user-data/) (not read: the host refused this session's fetch) | none; the rule below is prose |
| Production database or infrastructure destroyed | a Replit agent deleted a production database during a code freeze, July 2025; `terraform destroy` ran against a stale state file, February 2026 ([Alexey Grigorev](https://alexeyondata.substack.com/p/how-i-dropped-our-production-database)); neither source was reachable from this session | none; the lab runs no production database |

## Rules for the patterns no hook decides yet

- **Do:** run `git stash push --include-untracked` before any command that discards working-tree state in a worktree only you use, and say so.
  A stash can be recovered and a reset cannot.
  A stash leaves ignored files behind, so read `git clean -n -x` before any `git clean -x`.
- **Do:** leave changes you do not recognize as your own in place, and tell the user what they are.
  Another session may be working in this worktree, and stashing its changes breaks it as surely as a reset.
- **Don't:** reach for `reset --hard`, `checkout -- .`, `restore`, `stash` or `clean -f` to clear changes you did not make, whether `git diff` or `git status` shows them.
- **Do:** print the absolute path an `rm -rf` would delete in one Bash call, read it, and stop if it is `/`, the home directory or a repository root.
  Then run the `rm -rf` in a later call, on that literal path.
- **Do:** when a deletion path must use a variable, as in a loop or a script, guard it with `${VAR:?}`, which stops the command when the variable is unset or empty.
  It cannot stop a variable that falls back to a real value.
  `$HOME` in a fresh shell is the real home directory ([#75859](https://github.com/anthropics/claude-code/issues/75859)).
- **Don't:** use a variable in a deletion path that an earlier Bash call set.
  Each call starts a fresh shell.
- **Do:** check that a directory exists after creating it, before moving anything into it.
- **Don't:** answer a refused `--force-with-lease` with a plain `--force`.
  Read the remote branch first ([`check-before-pushing`](check-before-pushing.md)).
- **Do:** fix a permission error on the one path that raised it, as your own user.
- **Don't:** run `chown -R` or `chmod -R` on `/`, `/usr`, `/etc`, a home directory or anything mounted into a container, with or without `sudo`.
- **Do:** treat any command that touches a production database, a cloud account or infrastructure state as needing Ezra's own words naming that action.
- **Don't:** run `terraform destroy`, a database drop or a schema reset that a person did not ask for by name.
