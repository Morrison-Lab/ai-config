# zsh shell semantics that produce a false absence

Satellite of [`tools.md`](tools.md), split at the 1200-line gate (ai-config#694 pattern).

The Bash tool runs zsh here, and this file collects the zsh-versus-bash differences where a check **reports nothing and looks like it ran**.
That shared shape is the reason they sit together: the output carries no error, so an empty result reads as a finding about the inputs rather than as a failure of the check.

Differences that produce a wrong *value* rather than an empty one stay in [`tools.md`](tools.md) --- the unquoted-expansion word-splitting entry, the `grep`-is-a-shell-function entry, and the reserved-variable notes in [`claude-code.md`](claude-code.md).

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
Sibling of the plumbing failures recorded in [`tools.md`](tools.md), whose causes there were shell *quoting* and stdin *contention*; this one is fd *lifetime*.

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

zsh's default `NOMATCH` option makes a glob matching no file a **fatal error for the entire command**, so nothing in the command list executes.
Bash's default passes the unmatched pattern through literally instead, so the command still runs.
A multi-path existence check therefore answers correctly under bash and answers nothing at all under zsh.

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

**`2>/dev/null` does not suppress the message, and the redirect is what makes this look like a clean answer.**
The complaint comes from the shell rather than from `ls`, and the shell emits it before any redirection the command line sets up.
So the output above is what a caller sees *with* stderr already discarded.

Measured 2026-08-24 on macOS 26.6.2, zsh 5.9 and bash 5.3.15, same command under each shell:

```zsh
zsh  -c 'ls -d /etc /nonexistent*/x 2>/dev/null'   # prints nothing; rc=1
bash -c 'ls -d /etc /nonexistent*/x 2>/dev/null'   # prints /etc;     rc=1
```

**Both shells exit 1, so the exit status cannot discriminate.**
Bash's `1` comes from `ls` failing on the literal unmatched pattern while it still lists `/etc`; zsh's `1` comes from the shell refusing to run `ls` at all.
A caller that branches on `rc` sees identical answers from a check that worked and a check that never happened, so **stdout is the only discriminator**.

The trigger is any unquoted glob character, not only one in a path.
The same failure hit a `grep` during this entry's own dupe-check, because an unquoted option value was glob-expanded against the working directory:

```text
(eval):1: no matches found: --include=*.md
```

Quoting the value (`--include="*.md"`) fixed it.

**Why it matters beyond zsh.**
This is a false negative that reads as a completed search, which puts it in a family the corpus already documents: [`batch-merge-and-resolve`](../shared/workflow/batch-merge-and-resolve.md)'s "a matrix of zeros is indistinguishable from a detector that never ran", [`fail-fast`](../shared/principles/fail-fast.md)'s pass-path-equals-failure-path shape, and [`fully-clean`](../shared/workflow/fully-clean.md)'s check run that passes having examined nothing.
The transferable lesson is about **existence checks that abort before running**: an absence is evidence only once you can show the check actually examined the population.

Four remedies, each verified on zsh 5.9 on 2026-08-24:

```zsh
for p in /etc /nonexistent/x; do [ -e "$p" ] && echo "$p"; done  # prints /etc
zsh -c 'setopt NULL_GLOB; ls -d /etc /nonexistent*/x'            # prints /etc
zsh -c 'ls -d /etc /nonexistent*/x(N)'                           # prints /etc
find ~/Documents/GitHub -maxdepth 2 -name ucd-serg.github.io     # no glob at all
```

The `(N)` glob qualifier applies `NULL_GLOB` to one pattern rather than to the whole shell, so it is the narrowest of the three zsh-specific fixes.
Note that the `for` loop above still exits 1, from the final iteration's failed `&&` --- another reason to read what a check printed rather than what it returned.

- **Do:** test one path per command, or loop with `test -e`/`-d`, when checking several candidate locations.
- **Do:** read a non-empty stderr as "the check failed to run", never as part of the answer.
- **Do:** quote any argument containing `*`, `?`, or `[` that is not meant as a glob, including option values like `--include="*.md"`.
- **Don't:** read an empty result from a multi-path glob check as "none of these exist" --- the paths without globs in them were never examined either.
- **Don't:** trust the exit status to tell the two apart; both shells return 1 here, and so does the correct loop.
- **Don't:** assume `2>/dev/null` hid only noise; it hides the one line saying the command never ran.

(Measured 2026-08-24 on this machine, in an ai-config session; tracked as ai-config#2128.
The user supplied the correction --- that the directory existed and the report of its absence was wrong.
The mechanism, the bash comparison, the identical-exit-status finding, the `--include=*.md` recurrence, and the four remedies were derived and measured afterwards while writing this entry.)
