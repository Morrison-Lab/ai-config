# zsh shell semantics that produce a false absence

Satellite of [`tools.md`](tools.md), split at the 1200-line gate (ai-config#694 pattern).

The Bash tool runs zsh here, and this file collects the **zsh-specific** shell semantics under which a check **reports nothing on stdout and looks like it ran**.
That shared shape is the reason the entries sit together: a caller reading stdout sees an empty result and takes it as a finding about the inputs rather than as a failure of the check.
Both entries do write to stderr, so stderr is the signal to read.

The boundary is zsh-specificity, not the false-absence shape.
[`tools.md`](tools.md) keeps the zsh differences that produce a wrong *value* rather than an empty one --- the unquoted-expansion word-splitting entry --- and it also keeps false-absence entries whose cause is not zsh at all, notably the `cmd | python3 - <<EOF` heredoc entry, which reports "0 found" on every input under any shell.

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
Sibling of two plumbing failures kept in [`tools.md`](tools.md) --- "A hand-rolled verification check is worth nothing until it has caught something" (shell *quoting*) and "`cmd | python3 - <<EOF` reads the heredoc, not the pipe" (stdin *contention*); this one is fd *lifetime*.

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

So a glob check with anything after it returns **success** while having examined nothing.

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

The distinction is *whose* fd 2 the redirect changes, not ordering.
Any wrapper that discards a subshell's stderr --- a CI step, a `$(...)` capture with stderr merged away, a harness --- removes the only evidence the check never ran.

Measured 2026-08-24 on macOS 26.6.2, zsh 5.9 and bash 5.3.15, same command under each shell:

```zsh
zsh  -c 'ls -d /etc /nonexistent*/x 2>/dev/null'   # no path on stdout; error on stderr; rc=1
bash -c 'ls -d /etc /nonexistent*/x 2>/dev/null'   # prints /etc on stdout;              rc=1
```

**On this shape both shells exit 1, so the exit status cannot discriminate.**
Bash's `1` comes from `ls` failing on the literal unmatched pattern while still listing `/etc`; zsh's `1` comes from the shell refusing to run `ls` at all.
That equality is an accident of the failing command being last, and it does not generalize --- put anything after the glob and zsh returns 0, as the command list above shows.
So read **stderr** for the signal, and treat stdout as the fallback discriminator once an outer redirect has thrown stderr away.

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

**The two zsh-specific fixes trade the false absence for a false *presence*, so prefer the two above.**
`setopt NULL_GLOB` and the `(N)` glob qualifier both delete an unmatched pattern from the argument list.
That is correct while some other argument survives, and when **every** pattern is unmatched they delete all of them --- leaving `ls -d` with no arguments, so it lists the working directory and exits 0.
Measured on zsh 5.9, 2026-08-24:

```zsh
zsh -c 'setopt NULL_GLOB; ls -d /etc /nonexistent*/x'                  # prints /etc;  rc=0
zsh -c 'setopt NULL_GLOB; ls -d /nonexistentA*/x /nonexistentB*/x'     # prints "." ;  rc=0
zsh -c 'ls -d /nonexistentA*/x(N) /nonexistentB*/x(N)'                 # prints "." ;  rc=0
zsh -c 'setopt CSH_NULL_GLOB; ls -d /nonexistentA*/x /nonexistentB*/x' # errors;       rc=1
```

A check that answers `.` to "does this repo exist" is worse than one that answers nothing, because the reply is non-empty and exits 0.
`CSH_NULL_GLOB` closes that hole --- `man zshoptions` describes it as not reporting an error unless every pattern in a command fails to match --- so it errors precisely in the all-unmatched case the other two get wrong.
The `(N)` qualifier applies `NULL_GLOB` to one pattern rather than to the whole shell, so it is the narrower of that pair, and it carries the same hole.

Testing only the one-matching-path case is what hid this: the fix looked verified because the surviving argument masked the empty-argument-list behaviour.
That is the negative-control discipline the process-substitution entry above already states, and this entry failed to apply it to its own remedies.

- **Do:** loop with `test -e`/`-d` over one path at a time, or use `find`, when checking several candidate locations.
- **Do:** read a non-empty stderr as "the check failed to run", never as part of the answer.
- **Do:** quote any argument containing `*`, `?`, or `[` that is not meant as a glob, including option values like `--include="*.md"`.
- **Do:** run the all-patterns-unmatched case before believing any glob-based existence check, since that is the case `NULL_GLOB` and `(N)` get wrong.
- **Don't:** read an empty result from a multi-path glob check as "none of these exist" --- the paths carrying no glob were never examined either.
- **Don't:** trust the exit status to separate a check that ran from one that never ran; zsh returns 0 whenever anything follows the failing command, and 1 only when it happens to come last.
- **Don't:** assume `2>/dev/null` hid only noise; the line it hides is the one saying the command never ran.

(Measured 2026-08-24 on this machine, in an ai-config session; tracked as ai-config#2128.
**From the user:** the correction that the directory existed and that reporting its absence was wrong.
**Derived and measured afterwards:** the mechanism, the bash contrast, the `--include=*.md` recurrence, and the remedies.
**From the adversarial review of this entry's own PR:** that the skip is scoped to one simple command rather than the command list, so zsh returns 0 whenever anything follows it; that `exec 2>/dev/null` and a block or wrapper redirect *do* capture the message, falsifying a first draft's cause claim; and that `NULL_GLOB` and `(N)` list the working directory when every pattern is unmatched.
The first draft asserted the opposite of each, which is why the entry now shows the commands rather than describing them.)
