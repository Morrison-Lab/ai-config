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
   Running `pkill -f 'pgrep -f "task.sh"'` matches the executing shell itself and terminates the calling session mid-command (a 128-plus-signal exit status) before any cleanup or follow-up runs.

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

(Measured 2026-09-01 during the [`serocalculator#668`](https://github.com/UCD-SERG/serocalculator/pull/668) session, documented in [ai-config#2915](https://github.com/Morrison-Lab/ai-config/issues/2915).)

### Two worktrees make the pattern non-discriminating, and the cwd filter does not exclude you

The bullets above already give the remedies: kill by PID,
and where a pattern is unavoidable, anchor it or exclude the current shell.
This section is what several worktrees of one repo add to that,
and the first half of it is an elaboration of "exclude the current shell process"
rather than a new fix.

**The pattern cannot tell the worktrees apart.**
Cutting a new worktree does not change a script's path within the repo,
so `pkill -f "scripts/run-local-validation.py"` matches every worktree's run of it,
a peer's live one included.
That holds for a *relative*-path invocation, which is the usual shape.
Launching by absolute path instead gives each worktree a distinct command line ---
a different technique from the regex anchoring the bullet above prescribes,
and one that solves a different problem:
anchoring constrains where in a string a match may occur,
while an absolute path makes the whole argv unique across worktrees.
Note that a relative-path *pattern* still matches an absolute-path invocation,
since the absolute path contains the relative one as a substring.

**Filtering the candidates by working directory does not exclude your own caller.**
`pgrep` on Linux (procps-ng) excludes its own PID and nothing else,
so a caller whose argv carries the pattern is itself a match ---
and its working directory is your worktree by construction,
which is exactly what such a filter accepts.
Run this from one of two throwaway directories standing in for worktrees,
with a long-running process carrying `$pattern` started in each:

```bash
loop='for pid in $(pgrep -f "$pattern"); do
  printf "pid=%s cwd=%s self=%s\n" "$pid" "$(readlink /proc/$pid/cwd)" \
    "$( [ "$pid" = "$$" ] && echo YES || echo no )"
done'

# A: the pattern reaches the caller through the environment
( cd /tmp/wtA && pattern="$PAT" bash -c "$loop" )

# B: the pattern is expanded into the command text itself
( cd /tmp/wtA && bash -c "pattern='$PAT'; $loop" )
```

```
A: pid=777 cwd=/tmp/wtB self=no
   pid=781 cwd=/tmp/wtA self=no

B: pid=777 cwd=/tmp/wtB self=no
   pid=781 cwd=/tmp/wtA self=no
   pid=788 cwd=/tmp/wtA self=YES    <- the caller, wrongly accepted by a cwd filter
```

**The caller matches only when the pattern's literal text sits in its own command line**,
which is the whole of the rule and is easy to state wrongly.
In A the caller's argv holds the eight characters `$pattern`, never the value,
so `pgrep -f` cannot match it and no `self=YES` row appears.
In B the shell expanded the value into the command before `bash` ever saw it,
so the caller carries the pattern and matches.
Invocation *form* is a consequence rather than the rule:
`sh script.sh` and a script on stdin keep the pattern out of argv for the same reason A does,
and a `bash -c` whose pattern is interpolated puts it in.
So one clean test proves nothing about the next invocation,
and the safe assumption is that the caller may be in the list.

`pgrep -A`/`--ignore-ancestors` drops row B's third line and keeps the first two.
BSD and macOS document the opposite default:
`pkill.1` in both `freebsd/freebsd-src` and `apple-oss-distributions/adv_cmds`
states, under `-a`, that "the current pgrep or pkill process and all of its ancestors are excluded".
So confirm which polarity your platform has
rather than carrying either assumption across.

**A report that a kill happened is a state claim about someone else's process.**
The natural follow-up to "I may have killed your run" is to tell the peer to re-run,
and acting on that without checking is backwards:
if the run survived, the advice destroys it.
Re-read the peer's process table before recommending or acting on any such remediation.

- **Do:** pair a `/proc/<pid>/cwd` filter with `pgrep -A`,
  or with an explicit `$$`-and-ancestors exclusion.
- **Do:** re-query a peer's process state before acting on any report that a kill succeeded, including your own.
- **Don't:** run `pkill -f` against a script path more than one worktree can run.
- **Don't:** conclude the caller is safe from one test ---
  an invocation whose argv omits the pattern hides the hazard rather than ruling it out.

(Measured 2026-09-09 on `Morrison-Lab/ai-config`, three worktrees deep:
an agent ran `pkill -f "scripts/run-local-validation.py"` to clear its own stale run
and reported it may have caught a peer's.
The peer's run was alive 90 seconds later,
so whether that `pkill` hit an earlier run or missed on timing was never established ---
the *mechanism* is confirmed, the damage on that occasion is not.
Tracked as [ai-config#3427](https://github.com/Morrison-Lab/ai-config/issues/3427).)

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

**A literal, predictable `/tmp/<name>.txt` like the one in the example above is not a safe destination for this, because `/tmp` is shared across every concurrent session on the machine.**
A second, unrelated session can pick the same obvious filename (`msg.txt`, `patch.diff`) at the same time, and whichever session writes last silently wins --- the first session's `git commit -F` then commits the *other* session's content with no error at any step.
Use the session's own scratchpad directory instead: the system prompt's "Scratchpad Directory" section names the actual, session-specific path (a long `/private/tmp/claude-<pid>/<sanitized-cwd>/<uuid>/scratchpad` form --- see [`claude-code.md`](claude-code.md), "The scratchpad directory path's trailing UUID is a usable stand-in for the harness session id"), so two sessions cannot collide on it by construction.
Substitute that literal path in place of `/tmp` above;
there is no standard environment variable that already holds it.

- **Do:** write a commit-message (or any other multi-line CLI-input) file to the exact scratchpad path the current session's system prompt names, not to a bare `/tmp/<name>` path.
- **Don't:** use a plain, predictable `/tmp` filename for content another concurrent session could plausibly also choose --- the collision is silent, and the resulting commit looks normal until someone reads its body.
- **Don't:** assume a `$SCRATCHPAD`-style variable already holds the path --- it doesn't, and a script that references one silently writes to the wrong place (or fails outright) when the variable is unset.

(Measured 2026-09-04: `git commit --amend -F /tmp/msg.txt` picked up a different concurrent session's message from the same shared path, silently replacing the intended PR's subject and body.)

**The scratchpad is also the answer to a second, independent hazard, and the collision argument above cannot reach it: an unignored message file written inside the worktree is staged by a blanket `git add -A` and committed.**
(`git add -A` skips ignored paths, so a newly created, untracked scratch name covered by `.gitignore` or `.git/info/exclude` escapes this.
An ignore rule does nothing for a path already tracked, which is what a file shipped by an earlier round has become.
Do not rely on either way: a per-PR scratch name is ad hoc and no repository ignores it by default.)
Note what the blanket staging means: [`preferences.md`](preferences.md) already forbids `git add -A` outright, because it sweeps unrelated in-flight edits into the commit.
So this hazard is a second consequence of a command the corpus had already ruled out.
Staging only the source paths you edited prevents it independently of where the file lives.
Note the limit of that.
Explicitness alone is not the safeguard, since `git add msg.txt` names an explicit path and stages the message file.
The safeguard is naming only the files the change itself touches.
A destination `git add` cannot reach is the stronger half, because it makes the mistake unavailable rather than merely avoidable.
Note what the reasoning above would permit.
It rejects `/tmp/msg.txt` because `/tmp` is shared, so a path nobody else can write --- a file in the worktree you alone are driving --- satisfies every word of it.
That path is the dangerous one.

The failing shape is one command:

```sh
git add -A && git commit -F msg.txt && rm -f msg.txt
```

`git add -A` stages `msg.txt` before `git commit` reads it, so the file enters the tree.
The `rm` afterwards removes only the working copy.
Nothing turns red.
On the occasion measured below, the checks passed and the push succeeded;
the staging is invisible to both by construction, since neither inspects the committed file set for scratch.
The `rm` does leave a trace, and it is a weak one: an unstaged deletion (` D msg.txt`) that reads as ordinary scratch cleanup, and that a later `git add -A` silently records.
So the durable evidence is in the commit rather than in the status.

That silence is what makes it worth stating separately from the collision case.
A wrong commit *message* is visible the moment anyone reads the commit;
a stray file in the repo root is visible only to someone looking for it, and it ships.
Deleting the file afterwards feels like the cleanup that makes the pattern safe, which is why the shape survives review --- the delete is real, and it runs one step too late.

A path outside the worktree is immune by construction rather than by discipline: `git add` cannot reach it, whatever flags it is given.
So the same substitution the bullets above prescribe fixes both hazards at once, and no second rule is needed.

- **Do:** pass `git commit -F` an absolute path under the session scratchpad, so no `git add` invocation can stage it.
- **Do:** audit the round's commits one by one, in every worktree the round touched:

  ```sh
  name=msg.txt   # the repository-relative path, bound before the pipeline
  git log --diff-filter=A --name-only --format= origin/<default-branch>..HEAD | grep -qxF -- "$name"
  ```

  Bind `name` rather than inheriting it.
  `--format=` emits blank separator lines, and an unset variable expands to an empty pattern, so `grep -qxF` matches one of those blanks and the audit reports success without having found anything.
  Two nearer answers both miss the case that matters, which is a file added in one commit and removed by a later cleanup commit.
  `git ls-files` reads the current index.
  A three-dot `git diff` compares the merge base against the final tree, so an add and a later delete cancel.
  Only walking the commits sees a path that was ever added.
  `-F` is what makes `grep` match the name literally rather than as a regex, so a scratch name carrying a metacharacter cannot match the wrong path or miss the tracked one;
  quoting the pattern does not do that, and `--` is separately needed so a leading `-` is not read as an option.
- **Don't:** write the message file into the worktree and rely on deleting it --- the delete runs after the staging that captured it.
- **Don't:** read "the path is private to me" as sufficient;
  that answers the collision hazard and not this one.

(Measured 2026-09-10 on `Lacaedemon/sparta`: the shape above shipped a stray `msg.txt` to three PRs in one turn --- [#1555](https://github.com/Lacaedemon/sparta/pull/1555), [#1556](https://github.com/Lacaedemon/sparta/pull/1556) and [#1560](https://github.com/Lacaedemon/sparta/pull/1560) --- because the same command was reused for each.
A reviewer caught it on one;
the other two were found only by grepping `git ls-files` afterwards.
Tracked as [ai-config#3558](https://github.com/Morrison-Lab/ai-config/issues/3558), which also proposes the guard: refuse a commit whose staged set contains the file passed to `-F`.)

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
- **`grep -qxF "$var" file` silently fails to match when `$var` starts with `-` --- unlike `find` above, `--` DOES fix it here.**
  A value beginning with `-` (a Claude session-project directory name, which encodes a filesystem path with every `/`, `.` and `_` mapped to `-`, e.g. `-Users-ezramorrison-...`) is parsed as an option by `grep`, so the match silently fails even though the file provably contains that exact line (verified: `grep -qxF "$var" file` returned no match;
  `grep -qxF -- "$var" file` matched).
  This is the opposite of the `find` case just above --- there `--` does NOT help because `find`'s own expression parser still reads a dash-prefixed argument as an expression after it;
  for `grep`, `--` is the ordinary POSIX end-of-options marker and works as documented.
  Don't generalize either finding to the other command: always pass `--` before a variable operand to `grep`, and separately verify the target of `<dir>` itself for `find`, per the bullet above.

  (Self-hit during a `clean-git` session, 2026-09-10: a safety filter meant to skip live sessions' worktrees under-matched silently because of this, reading a genuinely live session's registration as absent.)
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

## Git Bash process substitution fails for a native-Windows consumer

In Git Bash on Windows, `<(...)` works for msys-native consumers and fails only when the consumer is a **native Windows binary** that has to reopen the msys `/proc/NNNN/fd/N` path.
Measured 2026-09-10 on Git Bash 2.37.2.windows.2: `cat <(cat f)`, `wc -l <(printf ...)` and `grep -c a <(printf ...)` all exit 0, while `git hash-object <(printf 'x\n')` exits 128 with `fatal: could not open '/proc/20068/fd/63' for reading`.
`git commit -F <(...)` fails the same way, reporting `could not read log file` --- so the error text comes from the consuming tool rather than from the shell, and grepping for a remembered message finds nothing.
Write the content to a real file and pass the path.

[`zsh.md`](zsh.md) records a different failure of the same construct, under zsh on Linux, with an explicit non-reproduction on macOS;
[`claude-code.md`](claude-code.md) points at that entry rather than adding a third measurement.
Two unrelated platform failures of one construct is the argument for suspecting it early rather than diagnosing it again.

- **Do:** write the content to a file when the consumer is a native Windows binary (`git`, and anything else not built against msys).
- **Do:** grep for the construct rather than for an error string, since the message belongs to the consumer.
- **Don't:** conclude process substitution is unavailable in Git Bash --- test it with `cat` and it works.
