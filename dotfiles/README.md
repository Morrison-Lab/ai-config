# dotfiles

Machine-specific shell tooling, tracked here so it survives the machine.

This is not consumable agent config: nothing under `dotfiles/` is symlinked
into `~/.claude`, and `bootstrap.sh` skips it in the loop that links the
top-level directories.
Each subdirectory is one machine or cluster, and owns an `install.sh` that
puts its files where that machine expects them.

| Directory | Machine | Installs into |
| --- | --- | --- |
| [`shiva/`](shiva/) | UCD PHS HPC login and compute nodes | `~/bin`, `~/.local/bin`, `~/.config/tui-alloc` |

## Why these live here rather than in a project repo

They are personal and machine-specific, so they don't belong in a shared
project repo where collaborators would inherit tooling they can't run.
ai-config is already the home for machine-specific agent configuration, and
`memories/tools.md` already documents this tooling's behavior.
Documenting behavior is not a backup, though.
Until these were tracked, the scripts existed in exactly one place, on one
cluster filesystem, with no history.

## Adding a machine

Create `dotfiles/<name>/` with an `install.sh` that:

- **Gates on the machine.**
  `bootstrap.sh` runs every installer it finds, so an installer that can't
  identify its own host will fire on a laptop or a web container.
  Detect by something stable from every node, not by hostname --- a shiva
  session launched by `claude-alloc` runs on a compute node, so `uname -n`
  reports `c2` rather than the login node.
- **Never clobbers.**
  Source `scripts/lib/link-one.sh` and use `link_one`, the same helper
  `bootstrap.sh` uses, so a real file already at the destination is reported
  rather than overwritten.
- **Prints what it skipped and why.**
  A silent installer is indistinguishable from one that didn't run.
