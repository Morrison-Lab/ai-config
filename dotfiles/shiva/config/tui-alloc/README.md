# tui-alloc -- interactive agent sessions in a SLURM slice (shiva)

Personal launchers that run Claude Code / Codex inside a right-sized SLURM
allocation on shiva, instead of on the login node or a whole reserved node.

- `claude-alloc` -- Claude Code in a slice
- `codex-alloc`  -- Codex CLI in a slice
- `tui-alloc <cmd>` -- shared core both wrap

## Start a session

From the repo you want to work in:

```bash
cd ~/Projects/bcs-fix-nas     # a bcs checkout auto-selects the `bcs` conda env
claude-alloc                  # or: codex-alloc
```

This grabs a slice (defaults: 8 hwthreads / 32G / 48h, off GPU node c1), lands
you on the **compute node** via `srun --pty`, activates `$ALLOC_CONDA_ENV` if
set (a `~/.zshrc` chpwd hook sets it to `bcs` inside `~/Projects/bcs*`), and
launches the agent.

Resource overrides (env vars):

```bash
ALLOC_CPUS=16 ALLOC_MEM=64G ALLOC_TIME=72:00:00 claude-alloc
claude-alloc --exclude=c1,c3        # extra salloc flags pass straight through
ALLOC_CONDA_ENV=otherenv codex-alloc
```

## Exit a session -- close the agent FIRST, then the shell

The allocation is two layers deep:

```
salloc                    <- holds the slice (your cores/mem)
 └─ srun --pty … zsh -i    <- shell on the compute node
     └─ claude / codex     <- the agent
```

1. **Quit the agent.** Claude: `/exit` (or Ctrl-C twice / Ctrl-D).
   Codex: `/exit` (or Ctrl-D).
   You drop back to the allocation's shell -- the slice is **still held** here.
2. **`exit` the shell** (or Ctrl-D).
   This releases the slice.

Two exits, because there are two layers.
Closing only the agent leaves the slice reserved.

Force-release regardless of the agent:

```bash
scancel $SLURM_JOB_ID          # from inside the slice
squeue -u $USER                # from the login node: find job named claude/codex
scancel <jobid>                #   then cancel it
```

Check you didn't leave one running (easy to forget after closing a terminal):

```bash
squeue -u $USER                # look for job name `claude` or `codex`
```

If `--time` expires, SLURM kills the allocation from under you -- the agent and
shell die abruptly.
Relaunch and `claude --continue` / resume codex.

## When the cluster is full

If all schedulable cores are allocated (e.g. your own ETT/MSM validation arrays
are saturating c1-c4), a new `claude-alloc` will **PEND** until cores free -- and
if you have pending array tasks queued, freed cores go to *them* first.
Options: request fewer cores (`ALLOC_CPUS=2`), throttle the array with
`yield-array` (below), or do light work on the login node until the arrays wind
down.
Heavy validation runs go out as separate `sbatch` array jobs regardless -- the
slice is only for the interactive session.

## yield-array -- free a slot from your own array, temporarily

When your *own* array jobs are saturating the cluster, `yield-array` throttles
them so a running task or two drains and hands its cores back, launches the
session, then **restores the original throttle on exit**.

```bash
yield-array 138948                       # hold back 4 tasks, run claude-alloc, restore
yield-array -f 8 138948                  # hold back 8 (free more)
yield-array -t 50 138948 -- codex-alloc  # explicit throttle cap; run codex
yield-array -n 138948                    # dry run -- show the plan, change nothing
```

It validates you own the job and prints the before/after throttle.
**CAVEAT:** a hard kill (SIGKILL), walltime death, or dropped SSH won't run the
restore -- undo manually with
`scontrol update jobid=<id> ArrayTaskThrottle=<orig>` (0 = unlimited).
Throttling other jobs is a deliberate side effect, so it lives in its own named
command -- never hidden inside `claude-alloc`.

## Config

- Launchers: `~/bin/{tui,claude,codex}-alloc`; slot-freer: `~/bin/yield-array`
- Session rc: `~/.config/tui-alloc/.zshrc` (sources `~/.zshrc`, activates
  `$ALLOC_CONDA_ENV`, cd's back, runs the agent)
- Env auto-select: `chpwd` hook in `~/.zshrc`
