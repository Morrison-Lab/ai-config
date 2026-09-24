#!/usr/bin/env python3
"""Tests for scripts/measure-cardinality-vocabulary.py.

That script exists to stop one specific reading: a comparison of two
vocabularies reporting perfect stability over a population it never examined.
Every failure it guards against is therefore a VACUOUS PASS -- a run that
prints agreeable numbers and exits 0 while measuring nothing, or measuring one
vocabulary twice.

So these tests pin the refusals rather than the arithmetic. A refusal that
stops firing turns no number wrong; it turns a broken run into a clean one,
which is invisible in the output and is exactly what the script was written
to prevent.

  REFUSALS   a substitution that would match nothing, a NARROW baseline
             identical to the live vocabulary, and a detection empty under
             BOTH vocabularies are each refused rather than reported.
  DIRECTION  a detection empty under only ONE vocabulary is NOT that refusal:
             it is a measured loss, and reporting it as a broken detector
             would assert something false about the vocabulary that still
             works.
  HONESTY    the direction report names both readings of a moved set rather
             than announcing which one applies, and the output carries the
             live vocabulary so a reader can tell which one was measured.

`claim_delta`'s multiset behaviour is pinned here too, because its own
docstring calls it defensive rather than load-bearing -- which is a claim
about today's `find_claims`, not a property anyone can rely on later.
"""
import importlib.util
import io
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "measure-cardinality-vocabulary.py"
spec = importlib.util.spec_from_file_location("mcv", SCRIPT)
mcv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcv)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def run_main(argv=("--ref", "HEAD")):
    """Run `main()` under captured streams; return (status, stdout, stderr).

    A `sys.exit` refusal and a `return 1` direction report are both outcomes
    worth asserting about, so both are normalized to a status here.
    """
    out, err = io.StringIO(), io.StringIO()
    saved_argv = sys.argv
    sys.argv = ["measure-cardinality-vocabulary.py", *argv]
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                status = mcv.main()
            except SystemExit as exc:
                status = exc.code
    finally:
        sys.argv = saved_argv
    return status, out.getvalue(), err.getvalue()


# A corpus with one body that any cardinality vocabulary flags, and one it
# does not. Two bodies rather than one, so an empty result is distinguishable
# from a corpus that was never read.
CORPUS = [
    "Widen the vocabulary\n\nthree files still carry the old spelling.",
    "Rename the constant\n\nNo count appears anywhere in this body at all.",
]


class FakeHook:
    """A stand-in hook whose vocabulary the test controls.

    Built from the real `CARDINALITY_RE` shape rather than from the real
    hook, so a test that breaks the wide vocabulary cannot be confused with
    one that broke the corpus.
    """

    def __init__(self, count, spelled=None):
        # `spelled` is how the vocabulary appears inside the pattern. It
        # differs from `count` only to reproduce the one case the
        # substitution cannot survive: an edit to `CARDINALITY_RE` after
        # which the constant no longer appears in it verbatim.
        self.CARDINALITY_COUNT = count
        self.CARDINALITY_RE = re.compile(
            rf"\b({spelled or count})\b[ \t]+[^\n.:]{{0,24}}?"
            r"([A-Za-z][\w-]*s)\b", re.I,
        )

    def find_claims(self, body):
        return [
            ("cardinality", m.group(0))
            for m in self.CARDINALITY_RE.finditer(body)
        ]


def with_fake(count, narrow, corpus=CORPUS):
    """Install a fake hook, NARROW and corpus for one `main()` run."""
    saved = (mcv.load_hook, mcv.NARROW, mcv.commit_bodies)
    mcv.load_hook = lambda: FakeHook(count)
    mcv.NARROW = narrow
    mcv.commit_bodies = lambda ref: list(corpus)
    try:
        return run_main()
    finally:
        mcv.load_hook, mcv.NARROW, mcv.commit_bodies = saved


# ---------------------------------------------------------------- REFUSALS

hook = FakeHook(r"three|four", spelled=r"four|three")
try:
    with redirect_stderr(io.StringIO()):
        mcv.claims_per_body(hook, CORPUS, r"one|two")
    refused = False
except SystemExit:
    refused = True
check(
    "a vocabulary CARDINALITY_RE no longer spells verbatim is refused",
    # The constant reads `three|four` while the pattern spells it
    # `four|three`, so the substitution silently changes nothing -- and a
    # no-op substitution measures one vocabulary twice and calls the result
    # stability.
    refused,
)

hook = FakeHook(r"three|four")
try:
    live = mcv.claims_per_body(hook, CORPUS, hook.CARDINALITY_COUNT)
    live_ok = live == [["three files"], []]
except SystemExit:
    live_ok = False
check(
    "the live vocabulary is measured rather than refused",
    # Same no-op substitution, legitimately: the guard must exempt the call
    # that asks for the vocabulary already in the pattern, or the script can
    # never measure the current one at all.
    live_ok,
)

hook = FakeHook(r"three|four")
mcv.claims_per_body(hook, CORPUS, r"three")
check(
    "CARDINALITY_RE is restored after a swap",
    hook.CARDINALITY_RE.pattern == FakeHook(r"three|four").CARDINALITY_RE.pattern,
)

status, out, err = with_fake(r"three|four", r"three|four")
check(
    "a NARROW identical to the live vocabulary is refused",
    # `claims_per_body`'s guard cannot see this: its exemption above fires
    # for both columns, so both measure one vocabulary and agree perfectly.
    isinstance(status, str) and "byte-identical" in status,
)

status, out, err = with_fake(r"zzz-absent", r"zzz-also-absent")
check(
    "a detection empty under both vocabularies is refused",
    isinstance(status, str) and "EITHER vocabulary" in status,
)

# --------------------------------------------------------------- DIRECTION

status, out, err = with_fake(r"zzz-absent", r"three|four")
check(
    "a detection empty under only the live vocabulary is not that refusal",
    # Gating the refusal on the wide set alone fires here -- the commonest
    # real case, a hook refactor that breaks the current vocabulary while the
    # hard-coded NARROW literal still works -- and then says the narrow
    # vocabulary found nothing, which is false.
    status == 1 and "EITHER vocabulary" not in (err + out),
)
check(
    "that case is reported as a loss, by direction",
    "no longer flagged" in err,
)

# ----------------------------------------------------------------- HONESTY

check(
    "the loss report names both readings rather than announcing one",
    # A message that called every lost claim a corrected false positive would
    # be a verdict the script has no way to reach.
    "is either a" in err and "only reading them settles" in err,
)

status, out, err = with_fake(r"three|four", r"three")
check(
    "the output carries the live vocabulary, not just its label",
    # `WIDE_LABEL` is deliberately generic, so without this the output never
    # says which vocabulary produced the numbers.
    "three|four" in out,
)

# -------------------------------------------------------------- CLAIM DELTA

gained, lost = mcv.claim_delta([["six lines"]], [["six lines", "fifty lines"]])
check(
    "a claim gained inside an already-flagged body is counted",
    # The failure this whole script was extended for: a body flagged under
    # both vocabularies can still gain or lose claims, which no body count
    # can represent.
    gained == ["fifty lines"] and lost == [],
)

gained, lost = mcv.claim_delta([[]], [["ten files", "ten files"]])
check(
    "a repeated claim is counted per instance, not per distinct text",
    len(gained) == 2,
)

# ------------------------------------------------------------ HISTORY READ

saved_run = mcv.subprocess.run
try:
    def missing_git(*a, **k):
        raise FileNotFoundError("git")
    mcv.subprocess.run = missing_git
    try:
        mcv.commit_bodies("HEAD")
        msg = ""
    except SystemExit as exc:
        msg = str(exc.code)
    except Exception as exc:
        # Caught so that dropping the handler reports as a named failure
        # rather than killing the run before the remaining cases print.
        msg = f"uncaught {type(exc).__name__}"
finally:
    mcv.subprocess.run = saved_run
check(
    "a missing git is named as such, not as an unreadable ref",
    "not on PATH" in msg,
)

saved_run = mcv.subprocess.run
try:
    def bad_ref(*a, **k):
        raise mcv.subprocess.CalledProcessError(
            128, "git", stderr="fatal: not a git repository\n")
    mcv.subprocess.run = bad_ref
    try:
        mcv.commit_bodies("origin/main")
        msg = ""
    except SystemExit as exc:
        msg = str(exc.code)
finally:
    mcv.subprocess.run = saved_run
check(
    "git's own stderr survives into the refusal",
    # The handler's advice covers an unfetched ref and a differently-named
    # remote. Outside a repository entirely, both remedies are wrong, and
    # only git's own line says so.
    "not a git repository" in msg,
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
