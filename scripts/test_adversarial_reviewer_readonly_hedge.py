#!/usr/bin/env python3
"""Pin the adversarial-reviewer Write-schema hedge (ai-config#2281).

The persona used to claim harness-enforced "no Edit or Write access" /
"can never alter code". Cursor Cloud Task still granted Write schemas to
this child (measured 2026-08-25 PDT). The declared restriction is not a
strip on that harness; the child's job is instruction-level discipline,
and the parent briefs read-only and checks HEAD.

This script is both the mutation control and the live-file gate.
Each clause of the predicate has a synthetic that fails only that clause.
A green run against the live files is not evidence unless those
synthetics still fail.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_ABSOLUTES = (
    "can never alter code",
    "you have no edit or write access",
    "with no edit or write access, so it can never",
    "can never call those tools",
)

REQUIRED_HEDGE = "still grant write schemas"
REQUIRED_DISCIPLINE = "instruction-level discipline"

# Origin/main wording as of 2026-08-26 (afaf6b66), truncated to the
# two sentences this issue names. Must keep failing the predicate.
OLD_ABSOLUTE = (
    "with no Edit or Write access, so it can never alter code "
    "and the calling session is the one that dispositions its findings.\n"
    "You have no Edit or Write access, so you cannot apply a correction, "
    "and you must not use `Bash` to work around that.\n"
    "Staying read-only on that side is instruction-level discipline "
    "rather than a harness guarantee, so it is on you.\n"
)

HEDGED = (
    "Its declared allowlist omits Edit and Write; "
    "some harnesses still grant Write schemas, so staying "
    "read-only is instruction-level discipline there rather "
    "than a harness guarantee.\n"
    "Do not apply a correction, even if this harness still grants Write.\n"
)

# Hedge added but the old absolute left in the description: the
# mixed case this pin exists to reject.
HEDGE_PLUS_OLD = HEDGED + OLD_ABSOLUTE

# Rewrite that drops the forbidden phrases and the hedge, keeping
# the discipline sentence. Fails only the REQUIRED_HEDGE clause.
NO_HEDGE = (
    "The tools list omits Edit and Write, so it cannot change a file.\n"
    "Staying read-only is instruction-level discipline rather "
    "than a harness guarantee.\n"
)

# Hedge present, discipline sentence dropped. Fails only
# the REQUIRED_DISCIPLINE clause.
HEDGE_NO_DISCIPLINE = (
    "some harnesses still grant Write schemas.\n"
    "Do not apply a correction.\n"
)

# agents.qmd's removed wording. Exercises the fourth forbidden
# needle; OLD_ABSOLUTE does not contain it.
OLD_QMD_ABSOLUTE = (
    "Every agent in this repo omits Edit and Write from its tools list, "
    "so it can never call those tools to change a file.\n"
    "Staying read-only is instruction-level discipline.\n"
)

HEDGE_PLUS_QMD_ABSOLUTE = (
    HEDGED + "so it can never call those tools to change a file.\n"
)

# One synthetic per forbidden needle, each carrying the hedge and
# the discipline sentence, so dropping any other needle still
# leaves this one able to fail.
HEDGE_PLUS_NEVER_ALTER = HEDGED + "so it can never alter code.\n"
HEDGE_PLUS_YOU_HAVE_NO = HEDGED + "You have no Edit or Write access.\n"
HEDGE_PLUS_WITH_NO = (
    HEDGED + "with no Edit or Write access, so it can never do that.\n"
)

passes = failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += bool(condition)
    failures += (not condition)


def persona_hedges_write_schemas(text: str) -> bool:
    """True when *text* hedges the Write-schema claim and drops the absolute."""
    lowered = text.lower()
    if any(needle in lowered for needle in FORBIDDEN_ABSOLUTES):
        return False
    if REQUIRED_HEDGE not in lowered:
        return False
    if REQUIRED_DISCIPLINE not in lowered:
        return False
    return True


check(
    "old absolute claim fails the predicate (negative control)",
    persona_hedges_write_schemas(OLD_ABSOLUTE) is False,
)
check(
    "hedge plus leftover absolute still fails",
    persona_hedges_write_schemas(HEDGE_PLUS_OLD) is False,
)
check(
    "rewrite with no hedge fails (REQUIRED_HEDGE control)",
    persona_hedges_write_schemas(NO_HEDGE) is False,
)
check(
    "hedge without discipline sentence fails (REQUIRED_DISCIPLINE control)",
    persona_hedges_write_schemas(HEDGE_NO_DISCIPLINE) is False,
)
check(
    "removed agents.qmd absolute fails (can never call those tools)",
    persona_hedges_write_schemas(OLD_QMD_ABSOLUTE) is False,
)
check(
    "hedge plus leftover agents.qmd absolute still fails",
    persona_hedges_write_schemas(HEDGE_PLUS_QMD_ABSOLUTE) is False,
)
check(
    "hedge plus 'can never alter code' still fails",
    persona_hedges_write_schemas(HEDGE_PLUS_NEVER_ALTER) is False,
)
check(
    "hedge plus 'You have no Edit or Write access' still fails",
    persona_hedges_write_schemas(HEDGE_PLUS_YOU_HAVE_NO) is False,
)
check(
    "hedge plus 'with no Edit or Write access, so it can never' still fails",
    persona_hedges_write_schemas(HEDGE_PLUS_WITH_NO) is False,
)
check(
    "hedged wording passes the predicate",
    persona_hedges_write_schemas(HEDGED) is True,
)

persona_paths = tuple(sorted(ROOT.glob("*/agents/adversarial-reviewer.md")))
examined = len(persona_paths)
check(
    f"derived at least 2 persona files (examined {examined})",
    examined >= 2,
)

for path in persona_paths:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT)
    check(
        f"{rel} hedges Write schemas and drops the absolute claim",
        persona_hedges_write_schemas(text),
    )
    check(
        f"{rel} still tells the child not to apply a correction",
        "Do not apply a correction" in text,
    )
    check(
        f"{rel} bans any write tool by category, not by name list",
        "Do not use any tool that writes, edits, moves, or deletes a file" in text,
    )

doc_text = (ROOT / "agents.qmd").read_text(encoding="utf-8")
check(
    "agents.qmd hedges Write schemas and drops the absolute claim",
    persona_hedges_write_schemas(doc_text),
)

print(f"\n{passes} passed, {failures} failed; examined {examined} persona files")
raise SystemExit(1 if failures else 0)
