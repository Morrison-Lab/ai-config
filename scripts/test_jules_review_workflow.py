#!/usr/bin/env python3
"""Regression tests for check_jules_review_workflow.py.

The live workflow is one case. The cases that matter are the negatives: the
pre-#2280 wrap (uses: plus YAML env) must fail, dropping the mention path
must fail, and a check that has never been watched fail is a guess.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check_jules_review_workflow.py"
ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / ".github" / "workflows" / "jules-review.yml"

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {extra}")
        failures += 1


def run_check(workflow: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(workflow)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout + proc.stderr


BROKEN_USES_WRAP = """\
name: Jules PR Review
on:
  issue_comment:
    types: [created]
jobs:
  review:
    steps:
      - name: Run Jules PR Reviewer
        env:
          GITHUB_EVENT_NAME: pull_request
          GITHUB_EVENT_PATH: /tmp/pull_request_event.json
        uses: sanjay3290/jules-pr-reviewer@fc66a7c78b499bfa2e16235b55574e458c6551d6
        with:
          extra_instructions: |
            Files are written as imperative prose addressed to an AI reader.
"""

DROPPED_MENTION = """\
name: Jules PR Review
on:
  pull_request:
    types: [opened]
jobs:
  review:
    steps:
      - run: |
          env \\
            GITHUB_EVENT_NAME=pull_request \\
            node /tmp/jules-pr-reviewer/dist/index.js
        env:
          JULES_PR_REVIEWER_SHA: fc66a7c78b499bfa2e16235b55574e458c6551d6
          INPUT_SKIP_DRAFTS: 'false'
          INPUT_EXTRA_INSTRUCTIONS: |
            Files are written as imperative prose addressed to an AI reader.
"""

MISSING_CHILD_OVERRIDE = """\
name: Jules PR Review
on:
  issue_comment:
    types: [created]
jobs:
  review:
    steps:
      - run: node /tmp/jules-pr-reviewer/dist/index.js
        env:
          JULES_PR_REVIEWER_SHA: fc66a7c78b499bfa2e16235b55574e458c6551d6
          INPUT_SKIP_DRAFTS: 'false'
          INPUT_EXTRA_INSTRUCTIONS: |
            Files are written as imperative prose addressed to an AI reader.
"""

MINIMAL_OK = """\
name: Jules PR Review
on:
  issue_comment:
    types: [created]
jobs:
  review:
    steps:
      - env:
          JULES_PR_REVIEWER_SHA: fc66a7c78b499bfa2e16235b55574e458c6551d6
        run: echo pin
      - run: |
          env \\
            GITHUB_EVENT_NAME=pull_request \\
            node "$JULES_ACTION_DIR/dist/index.js"
        env:
          INPUT_SKIP_DRAFTS: 'false'
          INPUT_EXTRA_INSTRUCTIONS: |
            Files are written as imperative prose addressed to an AI reader.
"""


def write_fixture(tmpdir: str, body: str) -> Path:
    path = Path(tmpdir) / "jules-review.yml"
    path.write_text(body, encoding="utf-8")
    return path


def case_exits(name: str, body: str, expect: int, needle: str | None = None) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_fixture(tmpdir, body)
        code, output = run_check(path)
    check(f"{name}: exit {expect}", code == expect, f"got {code}\n{output}")
    if needle is not None:
        check(f"{name}: mentions {needle!r}", needle in output, output)


# Live file must pass through the same entry point CI will run.
check("live workflow exists", LIVE.is_file())
live_code, live_out = run_check(LIVE)
check("live workflow is clean", live_code == 0, live_out)

# Negative controls: each defect the check claims to catch.
case_exits(
    "pre-#2280 uses:+env wrap",
    BROKEN_USES_WRAP,
    1,
    "uses:",
)
case_exits(
    "dropped mention path",
    DROPPED_MENTION,
    1,
    "issue_comment",
)
case_exits(
    "missing env(1) child override",
    MISSING_CHILD_OVERRIDE,
    1,
    "GITHUB_EVENT_NAME=pull_request",
)

# Positive control: a minimal fixture that is not the live file, so a checker
# that only special-cases the real path cannot hide here.
case_exits("minimal valid wrap", MINIMAL_OK, 0)

# Mechanism: env(1) overrides an inherited GITHUB_EVENT_NAME. This is the
# property the workflow relies on and that YAML env: on uses: does not have.
proc = subprocess.run(
    [
        "env",
        "GITHUB_EVENT_NAME=issue_comment",
        "env",
        "GITHUB_EVENT_NAME=pull_request",
        sys.executable,
        "-c",
        "import os; assert os.environ['GITHUB_EVENT_NAME'] == 'pull_request'",
    ],
    capture_output=True,
    text=True,
    env=os.environ | {"GITHUB_EVENT_NAME": "issue_comment"},
)
check(
    "env(1) overrides inherited GITHUB_EVENT_NAME",
    proc.returncode == 0,
    proc.stdout + proc.stderr,
)

# Missing workflow is a usage error, not a clean pass.
missing_code, missing_out = run_check(ROOT / "no-such-jules-review.yml")
check("missing file exits 2", missing_code == 2, missing_out)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
