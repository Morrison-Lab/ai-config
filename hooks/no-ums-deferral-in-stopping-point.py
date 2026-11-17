#!/usr/bin/env python3
"""Stop-hook guard: a Stopping Point line must not say the UMS pass was not run.

THE MEASURED CASE (2026-11-08, Morrison-Lab project thread; ai-config#5133)
---------------------------------------------------------------------------
The gha owner thread ended several pauses with a line such as
`**Stopping Point**: Not clean; UMS not yet run`. `run-ums-proactively.md`
says to run the pass at the first pause, that a merge or clean verdict is a
trigger, and (2nd occurrence, 2026-10-29) that writing "a pass is owed" in a
stopping-point line is not a deferral. Prose failed twice; Ezra wrote
"wtf ums". `require-stopping-point.py` only checks that a declaration exists.

WHAT IT CHECKS
--------------
Any user-visible output of the current turn (reply-tool payload or assistant
text since the person last wrote), outside code fences, has a line that opens
with `Stopping Point` and says UMS was not run: "UMS not (yet) run /
executed / done / completed", "UMS pending / owed / skipped / deferred",
"UMS still to run", "will run UMS later", "no UMS". The remedy is to run the
`ums` skill now and restate the line in the past tense ("UMS executed").

Why a deny and not a reminder: no state can tell the hook the pass is not
owed, because the rule has no exemption -- every pause runs it first. Blocks
once per turn through agent_notice.stop_notice, so a session that truly
cannot run the pass (no tools) is not trapped. Fails open on any parse
trouble.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
_LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from sibling import load_sibling
except ImportError as _exc:
    print(f"no-ums-deferral-in-stopping-point: cannot load scripts/lib/sibling.py "
          f"({_exc}); not checking", file=sys.stderr)
    load_sibling = None

try:
    from agent_notice import stop_notice
except Exception:  # pragma: no cover - library missing in an odd install
    def stop_notice(payload, message, hook):  # noqa: D103
        if payload.get("stop_hook_active"):
            return json.dumps({"systemMessage": message})
        return json.dumps({"decision": "block", "reason": message, "systemMessage": message})

try:
    from fences import strip_fences
except Exception:  # pragma: no cover
    def strip_fences(text):  # noqa: D103
        return re.sub(r"```.*?```|~~~.*?~~~", " ", text, flags=re.S)

HOOK = "no-ums-deferral-in-stopping-point"

RX_LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+|\d+\.[ \t]+|#{1,6}[ \t]+)?(?:\*\*)?Stopping Point\b[^\n]*",
    re.I | re.M,
)
_UMS = r"(?:UMS|update[- ]memories(?:[- ]and[- ]skills)?|memory pass|lessons[- ]learned pass)"
_NOT = (
    r"(?:not|never|(?:has|have|had|did|do|does|was|is|are|were|wo|would|should|could|ca)n[^\w\s]t|"
    r"yet to|still to|still need(?:s|ed)? to|"
    r"pending|owed|outstanding|skipped|deferred|postponed|next|later|queued|todo)"
)
RX_DEFER = re.compile(
    r"\b" + _UMS + r"\b[^;.,\n]{0,40}?\b" + _NOT + r"\b"          # UMS not yet run
    r"|\b" + _NOT + r"\b[^;.,\n]{0,25}?\b" + _UMS + r"\b"          # not run UMS / pending UMS
    r"|\b(?:will|to|going to|should)\s+(?:be\s+)?(?:run|ran|do|done)\b[^;.\n]{0,20}\b" + _UMS + r"\b"
    r"|\bno\s+" + _UMS + r"\b",
    re.I,
)


# `turn_outputs` comes from no-park-on-tracked-blocker.py; without it the
# hook does not check (scripts/lib/sibling.py).
_PARK = None
if load_sibling is not None:
    _PARK = load_sibling(__file__, "no-park-on-tracked-blocker.py", "no_park_turn")


def find_deferral(text):
    """The first Stopping Point line saying UMS was not run, or None."""
    prose = strip_fences(text)
    for m in RX_LINE.finditer(prose):
        line = m.group().strip()
        if RX_DEFER.search(line):
            return line
    return None


MESSAGE = (
    "Your Stopping Point line says the UMS pass was not run: \"{hit}\".\n\n"
    "Standing rule (shared/workflow/run-ums-proactively.md; Ezra, 2026-11-08: "
    "\"wtf ums\"): run UMS before the pause, never list it as owed. Run the "
    "`ums` skill now: record this turn's learnings in their global home, then "
    "restate the Stopping Point line in the past tense (\"UMS executed\")."
)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    path = payload.get("transcript_path")
    turn_outputs = getattr(_PARK, "turn_outputs", None)
    if not isinstance(path, str) or turn_outputs is None:
        return 0
    text = "\n\n".join(turn_outputs(path))
    hit = find_deferral(text) if text else None
    if not hit:
        return 0
    print(stop_notice(payload, MESSAGE.format(hit=hit[:200]), HOOK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
