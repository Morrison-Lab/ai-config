# Python and CPython runtime behavior

Cross-project notes on Python-the-language and CPython-the-implementation:
compiled-code introspection, platform-divergent stdlib behavior, and the
measurements that settled each.

## A literal inside a collection display can be invisible to a top-level `co_consts` probe

`assert "gh" not in fn.__code__.co_consts` reads like a guard against the
literal `"gh"` reappearing in `fn`, and it is vacuous whenever the literal
sits inside a collection display that CPython's compiler constant-folds:
the display becomes a single nested constant, the string lives one level
down --- `co_consts` is `(None, ('gh', 'search', ...))` --- and top-level
membership never sees it, so the assertion passes on exactly the reverted
code it exists to catch.
A green check that measures nothing is worse than no check, because it
attests coverage that does not exist.

The folding is shape- and threshold-dependent, so probe it rather than
assuming either way (measured on CPython 3.13.7: a 2-element list display
was left unfolded and the top-level probe saw its elements; 3-element and
longer lists folded; tuple displays folded at every length; an `in {...}`
membership set folded to a `frozenset` constant; nested displays folded
into tuples of tuples, two levels down).

Search the constant tree recursively, not one level:

```python
def constant_literals(consts):
    for const in consts:
        if isinstance(const, (tuple, list, set, frozenset)):
            yield from constant_literals(const)
        else:
            yield const

assert "gh" not in set(constant_literals(fn.__code__.co_consts))
```

(A function whose body defines lambdas, nested `def`s, or generator
expressions carries their code objects in `co_consts`; extend the walk
into `const.co_consts` when guarding one of those.
List/set/dict comprehensions carry none since PEP 709's inlining in
CPython 3.12 --- measured on 3.13.7, a listcomp's literal lands directly
in the enclosing function's `co_consts`, where this guard already sees it;
on 3.11 and earlier they carry code objects like the rest.)
And negative-control the guard: compile a simulation of the revert and
confirm the assertion fails on it, since this failure mode is precisely a
guard that cannot fail.

- **Do:** walk nested collection consts recursively when asserting a
  literal's absence from compiled code, and negative-control the guard
  against a compiled revert.
- **Do:** re-probe the folding threshold on the interpreter you target
  before relying on a shape claim --- it is an optimizer detail, not a
  language guarantee.
- **Don't:** assert membership on `co_consts` directly for a literal that
  would sit inside a collection display --- folding hides it at three
  elements on 3.13.7, and `{...}` membership sets hide it in a `frozenset`.

(Measured 2026-08-23, CPython 3.13.7, during ai-config#1976's review loop:
the top-level form passed on both the fixed code and a compiled revert
simulation; the adversarial reviewer caught that, and a second round caught
the one-level search missing the `frozenset` and two-level-tuple shapes.)

## `os.kill(pid, 0)` on Windows is `GenerateConsoleCtrlEvent`, not a liveness probe

On Windows, `signal.CTRL_C_EVENT == 0`, so `os.kill(pid, 0)` takes the
console-control branch of CPython's `os_kill_impl`: it calls
`GenerateConsoleCtrlEvent(CTRL_C_EVENT, pid)`, where `pid` names a process
**group**.
Every signal value other than `CTRL_C_EVENT`/`CTRL_BREAK_EVENT` goes to
`OpenProcess` + `TerminateProcess` --- and the documentation's
"any other value for sig" sentence has always excluded 0, so the folk
belief that a signal-0 probe is lethal on Windows was wrong in both
directions: 0 was never routed to `TerminateProcess`, and what it does
instead is not a probe either.

Three measured consequences (2026-08-23, Windows 11, CPython 3.13.7):

- Against the caller's own `subprocess` child: the call returned without
  error and the child survived, so in that topology it walks and quacks
  like the POSIX probe.
- Against live unrelated processes it fails, in two measured shapes:
  `OSError` WinError 87 on verified same-user targets (`cmd.exe`,
  `explorer.exe`, `conhost.exe`) --- byte-identical to what a dead pid
  raises --- and WinError 5 on service or unverified-owner targets
  (`svchost.exe`), consistent with access-denied.
  So read as a probe, it reports live processes as gone.
  The exact Win32 predicate separating success from failure was not
  established; what the measurements support is "succeeds on the caller's
  own children and parent, fails variously on unrelated live processes",
  and the entry deliberately claims no more than that.
- Delivery: `GenerateConsoleCtrlEvent`'s own documentation says CTRL_C
  "cannot be generated for process groups" --- a nonzero id never
  delivers, and when the call succeeds nothing was received (measured: a
  `CREATE_NEW_PROCESS_GROUP` child probed with signal 0 survived
  untouched).
  Only `os.kill(0, 0)`, the POSIX self-group idiom, actually delivers ---
  a real CTRL_C to the caller's own console group, caller included.

So the POSIX idiom (probe with signal 0, treat `OSError` as gone) is
POSIX-only.
The one Windows context that tolerates it is a wait-for-death loop over a
process you have already signalled to die: there a false "gone" only ends
the wait early.
For a real Windows liveness check, ask the process API
(`OpenProcess`/`GetExitCodeProcess` via `ctypes`, or `psutil.pid_exists`).

Two caveats for wait-for-death loops keyed on the probe, one per
platform: on POSIX it succeeds
on a zombie (an unreaped child) until the reap, and on Windows it succeeds
on a terminated child while any handle stays open (a `subprocess.Popen`
object holds one) --- so in test topologies a dead child often stays
"observable" and the loop times out rather than confirming the death.
Give the timeout its own observable outcome, per
[`fail-fast`](../shared/principles/fail-fast.md).

- **Do:** treat `os.kill(pid, 0)` as a liveness probe on POSIX only, and
  use a process-API check for liveness on Windows.
- **Do:** record both halves of the correction: the retired belief was
  "Windows `os.kill` routes signal 0 to `TerminateProcess`"; the
  replacement is "signal 0 IS `CTRL_C_EVENT`, routed to
  `GenerateConsoleCtrlEvent`, whose success does not track liveness and
  which delivers nothing for a nonzero pid".
- **Don't:** generalize a probe that behaved on your own subprocess
  children to arbitrary pids --- the measured discrimination covers your
  own children and parent, not existence in general.
- **Don't:** treat a succeeding probe as proof of a live process anywhere
  --- zombies and open-handle corpses both pass it.

## `time.tzset()` and timezone resolution on Windows

`time.tzset()` is unavailable on Windows --- CPython documents it as `Availability: Unix`.
It resets the C library's time-conversion rules from the `TZ` environment variable;
merely reading the local time needs no `tzset()` on any platform (`time.localtime()`, `datetime.datetime.now().astimezone()`).
What Windows loses is the ability to re-apply a changed `TZ` inside a running process, which is why the bash `TZ=America/Los_Angeles date` recap recipe has no direct Python equivalent there.

Python's `zoneinfo` module (3.9+) reads the system IANA time zone database where one exists, and falls back to the first-party `tzdata` PyPI package otherwise.
Windows ships no IANA database in the format `zoneinfo` expects, so on a standard Windows Python installation without the `tzdata` package, `zoneinfo.ZoneInfo("America/Los_Angeles")` raises `zoneinfo.ZoneInfoNotFoundError` (a `KeyError` subclass).
The internal `ModuleNotFoundError` for `tzdata` is caught inside `zoneinfo` and survives only as the traceback's chained `__context__`, so `except ModuleNotFoundError` around the `ZoneInfo` call catches nothing.
Measured 2026-08-26 on CPython 3.11.15 (Linux), forcing the no-system-data path --- the one a Windows install without `tzdata` takes --- via `zoneinfo.reset_tzpath([])`;
the mechanism is `Lib/zoneinfo/_common.py`'s `load_tzdata()`, which catches `ImportError`/`FileNotFoundError` and raises `ZoneInfoNotFoundError`.

For dependency-free local-time output on Windows, do not substitute a fixed UTC offset: a DST-observing zone like `America/Los_Angeles` is UTC-7 or UTC-8 depending on the date, so a hard-coded `datetime.timedelta` is wrong for half the year.
Use the system's own local clock (`datetime.datetime.now().astimezone()`) when the machine's zone is the wanted one, or the DST-aware PowerShell fallback in `CLAUDE.md`'s "Timestamp recaps in local time" section when it is not.

- **Do:** install the `tzdata` PyPI package when full IANA `zoneinfo` support is needed on Windows.
- **Do:** catch `zoneinfo.ZoneInfoNotFoundError` when handling a missing time zone database.
- **Don't:** assume `time.tzset()` exists, or that `zoneinfo.ZoneInfo("America/Los_Angeles")` succeeds out-of-the-box, on a Windows Python installation.
- **Don't:** wrap a `ZoneInfo` call in `except ModuleNotFoundError`, or hard-code a fixed UTC offset for a DST-observing zone.

## `itertools.islice` caps a generator by prefix, and the obvious integer stride collapses to it

`itertools.islice(gen, n)` takes the **first** `n` items, not `n` items spread across what `gen` produces.
Over a nested generator --- an outer loop varying one component, inner loops varying the rest --- the first `n` items therefore share whatever the outer loop emitted first, and a `--limit` implemented this way yields a sample that is narrow rather than merely small.
The structural claim holds whatever the corpus size: on `scripts/check-verdict-scan-parity.py` (shipped by [ai-config#2515](https://github.com/Morrison-Lab/ai-config/pull/2515), whose `--limit` now carries the fractional-step form below), `LEAD` is the outermost of seven `itertools.product` axes, so a prefix holds `LEAD[0]` fixed for the first 241,920 of 1,693,440 bodies.
The **blind-prefix length** is the part that has to be measured, and the measurement on record was wrong: re-derived 2026-08-28, the negative control's first divergence sits at prefix index **485**, with 120 divergences inside the first 8,000.
Those are figures about a *prefix*, so they say nothing about what a capped run does --- `--limit` strides, and at limit 500 the stride is 3,386, which never samples index 485.
Measured separately, a strided run at that cap finds **125** divergences and prints `DISCRIMINATES`;
the same 500 bodies taken as a prefix find 15.
Quoting the prefix index as the reason the capped run works is the very prefix-versus-stride conflation this entry exists to prevent.
An earlier reading of this entry said the first 8,000 were blind, and attributed that to figure decay --- the corpus having grown from 221,184 bodies to 1,693,440 under the same PR.
Recovering the history shows the decay story is wrong.
The claim was introduced by `936aea2`, the very commit that widened the corpus, so it never faced the smaller one.
What produced it was the **dead negative control** that commit also carried: patching `strip_cited_finding_vocab` after the scans had moved to `strip_cited_finding_vocab_with_mask`.
Measured at `936aea2` against base `936aea2^`, the dead control reports **0** divergences over the first 8,000 while the repaired control reports **120** over the identical corpus and revisions.
So the blind reading was an artifact of a control patching code nothing called, which is the failure [`algorithmatize-checks.md`](../shared/workflow/algorithmatize-checks.md)'s "A control's patch point drifts" section describes, not the widening failure it was filed under.
The same stale sentence is still a source comment on `main`, tracked as [ai-config#2532](https://github.com/Morrison-Lab/ai-config/issues/2532). (For the record, the widening did happen and was substantial --- `FILLER_EXTRA` from 0 to 8 entries, `LEAD` from 4 to 7, `NEGATION` from 4 to 6, and a fourth template becoming a fifth --- it simply is not what made the figure wrong.)
Re-derive a blind-prefix length before quoting one;
quote the axis structure freely, since it does not decay.

Striding fixes it, and the arithmetic has one trap.
An integer step, `step = len(items) // limit`, is exactly `1` for every `limit` strictly above half the corpus, so the "stride" degenerates back to a prefix --- and that is the regime a generously-raised cap puts you in, which is why the naive form is likeliest to be wrong precisely when someone has tried to be careful.
Measured on a 100-item list: `limit=51` gives an integer step of 1 and stops at index 50, while the float stride reaches index 98.
Compute the step in floating point and round at each index instead:

```python
if limit is not None and limit < total:
    step = total / limit
    picked = (items[int(i * step)] for i in range(limit))
```

`total / limit` is a `float` and stays above 1 for every `limit < total`, so each index advances.
`range(0, total, total // limit)` fails in the **opposite** direction rather than reproducing the prefix bug: for `total=100, limit=51` the step is `1`, so it yields all 100 indices and caps nothing at all.
Only when `limit > total` does it fail loudly, the step being `0` and `range` raising `ValueError: range() arg 3 must not be zero`.
So the integer-step trap has two distinct outcomes worth separating --- a slice stride degenerates to a prefix, while a `range` step degenerates to no cap --- and neither is the even spread the arithmetic was supposed to buy.

A generator has no `len()`, so striding it requires either materializing it or making the generator itself accept the stride.
Apply the cap *inside* the generator where you can, since materializing first spends the whole cost the cap was meant to avoid ([ai-config#2534](https://github.com/Morrison-Lab/ai-config/issues/2534)).
Materializing is not free either, and "short strings" hides the cost: 1,693,440 of these bodies took about 1.5 s and raised peak RSS from 12 MB to 350 MB, measured 2026-08-28 on CPython 3.11 under Linux with nothing else in the process.
Read that 337 MB as the step's own cost only because the baseline was measured beside it;
peak RSS is process-wide, so a bare "peaked at N MB" attributes every other allocation in the run to whichever step you were watching. (A first reading of 5.9 s and 511 MB came from a run with `tracemalloc` enabled, which inflates both.)
That is affordable for a bounded corpus and unbounded for a generator with no end, which is the asymmetry that decides which form to reach for --- but quote the number rather than calling it cheap, since half a gigabyte is a real constraint on a small runner.

- **Do:** stride across a generated product space when capping it, computing the step as a float and indexing by `int(i * step)`.
- **Do:** state in the run's own output which sampling mode produced the figures, so a capped number is never read as a swept one (the tool this entry is drawn from does not, tracked as [ai-config#2534](https://github.com/Morrison-Lab/ai-config/issues/2534)).
- **Don't:** implement a `--limit` as `itertools.islice` over a nested product generator --- that fixes the slowest-varying component.
- **Don't:** use `total // limit` as a stride;
  it is 1 for every limit above half the corpus, which is a prefix by another name.

## An uncaught exception exits 1, which is a lie in any tool where 1 means something

Python's default status for an uncaught exception is **1**.
That is harmless in a script whose only other status is 0, and actively dangerous the moment a tool assigns 1 a meaning --- "absent", "not found", "no match", "clean" --- because a crash then reports that meaning.

The failure is not the crash.
It is that the crash is indistinguishable from a successful negative answer, so a caller branching on the exit code acts on a conclusion the tool never reached.

```python
try:
    result = scan(root, needle)
    ...
    return {"found": 0, "absent": 1, "degraded": 2}[outcome]
except Exception as exc:          # noqa: BLE001 -- mapped to 2, never to 1
    print(f"failed before it could answer: {type(exc).__name__}: {exc}",
          file=sys.stderr)
    return 2
```

**Guard the whole body, not the part you think can raise.**
Three sites are easy to leave outside it, and each was measured 2026-08-28 on [ai-config#2539](https://github.com/Morrison-Lab/ai-config/pull/2539):

- **Argument and root resolution**, which runs before the work.
  `CLAUDE_CONFIG_DIR='~nosuchuser/x'` made `Path.expanduser()` raise, and the tool exited 1 --- "no record contains it".
- **The reporting itself**, which runs after.
  Under `LC_ALL=C`, printing a matched record containing an em-dash raised `UnicodeEncodeError`: the tool **found** the record, then died showing it, and exited 1.
  Reconfigure the stream rather than only catching this: `sys.stdout.reconfigure(errors="replace")`, wrapped in its own `try` since it is absent on a replaced stream.
- **`__doc__` under `-OO`**, which strips docstrings, so `argparse.ArgumentParser(description=__doc__.splitlines()[0])` raises `AttributeError` on `None`.
  Use `(__doc__ or "fallback")`.

A broad `except Exception` is normally a [`fail-fast`](../shared/principles/fail-fast.md) violation.
It is the correct construct here precisely because it is not silent: it maps to a status that means *the work did not happen*, and it prints what failed.
That is the explicit, bounded, observable fallback that fragment asks for rather than the swallowing it forbids.

- **Do:** reserve a distinct status for "could not answer", and map every unexpected exception to it.
- **Do:** wrap argument resolution and output, not only the computation.
- **Do:** harden the output stream, so a value the console cannot encode does not destroy an answer already computed.
- **Don't:** leave exit 1 meaning both "the answer is no" and "there is no answer".
- **Don't:** read a bare `except Exception` as automatically wrong --- it is wrong when it hides the failure, not when it classifies it.

## `-W` reaches only the interpreter it is given to; a spawned child starts with a fresh filter

A `python3 -W error::SyntaxWarning script.py` flag governs the warnings filter of *that one process*.
It does not survive into a child `python` process the script itself spawns via `subprocess.run`/`Popen` --- the child starts with its own default filter, unaware the parent was ever given a flag at all.
Only environment variables cross that boundary: `PYTHONWARNINGS` (same `action::category` syntax as `-W`) is read by every interpreter that inherits the environment, parent and child alike.

The trap is specific to a **test harness that spawns its subject as a subprocess** rather than importing it in-process.
Applying `-W` only to the outer runner passes silently on exactly the case the flag exists to catch, because the warning fires inside the un-flagged grandchild and never becomes an error there.
The failure is invisible from the outside: the outer process still exits 0, and nothing in its own output distinguishes "no warning occurred" from "a warning occurred where nobody was listening".

- **Do:** set `PYTHONWARNINGS` in the subprocess environment (`env=dict(os.environ, PYTHONWARNINGS="error::SyntaxWarning")`) when the goal is for a spawned child to inherit the same warnings-as-errors behavior as its parent.
- **Do:** verify the propagation empirically --- inject the exact defect class into a subject invoked the same way production invokes it, and confirm the harness actually fails --- rather than trusting that a flag which works on the outer process must also reach an inner one.
- **Don't:** assume `-W` on the outer interpreter secures anything a subprocess it spawns does.

(Morrison-Lab/ai-config#1969/#2568, 2026-08-28: a fix adding `-W error::SyntaxWarning` to `scripts/test_hooks.py`'s suite runner passed review's own empirical check --- 46/46 suites still green --- because the corpus was already clean of warnings, which proved nothing about whether the mechanism would catch a *new* one.
Caught in review by injecting an invalid escape sequence into a hook whose test spawns it via `subprocess.run([sys.executable, HOOK], ...)` (36 of 46 suites use this pattern;
the rest import their subject in-process, some using both): the suite still reported 19/19 correct, exit 0.
Fixed by switching to `PYTHONWARNINGS`, and reproducing the same injection to confirm the fixed suite now fails.)
