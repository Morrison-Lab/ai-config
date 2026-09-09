# `pkill -f <script>` on a path shared across worktrees kills every worktree's run, not just yours

A satellite of [`git-worktrees.md`](git-worktrees.md) (ai-config#694 pattern), written here rather than appended there because that file stands at 1249 lines against `scripts/check-memory-file-size.py`'s 1250-line cap, leaving no room for this entry.
Nothing was moved out of it, so it carries no "Moved to" stub back to this file and discoverability rests on the [`MEMORY.md`](MEMORY.md) index row alone (ai-config#3449).

Three worktrees of this repo can each run the identical validation script (`scripts/run-local-validation.py`) from the identical relative path, in parallel, in their own separate working directories.
`pkill -f` matches the full command line as a pattern.
It carries no notion of which working directory a matched process was started from, and cutting a worktree does not change the script's own path.
So a pattern chosen to mean "my stale run" --- the script's path, with nothing narrower available to distinguish worktrees by --- means "any worktree's run of this script" to `pkill`, a peer's live, progressing run included.

An agent clearing what it believed was its own stale background run of `scripts/run-local-validation.py` ran `pkill -f "scripts/run-local-validation.py"`.
It then reported, unprompted, that it believed the command had also killed a peer worktree's run --- the correct instinct to report, worth naming as such before naming what went wrong.

**State the impact honestly, because it was not fully established.**
When the peer worktree's process table was checked roughly ninety seconds later, a `run-local-validation.py` run there was alive, had been up for 1m26s, and its log had been written 4 seconds earlier.
So either the `pkill` missed that run on timing, or it killed an earlier run that had already been replaced by the time of the check.
The *mechanism* --- that the pattern cannot distinguish worktrees --- is confirmed regardless of which of those happened.
The *damage on this specific occasion* is not established, and asserting it occurred would be exactly the failure the second half of this section exists to name.

**Scope a process kill by identity or working directory, never by a script path shared across worktrees.**
Two safe forms exist.
Keep the PID from the launch (`nohup ... & pid=$!`, or an equivalent capture of `$!`) and `kill "$pid"` against that specific number.
Or, when the PID was not captured, resolve candidates with `pgrep -f <pattern>` and filter each one on its actual working directory before killing it --- `readlink /proc/<pid>/cwd` (or the platform equivalent) compared against your own worktree path, killing only a match.

**That working-directory filter is necessary and not sufficient, and the case it misses is your own caller.**
`pgrep` excludes its own PID and no other, so the shell running the `pgrep` can itself be a candidate: that shell's command line may contain the pattern, because the pattern was typed into it.
Its working directory is your worktree by construction, which is exactly what the filter is told to accept.
So the filter protects a peer correctly --- a peer's run has a different working directory and is excluded --- while admitting the one process whose death costs you the operation in progress.

Reproduce it with two throwaway directories standing in for two worktrees, a `sleep` in each carrying a unique pattern, and this listing run from the first:

```bash
for pid in $(pgrep -f "$pattern"); do
  printf 'pid=%s cwd=%s self=%s\n' "$pid" "$(readlink /proc/$pid/cwd)" \
    "$( [ "$pid" = "$$" ] && echo YES || echo no )"
done
```

Run as `bash -c '<that script>'` from `/tmp/wtDemoA`, with a peer's process in `/tmp/wtDemoB`:

```
pid=19236 cwd=/tmp/wtDemoB self=no
pid=19238 cwd=/tmp/wtDemoA self=no
pid=19240 cwd=/tmp/wtDemoA self=YES
```

Three matches: the peer's process, the genuine stale target, and the caller.
The working-directory filter accepts rows two and three and rejects only the peer, so the caller dies alongside the target.
Adding `-A` leaves `19236` and `19238` and drops `19240`.

**Whether the caller appears at all depends on how the caller was invoked, which is why testing this once is not enough to conclude you are safe.**
`pgrep -f` matches a command *line*.
A `bash -c '<script>'` caller carries the pattern in its own argv and matches;
the same script fed to `bash` on **stdin** does not, because its argv is just the shell.
Re-running the same listing that way returns only `19236` and `19238`, with no `self=YES` row.
So a reader who tests the stdin form, sees no self-match, and concludes the hazard is imaginary has tested the one shape that hides it.

Pass `pgrep -A`/`--ignore-ancestors`, or drop `$$` and its ancestors from the candidate list, before killing anything the working-directory filter accepted.
`-A` is procps-ng's, so on a `pgrep` that lacks it (BSD, macOS, busybox) the manual ancestor walk is the portable form --- the same caveat the `/proc/<pid>/cwd` read above already carries.
The general shape: a kill with any peer-visible side effect needs a scoping predicate the pattern itself does not supply, because the pattern is necessarily identical across every worktree running the same script.
It does not matter how confident you are that only your own run is stale --- the pattern cannot tell your worktree's process from a peer's.

**A report about another process's or another agent's state is a state claim, and it gets re-queried before anyone acts on it --- including a report you just wrote about your own action.**
The natural next step after "I may have killed your run" is to tell the peer so, and the natural remediation to suggest is "re-run validation there."
Acting on that suggestion without checking first is exactly backwards: if the peer's run had in fact survived --- as the measurement above shows it had, at least at the moment checked --- following that remediation would have prompted the peer to kill its own healthy, progressing run and start over, converting a near-miss into the very damage the report was only warning about.
The report is evidence that a kill was *attempted*, not evidence about its *effect*.
Only a fresh read of the peer's own process table settles the effect.

The same premise appears in [`git-worktrees.md`](git-worktrees.md)'s "A quiet worktree is not evidence the session working it has stopped" section, for a different signal --- a snapshot answers a question about a moment, not about what is true now --- applied here to a report of an action rather than to an absence of activity.
That section's remedy is to ask the affected party or re-read live state before concluding a peer is *idle*.
The same remedy applies one step earlier here, before concluding a peer's process is *dead*.

- **Do:** re-check the peer's actual process state (or ask the peer) before recommending, or acting on, a remediation that assumes a kill succeeded.
- **Do:** capture the PID at launch and kill that PID, or filter `pgrep -f` candidates by `/proc/<pid>/cwd` against your own worktree *and* drop `$$` and its ancestors (`pgrep -A`) before killing any of them.
- **Don't:** run `pkill -f` against a script path that more than one worktree can run.
- **Don't:** reach for `killall` as the narrower alternative --- it has no full-command-line mode at all, so it cannot match a script path, and `killall python3` instead kills every `python3` on the machine.
- **Don't:** conclude the caller is safe because one test showed no `self=YES` row --- a shell reading its script on stdin never matches, so that shape hides the hazard rather than ruling it out.
- **Don't:** treat your own report of an attempted kill as confirmation of its effect, and don't pass a "you should re-run" recommendation to a peer without that check --- the recommendation itself can cause the damage the report only suspected.

(Measured 2026-09-09, `Morrison-Lab/ai-config`: three worktrees of this repo each ran `scripts/run-local-validation.py`.
An agent ran `pkill -f "scripts/run-local-validation.py"` to clear its own stale run and reported, unprompted, that it believed it had also killed a peer's run.
A check of the peer worktree's process table roughly ninety seconds later found a `run-local-validation.py` run alive, up 1m26s, with its log written 4 seconds earlier --- so the `pkill` either missed that run on timing or killed an earlier run already superseded.
Tracked as [ai-config#3427](https://github.com/Morrison-Lab/ai-config/issues/3427).)
