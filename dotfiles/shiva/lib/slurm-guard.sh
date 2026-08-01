#!/usr/bin/env bash
# refuse_if_nested -- stop a launcher from grabbing a second SLURM allocation
# when it is already running inside one.
#
# Sourced by both cnode and tui-alloc, which had (and needed) the same check:
# a fresh srun/salloc from inside an existing allocation contends with that
# allocation's own step rather than getting new resources. Measured on
# 2026-07-31 this deadlocked two jobs, one holding c1 while the other sat in
# PENDING (Resources). Better to refuse than to hang.
#
# Usage:
#   refuse_if_nested "<command the user should run instead>"
#
# Prints an explanation and exits 1 when nested; returns 0 otherwise, so the
# caller can carry on unconditionally.
#
# Holding an allocation and being ON a compute node are DIFFERENT states here,
# and conflating them is a real hazard rather than a pedantic distinction.
# cnode's own header records why: shiva has `LaunchParameters = (null)`, so
# salloc's use_interactive_step is off and a bare `salloc` sets SLURM_JOB_ID
# while leaving the shell on the login node. Only `srun --pty` moves you.
#
# So a shell that ran salloc and then invoked a launcher is inside a job and
# still on shiva. Refusing there is correct -- a nested srun would contend with
# that job's own step -- but advising the bare command would execute it ON THE
# LOGIN NODE, the single outcome these launchers exist to prevent. The two
# states need different advice, not one message that prints `uname -n` beside
# a claim it contradicts.

# on_compute_node -- true when this host is one SLURM schedules onto.
# sinfo lists the schedulable nodes, so membership answers the question
# whatever the environment says; a login node is absent from it.
on_compute_node() {
  local host
  command -v sinfo >/dev/null 2>&1 || return 1
  host="$(uname -n)"; host="${host%%.*}"
  sinfo -h -N -o %N 2>/dev/null | grep -qxF "$host"
}

refuse_if_nested() {
  local suggestion="$1" host step
  host="$(uname -n)"; host="${host%%.*}"

  if [ -n "${SLURM_JOB_ID:-}" ]; then
    if on_compute_node; then
      # Inside an allocation, on the node it gave us. The bare command is the
      # right advice: it runs on the compute node, which is the goal.
      printf '%s: already inside SLURM job %s on %s.\n' \
        "${0##*/}" "$SLURM_JOB_ID" "$host" >&2
      printf '       Nesting here contends with that allocation. Instead run:\n' >&2
      printf '           %s\n' "$suggestion" >&2
    else
      # The salloc case. Do NOT suggest the bare command; it would run here,
      # on the login node. Step into the existing allocation instead.
      step="${suggestion#exec }"
      printf '%s: holding SLURM job %s, but still on %s -- a login node.\n' \
        "${0##*/}" "$SLURM_JOB_ID" "$host" >&2
      printf '       salloc does not move you on this cluster; only srun --pty does.\n' >&2
      printf '       Do not run the command here. Step into the allocation:\n' >&2
      printf '           srun --jobid=%s --pty %s\n' "$SLURM_JOB_ID" "$step" >&2
    fi
    exit 1
  fi

  # A compute-node shell with no SLURM_JOB_ID -- e.g. one reached by ssh
  # rather than by srun.
  if on_compute_node; then
    printf '%s: already on compute node %s.\n' "${0##*/}" "$host" >&2
    printf '       Nesting here contends for that node. Instead run:\n' >&2
    printf '           %s\n' "$suggestion" >&2
    exit 1
  fi

  return 0
}
