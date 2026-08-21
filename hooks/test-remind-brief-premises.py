"""Test the remind-brief-premises hook.

Feeds the hook a PreToolUse payload for an `Agent` call and asserts it prints a
reminder for a brief that asserts corpus state without deriving it, and NOTHING
for everything else.

Three properties this suite exists to pin:

  1. It may only ADD context.
     It must never exit non-zero, never emit a `permissionDecision`, and never
     rewrite the prompt.
     A brief is right to send; only the underived premise inside it is the
     problem.
  2. Both real incidents fire, pasted in VERBATIM from the transcripts that
     produced them rather than retyped into a tidied form, per
     `shared/workflow/algorithmatize-checks.md`'s "Test the instrument against
     the incident that prompted it, verbatim".
     The odd backtick inside incident 2's quoted shell string is exactly the
     kind of thing a tidied fixture loses, and it defeated two earlier drafts
     of the matcher.
  3. Each clause of the ANDed fire condition is mutation-checked ALONE, against
     a case only that clause keeps correct.
     Reverting one clause otherwise still passes any case a sibling clause
     happens to decide.

Run:  python3 hooks/test-remind-brief-premises.py hooks/remind-brief-premises.py
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = os.path.abspath(sys.argv[1])

if not os.path.isfile(HOOK):
    sys.exit(
        f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
        "read as 'silent' on every case and print a perfect pass"
    )

spec = importlib.util.spec_from_file_location("hook_under_test", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

# --------------------------------------------------------------- the incidents
# Both pasted unaltered from the 2026-08-04 session transcripts.
#
# The source lines below pack more than one sentence, and are left that way on
# purpose. Re-wrapping them at sentence boundaries would preserve the string
# values but is exactly the tidying pass that loses a fixture's fidelity, and
# the corpus's own semantic-line-break check scopes to prose (`*.md`) rather
# than to string literals.

INCIDENT_1 = (
    "`shared/workflow/fully-clean.md` documents a reviewer-run result object "
    "with `total_cost_usd: 0` and `num_turns: 1` as the signature of a QUOTA "
    'stop. `CLAUDE.md` carries the same carve-out ("`total_cost` 0 at '
    '`num_turns` 1"). That signature is REAL but NOT UNIQUE to quota: an '
    "expired or invalid credential produces the identical shape, because in "
    "both cases the run dies at the model call having done no billable work."
)

INCIDENT_2 = (
    "I briefed a subagent asserting that `CLAUDE.md` carries a quota carve-out "
    'phrased as "`total_cost` 0 at `num_turns` 1". That was false, asserted '
    'from recollection. Verified since: `grep -n "total_cost\\|num_turns" '
    "CLAUDE.md` returns nothing, and `grep -rn 'total_cost` 0 at' "
    "--include='*.md' .` returns exactly one tracked hit, "
    "`shared/workflow/fully-clean.md:651`. `CLAUDE.md`'s five quota mentions "
    "all concern an explicit bot *comment* (`Claude review skipped --- API "
    "quota exhausted`), which is a stated signal rather than an inference from "
    "a zero cost. Re-run both greps yourself."
)

# --------------------------------------------------------------- transcripts


def tool(name, inp, tid="t1"):
    return {"type": "assistant", "isSidechain": False,
            "message": {"content": [
                {"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def result(out, tid="t1", is_error=False):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid,
         "content": out, "is_error": is_error}]}}


def transcript(recs):
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    return p


# `grep -n` LISTS lines; it does not COUNT them. This is the transcript state
# incident 2 was actually launched from, and the distinction is the reason it
# still fires.
GREP_N = [tool("Bash", {"command": 'grep -n "total_cost\\|num_turns" CLAUDE.md'}),
          result("927:...\n931:...\n932:...\n946:...")]
GREP_C = [tool("Bash", {"command": "grep -ci quota CLAUDE.md"}), result("6")]

# --------------------------------------------------------------- corpus cases

REMIND = [
    (INCIDENT_1, None, "incident 1, verbatim: CLAUDE.md carries a carve-out it does not"),
    (INCIDENT_2, GREP_N,
     "incident 2, verbatim: a COUNT claim, with only a line-listing grep behind it"),
    ("`shared/workflow/ardi.md` covers a fix that never reached the PR's head.",
     None, "a bare coverage assertion"),
    ("`memories/github.md` does not mention the rate-limit pool at all.", None,
     "a negative content assertion"),
    ("`shared/workflow/metacognitive-monitoring.md`'s four claim types are the frame.",
     None, "possessive cardinality"),
    ("There are three sites in `hooks/no-unreviewed-pr.py` that discharge.", None,
     "prepositional cardinality"),
    (INCIDENT_2, None, "incident 2 with no transcript at all"),

    # Round 1 review findings, each reproduced from the reviewer's own repro.
    # All four discharge-side ones are SILENT false negatives, which is the
    # dangerous direction: a guard that goes quiet looks exactly like a corpus
    # where nobody asserts anything.
    ("`skills/ardi/SKILL.md` carries a step requiring a claim comment first.\n"
     "Unrelated check: `grep -n paws skills/gip/SKILL.md`.\n", None,
     "R1: a same-BASENAME derivation must not discharge another file's claim"),
    ("`CLAUDE.md` carries the rule that a phrase grep returning nothing is "
     "not evidence.", None,
     "R1: the bare word 'grep' in PROSE is not a derivation"),
    ("`CLAUDE.md` carries a pointer to `shared/workflow/grep-is-not-coverage.md`.",
     None, "R1: a filename containing 'grep' is not a derivation"),
    ("Update the changelog, since `CLAUDE.md` carries a quota carve-out.", None,
     "R1: an imperative governing a DIFFERENT clause must not suppress"),
    ("Land the fix; `CLAUDE.md` carries a quota carve-out.", None,
     "R1: same, across a semicolon"),
    ("`CLAUDE.md` has 1200 lines of guidance.\n`grep -n quota CLAUDE.md`\n",
     None, "R1: a 4-digit count is still a COUNT, so a plain grep cannot clear it"),

    # Round 3 finding: the R2 fallback window skipped `;` along with `,`, so an
    # aside-interrupted imperative reached across an independent clause and
    # silently discharged a claim it had nothing to do with.
    ("Verify, before merging, that the branch is synced; "
     "`shared/workflow/ardi.md` covers the merged-PR case.", None,
     "R3: an aside must not reach across a semicolon"),
    ("Verify, before merging, that CI passes; "
     "`CLAUDE.md` carries a quota carve-out.", None,
     "R3: same, with the docstring's own wording"),
    ("Before merging, that the branch is synced; "
     "`shared/workflow/ardi.md` covers the merged-PR case.", None,
     "R3 control: no leading aside, so nothing could have governed it anyway"),

    # Round 4 finding: `imperative_governs`'s docstring named this as a
    # residual it still misses. It fires -- the verb reaches its object before
    # the comma, so the fallback correctly declines. Pinned as a case so the
    # docstring cannot drift from the behaviour again.
    ("Verify the changelog, before merging, since `CLAUDE.md` carries X.", None,
     "R4: an imperative with a COMPLETE object does not govern a later clause"),
]

SILENT = [
    ("Read `CLAUDE.md` and follow it.", None, "a bare mention, no assertion"),
    ("Work in the ai-config repo and open a PR when the tests pass.", None,
     "no corpus path at all"),
    ("Three sites need fixing before this ships.", None,
     "a count with no path to attach it to"),
    ("Verify that `CLAUDE.md` carries the quota carve-out before using it.",
     None, "imperative: the brief already asks for the check"),
    ("Update `shared/workflow/ardi.md` so it covers the merged-PR case.", None,
     "imperative: an instruction to edit, not a claim about content"),
    ("(see `shared/workflow/challenge-redundant-content.md` and "
     "`shared/workflow/grep-is-not-coverage.md` -- and note that a phrase grep "
     "returning nothing is NOT evidence)", None,
     "a citation whose next verb belongs to the reader, not the file"),
    (INCIDENT_1, [tool("Bash", {"command": "grep -n carve-out CLAUDE.md "
                                "shared/workflow/fully-clean.md"}),
                  result("651: ... the quota case ...")],
     "content claims discharged by an in-session grep"),
    ("`CLAUDE.md`'s five quota mentions all concern a bot comment.", GREP_C,
     "a COUNT claim discharged by a COUNTING command"),
    ("`CLAUDE.md` carries the carve-out.\n"
     "Derived just now: `grep -n carve-out CLAUDE.md`.", None,
     "discharged by a command pasted beside the claim"),
    ("The `hooks/` directory holds the guards; `scripts/install-hooks.py` "
     "registers them.", None, "paths named with no assertion about contents"),

    # Controls for the round 1 findings: the same shapes where the discharge
    # SHOULD fire. Without these, the fixes above could have been "never
    # discharge anything", which passes every REMIND case and guards nothing.
    ("`skills/ardi/SKILL.md` carries a step requiring a claim comment.\n"
     "Derived: `grep -n paws skills/ardi/SKILL.md`.\n", None,
     "R1 control: the SAME file's derivation still discharges"),
    ("`CLAUDE.md` carries the carve-out.\nDerived: `grep -n carve-out CLAUDE.md`",
     None, "R1 control: a grep in a CODE span still discharges"),
    ("Update `shared/workflow/ardi.md` so it covers the merged-PR case.", None,
     "R1 control: an imperative on the claim's OWN object still suppresses"),
    ("context\n\n\n\n\n\n\n> a quoted requirement\n"
     "`CLAUDE.md` carries a quota carve-out.\n"
     "`grep -n quota CLAUDE.md`\n", None,
     "R1: blank lines before a blockquote must not drift the claim's line"),

    # Round 2 finding: the R1 comma fix clipped the imperative verb out of the
    # window whenever an aside interrupted it and its object, so a brief that
    # already asks for the check got reminded to ask for it.
    ("Verify, before merging, that `CLAUDE.md` carries the rule.", None,
     "R2: a comma-set-off aside must not defeat the imperative guard"),
    ("Check, if unsure, whether `CLAUDE.md` carries the rule.", None,
     "R2: same, with a different aside"),

    # The accepted residual, pinned deliberately rather than left to prose.
    # The fallback must skip commas to reach back over an aside at all, so it
    # cannot tell a comma-joined clause from the aside's own comma. A
    # semicolon there IS caught (see the R3 cases under REMIND). If this case
    # ever starts firing, that is a behaviour change to argue for, not a bug
    # fix to land quietly.
    ("Verify, before merging, that CI passes, and `CLAUDE.md` carries a "
     "quota carve-out.", None,
     "R4: accepted residual -- an aside cannot reach across a comma-joined clause"),
]

# ------------------------------------------------------------------- runner


def run(prompt, recs, sentinel_dir=None, tool_name="Agent"):
    """Run the hook as a subprocess and return 'REMIND' or 'silent'."""
    tpath = transcript(recs) if recs else None
    own = sentinel_dir is None
    if own:
        sentinel_dir = tempfile.mkdtemp()
    if tool_name == "SendMessage":
        # Derived from the tool's own schema, not assumed to match `prompt`:
        # SendMessage carries its brief in `message`, beside a `to`.
        tool_input = {"to": "worker", "message": prompt}
    else:
        tool_input = {"prompt": prompt, "subagent_type": "general-purpose"}
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    if tpath:
        payload["transcript_path"] = tpath
    try:
        p = subprocess.run(["python3", HOOK], input=json.dumps(payload),
                           capture_output=True, text=True,
                           env=dict(os.environ, TMPDIR=sentinel_dir))
    finally:
        if tpath:
            os.unlink(tpath)
        if own:
            shutil.rmtree(sentinel_dir, ignore_errors=True)

    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode}\n{p.stderr.strip()}")
    if not p.stdout.strip():
        return "silent"
    out = json.loads(p.stdout)
    if "permissionDecision" in json.dumps(out):
        sys.exit("FATAL: hook emitted a permissionDecision. It must only ever "
                 f"add context, never decide permission.\n{p.stdout}")
    ctx = out["hookSpecificOutput"]["additionalContext"]
    if prompt.strip() and prompt.strip()[:40] in json.dumps(out):
        sys.exit("FATAL: hook echoed the prompt back; it must never rewrite it.")
    assert ctx.strip(), "empty additionalContext"
    return "REMIND"


wrong = 0
print("should REMIND:")
for prompt, recs, desc in REMIND:
    v = run(prompt, recs)
    wrong += v != "REMIND"
    print(f"  {v:<7} {desc}")

print("\nshould stay SILENT:")
for prompt, recs, desc in SILENT:
    v = run(prompt, recs)
    wrong += v != "silent"
    print(f"  {v:<7} {desc}")

# ----------------------------------------------------------- contract checks
print("\ncontract:")
CONTRACT = [
    (run(INCIDENT_1, None, tool_name="Bash"), "silent", "not an Agent call"),
    (run("", None), "silent", "empty prompt"),
]
for got, want, desc in CONTRACT:
    wrong += got != want
    print(f"  {got:<7} {desc}")

# A malformed payload must fail OPEN and silent rather than break the launch.
p = subprocess.run(["python3", HOOK], input="not json at all",
                   capture_output=True, text=True)
ok = p.returncode == 0 and not p.stdout.strip()
wrong += not ok
print(f"  {'silent' if ok else 'BROKE':<7} malformed payload fails open")

# ------------------------------------------------------------ sentinel scope
print("\nsentinel (one shared dir):")
shared = tempfile.mkdtemp()
try:
    seq = [
        (run(INCIDENT_1, None, shared), "REMIND", "first launch"),
        (run(INCIDENT_1, None, shared), "silent", "same claims again -- fires once"),
        (run("`shared/workflow/ardi.md` covers the merged-PR case.", None, shared),
         "REMIND", "a DIFFERENT claim is not suppressed by it"),
    ]
finally:
    shutil.rmtree(shared, ignore_errors=True)
for got, want, desc in seq:
    wrong += got != want
    print(f"  {got:<7} {desc}")

# ------------------------------------------------------------- SendMessage
#
# The channel the guard did not cover until 2026-08-20. A follow-up message to
# a running agent is where corrections and NEW premises land, so it is the
# higher-risk brief, and it was the unguarded one.
#
# The false-positive direction is weighted deliberately here. This hook only
# warns, so a miss costs one unverified premise, while a warn on every routine
# ping gets the whole guard tuned out -- which is why ordinary traffic
# outnumbers the firing cases below.
print("\nSendMessage (the follow-up-brief channel):")

# Text known to fire on its own; reused as the protocol dict's `reason` so
# that case can discriminate a stringifying mutant.
PROTOCOL_REASON = "`shared/workflow/ardi.md` covers the merged-PR case."

SM_REMIND = [
    (INCIDENT_1, "a corpus-state claim sent as a follow-up message"),
    ("Correction to my last message: `shared/workflow/fully-clean.md` "
     "already documents the three-valued exit status, so drop that half.",
     "a CORRECTION carrying a fresh underived premise"),
]

# Ordinary coordination traffic. None of it asserts corpus state, and the
# guard must stay silent on all of it.
SM_SILENT = [
    ("Status ping -- where are you on the PR?", "a status ping"),
    ("Stop what you are doing and report back.", "a stop-and-report"),
    ("Thanks, that is exactly what I needed.", "a thank-you"),
    ("Nice catch on the contradiction. Ship it.", "an acknowledgement"),
    ("Please also request Copilot on that PR when you get a chance.",
     "a plain instruction naming no file"),
    ("Two more things after this one: rerun the tests, then push.",
     "a queued-work note"),
    ("I ran `grep -c quota CLAUDE.md` and got 6, so use 6 not 5.",
     "a claim that PASTES its own deriving command"),
]

for prompt, desc in SM_REMIND:
    v = run(prompt, None, tool_name="SendMessage")
    wrong += v != "REMIND"
    print(f"  {v:<7} {desc}")
for prompt, desc in SM_SILENT:
    v = run(prompt, None, tool_name="SendMessage")
    wrong += v != "silent"
    print(f"  {v:<7} {desc}")

# A protocol message is a dict, not prose, and must fail open and silent rather
# than reach `evaluate` as a stringified dict.
#
# Two things make this case discriminate, and it pinned NOTHING without both:
#   - `reason` carries text that genuinely fires as a plain string, so a mutant
#     that stringifies the dict has something to fire on.
#   - a FRESH TMPDIR. A nonexistent TMPDIR silently falls back to /tmp, where
#     the sentinel from an earlier identical claim suppresses the second run --
#     which reads as the mutant being caught when nothing ran.
_pd = tempfile.mkdtemp()
try:
    proto = subprocess.run(
        ["python3", HOOK],
        input=json.dumps({"tool_name": "SendMessage",
                          "tool_input": {"to": "lead", "message": {
                              "type": "shutdown_request",
                              "reason": PROTOCOL_REASON}}}),
        capture_output=True, text=True, env=dict(os.environ, TMPDIR=_pd))
finally:
    shutil.rmtree(_pd, ignore_errors=True)
ok = proto.returncode == 0 and not proto.stdout.strip()
wrong += not ok
print(f"  {'silent' if ok else 'BROKE':<7} a protocol dict message is not prose")
SM_EXTRA = 1

# Guard the guard: if PROTOCOL_REASON ever stops firing on its own, the case
# above passes for the wrong reason and silently stops testing anything.
_ctl = run(PROTOCOL_REASON, None, tool_name="SendMessage")
wrong += _ctl != "REMIND"
print(f"  {_ctl:<7} control: that same text DOES fire as a plain string")
SM_EXTRA += 1

# Registration is half the coverage: widening BRIEF_TOOLS without widening
# hooks.json's matcher would leave every case above unreachable in production.
# Assert the binding itself, so the suite cannot pass on a guard nothing calls.
# Resolved from THIS FILE, not from HOOK: a mutation run passes a temp copy as
# HOOK, and pathing off it crashed the suite for a reason unrelated to the
# mutant -- which reads as the mutant being caught when it is not.
_hj = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "hooks.json"), encoding="utf-8"))
_matchers = [e.get("matcher", "") for e in _hj["hooks"].get("PreToolUse", [])
             if any("remind-brief-premises" in json.dumps(h)
                    for h in e.get("hooks", []))]
# One group per matcher is this repo's convention (check-hook-catalog.py joins
# them for README), so aggregate ACROSS groups rather than per group.
reg_ok = set(_matchers) >= {"Agent", "Task", "SendMessage"}
wrong += not reg_ok
print(f"  {'ok    ' if reg_ok else 'WRONG '} hooks.json matcher covers all of "
      f"BRIEF_TOOLS (got {_matchers})")
SM_EXTRA += 1

# --------------------------------------------------- clause-isolation mutants
#
# Each mutant reverts exactly ONE clause of the fire condition, and each is
# paired with a case that ONLY that clause decides. A mutant that changes
# nothing means its clause is untested, which is the failure
# `algorithmatize-checks` warns an ANDed condition hides.
print("\nmutation checks (each must flip its own isolating case):")


def fires(prompt, recs=None):
    tpath = transcript(recs) if recs else ""
    try:
        return bool(hook.evaluate(prompt, tpath))
    finally:
        if tpath:
            os.unlink(tpath)


def kinds(prompt):
    return [k for k, _ in hook.evaluate(prompt, "")]


MUTANTS = [
    ("clause A: the path matcher",
     "PATH", re.compile(r"(?<![\w./-])(zzz-never-matches)"),
     lambda: fires("`shared/workflow/ardi.md` covers the merged-PR case."),
     True, False),

    ("clause B: the content-verb matcher",
     "VERB", r"zzz-never-matches",
     lambda: fires("`shared/workflow/ardi.md` covers the merged-PR case."),
     True, False),

    ("clause B: the cardinality noun rule",
     "COUNT", r"zzz-never-matches",
     lambda: fires("There are three sites in `hooks/no-unreviewed-pr.py`."),
     True, False),

    ("the imperative guard",
     "IMPERATIVE", re.compile(r"zzz-never-matches"),
     lambda: fires("Verify that `CLAUDE.md` carries the quota carve-out."),
     False, True),

    # Both of incident 1's paths must be covered, or the surviving claim keeps
    # the case firing and the mutant flips nothing -- which would look like a
    # tested clause while testing none.
    ("discharge: content, from the transcript",
     "DERIVE_ANY", re.compile(r"zzz-never-matches"),
     lambda: fires(INCIDENT_1,
                   [tool("Bash", {"command": "grep -n carve-out CLAUDE.md "
                                  "shared/workflow/fully-clean.md"}),
                    result("651: ...")]),
     False, True),

    ("discharge: a COUNT needs a COUNTING command",
     "DERIVE_COUNT", re.compile(r"\bzzz\b"),
     lambda: fires("`CLAUDE.md`'s five quota mentions all concern a bot comment.",
                   GREP_C),
     False, True),

    ("discharge: proximity of an in-brief derivation",
     "NEAR_LINES", 10 ** 6,
     lambda: fires("`shared/workflow/ardi.md` covers the merged-PR case.\n"
                   + "\n" * 40
                   + "Unrelated: `grep -n foo shared/workflow/ardi.md`."),
     True, False),

    ("identifiers are not plural nouns (claim KIND, not fire/silent)",
     "NOT_A_NOUN", re.compile(r"zzz-never-matches"),
     lambda: kinds(INCIDENT_1) == ["cardinality", "cardinality"],
     False, True),

    ("discharge key is the full path, not the basename",
     "key_for", staticmethod(lambda p: __import__("os").path.basename(p)),
     lambda: fires("`skills/ardi/SKILL.md` carries a step requiring a claim.\n"
                   "Unrelated: `grep -n paws skills/gip/SKILL.md`.\n"),
     True, False),

    ("an in-brief derivation must sit in a CODE span, not prose",
     "code_segments",
     staticmethod(lambda prompt: enumerate(prompt.splitlines())),
     lambda: fires("`CLAUDE.md` carries the rule that a phrase grep returning "
                   "nothing is not evidence."),
     True, False),

    # The R2 fix must not silently undo the R1 one: reverting to the
    # clause-only window has to flip the aside case and ONLY that case, and
    # the R1 compound-sentence case is asserted above under `REMIND`.
    ("an aside between an imperative and its object still suppresses",
     "imperative_governs",
     staticmethod(lambda text, pos, upto: bool(
         hook.IMPERATIVE.match(text[hook.segment_start(text, pos):upto]))),
     lambda: fires("Verify, before merging, that `CLAUDE.md` carries the rule."),
     False, True),

    ("an aside must not reach across a semicolon",
     "SENTENCE_BOUNDS", r"(?:\n|(?<=[.!?:])\s)",
     lambda: fires("Verify, before merging, that CI passes; "
                   "`CLAUDE.md` carries a quota carve-out."),
     True, False),

    ("tool_result must carry output",
     "_none_", None,
     lambda: fires(INCIDENT_1,
                   [tool("Bash", {"command": "grep -n carve-out CLAUDE.md"}),
                    result("   ")]),
     True, True),
]

for desc, attr, mutant, probe, want_before, want_after in MUTANTS:
    before = probe()
    if attr == "_none_":
        after = before  # no mutant: this row asserts a standing property
    else:
        original = getattr(hook, attr)
        setattr(hook, attr, mutant)
        try:
            after = probe()
        finally:
            setattr(hook, attr, original)
    ok = before == want_before and after == want_after
    wrong += not ok
    flip = "" if attr == "_none_" else f" -> {after}"
    print(f"  {'ok   ' if ok else 'WRONG'}  {desc}: {before}{flip}")

# A property, not another example. Round 3's leak was one missing character in
# a regex, and no by-example suite is obliged to notice one -- so assert the
# invariant the two windows are supposed to hold instead of adding a case and
# hoping the next omission looks like this one.
print("\nsegment-boundary invariant:")
diff = set(hook.CLAUSE_BOUNDS) ^ set(hook.SENTENCE_BOUNDS)
ok = diff == {","}
wrong += not ok
print(f"  {'ok   ' if ok else 'WRONG'}  the two windows differ by exactly ',' (got {diff or 'nothing'})")

total = (1 + len(REMIND) + len(SILENT) + len(CONTRACT) + 1 + len(seq)
         + len(SM_REMIND) + len(SM_SILENT) + SM_EXTRA + len(MUTANTS))
print(f"\n{total - wrong}/{total} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
