# shiva dotfiles

Personal launchers for the UCD PHS HPC cluster (`ClusterName = shiva`),
tracked so they survive the machine.
`memories/tools.md` documents how to *use* them; this directory is the source
of truth for what they *are*.

## Contents

| Tracked path | Installs to | What it is |
| --- | --- | --- |
| `bin/tui-alloc` | `~/bin/tui-alloc` | the core: `salloc` plus an `srun --pty` step, with a node-side zsh guard |
| `bin/claude-alloc` | `~/bin/claude-alloc` | three-line wrapper: `tui-alloc claude` |
| `bin/codex-alloc` | `~/bin/codex-alloc` | three-line wrapper: `tui-alloc codex` |
| `bin/yield-array` | `~/bin/yield-array` | temporarily throttles your own array jobs to free a slot, then restores |
| `local-bin/cnode` | `~/.local/bin/cnode` | a plain interactive zsh on a compute node, no agent |
| `local-bin/encrypt-gh-token.sh` | `~/.local/bin/encrypt-gh-token.sh` | writes the GPG-encrypted `~/.gh-token.gpg` from `gh`'s hosts file |
| `config/tui-alloc/.zshrc` | `~/.config/tui-alloc/.zshrc` | the session rc `tui-alloc` points `ZDOTDIR` at; sources `~/.zshrc`, activates the env, launches the agent |
| `config/tui-alloc/README.md` | `~/.config/tui-alloc/README.md` | the user-facing usage and exit doc |
| `zshrc-fragment.zsh` | sourced from `~/.zshrc` | puts `~/bin` on PATH, installs the `ALLOC_CONDA_ENV` chpwd hook |
| `lib/slurm-guard.sh` | not installed | `refuse_if_nested`, shared by `tui-alloc` and `cnode`; sourced through the install symlink |
| `lib/test-slurm-guard.sh` | not installed | tests for `refuse_if_nested`; stubs `sinfo`/`uname` to cover all four node/job states |

## Install

`bootstrap.sh` calls `install.sh` automatically, and it is safe to run
directly:

```bash
dotfiles/shiva/install.sh -n        # dry run: show the plan
dotfiles/shiva/install.sh           # link whatever isn't already there
dotfiles/shiva/install.sh --adopt   # also replace identical real files with links
```

`--adopt` exists for the first run on a machine where these files already sit
on disk as real, unlinked copies, which is how they got into the repo.
It only fires when `cmp` says the destination is byte-identical to the tracked
copy, so nothing can be lost; a file that differs is reported with the `diff`
command to inspect it, and left alone.

The installer never edits `~/.zshrc`.
It reports whether the fragment is sourced and prints the line to add.

## What is deliberately not tracked

- **`~/.zshrc`** --- personal, and it carries credential helpers.
  Only the two launcher-critical pieces are extracted, into
  `zshrc-fragment.zsh`.
- **`~/.config/tui-alloc/.zcompdump-c*-5.9`** and their `.zwc` companions ---
  generated per-node zsh completion caches, 60-135KB each.
  Cache, not config.
- **Third-party binaries in `~/.local/bin`** (`claude`, `codex`, `duckdb`,
  `bwrap`, `github-mcp-server*`, `pdf*`) --- installed, not authored here.
- **`~/.gh-token.gpg`** --- the encrypted credential itself.
  `encrypt-gh-token.sh` is the script that writes it and holds no secret of
  its own.

## Host detection

`install.sh` gates on SLURM's `ClusterName`, not on the hostname.
A session launched by `claude-alloc` or `cnode` runs on a compute node, so
`uname -n` reports `c2`, `c3`, or `c4` rather than the login node, while
`scontrol show config` reads the same from either.
Set `AI_CONFIG_DOTFILES_FORCE=1` to install on a machine that fails the gate.

## Both launchers refuse to nest

`refuse_if_nested` exits rather than grabbing a second allocation from inside
an existing one, because a nested `srun`/`salloc` contends with its parent
allocation's own step instead of getting new resources.

It distinguishes two states that are easy to conflate, because on shiva they
come apart.
Holding an allocation is not the same as being on a compute node: with
`LaunchParameters = (null)`, a bare `salloc` sets `$SLURM_JOB_ID` and leaves
the shell on the login node, and only `srun --pty` moves you.
Both states refuse, and the **advice differs**.
On a compute node it tells you to run the command directly, which is the goal.
On the login node it must not, since that would execute the command there ---
the one outcome these launchers exist to prevent --- so it points at
`srun --jobid=<id> --pty <cmd>` instead.
`sinfo`'s node list decides which state you are in, and also catches a compute
node reached without a job id, such as by `ssh`.

`lib/test-slurm-guard.sh` covers all four combinations with a stubbed `sinfo`
and `uname`.
The salloc case is the regression it exists for: run against the previous
guard, it reports `already inside SLURM job 4242 on shiva` --- the login
hostname, beside a claim it contradicts --- and advises the bare command.

## Slices hold resources until you release them

Both layers have to exit.
Quitting the agent returns you to a shell that still holds the slice, because
the agent is the last line of `config/tui-alloc/.zshrc`; only exiting that
shell releases the cores and memory.
Check for a forgotten one with `squeue -u $USER`, looking for a job named
`claude`, `codex`, or `cnode`.
