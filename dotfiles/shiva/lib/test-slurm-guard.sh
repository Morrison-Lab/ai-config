#!/usr/bin/env bash
# Tests for refuse_if_nested.
#
# The case that motivated them is the salloc one: on shiva `LaunchParameters =
# (null)`, so `salloc` sets SLURM_JOB_ID and leaves the shell on the login
# node. A guard keyed on SLURM_JOB_ID alone refuses there AND advises the bare
# command, which would then run on the login node -- the outcome these
# launchers exist to prevent.
#
# sinfo is stubbed rather than mocked away, so on_compute_node runs its real
# logic against a known node list.
#
# Run:  bash dotfiles/shiva/lib/test-slurm-guard.sh
set -uo pipefail

GUARD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/slurm-guard.sh"
STUB="$(mktemp -d)"
trap 'rm -rf "$STUB"' EXIT

# sinfo reports c2 and c3 as schedulable; the login node is absent, as on shiva.
cat > "$STUB/sinfo" <<'SINFO'
#!/usr/bin/env bash
printf 'c2\nc3\n'
SINFO
chmod +x "$STUB/sinfo"

cat > "$STUB/uname" <<'UNAME'
#!/usr/bin/env bash
printf '%s\n' "${FAKE_HOST:-shiva}"
UNAME
chmod +x "$STUB/uname"

# run <host> <job_id> -- returns "rc|stderr"
run() {
  local host="$1" job="$2" out rc
  out="$(
    PATH="$STUB:$PATH" FAKE_HOST="$host" \
    env $( [ -n "$job" ] && echo "SLURM_JOB_ID=$job" ) \
      bash -c '. "$1"; refuse_if_nested "exec ~/miniconda3/bin/zsh -i"' _ "$GUARD" 2>&1
  )"; rc=$?
  printf '%s|%s' "$rc" "$out"
}

fail=0
check() {
  local name="$1" got="$2" want_rc="$3" want_sub="$4" rc="${2%%|*}" body="${2#*|}"
  if [ "$rc" != "$want_rc" ]; then
    printf 'FAIL  %s: exit %s, wanted %s\n' "$name" "$rc" "$want_rc"; fail=1; return
  fi
  if [ -n "$want_sub" ] && ! grep -qF -- "$want_sub" <<< "$body"; then
    printf 'FAIL  %s: output lacks %s\n      got: %s\n' "$name" "$want_sub" "$body"; fail=1; return
  fi
  printf 'ok    %s\n' "$name"
}

# 1. Clean login-node shell, no allocation: proceed.
check "login node, no job -> proceeds" "$(run shiva '')" 0 ""

# 2. THE REGRESSION. salloc set SLURM_JOB_ID but the shell is still on shiva.
#    Must refuse, must NOT advise the bare command, must advise srun --jobid.
got="$(run shiva 4242)"
check "salloc on login node -> refuses" "$got" 1 "login node"
check "salloc on login node -> advises srun --jobid" "$got" 1 "srun --jobid=4242 --pty"
if grep -qE '^ +exec ~/miniconda3/bin/zsh -i$' <<< "${got#*|}"; then
  printf 'FAIL  salloc on login node: advised the bare command, which runs HERE\n'; fail=1
else
  printf 'ok    salloc on login node: does not advise the bare command\n'
fi

# 3. Inside an allocation, actually on a compute node: bare command is right.
got="$(run c2 4242)"
check "on compute node with job -> refuses" "$got" 1 "already inside SLURM job 4242 on c2"
check "on compute node with job -> advises the bare command" "$got" 1 "exec ~/miniconda3/bin/zsh -i"

# 4. Compute node reached without SLURM_JOB_ID (e.g. ssh): still refuse.
check "compute node, no job -> refuses" "$(run c3 '')" 1 "already on compute node c3"

[ "$fail" = 0 ] && printf '\nall tests passed\n' || printf '\nFAILURES\n'
exit "$fail"
