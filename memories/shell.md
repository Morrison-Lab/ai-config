# Shell and Bash scripting

## Background process waiters: `pgrep -f` matches its own command line (self-match deadlock)

`pgrep -f "<name>"` matches every process whose full command line contains `<name>`, including any shell or loop that is itself waiting on or searching for `<name>`.
Because the pattern is a substring of the searcher's own `argv`, this causes silent failure modes with no error messages:

1. **Stale "still running" readings**:
   A waiter like `until ! pgrep -f "job.sh"; do sleep 10; done` never terminates because its own command line in the process table contains `job.sh`.
   Subsequent status checks using `pgrep -f "job.sh"` confirm the process is still running even hours after the target script finished.
2. **Deadlocks across scripts**:
   A sequence guarding a step with `while pgrep -f "task.sh"; do sleep 3; done` blocks indefinitely if an earlier waiter (`until ! pgrep -f "task.sh" ...`) remains alive, even though the original `task.sh` exited.
3. **Self-inflicted process termination**:
   Running `pkill -f 'pgrep -f "task.sh"'` matches the executing shell itself and terminates the calling session mid-command (exit code 144) before any cleanup or follow-up runs.

### Robust remedies

- **Poll a done-marker file**:
  Write a sentinel file on completion and poll for file existence rather than process inspection:

  ```bash
  # inside the background script:
  ... ; touch "$SP/job.done"

  # inside the waiter:
  until [ -f "$SP/job.done" ]; do sleep 5; done
  ```

- **Kill by PID, not pattern**:
  Store `$!` or read a recorded PID file, then target the process hierarchy explicitly:

  ```bash
  kill -9 "$pid"; pkill -9 -P "$pid"
  ```

- **Anchor `pgrep -f` when unavoidable**:
  Anchor to the interpreter binary (`pgrep -f "^bash .*<name>"`) or exclude the current shell process to avoid self-matching.

(Measured 2026-09-01 during `serocalculator#668` session, documented in ai-config#2915.)

## Heredocs in chained terminal commands are unreliable

Multi-line heredoc-style commands in chained terminal commands get garbled or silently fail.
Always write multi-line content to a temp file first, then reference it:

```sh
cat > /tmp/msg.txt << 'EOF'
line 1
line 2
EOF
git commit -F /tmp/msg.txt
```

Never inline heredocs in chained commands.
Applies to git commit messages, MR descriptions, and any other multi-line content passed to CLI tools.
(Learned during HACtions MR !37.)

## Writing robust bash scripts (recurring review findings)

Lessons the reviewer flagged across the `session-lock` PR (Morrison-Lab/ai-config#38) ---
pre-empt these when authoring shell, especially under `set -euo pipefail`:

- **`mktemp` + rename: add a cleanup trap.**
  A process killed between `mktemp` and the `mv` orphans temp files forever.
  Pattern: `tmp=$(mktemp -- "<dir>"/.tmp.XXXXXX); trap 'rm -f "${tmp:-}"' EXIT; ... > "$tmp"; mv -f "$tmp" "$dest"; trap - EXIT`.
  Quoting alone isn't enough here: a `<dir>` value starting with `-` (e.g. `-cache`) makes the whole substituted template start with `-`, and `mktemp` parses that as an option regardless of quoting (verified: `mktemp "-cache"/.tmp.XXXXXX` fails with "unknown option -- c";
  `mktemp -- "-cache"/.tmp.XXXXXX` correctly treats it as a path instead).
  Belt-and-suspenders for `SIGKILL` (trap can't fire): a prune path that sweeps `find "<dir>" -maxdepth 1 -name '.tmp.*' -type f -mmin +60 -delete` --- without `-maxdepth 1 -type f` it recurses into subdirectories and can delete unrelated `.tmp.*` files nested below `<dir>`, not just this script's own orphans (see the reference implementation, the `find` prune inside `prune_stale()` in `skills/session-lock/scripts/ai-session.sh`, which includes both flags).
  Those two flags bound depth and type, not ownership: `.tmp.*` is a generic pattern, so in a directory shared with other processes (bare `/tmp`, most of all) the prune can delete another process's live temp files that happen to match.
  The reference implementation is safe because its `$REG_DIR` (`"$COMMON_DIR/ai-sessions"`) is reserved for that script alone.
  Point `<dir>` at a script-reserved directory like that, or --- when the directory must be shared --- put a script-specific prefix in the `mktemp` template and the glob alike (`.myapp.tmp.XXXXXX` -> `'.myapp.tmp.*'`), so the sweep can only ever match this script's own files.
  Separately, **`--` does not fix this for `find`** the way it does for `mktemp`: GNU `find`'s own path-vs-expression parser still reads a dash-prefixed argument as an expression even after `--` (verified: `find -- "-weird"` fails with "unknown predicate `-weird'`).
  Make sure `<dir>` itself never starts with `-` --- prefix a relative one with `./`, or use an absolute path, before it reaches `find`.
  Separately, the `-name` glob must match the `mktemp` prefix you chose,
  or it silently misses every orphan (`.tmp.XXXXXX` -> `'.tmp.*'`;
  mktemp's bare `tmp.XXXXXX` default -> `'tmp.*'`).
- **Bounds-check value-taking flags before `shift 2`.**
  In a `set -e` arg parser, `--flag` as the last arg makes `${2:-}` expand to "" but the following `shift 2` fail (count out of range) -> script aborts with a cryptic error.
  Guard with the `set -u`-safe presence test:
  `--flag) [ "${2+set}" = set ] || die "--flag requires a value"; V="$2"; shift 2 ;;`
  (`${2+set}` -> `set` when `$2` is present even if empty, `""` when absent.)
- **Never interpolate shell vars into a `python3 -c` / `awk` program string.**
  Pass them as arguments: `python3 -c '...sys.argv[1]...' "$val"` (not `"...'$val'..."`)
  --- keeps code and data separate and avoids quoting/injection breakage.
- **Declare loop-local vars once** in the function's top `local` line;
  bash `local` is function-scoped, so re-declaring inside loop bodies is redundant.
- **bash 3.2 (macOS default) compatibility:** indexed arrays, C-style `for ((...))`, and `${2+set}` all work;
  **associative arrays do NOT** (4.0+).
  Parse key=value records with `while IFS='=' read -r k v; do case "$k" in ...`.
