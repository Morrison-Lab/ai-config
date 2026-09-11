# Debugging: case records

Worked examples moved out of [`debugging.md`](debugging.md), which sits against a 1250-line gate that CI enforces with `--strict`.
The rules themselves stay there; each record here leaves a pointer behind.

Write every cross-reference by name, never by position --- a record here and the entry it belongs to sit in different files, so "above" and "below" are false the moment either moves, and they stay present while becoming false.

## A GNU-only grep flag in an `xargs` child

Belongs to [`debugging.md`](debugging.md)'s "A second route into this section's failure" entry, under the `grep -P` locale section.

Measured 2026-09-10 during a `Morrison-Lab/qwt` CI fix, against `grep (BSD grep, GNU compatible) 2.6.0-FreeBSD` on macOS.

### The command

```bash
git ls-files -z | xargs -0 grep -lP '[\x{2014}]'
```

Printed `grep: invalid option -- P` to stderr, exited 1, and emptied stdout.
The session's `grep` is a `ugrep` shell function, which does not cross into an `xargs` child, so the child got `/usr/bin/grep`.

### Which flags BSD grep actually rejects

Two, not the seven a first draft of the guard claimed:

```
-P                 rc=2  grep: invalid option -- P
--perl-regexp      rc=2  grep: unrecognized option `--perl-regexp'
-z                 rc=0  (documented in its own man page)
--null-data        rc=0
--include=*.md     rc=0
--exclude=*.txt    rc=0
--exclude-dir=sub  rc=0
```

The two rejections print *different* stderr lines, so a guard quoting one of them for both misreports the long form.
`/usr/bin/egrep -lP` and `/usr/bin/fgrep -lP` also print `invalid option -- P`; `ggrep` is GNU grep, where `-P` works.

That first draft generalized from the one flag that had been tested, which would have made the guard assert "BSD grep rejects `--include`" over a correct command --- the same unmeasured-claim error as the false zero it exists to catch.

### The exit-code laundering

```
/usr/bin/grep -lP x a.md                      rc=2
printf 'a.md' | xargs -0 /usr/bin/grep -lP x  rc=1   (BSD xargs)
printf 'a.md' | xargs -0 /usr/bin/grep -l ZZZ rc=1   (honest no-match, same value)
```

The second and third are indistinguishable, which is the whole defect.

**The laundered value is each utility's own, and differs by implementation.**
BSD/macOS `xargs` gives 1 for any non-zero child (measured).
GNU findutils documents 123 for a child exiting 1-125.
BSD/macOS `find ... {} +` also gives 1 (measured); its GNU value is not measured here.
`parallel` is not installed on the machine these measurements come from and keeps its own exit-status convention, so only the collapse is claimed for it.
A later round caught the `xargs` numbers being rendered for `parallel` and `find` too, which is the same over-generalization one layer down: the fix corrected the number and left the sentence describing every laundering utility with one utility's measurements.
Every figure in this record was measured on macOS, so the BSD value is the one here.
A review caught the unqualified `1` being shipped in the guard's warning text and in this file, after five earlier rounds had corrected the same class of over-generalization on other axes --- this one on the host implementation, which none of those rounds had thought to vary.
What made it survivable: the test asserting the guard's rc story compared the rendered text against expectations written from the same measurements the guard encodes, so a wrong table and a wrong expectation agreed and neither ran `xargs`.
The check now measures the host's own `xargs` and requires the message to be consistent with whatever it returns.

[`batch-merge-and-resolve`](../shared/workflow/batch-merge-and-resolve.md)'s negative-control section makes the same point for a different detector: a zero matrix and a detector that never ran look alike, so report the population examined rather than only the hits.

### What each indirection does to the exit status

Measured against a stub that prints BSD grep's rejection and exits 2:

```
sh -c            rc=2   preserved
bash -c          rc=2   preserved
zsh -c           rc=2   preserved
env              rc=2   preserved
xargs -0         rc=1   laundered (BSD; GNU findutils gives 123)
find ... {} \;   rc=0   discarded
find ... {} +    rc=1   laundered
```

A draft of the guard asserted "laundered" for all seven, having measured only `xargs`.

Nested chains compose, and the outer link wins:

```
sh -c                        rc=2
xargs -0 sh -c ...           rc=1   outer xargs launders the preserved 2 (BSD value)
find ... -exec sh -c ... \;   rc=0   outer find discards it
find ... -exec sh -c ... +    rc=1   outer find launders it
```

A second draft reported the *innermost* link's behaviour, so `xargs -0 sh -c 'grep -P ...'` was told "rc=2, branch on it" while the caller sees 1.
That is worse than the uniform claim it replaced: it pointed a reader at the `case $rc` remedy in the one shape where that remedy never fires.
A per-item subshell is the ordinary idiom once the per-invocation logic needs more than one command, so the shape is common rather than exotic.
Four of them are the opposite, and `find`'s semicolon form is worse than either: a rejected flag then looks like complete success rather than an empty result.

The four preserved cases are the ones worth getting right.
Claiming the `xargs` story uniformly would tell a reader an rc branch cannot separate "rejected the flag" from "found nothing" in exactly the cases where that branch is the correct remedy --- so the generalization does not merely overstate, it inverts the advice.

The guard now picks its sentence from this table, and `find` is resolved from the terminator rather than the table, since the two forms differ.

### What the false zero cost

Five tracked files still contained an em dash when the broken scan reported none.
That is what remained at that point rather than the incident's total.
Twelve of the thirteen files the fix touched carried an em dash.
Seven were already clean when this scan ran --- the four CI had flagged, plus the three under `.claude/**` that the checker's `ignored_dirs` skips --- leaving the five outside its extension set.
State both already-fixed groups: naming only the CI-flagged four implies eight remaining, which is how a reviewer came to read the accounting as wrong even after the number was defended.
Worth stating, because a later reviewer read the 13-file total as contradicting the five.
The scan reported none, the claim went into a commit message, and an adversarial reviewer caught it.
The replacement scan reports `examined 79 of 82 tracked files` alongside the hit count, the other three being two binaries and a submodule, so a zero now carries evidence the scan ran.

### The guard

[`hooks/flag-indirect-gnu-grep-flag.py`](../hooks/flag-indirect-gnu-grep-flag.py) warns when one of the two rejected flags reaches a `grep` that an indirection actually runs.
It pairs the indirection with its utility rather than checking for each independently, because `xargs -0 python3 script.py grep -P f` runs `python3` and never invokes grep.
It is a heuristic and says so: `xargs -n 4 grep -P` leaves the value in the utility slot and is missed, a false negative, which is the safe direction for a guard that only adds context.
