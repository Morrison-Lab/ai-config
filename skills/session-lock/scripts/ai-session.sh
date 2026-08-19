#!/usr/bin/env bash
#
# ai-session.sh — deconflict multiple AI agent sessions sharing one local repo.
#
# When several Claude Code / Copilot / other agent sessions work the *same*
# local checkout at once they clobber each other: one `git checkout`s a branch
# out from under another's uncommitted edits, two push to the same branch, two
# run the same expensive render. This maintains a machine-local registry of
# active sessions so they can see each other, refuse to collide, and recover
# after a crash.
#
# The registry lives under the repo's shared git *common* dir:
#     $(git rev-parse --git-common-dir)/ai-sessions/
# which is the right home because it is:
#   - machine-local  — git never tracks anything under .git/, so it is never
#                      committed or pushed (no cross-machine leakage);
#   - repo-scoped    — one registry per repo;
#   - worktree-wide  — every `git worktree` of the repo shares the common dir,
#                      so sessions in different worktrees still see each other.
#
# No daemon and no flock: each session owns exactly one file, written
# temp-then-rename (atomic on one filesystem), and readers tolerate races.
# Liveness is judged by (1) a dead PID on the same host, then (2) heartbeat age.
#
# Usage:
#   ai-session.sh register  [--id ID] [--task TEXT] [--agent NAME]
#   ai-session.sh heartbeat [--id ID]                # refresh liveness + branch
#   ai-session.sh check     [--id ID]                # exit !=0 if work here collides
#   ai-session.sh list      [--all]                  # show live (or --all) sessions
#   ai-session.sh release   [--id ID]                # drop this session's record
#   ai-session.sh prune                              # drop stale records
#   ai-session.sh worktree  BRANCH [--base REF]      # isolate: new worktree + branch
#   ai-session.sh enable-mwc  [--id ID]              # enable merge-when-confident permission
#   ai-session.sh disable-mwc [--id ID]              # revoke merge-when-confident permission
#   ai-session.sh check-mwc   [--id ID]              # check if MWC permission is active
#
# Identity (--id) resolves: --id flag > $AI_SESSION_ID > $CLAUDE_SESSION_ID.
# Stale threshold: $AI_SESSION_STALE_SECONDS (default 1800 = 30 min).
# Worktree parent: $AI_WORKTREE_DIR (default "<repo-toplevel>.worktrees").

set -euo pipefail

STALE_SECONDS="${AI_SESSION_STALE_SECONDS:-1800}"

die() { printf 'ai-session: %s\n' "$*" >&2; exit 1; }

# --- locate the registry (shared across all worktrees of this repo) ----------
git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"
COMMON_DIR="$(git rev-parse --git-common-dir)"
# --git-common-dir may be relative to CWD; make it absolute.
COMMON_DIR="$(cd "$COMMON_DIR" && pwd)"
REG_DIR="$COMMON_DIR/ai-sessions"
mkdir -p "$REG_DIR"

TOPLEVEL="$(git rev-parse --show-toplevel)"
HOST="$(hostname 2>/dev/null || echo unknown)"
NOW="$(date +%s)"

# Current branch, or "(detached:<sha>)" when not on a branch.
current_branch() {
  git symbolic-ref --quiet --short HEAD 2>/dev/null \
    || printf '(detached:%s)' "$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
}

# Sanitize an arbitrary string into a filename-safe token.
sanitize() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'; }

# Best-effort: walk the process-ancestor chain to find the long-lived `claude`
# process, whose PID is a reliable liveness signal on this host. Empty if not
# found (e.g. a different agent or an unusual launcher) — liveness then falls
# back to heartbeat age.
find_agent_pid() {
  local pid=$$ comm i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    pid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')" || return 1
    [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null || return 1
    comm="$(ps -o comm= -p "$pid" 2>/dev/null || true)"
    case "$comm" in *[Cc]laude*) printf '%s' "$pid"; return 0;; esac
  done
  return 1
}

# Resolve session id from flag, then env, then single live session in registry.
resolve_id() {
  if [ -n "${OPT_ID:-}" ]; then printf '%s' "$OPT_ID"; return; fi
  if [ -n "${AI_SESSION_ID:-}" ]; then printf '%s' "$AI_SESSION_ID"; return; fi
  if [ -n "${CLAUDE_SESSION_ID:-}" ]; then printf '%s' "$CLAUDE_SESSION_ID"; return; fi
  local live_ids=() f
  shopt -s nullglob
  for f in "$REG_DIR"/*.session; do
    load_session "$f"
    if [ "$S_host" = "$HOST" ] && ! is_stale; then
      live_ids+=("$S_id")
    fi
  done
  shopt -u nullglob
  if [ "${#live_ids[@]}" -eq 1 ]; then
    printf '%s' "${live_ids[0]}"
    return 0
  fi
  return 1
}

session_file() { printf '%s/%s.session' "$REG_DIR" "$(sanitize "$1")"; }

# The merge-when-confident grant marker for a session. Composed in ONE place
# because two readers must agree on it exactly: this script and
# hooks/no-unauthorized-merge.py. A marker written at one path and looked for at
# another is indistinguishable from no grant at all -- the failure ai-config#1279
# reported, where a grant read active one way and inactive another.
mwc_file() { printf '%s/%s.mwc' "$REG_DIR" "$(sanitize "$1")"; }

# Load a session file into S_* globals (bash 3.2 compatible — no assoc arrays).
load_session() {
  S_id=; S_agent=; S_host=; S_pid=; S_worktree=; S_branch=
  S_started=; S_heartbeat=; S_status=; S_task=
  local k v
  while IFS='=' read -r k v; do
    # Strip a trailing CR so a record that reached the registry with CRLF line
    # endings still parses. Without it `heartbeat=<n>\r` reaches is_stale's
    # `$(( NOW - ... ))` and raises "invalid arithmetic operator", which under
    # `set -e` kills the whole command mid-check -- so check-mwc exited 1, the
    # code meaning "no grant recorded", for a grant that was sitting right
    # there. A crash must not be reported as an absent grant.
    v="${v%$'\r'}"
    case "$k" in
      id) S_id=$v ;; agent) S_agent=$v ;; host) S_host=$v ;; pid) S_pid=$v ;;
      worktree) S_worktree=$v ;; branch) S_branch=$v ;; started) S_started=$v ;;
      heartbeat) S_heartbeat=$v ;; status) S_status=$v ;; task) S_task=$v ;;
    esac
  done < "$1"
}

# Liveness for the currently-loaded S_* session. Echoes: alive | dead | unknown.
session_liveness() {
  if [ "$S_host" = "$HOST" ] && [ -n "$S_pid" ]; then
    if kill -0 "$S_pid" 2>/dev/null; then echo alive; else echo dead; fi
  else
    echo unknown
  fi
}

# Is the loaded S_* session stale (crashed / abandoned)?
is_stale() {
  case "$(session_liveness)" in
    dead)  return 0 ;;                       # process gone on this host
    alive) return 1 ;;                       # process still running — trust it
    unknown)                                 # cross-host / no pid — use heartbeat
      local age=$(( NOW - ${S_heartbeat:-0} ))
      [ "$age" -gt "$STALE_SECONDS" ] && return 0 || return 1 ;;
  esac
}

fmt_epoch() { # epoch -> human, GNU then BSD date, else raw
  date -d "@$1" '+%Y-%m-%d %H:%M' 2>/dev/null \
    || date -r "$1" '+%Y-%m-%d %H:%M' 2>/dev/null \
    || printf '%s' "$1"
}

# Drop every stale record. Prints what it removed.
prune_stale() {
  local f removed=0
  for f in "$REG_DIR"/*.session; do
    [ -e "$f" ] || continue
    load_session "$f"
    if is_stale; then
      rm -f "$f" "$(mwc_file "$S_id")"
      printf 'pruned stale session %s (%s on %s)\n' "$S_id" "${S_branch:-?}" "${S_host:-?}"
      removed=$((removed + 1))
    fi
  done
  # Sweep orphaned .mwc files whose session file is gone
  for f in "$REG_DIR"/*.mwc; do
    [ -e "$f" ] || continue
    local sid; sid="$(basename "$f" .mwc)"
    [ -f "$REG_DIR/$sid.session" ] || rm -f "$f"
  done
  # Belt-and-suspenders: sweep temp files orphaned by a SIGKILL (where the EXIT
  # trap in write_record can't fire). Only old ones, never a write in flight.
  find "$REG_DIR" -maxdepth 1 -name '.tmp.*' -type f -mmin +60 -delete 2>/dev/null || true
  [ "$removed" -eq 0 ] && printf 'no stale sessions\n'
  return 0
}

write_record() { # id task agent
  local id="$1" task="$2" agent="$3" pid started tmp
  pid="$(find_agent_pid || true)"
  local existing; existing="$(session_file "$id")"
  if [ -f "$existing" ]; then
    load_session "$existing"; started="${S_started:-$NOW}"
    [ -z "$task" ]  && task="$S_task"
    [ -z "$agent" ] && agent="$S_agent"
  else
    started="$NOW"
  fi
  tmp="$(mktemp "$REG_DIR/.tmp.XXXXXX")"
  trap 'rm -f "${tmp:-}"' EXIT     # don't leak the temp file if killed before the rename
  {
    printf 'id=%s\n'        "$id"
    printf 'agent=%s\n'     "${agent:-unknown-agent}"
    printf 'host=%s\n'      "$HOST"
    printf 'pid=%s\n'       "${pid:-}"
    printf 'worktree=%s\n'  "$TOPLEVEL"
    printf 'branch=%s\n'    "$(current_branch)"
    printf 'started=%s\n'   "$started"
    printf 'heartbeat=%s\n' "$NOW"
    printf 'status=%s\n'    "active"
    printf 'task=%s\n'      "$task"
  } > "$tmp"
  mv -f "$tmp" "$existing"     # atomic on the same filesystem
  trap - EXIT
}

# Dashboard view: report any worktree or branch held by >=2 live sessions —
# true contention anywhere in the repo, independent of who is asking.
summarize_contention() {
  local f n=0 i j k members count seen printed=0
  local WT=() BR=() ID=() TK=() HS=()        # parallel indexed arrays
  for f in "$REG_DIR"/*.session; do
    [ -e "$f" ] || continue
    load_session "$f"; is_stale && continue
    WT[$n]="$S_worktree"; BR[$n]="${S_branch:-?}"; ID[$n]="$S_id"
    TK[$n]="${S_task:-}"; HS[$n]="${S_host:-?}"; n=$((n + 1))
  done
  # Worktree contention (the dangerous one: shared uncommitted edits).
  seen=" "
  for ((i = 0; i < n; i++)); do
    case "$seen" in *" $i "*) continue;; esac
    members="$i" count=1
    for ((j = i + 1; j < n; j++)); do
      [ "${WT[$j]}" = "${WT[$i]}" ] && { members="$members $j"; count=$((count + 1)); seen="$seen$j "; }
    done
    if [ "$count" -ge 2 ]; then
      [ "$printed" -eq 0 ] && { printf '\nCONTENTION:\n'; printed=1; }
      printf '⚠️  SAME WORKING TREE %s — %d live sessions; uncommitted edits/branch switches WILL collide:\n' "${WT[$i]}" "$count"
      for k in $members; do printf '    %s  [%s]  %s\n' "${ID[$k]}" "${BR[$k]}" "${TK[$k]}"; done
      printf '    Isolate the extras with:  ai-session.sh worktree <branch>   then cd into it.\n'
    fi
  done
  # Branch contention across distinct worktrees (push races).
  seen=" "
  for ((i = 0; i < n; i++)); do
    case "$seen" in *" $i "*) continue;; esac
    members="$i" count=1
    for ((j = i + 1; j < n; j++)); do
      if [ "${BR[$j]}" = "${BR[$i]}" ] && [ "${WT[$j]}" != "${WT[$i]}" ]; then
        members="$members $j"; count=$((count + 1)); seen="$seen$j "
      fi
    done
    if [ "$count" -ge 2 ]; then
      [ "$printed" -eq 0 ] && { printf '\nCONTENTION:\n'; printed=1; }
      printf '⚠️  SAME BRANCH %s — %d live sessions in different worktrees; pushes may race:\n' "${BR[$i]}" "$count"
      for k in $members; do printf '    %s  on %s  %s\n' "${ID[$k]}" "${HS[$k]}" "${TK[$k]}"; done
    fi
  done
  return 0
}

# Collect conflicts with the (resolved) current session. Sets globals
# WT_CONFLICTS / BR_CONFLICTS to newline-separated "id\tbranch\ttask" lines.
gather_conflicts() {
  local me="${1:-}" f live
  WT_CONFLICTS=""; BR_CONFLICTS=""
  local my_branch; my_branch="$(current_branch)"
  for f in "$REG_DIR"/*.session; do
    [ -e "$f" ] || continue
    load_session "$f"
    [ -n "$me" ] && [ "$S_id" = "$me" ] && continue   # skip self
    is_stale && continue                              # skip dead
    live="$S_id	${S_branch:-?}	${S_task:-}	${S_host:-?}"
    if [ "$S_worktree" = "$TOPLEVEL" ]; then
      WT_CONFLICTS="${WT_CONFLICTS}${live}"$'\n'
    elif [ "$S_branch" = "$my_branch" ]; then
      BR_CONFLICTS="${BR_CONFLICTS}${live}"$'\n'
    fi
  done
}

# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------
cmd_register() {
  local id; id="$(resolve_id)" || die "no session id (pass --id, or set \$AI_SESSION_ID / \$CLAUDE_SESSION_ID)"
  prune_stale >/dev/null
  write_record "$id" "${OPT_TASK:-}" "${OPT_AGENT:-}"
  printf 'registered session %s on branch %s (worktree %s)\n' "$id" "$(current_branch)" "$TOPLEVEL"
  # Surface any collision immediately so the agent knows to isolate.
  gather_conflicts "$id"
  if [ -n "$WT_CONFLICTS" ] || [ -n "$BR_CONFLICTS" ]; then
    printf '\n'; report_conflicts
  fi
}

cmd_heartbeat() {
  local id; id="$(resolve_id)" || die "no session id (pass --id, or set \$AI_SESSION_ID / \$CLAUDE_SESSION_ID)"
  [ -f "$(session_file "$id")" ] || die "session $id is not registered; run 'register' first"
  write_record "$id" "" ""
  printf 'heartbeat %s @ %s\n' "$id" "$(fmt_epoch "$NOW")"
}

report_conflicts() {
  local line
  if [ -n "$WT_CONFLICTS" ]; then
    printf '⚠️  SAME WORKING TREE — another live session is editing this exact checkout:\n'
    printf '%s' "$WT_CONFLICTS" | while IFS=$'\t' read -r id br task host; do
      [ -n "$id" ] && printf '    %s  [%s]  %s\n' "$id" "$br" "$task"
    done
    printf '    Uncommitted edits and branch switches WILL collide.\n'
    printf '    Isolate with:  ai-session.sh worktree <your-branch>   then cd into it.\n'
  fi
  if [ -n "$BR_CONFLICTS" ]; then
    printf '⚠️  SAME BRANCH (different worktree) — pushes may race:\n'
    printf '%s' "$BR_CONFLICTS" | while IFS=$'\t' read -r id br task host; do
      [ -n "$id" ] && printf '    %s  [%s]  on %s  %s\n' "$id" "$br" "$host" "$task"
    done
    printf '    Coordinate pushes, or work on a distinct branch.\n'
  fi
}

cmd_check() {
  local id; id="$(resolve_id || true)"
  prune_stale >/dev/null
  # Keep our own heartbeat fresh if we know who we are.
  [ -n "$id" ] && [ -f "$(session_file "$id")" ] && write_record "$id" "" "" || true
  gather_conflicts "$id"
  if [ -n "$WT_CONFLICTS" ]; then report_conflicts; exit 3; fi
  if [ -n "$BR_CONFLICTS" ]; then report_conflicts; exit 4; fi
  printf '✓ no conflicts: this worktree (%s) and branch (%s) are not claimed by another live session\n' \
    "$TOPLEVEL" "$(current_branch)"
}

cmd_list() {
  local show_all="${OPT_ALL:-}" f any=0 mark live
  # Plain `list` prunes dead records first; `--all` preserves them for display.
  [ -n "$show_all" ] || prune_stale >/dev/null
  printf '%-22s %-7s %-26s %s\n' "SESSION" "STATE" "BRANCH" "TASK"
  for f in "$REG_DIR"/*.session; do
    [ -e "$f" ] || continue
    load_session "$f"
    live="$(session_liveness)"
    if is_stale; then
      [ -n "$show_all" ] || continue
      mark="stale"
    else
      mark="$live"
    fi
    any=1
    printf '%-22s %-7s %-26s %s\n' "$S_id" "$mark" "${S_branch:-?}" "${S_task:-}"
    printf '    %s  on %s  since %s\n' "${S_worktree}" "${S_host:-?}" "$(fmt_epoch "${S_started:-$NOW}")"
  done
  [ "$any" -eq 0 ] && printf '(no%s sessions registered)\n' "$([ -n "$show_all" ] && echo '' || echo ' live')"
  summarize_contention
}

cmd_release() {
  local id; id="$(resolve_id)" || die "no session id (pass --id, or set \$AI_SESSION_ID / \$CLAUDE_SESSION_ID)"
  rm -f "$(mwc_file "$id")"
  local f; f="$(session_file "$id")"
  if [ -f "$f" ]; then rm -f "$f"; printf 'released session %s\n' "$id"; else printf 'no record for session %s\n' "$id"; fi
}

cmd_prune() { prune_stale; }

cmd_worktree() {
  local branch="${OPT_WT_BRANCH:-}" base="${OPT_BASE:-HEAD}"
  [ -n "$branch" ] || die "usage: ai-session.sh worktree <branch> [--base REF]"
  local parent="${AI_WORKTREE_DIR:-${TOPLEVEL}.worktrees}"
  local path="$parent/$(sanitize "$branch")"
  [ -e "$path" ] && die "worktree path already exists: $path"
  mkdir -p "$parent"
  if git show-ref --verify --quiet "refs/heads/$branch"; then
    git worktree add "$path" "$branch"
  else
    git worktree add -b "$branch" "$path" "$base"
  fi
  printf '\n✓ isolated worktree ready:\n    path:   %s\n    branch: %s\n\n' "$path" "$branch"
  printf 'Work there instead of the shared checkout. Next steps:\n'
  printf '    cd %s\n' "$path"
  printf '    ai-session.sh register --id <your-id> --task "<what you are doing>"\n'
  printf '\nRemove it when done:  git worktree remove %s\n' "$path"
}

# ---------------------------------------------------------------------------
# arg parsing
# ---------------------------------------------------------------------------
[ $# -ge 1 ] || die "usage: ai-session.sh {register|heartbeat|check|list|release|prune|worktree|enable-mwc|disable-mwc|check-mwc} [opts]  (see header)"
CMD="$1"; shift

OPT_ID=""; OPT_TASK=""; OPT_AGENT=""; OPT_ALL=""; OPT_BASE=""; OPT_WT_BRANCH=""
while [ $# -gt 0 ]; do
  case "$1" in
    --id)    [ "${2+set}" = set ] || die "--id requires a value";    OPT_ID="$2";    shift 2 ;;
    --task)  [ "${2+set}" = set ] || die "--task requires a value";  OPT_TASK="$2";  shift 2 ;;
    --agent) [ "${2+set}" = set ] || die "--agent requires a value"; OPT_AGENT="$2"; shift 2 ;;
    --base)  [ "${2+set}" = set ] || die "--base requires a value";  OPT_BASE="$2";  shift 2 ;;
    --all)   OPT_ALL=1; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    --*)     die "unknown option: $1" ;;
    *)       [ -z "$OPT_WT_BRANCH" ] && OPT_WT_BRANCH="$1" || die "unexpected argument: $1"; shift ;;
  esac
done

case "$CMD" in
  register)  cmd_register ;;
  heartbeat) cmd_heartbeat ;;
  check)     cmd_check ;;
  list)      cmd_list ;;
  release)   cmd_release ;;
  prune)     cmd_prune ;;
  worktree)  cmd_worktree ;;
  enable-mwc)
    id="$(resolve_id)" || die "no session id (pass --id, or set \$AI_SESSION_ID / \$CLAUDE_SESSION_ID)"
    write_record "$id" "${OPT_TASK:-}" ""
    touch "$(mwc_file "$id")"
    printf 'enabled mwc (merge-when-confident) for session %s\n' "$id"
    ;;
  disable-mwc)
    id="$(resolve_id)" || die "no session id (pass --id, or set \$AI_SESSION_ID / \$CLAUDE_SESSION_ID)"
    rm -f "$(mwc_file "$id")"
    printf 'disabled mwc for session %s\n' "$id"
    ;;
  check-mwc)
    # A QUERY, and only a query. It deliberately does not prune, and does not
    # delete the marker on a stale read, because both make asking destructive:
    # one liveness false negative permanently revokes a grant a human made, and
    # the report is then identical to "never granted". The marker alone
    # authorizes nothing -- the guard requires a marker AND a live session --
    # so leaving a stale one in place is inert, and a later heartbeat restores
    # the grant instead of it having to be re-issued. `disable-mwc`, `release`
    # and `prune` remain the ways to actually remove a marker.
    #
    # The three outcomes are reported distinctly, per
    # shared/principles/fail-fast.md: "no grant" and "a grant whose session
    # reads dead" want opposite responses, and printing one sentence for both
    # is the pass-path-and-failure-path-look-alike shape that rule bans.
    #   0  active
    #   1  no grant recorded
    #   2  grant recorded but not currently honourable (say why, and how to fix)
    id="$(resolve_id)" || die "no session id (pass --id, or set \$AI_SESSION_ID / \$CLAUDE_SESSION_ID)"
    f="$(mwc_file "$id")"
    s_file="$(session_file "$id")"
    if [ ! -f "$f" ]; then
      printf 'mwc is NOT active for session %s: no grant recorded.\n' "$id"
      printf "  Grant it with:  ai-session.sh enable-mwc --id '%s'\n" "$id"
      exit 1
    fi
    if [ ! -f "$s_file" ]; then
      printf 'mwc is NOT active for session %s: grant recorded, but no session record.\n' "$id"
      printf '  Marker: %s\n' "$f"
      printf "  Fix with:  ai-session.sh register --id '%s' && ai-session.sh enable-mwc --id '%s'\n" "$id" "$id"
      exit 2
    fi
    load_session "$s_file"
    if is_stale; then
      printf 'mwc is NOT active for session %s: grant recorded, but the session reads %s.\n' \
        "$id" "$(session_liveness)"
      printf '  Marker: %s\n' "$f"
      printf '  Last heartbeat %s; a session goes stale after %ss.\n' \
        "$(fmt_epoch "${S_heartbeat:-0}")" "$STALE_SECONDS"
      printf "  If the session IS live:  ai-session.sh heartbeat --id '%s'\n" "$id"
      exit 2
    fi
    printf 'mwc is active for session %s\n' "$id"
    if [ -z "${AI_SESSION_ID:-}" ] && [ -z "${CLAUDE_SESSION_ID:-}" ]; then
      printf '  Notice: AI_SESSION_ID and CLAUDE_SESSION_ID are unset in this shell.\n'
      printf '  The pre-tool-use merge guard will resolve session id from the harness hook payload\n'
      printf '  (session_id or transcript_path stem). Ensure the granted id matches the harness session.\n'
    fi
    exit 0
    ;;
  -h|--help) sed -n '2,40p' "$0" ;;
  *)         die "unknown command: $CMD" ;;
esac
