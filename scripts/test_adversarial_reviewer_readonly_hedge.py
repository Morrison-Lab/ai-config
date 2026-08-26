#!/usr/bin/env python3
"""Pin the adversarial-reviewer Write-schema hedge (ai-config#2281).

The persona used to claim harness-enforced "no Edit or Write access" /
"can never alter code". Cursor Cloud Task still granted Write schemas to
this child (measured 2026-08-25 PDT). The declared allowlist is not a
strip on that harness; the child's job is instruction-level discipline,
and the parent briefs read-only and checks HEAD.

This script is both the mutation control and the live-file gate.
A synthetic copy of the old claim must FAIL the predicate, or a green
run against the live files is not evidence the predicate still rejects
the defect it exists to catch.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PERSONA_PATHS = (
    ROOT / ".claude" / "agents" / "adversarial-reviewer.md",
    ROOT / ".opencode" / "agents" / "adversarial-reviewer.md",
)

FORBIDDEN_ABSOLUTES = (
    "can never alter code",
    "You have no Edit or Write access",
    "with no Edit or Write access, so it can never",
)

REQUIRED_HEDGE = "still grant Write schemas"
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

passes = failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += bool(condition)
    failures += (not condition)


def persona_hedges_write_schemas(text: str) -> bool:
    """True when *text* hedges the Write-schema claim and drops the absolute."""
    lowered = text
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
    "hedged wording passes the predicate",
    persona_hedges_write_schemas(HEDGED) is True,
)

examined = 0
for path in PERSONA_PATHS:
    examined += 1
    check(f"{path.relative_to(ROOT)} exists", path.is_file())
    if not path.is_file():
        continue
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

check(f"examined {examined} persona files (expected 2)", examined == 2)

print(f"\n{passes} passed, {failures} failed; examined {examined} persona files")
raise SystemExit(1 if failures else 0)
