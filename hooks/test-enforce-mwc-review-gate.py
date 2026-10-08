#!/usr/bin/env python3
"""Test suite for hooks/enforce-mwc-review-gate.py.

Verifies that enforce-mwc-review-gate.py correctly enforces review gating
under both Claude Code (Bash & MCP payloads) and Antigravity (run_command payloads),
emits the dual-compatible output shape (decision + hookSpecificOutput),
and handles GitLab merges, GraphQL mutations, chained merges, and auto-merge tools.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and os.path.isfile(sys.argv[1])
    else str(Path(__file__).parent / "enforce-mwc-review-gate.py")
)

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")

spec = importlib.util.spec_from_file_location("enforce_mwc_review_gate", HOOK)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

HEAD = "8d7864c66c90ce495ae53deeaa8f1e86f3cf18b7"

checks = 0
failures = []


def check(desc: str, condition: bool, detail: str = ""):
    global checks
    checks += 1
    if condition:
        print(f"  ok: {desc}")
    else:
        print(f"  FAIL: {desc} {detail}")
        failures.append(f"{desc}: {detail}")


def run_main(payload_dict_or_str: dict | str, argv: list[str] | None = None) -> dict:
    inp = payload_dict_or_str if isinstance(payload_dict_or_str, str) else json.dumps(payload_dict_or_str)
    args = argv or ["enforce-mwc-review-gate.py"]
    captured = io.StringIO()
    with patch("sys.stdin", io.StringIO(inp)), patch("sys.argv", args), patch("sys.stdout", captured):
        gate.main()
    val = captured.getvalue().strip()
    return json.loads(val) if val else {}


def clean_pr_state():
    return {
        "url": "https://github.com/Morrison-Lab/ai-config/pull/123",
        "headRefOid": HEAD,
        "author": {"login": "someone"},
        "reviews": [],
        "comments": [
            {
                "author": {"login": "github-actions"},
                "body": (
                    "**Claude finished review**\n\n"
                    "### Verdict\n"
                    "**Ready for merge** --- all prior findings addressed.\n\n"
                    f"Reviewed commit: {HEAD}"
                ),
                "createdAt": "2026-10-07T12:00:00Z",
            }
        ],
        "reviewComments": [],
        "statusCheckRollup": [
            {
                "name": "test",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            }
        ],
    }


def not_clean_pr_state():
    return {
        "url": "https://github.com/Morrison-Lab/ai-config/pull/123",
        "headRefOid": HEAD,
        "author": {"login": "someone"},
        "reviews": [],
        "comments": [
            {
                "author": {"login": "github-actions"},
                "body": f"### Verdict\nNeeds more work\nReviewed commit: `{HEAD}`\n",
                "createdAt": "2026-10-07T12:00:00Z",
            }
        ],
        "reviewComments": [],
        "statusCheckRollup": [
            {
                "name": "test",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            }
        ],
    }


def main():
    print(f"Testing {HOOK}...")

    # 1. Output shape invariants
    allow_out = gate.ALLOW
    check("ALLOW has decision == 'allow'", allow_out.get("decision") == "allow")
    check("ALLOW has hookSpecificOutput.hookEventName == 'PreToolUse'",
          allow_out.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse")

    deny_out = gate.deny("test reason")
    check("deny has decision == 'deny'", deny_out.get("decision") == "deny")
    check("deny has reason", deny_out.get("reason") == "test reason")
    check("deny has hookSpecificOutput.permissionDecision == 'deny'",
          deny_out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")
    check("deny has hookSpecificOutput.permissionDecisionReason",
          deny_out.get("hookSpecificOutput", {}).get("permissionDecisionReason") == "test reason")

    # 2. Tool name detection
    check("is_mcp_merge_tool detects mcp__github__merge_pull_request",
          gate.is_mcp_merge_tool("mcp__github__merge_pull_request"))
    check("is_mcp_merge_tool detects enable_pull_request_auto_merge",
          gate.is_mcp_merge_tool("mcp__github__enable_pull_request_auto_merge"))
    check("is_mcp_auto_merge_tool detects auto_merge variant",
          gate.is_mcp_auto_merge_tool("enable_pull_request_auto_merge"))
    check("is_mcp_merge_tool returns False for non-merge tool",
          not gate.is_mcp_merge_tool("mcp__github__issue_read"))

    # 3. Claude Code Bash payloads
    out = run_main({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    check("Bash non-merge command allows", out.get("decision") == "allow" and
          out.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse")

    out = run_main({"tool_name": "Edit", "tool_input": {"file_path": "foo.py"}})
    check("Non-shell/non-MCP tool allows", out.get("decision") == "allow")

    out = run_main({"tool_name": "Bash", "tool_input": {"command": "glab mr merge 12"}})
    check("glab mr merge denies", out.get("decision") == "deny" and
          "GitLab merge requests" in out.get("reason", ""))

    out = run_main({"tool_name": "Bash", "tool_input": {"command": "glab api projects/1/merge_requests/2/merge -X PUT"}})
    check("glab api merge denies", out.get("decision") == "deny" and
          "GitLab merge requests" in out.get("reason", ""))

    out = run_main({"tool_name": "Bash", "tool_input": {"command": "gh api graphql -f query='mutation { mergePullRequest(input: {}) }'"}})
    check("GraphQL merge denies", out.get("decision") == "deny" and
          "GraphQL mutation is not allowed" in out.get("reason", ""))

    out = run_main({"tool_name": "Bash", "tool_input": {"command": "echo 'checking'; gh pr merge 123 --squash"}})
    check("Chained merge denies", out.get("decision") == "deny" and
          "must be executed on their own" in out.get("reason", ""))

    # 4. MCP payloads
    out = run_main({
        "tool_name": "mcp__github__enable_pull_request_auto_merge",
        "tool_input": {"owner": "foo", "repo": "bar", "pull_number": 1},
    })
    check("MCP auto-merge tool denies", out.get("decision") == "deny" and
          "auto-merge MCP tools cannot be verified" in out.get("reason", ""))

    out = run_main({
        "tool_name": "mcp__github__merge_pull_request",
        "tool_input": {"owner": "foo"},
    })
    check("MCP merge missing pull_number/repo denies", out.get("decision") == "deny" and
          "missing required owner, repo, or pull_number" in out.get("reason", ""))

    # 5. Review-gated evaluations with mocked fetch
    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (clean_pr_state(), None)
        out = run_main({
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": {
                "owner": "Morrison-Lab",
                "repo": "ai-config",
                "pull_number": 123,
                "expectedHeadSha": HEAD,
            },
        })
        check("MCP merge with clean review allows", out.get("decision") == "allow" and
              out.get("hookSpecificOutput", {}).get("hookEventName") == "PreToolUse")

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (clean_pr_state(), None)
        out = run_main({
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": {
                "owner": "Morrison-Lab",
                "repo": "ai-config",
                "pull_number": 123,
                "expectedHeadSha": "0000000000000000000000000000000000000000",
            },
        })
        check("MCP merge with mismatched expectedHeadSha denies", out.get("decision") == "deny" and
              "does not match current PR head SHA" in out.get("reason", ""))

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (not_clean_pr_state(), None)
        out = run_main({
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": {
                "owner": "Morrison-Lab",
                "repo": "ai-config",
                "pull_number": 123,
                "expectedHeadSha": HEAD,
            },
        })
        check("MCP merge with not-clean review denies", out.get("decision") == "deny" and
              "Needs more work" in out.get("reason", ""))

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (clean_pr_state(), None)
        out = run_main({
            "tool_name": "Bash",
            "tool_input": {"command": "gh pr merge 123 --squash"},
        })
        check("Bash gh pr merge with clean review allows", out.get("decision") == "allow")

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (not_clean_pr_state(), None)
        out = run_main({
            "tool_name": "Bash",
            "tool_input": {"command": "gh pr merge 123 --squash"},
        })
        check("Bash gh pr merge with not-clean review denies", out.get("decision") == "deny" and
              "Needs more work" in out.get("reason", ""))

    # 6. Antigravity run_command format
    out = run_main({
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "git status"},
        }
    })
    check("Antigravity run_command non-merge allows", out.get("decision") == "allow")
    check("Antigravity output omits hookSpecificOutput for protojson compatibility",
          "hookSpecificOutput" not in out)

    out = run_main({
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "glab mr merge 12"},
        }
    })
    check("Antigravity run_command glab mr merge denies", out.get("decision") == "deny")
    check("Antigravity deny omits hookSpecificOutput for protojson compatibility",
          "hookSpecificOutput" not in out)

    out = run_main({
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": "a.txt"},
        }
    })
    check("Antigravity non-run_command allows", out.get("decision") == "allow")

    with patch.object(gate, "fetch_pr_data") as mock_fetch:
        mock_fetch.return_value = (clean_pr_state(), None)
        out = run_main({
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "gh pr merge 123 --squash"},
            }
        })
        check("Antigravity run_command gh pr merge with clean review allows", out.get("decision") == "allow")

    # 7. Unparseable stdin fails closed
    out = run_main("not-json{{{")
    check("Unparseable stdin denies fail-closed", out.get("decision") == "deny" and
          out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")

    # 8. Dry-run arguments
    out = run_main("", argv=["enforce-mwc-review-gate.py", "--dry-run", "git status"])
    check("--dry-run non-merge allows", out.get("decision") == "allow")

    out = run_main("", argv=["enforce-mwc-review-gate.py", "--dry-run", "glab mr merge 5"])
    check("--dry-run glab mr merge denies", out.get("decision") == "deny")

    print(f"\n{checks - len(failures)}/{checks} checks passed.")
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
