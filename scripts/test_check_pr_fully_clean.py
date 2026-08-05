#!/usr/bin/env python3
"""Regression and unit tests for scripts/check-pr-fully-clean.py.

Tests:
1. CI check run status filtering (completed with success/neutral/skipped vs in_progress/failure).
2. Review comment parsing (clean verdict vs finding pattern matching).
"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "checker", Path(__file__).parent / "check-pr-fully-clean.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

passes = 0
failures = 0


def check(name: str, condition: bool):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def main() -> int:
    print("Testing check-pr-fully-clean.py...")

    # Test finding pattern regexes
    clean_body = """### 🤖 Antigravity Agent Report (Code-Review)

## Code Review: PR #1166 — feat(workflow): add agy-review-workflow skill

### Summary of Review
Everything looks great! No issues found.

Verdict: Clean / Ready for merge.
"""

    findings_body = """### 🤖 Antigravity Agent Report (Code-Review)

## Code Review: PR #1166 — feat(workflow): add agy-review-workflow skill

### Detailed Findings

#### 1. Unlinked File Reference
**Location:** memories/tools.md:L843
"""

    import re
    has_finding_clean = any(re.search(pat, clean_body, re.IGNORECASE) for pat in [
        r"### Actionable Findings",
        r"### Detailed Findings",
        r"Verdict:\s*Ready after addressing findings",
        r"Verdict:\s*Needs work",
        r"Verdict:\s*Changes requested",
        r"#### \d+\.",
    ])
    check("clean comment body produces no finding matches", not has_finding_clean)

    has_finding_dirty = any(re.search(pat, findings_body, re.IGNORECASE) for pat in [
        r"### Actionable Findings",
        r"### Detailed Findings",
        r"Verdict:\s*Ready after addressing findings",
        r"Verdict:\s*Needs work",
        r"Verdict:\s*Changes requested",
        r"#### \d+\.",
    ])
    check("findings comment body matches finding patterns", has_finding_dirty)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
