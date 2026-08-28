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
The **blind-prefix length** is the part that decays, and it decayed here: re-derived 2026-08-28, the negative control's first divergence is at prefix index **485**, with 120 divergences inside the first 8,000, so `--limit 500` already prints `DISCRIMINATES`.
An earlier reading of this entry said the first 8,000 were blind.
That was true when measured against a ~221k-body corpus and false after the same PR widened the corpus to 1,693,440 --- adding `FILLER_EXTRA`, two `LEAD` values, two `NEGATION` values and a further template (the generator now carries five;
the count before the widening is unrecoverable, since #2515 was squash-merged) --- which changed generation order entirely, and nobody re-derived it.
That is [`algorithmatize-checks.md`](../shared/workflow/algorithmatize-checks.md)'s "Widening an instrument invalidates every figure it produced" committed into the instrument built to catch that class.
The same stale sentence is still a source comment on `main`, tracked as [ai-config#2532](https://github.com/Morrison-Lab/ai-config/issues/2532).
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
Materializing is not free either, and "short strings" hides the cost: 1,693,440 of these bodies took 5.9 s and peaked at 511 MB max RSS (328 MB by `tracemalloc`), measured 2026-08-28 on CPython 3.11 under Linux.
That is affordable for a bounded corpus and unbounded for a generator with no end, which is the asymmetry that decides which form to reach for --- but quote the number rather than calling it cheap, since half a gigabyte is a real constraint on a small runner.

- **Do:** stride across a generated product space when capping it, computing the step as a float and indexing by `int(i * step)`.
- **Do:** state in the run's own output which sampling mode produced the figures, so a capped number is never read as a swept one (the tool this entry is drawn from does not, tracked as [ai-config#2534](https://github.com/Morrison-Lab/ai-config/issues/2534)).
- **Don't:** implement a `--limit` as `itertools.islice` over a nested product generator --- that fixes the slowest-varying component.
- **Don't:** use `total // limit` as a stride;
  it is 1 for every limit above half the corpus, which is a prefix by another name.
