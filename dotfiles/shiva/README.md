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

## Slices hold resources until you release them

Both layers have to exit.
Quitting the agent returns you to a shell that still holds the slice, because
the agent is the last line of `config/tui-alloc/.zshrc`; only exiting that
shell releases the cores and memory.
Check for a forgotten one with `squeue -u $USER`, looking for a job named
`claude`, `codex`, or `cnode`.
