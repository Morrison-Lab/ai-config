#!/usr/bin/env python3
"""UserPromptSubmit reminder: a verdict read off a LOCAL sim run owes a CI cross-check.

A deterministic simulation is deterministic per (seed, platform, renderer
config) -- not across them. Sparta's own demo notes record this repeatedly: a
local run and CI's transcript agree exactly for hundreds of ticks and then
diverge, because hundreds of ticks of floating-point soldier-collision physics
compound differently on another platform.

The corpus already teaches that, and scopes it to CAPTIONS and to precise
per-tick numbers quoted into comments. What it did not say, and what this hook
exists for, is that the divergence is large enough to **invert a gating
verdict**. Measured 2026-08-22 on `demos/inputs/relief-fighting-withdrawal.json`
at one commit and one seed: `uid0 overlap worst=1.611` locally (a FAIL against
a 2.25 threshold) and `worst=2.432` on CI (a PASS). A decision was published
off the local number -- a correction of the user's own stated premise, no less
-- and the local number was the wrong one.

WHY THIS IS NOT A ONE-OFF, AND SO IS WORTH MECHANIZING
------------------------------------------------------
`shared/principles/deterministic-tools.md` sets a third-occurrence bar for
building a tool. This class is well past it, by the consumer repo's own dated
case record: the same trap is logged on PR #794 (2026-07-12), then twice more
in one session on #861 and #866 (2026-07-15, both caught by a reviewer rather
than by the author), then again on #1199 (2026-08-05). Every one of those was
about prose. The 2026-08-22 recurrence moved it into a gating verdict, which is
strictly worse: prose gets reviewed, and a verdict gets acted on.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Modeled on `remind-ums-after-error.py`, not on `no-offer-to-file.py`, and the
distinction is load-bearing.

A `Stop` guard suppresses a message that is WRONG TO SEND. A local verdict is
not wrong to send. Reporting one while diagnosing, or quoting one explicitly
labelled local, is ordinary correct work -- what is wrong is *gating a decision*
on it without corroboration, and "gating a decision" has no lexical signature.
Blocking would also demand a remedy the model cannot supply inside the turn: a
CI answer is minutes away, so a blocked reply would stall on something no edit
can satisfy.

So this fires on the next prompt and only ever adds context. There is no code
path here that can suppress, delay, or alter a message.

MECHANISM
---------
Fires when all three hold:

  1. the transcript contains a Bash call running one of the LOCAL sim/transcript
     tools (a state dump, the transcript analyzer, a catalog sweep);
  2. a LATER assistant message states a verdict-shaped claim (`worst=`,
     `N/M verdicts`, `PASS uid3`, `nnd_min`, ...);
  3. no CI-side read (`gh run view`, a `check-runs` / `issues/comments` API
     call) sits between the two.

Condition 3 is what keeps it quiet on a turn that did the right thing, and it
is why this cannot simply key on the presence of a number.

Fails OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Local tools that produce sim state or judge it, none of which involve CI.
# Deliberately specific: a bare `godot` would fire on every unit-test run,
# and the noise is what gets a guard switched off.
LOCAL_SIM_TOOL = re.compile(
    r"""(
      dump-state\.sh
    | dump-demo-states\.sh
    | analyze_transcript\.gd
    | website-demo-defect-sweep\.sh
    | website-demo-defect-delta\.sh
    | check\.sh[^\n|;&]*\bdemo_defects\b
    | SPARTA_DEMO_STATE
    )""",
    re.X,
)

# A read of what CI itself measured. `gh pr checks` is deliberately ABSENT:
# it reports check STATE, never a verdict's numbers, so treating it as
# corroboration would discharge the obligation without anyone having looked at
# a CI-side figure -- the same conflation `fully-clean.md` warns about when it
# says a green rollup is about CI state rather than review content.
CI_READ = re.compile(
    r"""(
      gh\s+run\s+view
    | gh\s+api[^\n]*check-runs
    | gh\s+api[^\n]*actions/(runs|jobs)
    | gh\s+api[^\n]*issues/comments
    | gh\s+api[^\n]*issues/\d+/comments
    | gh\s+api[^\n]*pulls/\d+/comments
    )""",
    re.X,
)

# Verdict-shaped claims. Each alternative is a SHAPE the analyzer emits, not a
# bare number, so ordinary prose about counts cannot trip it.
VERDICT_CLAIM = re.compile(
    r"""(
      \bworst\s*=
    | \bnnd_(min|med)\b
    | \b\d+\s*/\s*\d+\s+verdicts\b
    | \b(PASS|FAIL|EXEMPT|STALE)\s+uid\d+
    | \b(overlap|blob|shape_residual|misslotted|path_crossing)\s*\(\s*uid\d+
    )""",
    re.X,
)

FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)


def visible_prose(text):
    """Drop code fences and blockquotes.

    A verdict table pasted into a fence is raw tool output being shown, not a
    claim being made in the model's own voice, and quoting CI's own posted
    table is the very behaviour this hook wants to encourage. Inline code is
    deliberately KEPT, unlike in `remind-ums-after-error.py`: a verdict quoted
    in the model's prose is nearly always written as `worst=1.611`, so
    stripping backticks would blind the hook to its main case.
    """
    text = FENCE.sub(" ", text)
    return QUOTED.sub(" ", text)


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(path):
    """Return (claim_text, claim_at, local_at, ci_at).

    Indices are record positions; -1 means never seen.
    """
    claim_txt, claim_at, local_at, ci_at = None, -1, -1, -1

    for i, m in enumerate(records(path)):
        # A subagent's own turns are not my outgoing message.
        if m.get("isSidechain"):
            continue
        if m.get("type") != "assistant":
            continue
        blocks = (m.get("message") or {}).get("content") or []
        if not isinstance(blocks, list):
            continue

        for b in blocks:
            if not isinstance(b, dict):
                continue

            if b.get("type") == "text":
                # Only count a claim that FOLLOWS a local run. A verdict
                # quoted before any local tool ran came from somewhere else.
                if local_at < 0:
                    continue
                hit = VERDICT_CLAIM.search(visible_prose(b.get("text", "")))
                if hit:
                    claim_txt, claim_at = hit.group(0).strip(), i

            elif b.get("type") == "tool_use":
                if (b.get("name") or "") != "Bash":
                    continue
                inp = b.get("input") or {}
                if not isinstance(inp, dict):
                    continue
                cmd = str(inp.get("command", ""))
                if LOCAL_SIM_TOOL.search(cmd):
                    local_at = i
                if CI_READ.search(cmd):
                    ci_at = i

    return claim_txt, claim_at, local_at, ci_at


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        claim_txt, claim_at, local_at, ci_at = scan(path)
    except Exception:
        return 0

    if not claim_txt or local_at < 0:
        return 0
    # A CI read between the local run and the claim discharges it.
    if local_at <= ci_at <= claim_at:
        return 0

    key = hashlib.sha256(f"{path}:{claim_txt}:{claim_at}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-ci-crosscheck-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(
        "[hook: remind-ci-crosscheck-sim-verdict] A verdict-shaped figure "
        f"({claim_txt!r}) was stated after a LOCAL sim/transcript run, with no "
        "CI-side read in between.\n"
        "\n"
        "A deterministic sim is deterministic per (seed, platform, renderer "
        "config), not across them. Measured: the same clip, same seed, same "
        "commit read `uid0 overlap worst=1.611` locally (FAIL) and "
        "`worst=2.432` on CI (PASS) -- the divergence inverts verdicts, it "
        "does not merely shift digits.\n"
        "\n"
        "Before this figure gates anything -- removing an exemption, calling a "
        "clip clean, correcting someone's stated premise -- get CI's own "
        "number. The cheap self-test: find an `expect` assertion your change "
        "cannot have affected. If it fails locally and passes on CI, discard "
        "the local run wholesale.\n"
        "\n"
        "If the figure is only being reported as a local diagnostic, say so in "
        "the text and carry on -- this hook only ever adds context."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
