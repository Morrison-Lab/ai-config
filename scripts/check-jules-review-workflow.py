#!/usr/bin/env python3
"""Gate the Jules mention-dispatch wrap against the failure in ai-config#2280.

`.github/workflows/jules-review.yml` exists to run Jules from an `@jules`
comment. The action it invokes (`sanjay3290/jules-pr-reviewer`) refuses every
event except `pull_request`. A step `env:` block that sets `GITHUB_EVENT_NAME`
on a `uses:` step looks like a wrap and is a no-op: GitHub ignores reserved
`GITHUB_*` assignments, measured 2026-08-26 on run 32942088643.

This check fails if the mention path is dropped, if automatic `pull_request`
reviews are reintroduced, if the action is invoked via `uses:` again, or if
the child-process `env(1)` override of event name *or* event path is missing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "jules-review.yml"
USES_ACTION_RE = re.compile(r"uses:\s*sanjay3290/jules-pr-reviewer@")
CHILD_EVENT_NAME_RE = re.compile(
    r"^[ \t]*GITHUB_EVENT_NAME=pull_request[ \t]*\\?\s*$",
    re.MULTILINE,
)
CHILD_EVENT_PATH_RE = re.compile(
    r"^[ \t]*GITHUB_EVENT_PATH=",
    re.MULTILINE,
)
YAML_EVENT_NAME_RE = re.compile(
    r"^[ \t]*GITHUB_EVENT_NAME:\s*pull_request\s*$",
    re.MULTILINE,
)
NODE_INVOCATION_RE = re.compile(
    r"^[ \t]*node[ \t].*dist/index\.js",
    re.MULTILINE,
)
SHA_PIN_RE = re.compile(
    r"^[ \t]*JULES_PR_REVIEWER_SHA:\s*[0-9a-f]{40}\s*$",
    re.MULTILINE,
)
SETUP_NODE_RE = re.compile(
    r"^[ \t]*(?:-\s+)?uses:\s*actions/setup-node@",
    re.MULTILINE,
)
NODE_VERSION_RE = re.compile(
    r"^[ \t]*node-version:\s*['\"]24['\"]",
    re.MULTILINE,
)
PREFLIGHT_ID_RE = re.compile(
    r"^[ \t]*(?:-\s+)?id:\s*preflight\s*$",
    re.MULTILINE,
)
SUCCESS_GATE_RE = re.compile(
    r"^[ \t]*(?:-\s+)?(?:if:\s+)?success\(\)",
    re.MULTILINE,
)
PREFLIGHT_OUTCOME_RE = re.compile(
    r"^[ \t]*(?:-\s+)?(?:if:\s+)?steps\.preflight\.outcome",
    re.MULTILINE,
)


def extra_instructions_block(text: str) -> str:
    """The YAML block scalar under INPUT_EXTRA_INSTRUCTIONS, not the rest of the file."""
    match = re.search(
        r"^([ \t]*)INPUT_EXTRA_INSTRUCTIONS:\s*\|\n",
        text,
        re.MULTILINE,
    )
    if not match:
        return ""
    indent = match.group(1)
    lines: list[str] = []
    for line in text[match.end() :].splitlines(keepends=True):
        if line.strip() == "":
            lines.append(line)
            continue
        if line.startswith(indent) and line[len(indent) : len(indent) + 1] in " \t":
            lines.append(line)
            continue
        break
    return "".join(lines)


def pre_jobs(text: str) -> str:
    """Trigger and concurrency only --- comments here can mention pull_request."""
    return text.split("\njobs:", 1)[0]


def on_block(text: str) -> str:
    """Indented body of the top-level `on:` mapping, or empty."""
    match = re.search(r"^on:\n((?:[ \t].*\n)*)", pre_jobs(text), re.MULTILINE)
    return match.group(1) if match else ""


def findings(text: str) -> list[str]:
    out: list[str] = []
    block = on_block(text)
    header = pre_jobs(text)
    if "issue_comment:" not in block and not re.search(
        r"^on:\s*issue_comment:", header, re.MULTILINE
    ):
        out.append("mention path dropped: workflow has no issue_comment trigger")
    if re.search(r"^on:\s*pull_request:", header, re.MULTILINE) or re.search(
        r"^  pull_request:", block, re.MULTILINE
    ):
        out.append(
            "automatic pull_request trigger reintroduced; mention path is the point"
        )
    if USES_ACTION_RE.search(text):
        out.append(
            "invokes sanjay3290/jules-pr-reviewer via uses:; "
            "GITHUB_* env on a uses: step is ignored"
        )
    if YAML_EVENT_NAME_RE.search(text) and not CHILD_EVENT_NAME_RE.search(text):
        out.append(
            "GITHUB_EVENT_NAME is set only as YAML env (ignored on uses: steps); "
            "need env(1) GITHUB_EVENT_NAME=pull_request on the node child"
        )
    elif not CHILD_EVENT_NAME_RE.search(text):
        out.append(
            "missing child-process override: env GITHUB_EVENT_NAME=pull_request"
        )
    if not CHILD_EVENT_PATH_RE.search(text):
        out.append(
            "missing child-process override: env GITHUB_EVENT_PATH= "
            "(without it, eventName is pull_request but the payload is still "
            "issue_comment)"
        )
    if not NODE_INVOCATION_RE.search(text):
        out.append(
            "does not run the pinned action's dist/index.js "
            "(need a `node ... dist/index.js` invocation, not a comment)"
        )
    if not SHA_PIN_RE.search(text):
        out.append("missing 40-character pin for sanjay3290/jules-pr-reviewer")
    if not re.search(
        r"^[ \t]*INPUT_SKIP_DRAFTS:\s*'false'", text, re.MULTILINE
    ):
        out.append(
            "INPUT_SKIP_DRAFTS is not 'false'; a mention on a draft would skip"
        )
    if "imperative prose" not in extra_instructions_block(text):
        out.append("missing extra_instructions that this corpus's prose is content")
    if not SETUP_NODE_RE.search(text) or not NODE_VERSION_RE.search(text):
        out.append(
            "Node is unpinned; GitHub forced this action onto Node 24 "
            "(run 32942088643), so the wrap needs actions/setup-node "
            "with node-version 24"
        )
    if not PREFLIGHT_ID_RE.search(text):
        out.append(
            "missing preflight step (id: preflight) for wrap inputs before node"
        )
    if not SUCCESS_GATE_RE.search(text):
        out.append(
            "wrap steps do not require success(); an explicit if: replaces "
            "the default and a failed pin would still spawn node"
        )
    if not PREFLIGHT_OUTCOME_RE.search(text):
        out.append(
            "could-not-start notifier does not gate on steps.preflight.outcome"
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workflow",
        nargs="?",
        type=Path,
        default=WORKFLOW,
        help="workflow file to check (default: .github/workflows/jules-review.yml)",
    )
    args = parser.parse_args(argv)
    path: Path = args.workflow
    if not path.is_file():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    problems = findings(text)
    if problems:
        print(f"{path}:")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"{path}: ok ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
