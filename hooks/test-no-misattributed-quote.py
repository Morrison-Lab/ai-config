"""Test the no-misattributed-quote guard.

Case one is the real incident verbatim: an agent attributed
"establishes nothing either way" to `shared/workflow/pr-on-claim.md`, which
contains zero occurrences of "either way", when the phrase lives in
`shared/workflow/pr-on-claim.rationale.md` and in past tense.

The suite runs against a HERMETIC synthetic corpus -- the subject hook is
copied into a temp tree so its `__file__`-derived root, `CLAUDE_PLUGIN_ROOT`
and `cwd` all point there.  A suite reading the live corpus would go stale the
next time anyone edits a fragment, and would be measuring the corpus rather
than the guard.  The fixtures carry the incident's real sentences verbatim,
and the live canary at the end separately confirms the real thing still
reproduces against the real files.

Every passing case is load-bearing.  Per `shared/principles/fail-fast.md` a
guard that misfires gets switched off and takes the real cases with it, so the
cases that must NOT fire (an external quote, a naming use, an absence report,
a reviewer's words) protect the guard's own survival.

The mutation matrix disables each clause of the fire condition separately and
reports three outcomes, not two -- caught, missed, and INAPPLICABLE -- per
`shared/workflow/algorithmatize-checks.md`, which notes that an AND-clause's
siblings mask each other and that scoring a mutation that never applied as a
pass is the failure that hides an untested clause.  Each mutation names the
case that must catch it, so "some case flipped" is not accepted in place of
"the case written for this clause flipped".

Run: python3 hooks/test-no-misattributed-quote.py hooks/no-misattributed-quote.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SUBJECT = Path(sys.argv[1]).resolve()
REPO = SUBJECT.parent.parent

# --- synthetic corpus -------------------------------------------------------
# The incident's own sentences are copied from the real files, so case one
# exercises the real wording rather than a paraphrase of it.

BASE = """\
# pr-on-claim

**Draft, not ready-for-review --- deliberately.**
A draft doesn't trigger the `@claude` review bot, so no review round is
spent on an empty or half-finished diff.

An empty pending list after a 201 supports one conclusion and not a second.
It is not evidence the request was blocked.

The reviewer's own account of what it did is the tell,
so a sentence naming the members it verified is reporting a narrower check.

Under `set -e` the `SH_WORD_SPLIT` option is set by the wrapper before it
ever reaches the callee.
"""

RATIONALE = """\
# pr-on-claim --- rationale

An empty pending list hands it to nobody, because it has established nothing
either way.

A restatement one file over: the reviewer's own account of what it did is the tell, so a sentence naming the members it verified is reporting a narrower check.

The same holds where the `SH_WORD_SPLIT` option is set by the wrapper.
"""

CASES = """\
# pr-on-claim --- cases

(2026-08-06: the POST returned 201 with a Location header, and a read five
seconds later showed Copilot absent from the pending list, reproduced twice.)
"""

OTHER = """\
# fail-fast

A check whose failure path and whose pass path print the same thing is not
yet a check.
"""


def build_corpus(root: Path):
    wf = root / "shared" / "workflow"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / "pr-on-claim.md").write_text(BASE, encoding="utf-8")
    (wf / "pr-on-claim.rationale.md").write_text(RATIONALE, encoding="utf-8")
    (wf / "pr-on-claim.cases.md").write_text(CASES, encoding="utf-8")
    pr = root / "shared" / "principles"
    pr.mkdir(parents=True, exist_ok=True)
    (pr / "fail-fast.md").write_text(OTHER, encoding="utf-8")
    (root / "CLAUDE.md").write_text("# CLAUDE\n\nNothing quotable here.\n",
                                    encoding="utf-8")
    (root / "hooks").mkdir(parents=True, exist_ok=True)


# --- cases ------------------------------------------------------------------
# (name, must_fire, clause this case ISOLATES or None, message text)
#
# "Isolates" means: an input where only that clause keeps the result correct,
# so reverting the clause is the one change that flips it.  The first draft of
# this suite had all cases passing and seven of eleven clauses unmeasured --
# the cases passed for reasons other than the clause they were written for,
# mostly by being dropped at the attribution stage before that clause was ever
# reached.  The matrix is what found that; the cases below are the repair.

P = "shared/workflow/pr-on-claim.md"
Q = "establishes nothing either way"
FILLER = "Filler prose here. " * 20  # > MAX_BRIDGE, no blank line, no cue word

CASES_SPEC = [
    ("incident", True, None,
     "The rule is stated plainly: `" + P + "` says a vanished reviewer "
     'request "' + Q + '", so the empty pending list settles nothing.'),

    ("quote-is-present", False, None,
     "As `" + P + "` puts it, a draft \"doesn't trigger the `@claude` review "
     'bot", so no review round is spent on an empty diff.'),

    ("external-source-no-file", False, None,
     "Gawande relays it from Boeing, via the veteran pilot Daniel Boorman: "
     'the term for the steps that are "both most often skipped and most '
     'costly to skip" is killer items.'),

    # Normalization must collapse the newline the source wraps at; without it
    # the phrase reads as absent from the base and present in the rationale.
    ("spans-a-line-break", False, "markup/whitespace normalization",
     "`" + P + "` states that \"the reviewer's own account of what it did is "
     'the tell, so a sentence naming the members it verified is reporting a '
     'narrower check".'),

    # Collapsing `_` and backticks is safe only because the same normalizer
    # runs over both the needle and the haystack.
    ("snake-case-identifier", False, "named-file presence gate",
     "`" + P + '` records that "the SH_WORD_SPLIT option is set by the '
     'wrapper".'),

    # Reverse direction: a `.cases.md` passage attributed to the base.
    ("sibling-reverse-direction", True, None,
     "Per `" + P + '`, a read five seconds later "showed Copilot absent from '
     'the pending list, reproduced twice".'),

    # Absent from the named file AND its siblings: silence is correct, because
    # a bare "not found" is the invented-quote misread this guard prevents.
    ("reviewer-quote-not-in-corpus", False, "sibling find floor",
     "In `" + P + "`'s thread the reviewer said \"this branch needs a "
     'regression test before merge", which I have now added.'),

    # A message REPORTING the misattribution must not be blocked for
    # containing it.  This hook's own PR description is such a message.
    ("absence-report", False, "absence-claim suppressor",
     "`" + P + '` says "' + Q + '" -- except it does not; the passage lives '
     "in the rationale file, in past tense."),

    ("naming-use", False, "naming-use skip",
     'The "' + Q + '" bullet in `' + P + '` is the one that matters here.'),

    # The citation sits inside the heading line, so no paragraph break masks
    # the clause under test.
    ("heading", False, "heading skip",
     "Reading the fragment now.\n\n## `" + P + '` says "' + Q + '"\n\n'
     "That section covers it."),

    ("fenced-code", False, "code-fence stripping",
     "Here is what the earlier session emitted:\n\n```\n`" + P + "` says a "
     'vanished reviewer request "' + Q + '".\n```\n\nI have not verified it.'),

    ("paragraph-break", False, "paragraph-break skip",
     "Per `" + P + '`.\n\nIt says "' + Q + '" plainly enough.'),

    ("bridge-too-long", False, "bridge length bound",
     "Per `" + P + "`, " + FILLER + 'it says "' + Q + '".'),

    ("no-attribution-cue", False, "attribution cue",
     "`" + P + '` and then, abruptly, "' + Q + '".'),

    # Three tokens, all three carried by the sibling, so only the floor keeps
    # this silent.
    ("quote-too-short", False, "min-token floor",
     "`" + P + '` says "nothing either way" is the standard.'),

    ("unresolvable-filename", False, "cited name must resolve",
     'Per `shared/workflow/pr-on-claim-typo.md`, "' + Q + '" is the standard.'),
]

MUST_FIRE = {name: fire for name, fire, _, _ in CASES_SPEC}


# --- runner -----------------------------------------------------------------

def run_hook(hook: Path, root: Path, text: str, sentinels: Path = None):
    """Run the guard on a one-message transcript. Returns the reason, or None.

    `sentinels` is the guard's fire-once-per-message scratch dir.  It defaults
    inside `root`; the live canary passes its own, so a repeat run of this
    suite cannot be silenced by the previous run's sentinel.
    """
    tdir = Path(tempfile.mkdtemp())
    tpath = tdir / "t.jsonl"
    tpath.write_text(json.dumps(
        {"type": "assistant",
         "message": {"content": [{"type": "text", "text": text}]}}) + "\n",
        encoding="utf-8")
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(root)
    env["TMPDIR"] = str(sentinels or (root / ".tmp"))
    env["TEMP"] = env["TMP"] = env["TMPDIR"]
    Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps({"transcript_path": str(tpath)}),
        capture_output=True, text=True, cwd=str(root), env=env)
    shutil.rmtree(tdir, ignore_errors=True)
    if proc.returncode != 0:
        raise AssertionError(f"hook exited {proc.returncode}: {proc.stderr}")
    out = proc.stdout.strip()
    return json.loads(out).get("reason") if out else None


def run_all(hook: Path, root: Path):
    """Returns {case_name: behaved?}, each with a fresh sentinel dir."""
    results = {}
    for name, must_fire, _clause, text in CASES_SPEC:
        shutil.rmtree(root / ".tmp", ignore_errors=True)
        try:
            reason = run_hook(hook, root, text)
        except AssertionError:
            results[name] = False
            continue
        results[name] = bool(reason) == must_fire
    return results


# --- mutation matrix --------------------------------------------------------
# (clause, exact source fragment, replacement, case that must catch it)

MUTATIONS = [
    ("min-token floor",
     "MIN_TOKENS = 4        #", "MIN_TOKENS = 1        #",
     "quote-too-short"),
    ("heading skip",
     'if prose[line_start:qs].lstrip().startswith("#"):', "if False:",
     "heading"),
    ("naming-use skip",
     "if _NAMING_RX.match(prose[qe + 1:qe + 40]):", "if False:",
     "naming-use"),
    ("paragraph-break skip",
     "if _PARA_RX.search(bridge):", "if False:",
     "paragraph-break"),
    ("bridge length bound",
     "if len(bridge) > MAX_BRIDGE:", "if False:",
     "bridge-too-long"),
    ("attribution cue",
     "if bare and not _ATTRIB_RX.search(bridge.lower()):", "if False:",
     "no-attribution-cue"),
    ("absence-claim suppressor",
     "if _ABSENCE_RX.search(window):", "if False:",
     "absence-report"),
    ("named-file presence gate",
     "if longest_ngram(tokens, hay) >= fire_floor:", "if False:",
     "snake-case-identifier"),
    # Collapsing only literal spaces leaves the source's own line wrap in
    # place, so a phrase the base carries across a newline reads as absent
    # there and present in the rationale, which is a fire.
    ("markup/whitespace normalization",
     r'_NORM_RX = re.compile(r"[`*_~\s]+")',
     r'_NORM_RX = re.compile(r"[ ]+")',
     "spans-a-line-break"),
    ("sibling find floor",
     "if longest_ngram(tokens, hay) >= find_floor:",
     "if longest_ngram(tokens, hay) >= 1:",
     "reviewer-quote-not-in-corpus"),
    ("code-fence stripping",
     "    for rx in (_FENCE_RX, _INDENTED_RX):", "    for rx in ():",
     "fenced-code"),
    ("cited name must resolve",
     "        targets = corpus.resolve(cited)",
     '        targets = corpus.resolve(cited) or corpus.resolve("pr-on-claim.md")',
     "unresolvable-filename"),
]


def mutate(source: str, old: str, new: str):
    """Return (mutant, status).  Faithfulness is asserted, not assumed."""
    n = source.count(old)
    if n != 1:
        return None, f"INAPPLICABLE (fragment occurs {n} times, expected 1)"
    mutant = source.replace(old, new, 1)
    if mutant == source:
        return None, "INAPPLICABLE (replacement left the source unchanged)"
    return mutant, None


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_corpus(root)
        hook = root / "hooks" / SUBJECT.name
        source = SUBJECT.read_text(encoding="utf-8")
        hook.write_text(source, encoding="utf-8")

        # 1. Baseline.
        base = run_all(hook, root)
        for name, ok in base.items():
            if not ok:
                want = "FIRE" if MUST_FIRE[name] else "PASS"
                failures.append(f"case {name}: expected {want}, got the opposite")
        print(f"cases: {sum(base.values())}/{len(base)} behaved")

        # 2. The reason must name BOTH files.  A bare "not found" is the
        #    invented-quote misread, so naming the sibling is the whole point.
        for idx, sibling in ((0, "pr-on-claim.rationale.md"),
                             (5, "pr-on-claim.cases.md")):
            shutil.rmtree(root / ".tmp", ignore_errors=True)
            reason = run_hook(hook, root, CASES_SPEC[idx][3]) or ""
            if sibling not in reason:
                failures.append(f"reason for {CASES_SPEC[idx][0]} does not name {sibling}")
            if "which does not contain it" not in reason:
                failures.append(f"reason for {CASES_SPEC[idx][0]} does not name the file that lacks it")

        # 3. Mutation matrix.
        if not failures:
            print("mutation matrix (each clause disabled alone):")
            unmeasured = []
            for clause, old, new, wanted in MUTATIONS:
                mutant, status = mutate(source, old, new)
                if mutant is None:
                    print(f"  {clause:28s} {status}")
                    failures.append(f"mutation '{clause}' never applied")
                    continue
                hook.write_text(mutant, encoding="utf-8")
                flipped = [n for n, ok in run_all(hook, root).items() if not ok]
                if wanted in flipped:
                    extra = [f for f in flipped if f != wanted]
                    note = f" (+ {extra})" if extra else ""
                    print(f"  {clause:28s} CAUGHT by {wanted}{note}")
                elif flipped:
                    print(f"  {clause:28s} MISSED by {wanted}; only {flipped} flipped")
                    failures.append(
                        f"clause '{clause}' is not isolated by its own case "
                        f"'{wanted}' -- {flipped} flipped instead")
                else:
                    print(f"  {clause:28s} MISSED -- no case distinguishes it")
                    unmeasured.append(clause)
            hook.write_text(source, encoding="utf-8")
            if unmeasured:
                # Reported, not deleted.  Per `algorithmatize-checks`, a zero
                # score describes the suite's coverage rather than the clause,
                # and for a GUARD a wrong deletion fails open and is silent.
                failures.append(f"measured-dead clauses: {unmeasured}")

    # 4. Live canary: the real incident still reproduces against the real files.
    base_f = REPO / "shared" / "workflow" / "pr-on-claim.md"
    sib_f = REPO / "shared" / "workflow" / "pr-on-claim.rationale.md"
    if not (base_f.is_file() and sib_f.is_file()):
        print("canary: SKIPPED -- corpus files not found")
    elif ("either way" in base_f.read_text(encoding="utf-8")
          or "nothing either way" not in sib_f.read_text(encoding="utf-8")):
        print("canary: SKIPPED -- the live corpus no longer has the incident's shape")
    else:
        with tempfile.TemporaryDirectory() as td2:
            reason = run_hook(SUBJECT, REPO, CASES_SPEC[0][3],
                              sentinels=Path(td2) / "s") or ""
            if "pr-on-claim.rationale.md" not in reason:
                failures.append("live-corpus canary: the incident did not reproduce")
            else:
                print("canary: the real incident reproduces against the real corpus")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(f"OK -- {len(CASES_SPEC)} cases, {len(MUTATIONS)} clause mutations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
