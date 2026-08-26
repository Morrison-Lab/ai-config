#!/usr/bin/env python3
"""Regression tests for check-jules-review-workflow.py.

The live workflow is one case. Each finding the checker claims to catch has
its own fixture that is otherwise valid, so deleting that finder turns the
matching test red. A check that has never been watched fail is a guess.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-jules-review-workflow.py"
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


# Otherwise-valid wrap. Each negative below changes one thing.
MINIMAL_OK = """\
name: Jules PR Review
on:
  issue_comment:
    types: [created]
jobs:
  review:
    steps:
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020
        with:
          node-version: "24"
      - id: preflight
        run: echo preflight
      - env:
          JULES_PR_REVIEWER_SHA: fc66a7c78b499bfa2e16235b55574e458c6551d6
        run: echo pin
      - run: |
          env \\
            GITHUB_EVENT_NAME=pull_request \\
            GITHUB_EVENT_PATH="$SYNTHETIC_EVENT_PATH" \\
            node "$JULES_ACTION_DIR/dist/index.js"
        env:
          INPUT_SKIP_DRAFTS: 'false'
          INPUT_RULES_FILE: ''
          INPUT_EXTRA_INSTRUCTIONS: |
            Files are written as imperative prose addressed to an AI reader.
      - if: steps.preflight.outcome == 'failure'
        run: echo could-not-start
"""


def tweak(old: str, new: str, body: str = MINIMAL_OK) -> str:
    if old not in body:
        raise AssertionError(f"fixture anchor missing: {old!r}")
    return body.replace(old, new, 1)


BROKEN_USES_WRAP = tweak(
    "    steps:\n",
    "    steps:\n      - uses: sanjay3290/jules-pr-reviewer@fc66a7c78b499bfa2e16235b55574e458c6551d6\n",
)

DROPPED_MENTION = tweak(
    "on:\n  issue_comment:\n    types: [created]\n",
    "on:\n  workflow_dispatch:\n",
)

ADDED_PULL_REQUEST = tweak(
    "on:\n  issue_comment:\n    types: [created]\n",
    "on:\n  issue_comment:\n    types: [created]\n  pull_request:\n    types: [opened]\n",
)

YAML_ONLY_EVENT_NAME = tweak(
    "            GITHUB_EVENT_NAME=pull_request \\\n",
    "",
)
YAML_ONLY_EVENT_NAME = tweak(
    "        env:\n          INPUT_SKIP_DRAFTS:",
    "        env:\n          GITHUB_EVENT_NAME: pull_request\n          INPUT_SKIP_DRAFTS:",
    YAML_ONLY_EVENT_NAME,
)

MISSING_CHILD_NAME = tweak(
    "            GITHUB_EVENT_NAME=pull_request \\\n",
    "",
)

MISSING_CHILD_PATH = tweak(
    '            GITHUB_EVENT_PATH="$SYNTHETIC_EVENT_PATH" \\\n',
    "",
)

# Prose still names dist/index.js; the node invocation is gone.
COMMENTED_ONLY_DIST = tweak(
    '            node "$JULES_ACTION_DIR/dist/index.js"\n',
    "            # start its dist/index.js under env(1)\n",
)

COMMENTED_CHILD_PATH = tweak(
    '            GITHUB_EVENT_PATH="$SYNTHETIC_EVENT_PATH" \\\n',
    '            # GITHUB_EVENT_PATH="$SYNTHETIC_EVENT_PATH" \\\n',
)

COMMENTED_SHA = tweak(
    "          JULES_PR_REVIEWER_SHA: fc66a7c78b499bfa2e16235b55574e458c6551d6\n",
    "          # JULES_PR_REVIEWER_SHA: fc66a7c78b499bfa2e16235b55574e458c6551d6\n",
)

MISSING_SHA = tweak(
    "          JULES_PR_REVIEWER_SHA: fc66a7c78b499bfa2e16235b55574e458c6551d6\n",
    "",
)

MISSING_SKIP_DRAFTS = tweak("          INPUT_SKIP_DRAFTS: 'false'\n", "")

COMMENTED_SKIP_DRAFTS = tweak(
    "          INPUT_SKIP_DRAFTS: 'false'\n",
    "          # INPUT_SKIP_DRAFTS: 'false'\n",
)

MISSING_PROSE = tweak("imperative prose", "review rules")

# Header/comment still names the phrase; extra_instructions does not.
COMMENTED_PROSE = tweak(
    "name: Jules PR Review\n",
    "name: Jules PR Review\n# corpus's own imperative prose\n",
)
COMMENTED_PROSE = tweak(
    "imperative prose addressed",
    "review rules addressed",
    COMMENTED_PROSE,
)

MISSING_SETUP_NODE = tweak(
    "      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020\n"
    '        with:\n          node-version: "24"\n',
    "",
)

# Substring still present; line-anchored finder must still fail.
COMMENTED_SETUP_NODE = tweak(
    "      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020\n"
    '        with:\n          node-version: "24"\n',
    "      # uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020\n"
    '      #   with:\n      #     node-version: "24"\n',
)

MISSING_PREFLIGHT_ID = tweak("      - id: preflight\n        run: echo preflight\n", "")

MISSING_PREFLIGHT_GATE = tweak(
    "      - if: steps.preflight.outcome == 'failure'\n        run: echo could-not-start\n",
    "",
)

# Substring still present; line-anchored finder must still fail.
COMMENTED_PREFLIGHT_GATE = tweak(
    "      - if: steps.preflight.outcome == 'failure'\n        run: echo could-not-start\n",
    "      - if: failure()\n        run: echo could-not-start\n      # steps.preflight.outcome\n",
)


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

live_text = LIVE.read_text(encoding="utf-8")
live_without_node, n_node = re.subn(
    r"^[ \t]*node[ \t].*dist/index\.js.*\n",
    "            # node dist/index.js under env(1)\n",
    live_text,
    count=1,
    flags=re.MULTILINE,
)
check("live workflow has one node dist/index.js invocation", n_node == 1)
check(
    "live workflow still names dist/index.js after stripping the invocation",
    live_without_node.count("dist/index.js") >= 2,
    f"count={live_without_node.count('dist/index.js')}",
)
case_exits(
    "live workflow without node invocation",
    live_without_node,
    1,
    "node ... dist/index.js",
)

case_exits("minimal valid wrap", MINIMAL_OK, 0)

# Unique negatives: each needle is the finding that would vanish if that
# branch of findings() were deleted.
case_exits(
    "pre-#2280 uses:+env wrap",
    BROKEN_USES_WRAP,
    1,
    "via uses:",
)
case_exits(
    "dropped mention path",
    DROPPED_MENTION,
    1,
    "issue_comment trigger",
)
case_exits(
    "automatic pull_request trigger beside mention",
    ADDED_PULL_REQUEST,
    1,
    "pull_request trigger reintroduced",
)
case_exits(
    "YAML env event name without env(1)",
    YAML_ONLY_EVENT_NAME,
    1,
    "only as YAML env",
)
case_exits(
    "missing env(1) GITHUB_EVENT_NAME",
    MISSING_CHILD_NAME,
    1,
    "GITHUB_EVENT_NAME=pull_request",
)
case_exits(
    "missing env(1) GITHUB_EVENT_PATH",
    MISSING_CHILD_PATH,
    1,
    "GITHUB_EVENT_PATH=",
)
case_exits(
    "GITHUB_EVENT_PATH only in a comment",
    COMMENTED_CHILD_PATH,
    1,
    "GITHUB_EVENT_PATH=",
)
case_exits(
    "dist/index.js only in comments",
    COMMENTED_ONLY_DIST,
    1,
    "node ... dist/index.js",
)
case_exits("missing SHA pin", MISSING_SHA, 1, "40-character pin")
case_exits("SHA pin only in a comment", COMMENTED_SHA, 1, "40-character pin")
case_exits("missing INPUT_SKIP_DRAFTS", MISSING_SKIP_DRAFTS, 1, "INPUT_SKIP_DRAFTS")
case_exits(
    "INPUT_SKIP_DRAFTS only in a comment",
    COMMENTED_SKIP_DRAFTS,
    1,
    "INPUT_SKIP_DRAFTS",
)
case_exits("missing extra_instructions prose", MISSING_PROSE, 1, "prose is content")
case_exits(
    "imperative prose only in a header comment",
    COMMENTED_PROSE,
    1,
    "prose is content",
)
case_exits("unpinned Node", MISSING_SETUP_NODE, 1, "Node is unpinned")
case_exits("Node pin only in comments", COMMENTED_SETUP_NODE, 1, "Node is unpinned")
case_exits("missing preflight step", MISSING_PREFLIGHT_ID, 1, "id: preflight")
case_exits(
    "could-not-start omits preflight",
    MISSING_PREFLIGHT_GATE,
    1,
    "steps.preflight.outcome",
)
case_exits(
    "could-not-start preflight only in a comment",
    COMMENTED_PREFLIGHT_GATE,
    1,
    "steps.preflight.outcome",
)

# Mechanism: env(1) overrides an inherited GITHUB_EVENT_NAME. This is the
# property the workflow relies on and that YAML env: on uses: does not have.
# Skip when `env` is not on PATH (Windows Python outside Git Bash).
env_bin = shutil.which("env")
if env_bin is None:
    print("SKIP: env(1) overrides inherited GITHUB_EVENT_NAME (env not on PATH)")
else:
    proc = subprocess.run(
        [
            env_bin,
            "GITHUB_EVENT_NAME=issue_comment",
            env_bin,
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
