#!/usr/bin/env python3
"""Gate the Jules mention-dispatch wrap against the failure in ai-config#2280.

`.github/workflows/jules-review.yml` exists to run Jules from an `@jules`
comment. The action it invokes (`sanjay3290/jules-pr-reviewer`) refuses every
event except `pull_request`. A step `env:` block that sets `GITHUB_EVENT_NAME`
on a `uses:` step looks like a wrap and is a no-op: GitHub ignores reserved
`GITHUB_*` assignments, measured 2026-08-26 on run 32942088643.

This check fails if the mention path is dropped, if the action is invoked
via `uses:` again, or if the child-process `env(1)` override is missing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "jules-review.yml"
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
USES_ACTION_RE = re.compile(
    r"^\s*uses:\s*sanjay3290/jules-pr-reviewer@",
    re.MULTILINE,
)
CHILD_EVENT_RE = re.compile(
    r"^[ \t]*GITHUB_EVENT_NAME=pull_request[ \t]*\\?\s*$",
    re.MULTILINE,
)
YAML_EVENT_OVERRIDE_RE = re.compile(
    r"^[ \t]*GITHUB_EVENT_NAME:\s*pull_request\s*$",
    re.MULTILINE,
)


def findings(text: str) -> list[str]:
    out: list[str] = []
    if "issue_comment:" not in text:
        out.append("mention path dropped: workflow has no issue_comment trigger")
    if "on:\n  pull_request:" in text or re.search(
        r"^on:\n(?:  .+\n)*  pull_request:", text
    ):
        # Automatic pull_request reviews were disabled on purpose (#856/#1172).
        # A wrap that re-adds that trigger undoes the file header.
        if re.search(r"^on:\s*$", text, re.MULTILINE) and re.search(
            r"^  pull_request:\s*$", text, re.MULTILINE
        ):
            out.append(
                "automatic pull_request trigger reintroduced; mention path is the point"
            )
    if USES_ACTION_RE.search(text):
        out.append(
            "invokes sanjay3290/jules-pr-reviewer via uses:; "
            "GITHUB_* env on a uses: step is ignored"
        )
    if YAML_EVENT_OVERRIDE_RE.search(text) and not CHILD_EVENT_RE.search(text):
        out.append(
            "GITHUB_EVENT_NAME is set only as YAML env (ignored on uses: steps); "
            "need env(1) GITHUB_EVENT_NAME=pull_request on the node child"
        )
    if not CHILD_EVENT_RE.search(text):
        out.append(
            "missing child-process override: env GITHUB_EVENT_NAME=pull_request"
        )
    if "dist/index.js" not in text or not re.search(
        r"\bnode\b.*dist/index\.js|dist/index\.js", text
    ):
        out.append("does not run the pinned action's dist/index.js")
    if "JULES_PR_REVIEWER_SHA:" not in text or not SHA_RE.search(text):
        out.append("missing 40-character pin for sanjay3290/jules-pr-reviewer")
    if "INPUT_SKIP_DRAFTS:" in text and not re.search(
        r"INPUT_SKIP_DRAFTS:\s*'false'", text
    ):
        out.append("INPUT_SKIP_DRAFTS is not 'false'; a mention on a draft would skip")
    if "imperative prose" not in text:
        out.append("missing extra_instructions that this corpus's prose is content")
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
