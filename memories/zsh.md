# zsh shell semantics that produce a false absence

Satellite of [`tools.md`](tools.md), split at the 1200-line gate (ai-config#694 pattern).

The Bash tool runs zsh, and this file collects the **zsh-specific** shell semantics under which a check **reports nothing on stdout and looks like it ran**.
That shared shape is the reason the entries sit together: a caller reading stdout sees an empty result and takes it as a finding about the inputs rather than as a failure of the check.
Each entry writes its complaint to stderr, so stderr is the signal to read.

**Check the platform before applying either entry: they were measured on different ones, and one of them turns out to be platform-bound.**
`NOMATCH` is a documented zsh default rather than a platform behaviour --- `man zshoptions` carries it, and `zsh -f -c 'echo $options[nomatch]'` prints `on`.
That entry was measured on macOS 26.6.2 with zsh 5.9.
The process-substitution entry was measured on shiva, a Linux host, and its `/proc/self/fd/11` error is a Linux path --- re-run on this macOS host, `diff <(...) <(...) | grep -c` returns the correct count, because `<(...)` names a `/dev/fd/N` path that stays open.
So that one is zsh-on-Linux rather than zsh-general.
Take the documented default as carrying across platforms and the measured error path as not, and re-measure before relying on either somewhere new --- the caveat `CLAUDE.md`'s "Tool transport collapses doubled backslashes" section states for itself: a claim stated unconditionally here is false there.

The boundary for this file is zsh-specificity, not the false-absence shape.
[`tools.md`](tools.md) keeps the zsh difference that produces a wrong *value* rather than an empty one --- the unquoted-expansion word-splitting entry --- and it also keeps false-absence entries whose cause is stdin or fd plumbing rather than a zsh expansion rule, notably the `cmd | python3 - <<EOF` heredoc entry.

## A process substitution feeding a pipeline fails under zsh, and reads as a clean zero

`diff <(a) <(b)` works at a zsh prompt and breaks the moment it feeds a pipe.
The piped form dies with `diff: /proc/self/fd/11: No such file or directory`, because the path `<(...)` names no longer resolves when `diff` opens it.
Bash runs the identical line correctly, so a snippet copied from a bash script or another machine silently changes meaning here.

Measured on zsh 5.9 and bash 5.1.16, against two files known to differ:

```bash
diff <(cat f1) <(cat f2)                             # zsh: works
o=$(diff <(cat f1) <(cat f2))                        # zsh: works
diff <(cat f1) <(cat f2) | grep -c '^>'              # zsh: /proc/self/fd error
bash -c 'diff <(cat f1) <(cat f2) | grep -c "^>"'    # bash: correct answer
```

The pipeline is the trigger.
Neither the surrounding `$(...)` nor a shell function inside the `<(...)` is required, since plain `cat` in a bare pipeline fails the same way.

**The failure presents as an all-clear rather than as an error.**
`diff` writes its complaint to stderr and produces no stdout, so a downstream `grep -c` counts zero, and a trailing `|| true` makes that zero unconditional.
The caller reads `0` as "the two inputs are identical".
This is the [`fail-fast`](../shared/principles/fail-fast.md) shape where the pass path and the failure path print the same thing, reached by a route that fragment does not cover: the comparison never ran at all, rather than its exit status being swallowed.
The `|| true` could not have helped in any case, because a pipeline reports only its last command's status --- see [`errexit-is-not-uniform`](../shared/coding/errexit-is-not-uniform.md)'s "A pipe discards the status of everything left of it".

Take the fd plumbing out of the comparison, and prove the detector works before believing any zero it reports:

```bash
norm "$tracked" > /tmp/a; norm "$inst" > /tmp/b      # real files, no <(...)
printf 'a\nb\n' > /tmp/nc1; printf 'a\nZZZ\n' > /tmp/nc2
nc=$(diff /tmp/nc1 /tmp/nc2 | grep -c '^>')
[ "$nc" -ge 1 ] || { echo "DETECTOR BROKEN --- aborting"; exit 1; }
add=$(diff /tmp/a /tmp/b | grep -c '^>')
```

The negative control is the load-bearing half, per [`batch-merge-and-resolve`](../shared/workflow/batch-merge-and-resolve.md)'s "Any conflict sweep needs a negative control".
A zero from a detector never once seen to report a difference is not evidence about the inputs.
Sibling of two plumbing failures kept in [`tools.md`](tools.md): "A hand-rolled verification check is worth nothing until it has caught something" (shell *quoting*) and "`cmd | python3 - <<EOF` reads the heredoc, not the pipe" (stdin *contention*).
This one is fd *lifetime*.

- **Do:** write both sides to real temp files and diff those, whenever a process substitution would otherwise feed a pipeline.
- **Do:** run a known-differing negative control first, and abort when the detector reports no difference.
- **Don't:** pipe the output of a command reading `<(...)` under zsh, on the strength of the same line working in bash or at a bare zsh prompt.
- **Don't:** read `0` from a `... | grep -c` as agreement when the producer could have died before writing anything.

(2026-08-03, auditing six installed dotfiles against their tracked copies on shiva: `add=$(diff <(norm "$tracked") <(norm "$inst") | grep -c '^>' || true)` reported `installed-only=0 repo-only=0` for all six files, which was read as "identical apart from em-dash normalization".
Every one of those runs had emitted the `/proc/self/fd/11` error on stderr.
Re-run against temp files, four of the six differed --- `tui-alloc` by 6 installed-only and 15 repo-only lines.
Every `<(...)` use already in this corpus was checked and is safe, since none feeds a pipeline: `skills/use-math-macros/SKILL.md`'s bare `comm -23`, plus the `< <(...)` redirects in `skills/cascade/SKILL.md` and `references/cloud-setup/cloud-setup.sh`.
Derive that set rather than counting it, since a count goes stale on the next one added: `git grep -n '<(' -- ':!memories/'`.)

## An unmatched glob aborts the whole command under zsh, so an existence check reports a clean absence

The entry above is a check that runs and produces nothing.
This one never runs at all, and the two are indistinguishable from the output.

zsh's default `NOMATCH` option makes a glob matching no file an error that **skips the whole simple command the pattern appeared in**, so `ls` never runs and none of its other arguments are ever examined.
Bash's default passes the unmatched pattern through literally instead, so the command still runs and still lists the paths that do exist.
A multi-path existence check therefore answers correctly under bash and answers nothing at all under zsh.

**The skip is scoped to that one simple command rather than to the whole script, which makes it worse rather than milder.**
The rest of the command list still runs, and the shell can still exit 0:

```zsh
zsh -c 'echo BEFORE; ls -d /nonexistent*/x; echo AFTER'   # prints BEFORE and AFTER; rc=0
```

What happens to the failed glob's status depends on **how** the next command is joined, so check the separator before reading anything into it:

```zsh
zsh -c 'ls -d /nonexistent*/x; true'         # rc=0   -- status replaced
zsh -c 'ls -d /nonexistent*/x; false'        # rc=1   -- status replaced, coincidentally 1
zsh -c 'ls -d /nonexistent*/x && echo YES'   # rc=1   -- status survives, YES never printed
```

After `;` or a newline the shell reports whatever ran last, so the glob's failure is gone and a check ending in any successful command reports success while having examined nothing.
After `&&` or `||` the failure short-circuits and does propagate, which is why `ls -d <paths> && echo found` is one of the few glob shapes whose status is trustworthy.

**The path that exists is never listed, which is the whole harm.**
The natural way to check several candidate locations is one command naming all of them, and one unmatched pattern anywhere in that list discards the answer for every other path in it.

This command was run on 2026-08-24 to check whether a local clone existed:

```zsh
ls -d ~/Documents/GitHub/ucd-serg.github.io ~/Documents/GitHub/*/ucd-serg.github.io 2>/dev/null
```

Its entire output was:

```text
(eval):1: no matches found: /Users/ezramorrison/Documents/GitHub/*/ucd-serg.github.io
```

That was reported to the user as "no local clone exists".
It was false: `~/Documents/GitHub/ucd-serg.github.io` --- the first path, which carries no glob --- existed the whole time, and the user had to correct it.

**A `2>/dev/null` written on the command itself does not suppress the message, and that is what makes the incident's output look like a clean answer.**
The abort happens while the shell expands that simple command's words, which is *before* the command's own redirections are applied --- so its `2>` never takes effect and the message goes to the shell's stderr.

The tempting cause claim is that the shell emits it before any redirection at all, and that is false.
A redirection already in effect on the **shell's** fd 2 does capture it, which matters because it is how the line disappears in practice:

```zsh
zsh -c 'ls -d /etc /nonexistent*/x 2>/dev/null'         # NOT suppressed
zsh -c '{ ls -d /etc /nonexistent*/x } 2>/dev/null'     # suppressed (block)
zsh -c 'exec 2>/dev/null; ls -d /etc /nonexistent*/x'   # suppressed (exec)
zsh -c 'ls -d /etc /nonexistent*/x' 2>/dev/null         # suppressed (outer wrapper)
```

One ordering rule explains every row: the message goes to whatever fd 2 is in effect *at expansion time*, which is the shell's own.
A redirection attached to the failing command has not been applied yet, so it cannot catch the message.
One that already changed the shell's own fd 2 has been applied, so it does.
That also covers a builtin, which has no separate process to own an fd --- `zsh -c 'echo /etc /nonexistent*/x 2>/dev/null'` leaves the message visible too, so the rule is about *when* the redirect applies rather than about which process owns it.

The rule cuts the obvious capture idiom the wrong way, so do not assume a `$(...)` sees the message:

```zsh
zsh -c 'out=$(ls -d /etc /nonexistent*/x 2>&1); print -r -- "captured=[$out]"'
# -> message goes to the terminal; captured=[]
```

The `2>&1` is attached to the failing command, so it is never applied, and the capture comes back empty while the error escapes to the caller's stderr.
Wrapping the whole thing instead --- `$(zsh -c '...' 2>&1)` or `$({ ... } 2>&1)` --- does capture it, and folds it into the value rather than discarding it, so the caller gets a non-empty "result" that is really an error message.
Either way it is a CI step, a harness, or an outer `2>/dev/null` that removes the only evidence the check never ran.

Measured 2026-08-24 on macOS 26.6.2, zsh 5.9 and bash 5.3.15, same command under each shell:

```zsh
zsh  -c 'ls -d /etc /nonexistent*/x 2>/dev/null'   # no path on stdout; error on stderr; rc=1
bash -c 'ls -d /etc /nonexistent*/x 2>/dev/null'   # prints /etc on stdout;              rc=1
```

**On this shape, on this machine, both shells exit 1 --- so the status cannot discriminate, while stdout can.**
Zsh's `1` comes from the shell refusing to run `ls` at all.
Bash's comes from `ls` running, listing `/etc`, and then failing on the literal unmatched pattern it was handed.
Those two `1`s mean opposite things, which is the point: read the `/etc` on stdout, not the status.

Both figures are BSD `ls` on macOS, and the bash one in particular should not be carried to Linux --- GNU coreutils `ls` reserves 2 for an inaccessible command-line argument, which is exactly what the passed-through pattern becomes there.
The platform caveat below has the measured numbers.
The equality is also an accident of the failing command being last, and does not survive a `;`, as the command list above shows.

**Read stderr for the signal.**
Once an outer redirect has discarded it, what remains is an empty stdout where a real path was requested --- and *that* is the durable tell, because it holds on either platform and under either `ls`:

```zsh
bash -c 'ls -d /etc /nonexistent*/x' 2>/dev/null   # prints /etc  -- ls ran
zsh  -c 'ls -d /etc /nonexistent*/x' 2>/dev/null   # prints nothing -- ls never ran
```

Bash passes the unmatched pattern through literally, so `ls` runs and lists `/etc` before failing on the bogus argument.
Zsh aborts the command, so nothing is listed at all.
Asking for a path you know exists and getting nothing back is therefore the check to run.

**Do not reach for the exit status here, and do not compare it against a ran-and-found-nothing baseline, because that comparison is platform-dependent.**
`ls -d /nonexistent1 /nonexistent2` --- two literal paths, no glob --- exits **1** under BSD `ls` and **2** under GNU coreutils `ls`, whose EXIT STATUS section reserves 2 for "serious trouble".
The `NOMATCH` abort exits 1 on both.
So on macOS the two cases are status-identical and on Linux they are not, and neither reading is about zsh.

Measured 2026-08-24 on macOS 26.6.2 with BSD `ls`, which gives 1 and 1.
Ubuntu with GNU coreutils and the same zsh 5.9 gives 2 and 1, measured by a reviewer on [#2129](https://github.com/Morrison-Lab/ai-config/pull/2129) who installed zsh 5.9 to check.
Test your own environment before relying on either, per the same caveat `CLAUDE.md`'s "Tool transport collapses doubled backslashes" section states for itself.

So preserve stderr, fall back to the empty-stdout tell, and treat the exit status as the least reliable of the three.

The trigger is any unquoted glob character, not only one in a path.
The same failure hit a `grep` during this entry's own dupe-check, because an unquoted option value was glob-expanded against the working directory:

```text
(eval):1: no matches found: --include=*.md
```

Quoting the value (`--include="*.md"`) fixed it.

**Why it matters beyond zsh.**
This is a false negative that reads as a completed search, which puts it in a family the corpus already documents: [`batch-merge-and-resolve`](../shared/workflow/batch-merge-and-resolve.md)'s "a matrix of zeros is indistinguishable from a detector that never ran", [`fail-fast`](../shared/principles/fail-fast.md)'s pass-path-equals-failure-path shape, and [`fully-clean`](../shared/workflow/fully-clean.md)'s check run that passes having examined nothing.
The transferable lesson is about **existence checks that abort before running**: an absence is evidence only once you can show the check actually examined the population.

Two remedies avoid globbing altogether, and they are the ones to reach for:

```zsh
for p in /etc /nonexistent/x; do [ -e "$p" ] && echo "$p"; done  # prints /etc
find ~/Documents/GitHub -maxdepth 2 -name ucd-serg.github.io     # no glob at all
```

Neither is zsh-specific: the loop is POSIX and runs unchanged under bash, and `find` is not a shell feature.
Note that the loop still exits 1, from the final iteration's failed `&&` --- another reason to read what a check printed rather than what it returned.

**Neither zsh-specific option fixes the incident without breaking something else, and the third one does not fix the incident at all.**
`setopt NULL_GLOB` and the `(N)` glob qualifier delete an unmatched pattern from the argument list.
Measured on zsh 5.9, 2026-08-24, with zsh's default included as the baseline:

```zsh
# incident shape: one literal path that exists, one unmatched glob
zsh -c '                      ls -d /etc /nonexistent*/x'                # no match; rc=1  <- the bug
zsh -c 'setopt NULL_GLOB;     ls -d /etc /nonexistent*/x'                # /etc    ; rc=0
zsh -c '                      ls -d /etc /nonexistent*/x(N)'             # /etc    ; rc=0
zsh -c 'setopt CSH_NULL_GLOB; ls -d /etc /nonexistent*/x'                # no match; rc=1  <- still the bug

# every pattern unmatched
zsh -c '                      ls -d /nonexistentA*/x /nonexistentB*/x'   # no match; rc=1
zsh -c 'setopt NULL_GLOB;     ls -d /nonexistentA*/x /nonexistentB*/x'   # "."     ; rc=0  <- false presence
zsh -c '                      ls -d /nonexistentA*/x(N) /nonexistentB*/x(N)'  # "."; rc=0  <- false presence
zsh -c 'setopt CSH_NULL_GLOB; ls -d /nonexistentA*/x /nonexistentB*/x'   # no match; rc=1

# at least one pattern matches: the only shape CSH_NULL_GLOB changes
zsh -c '                      ls -d /et* /nonexistent*/x'                # no match; rc=1
zsh -c 'setopt CSH_NULL_GLOB; ls -d /et* /nonexistent*/x'                # /etc    ; rc=0
```

`NULL_GLOB` and `(N)` handle the incident correctly and fail the all-unmatched case: every pattern is deleted, `ls -d` is left with no operands, and it prints `.` --- its own name for the working directory, not that directory's contents --- and exits 0.
A check answering `.` to "does this repo exist" is worse than one answering nothing, because the reply is non-empty and the status is success.

**`CSH_NULL_GLOB` is not the fix, and its man page is what makes it look like one.**
The wording is "do not report an error unless all the patterns in a command have no matches", and a literal path carrying no metacharacter **is not a pattern**.
So in the incident shape the sole pattern is the unmatched one, every pattern has therefore failed, and the option behaves exactly as the default does --- erroring and discarding `/etc`, which is the false absence this entry exists to prevent.
Reading "pattern" as "argument" is what makes it look like the fix.
Against the default it changes only the third shape above, where some *other glob* matched, which is a case this incident never involved.

The `(N)` qualifier applies `NULL_GLOB` to a single pattern rather than to the whole shell, so of `NULL_GLOB` and `(N)` it is the narrower, and it carries the same all-unmatched hole.

A first draft of this entry recommended `CSH_NULL_GLOB` on the strength of the all-unmatched row alone, and called `NULL_GLOB` and `(N)` verified on the strength of the incident row alone.
Each option was tested only in the shape that flattered it.
That is the negative-control discipline the process-substitution entry above already states, missed twice in one paragraph --- and the reason this block now measures every option against both shapes.

- **Do:** loop with `test -e`/`-d` over one path at a time, or use `find`, when checking several candidate locations.
- **Do:** read a non-empty stderr as "the check failed to run", never as part of the answer.
- **Do:** ask for a path you know exists, and read an empty stdout as the check never having run --- the one tell that holds on either platform once stderr is gone.
- **Do:** quote any argument containing `*`, `?`, or `[` that is not meant as a glob, including option values like `--include="*.md"`.
- **Do:** run the all-patterns-unmatched case before believing any glob-based existence check, since that is the case `NULL_GLOB` and `(N)` get wrong.
- **Do:** measure a candidate `setopt` against zsh's default as a baseline, so an option that changes nothing in your shape is visible as such.
- **Don't:** reach for `setopt CSH_NULL_GLOB` to fix this --- it behaves exactly like the default whenever the only pattern is the unmatched one, so it reproduces the false absence it looks like it prevents.
- **Don't:** read "pattern" in a zsh option's man page as "argument".
  A literal path is not a pattern, and that substitution is what makes `CSH_NULL_GLOB` read as a fix.
- **Don't:** read an empty result from a multi-path glob check as "none of these exist" --- the paths carrying no glob were never examined either.
- **Don't:** trust the exit status to separate a check that ran from one that never ran.
  After `;` or a newline the failed glob's status is replaced by whatever ran next, and only `&&` or `||` preserves it.
- **Don't:** carry an `ls` exit code across platforms --- BSD returns 1 where GNU coreutils returns 2 for an inaccessible command-line argument, which has nothing to do with zsh.
- **Don't:** assume `2>/dev/null` hid only noise.
  The line it hides is the one saying the command never ran.

(Measured 2026-08-24 on this machine, in an ai-config session.
Tracked as ai-config#2128.
**From the user:** the correction that the directory existed and that reporting its absence was wrong.
**Derived and measured afterwards:** the mechanism, the bash contrast, the `--include=*.md` recurrence, and the remedies.
**From three adversarial review rounds on this entry's own PR**, each correcting the draft before it.
The skip is scoped to one simple command rather than to the command list.
`exec 2>/dev/null`, a block, and an outer wrapper *do* capture the message, which falsified a first draft's cause claim.
`NULL_GLOB` and `(N)` print `.` when every pattern is unmatched.
`CSH_NULL_GLOB`, which a second draft recommended as the fix, behaves like the default on the incident's own shape, because a literal path is not a pattern.
`&&` preserves the failed glob's status, so a third draft's "discarded whenever anything follows it" was false.
And an exit-code pairing offered as proof that stdout cannot discriminate was itself platform-bound: a reviewer installed zsh 5.9 on Ubuntu and measured 2 where BSD `ls` gives 1, so the argument was rebuilt on the empty-stdout tell, which holds under either `ls`.
Each draft fixed one false claim by asserting another, which is why every option is now measured against zsh's own default as a baseline and every row is a command the reader can re-run.)
