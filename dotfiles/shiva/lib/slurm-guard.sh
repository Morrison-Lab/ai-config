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

refuse_if_nested() {
  local suggestion="$1" host

  # Being inside an allocation is the condition that actually matters, and
  # SLURM states it directly -- no external command, and correct even on a
  # login node that is also schedulable.
  if [ -n "${SLURM_JOB_ID:-}" ]; then
    printf '%s: already inside SLURM job %s on %s.\n' \
      "${0##*/}" "$SLURM_JOB_ID" "$(uname -n)" >&2
    printf '       Nesting here contends with that allocation. Instead run:\n' >&2
    printf '           %s\n' "$suggestion" >&2
    exit 1
  fi

  # Fallback for a shell on a compute node with no SLURM_JOB_ID -- e.g. one
  # reached by ssh rather than by srun. sinfo lists the schedulable nodes, so
  # membership means this is a compute node whatever the environment says.
  if command -v sinfo >/dev/null 2>&1; then
    host="$(uname -n)"; host="${host%%.*}"
    if sinfo -h -N -o %N 2>/dev/null | grep -qxF "$host"; then
      printf '%s: already on compute node %s.\n' "${0##*/}" "$host" >&2
      printf '       Nesting here contends for that node. Instead run:\n' >&2
      printf '           %s\n' "$suggestion" >&2
      exit 1
    fi
  fi

  return 0
}
