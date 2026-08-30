#!/usr/bin/env python3
"""Tests for scripts/lib/payload_fetcher.py and the --from-json path.

ai-config#2441: check-pr-fully-clean.py hard-required `gh`, so the corpus's
deterministic fully-clean instrument could not run in remote/web sessions.

The cases that matter most here are the NEGATIVE ones, and for a reason
specific to this script: exit 1 is its "NOT fully clean" verdict. So a payload
that cannot be read must exit 2, not 1 -- otherwise a data problem is
indistinguishable from a finding about the PR. Every "must error" case below
asserts the exit CODE, not merely that something went wrong.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from payload_fetcher import PayloadError, PayloadFetcher  # noqa: E402

SCRIPT = Path(__file__).parent / "check-pr-fully-clean.py"
HEAD = "abc1234def5678901234567890abcdef12345678"

passes = 0
failures = 0


def check(name, cond):
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name}")


def base_payload():
    return {
        "repo": "example-org/example-repo",
        "pr": {
            "headRefOid": HEAD,
            "headRefName": "feat/example",
            "state": "OPEN",
            "reviewDecision": "",
            "commits": [{"committedDate": "2026-08-30T01:00:00Z"}],
            "reviews": [],
            "comments": [
                {
                    "body": "**Claude finished review**\n\n### Verdict\n"
                            f"**Ready for merge**\n\nReviewed commit: {HEAD}",
                    "author": {"login": "github-actions"},
                    "createdAt": "2026-08-30T01:05:00Z",
                    "authorAssociation": "NONE",
                }
            ],
        },
        "check_runs": [
            {"name": "validate", "status": "completed",
             "conclusion": "success", "html_url": "https://example.invalid/1"},
        ],
    }


def run_script(payload):
    """Run the real CLI against *payload*; return (exit_code, output)."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        path = fh.name
    try:
        res = subprocess.run(
            [sys.executable, str(SCRIPT), "2629", "-R", "example-org/example-repo",
             "--from-json", path],
            capture_output=True, encoding="utf-8", check=False,
        )
        return res.returncode, (res.stdout or "") + (res.stderr or "")
    finally:
        Path(path).unlink(missing_ok=True)


def main():
    # --- end-to-end exit codes: the three states must stay distinct ---
    code, out = run_script(base_payload())
    check("a clean payload exits 0", code == 0)
    check("...and says FULLY CLEAN", "FULLY CLEAN" in out)

    p = base_payload()
    p["check_runs"][0] = {"name": "validate", "status": "in_progress",
                          "conclusion": None, "html_url": "x"}
    code, out = run_script(p)
    check("a pending check exits 1 (not clean)", code == 1)

    p = base_payload()
    p["check_runs"][0]["conclusion"] = "failure"
    code, _ = run_script(p)
    check("a failed check exits 1 (not clean)", code == 1)

    # --- the safety property: unusable data is exit 2, never exit 1 ---
    p = base_payload()
    del p["check_runs"]
    code, out = run_script(p)
    check("missing check_runs exits 2, NOT 1", code == 2)
    check("...and names the missing key", "check_runs" in out)
    check("...and does not claim a verdict", "FULLY CLEAN" not in out)

    p = base_payload()
    del p["pr"]
    code, _ = run_script(p)
    check("missing pr key exits 2", code == 2)

    code, out = run_script([1, 2, 3])
    check("a non-object payload exits 2", code == 2)

    # a file that is not JSON at all
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        fh.write("{not json")
        bad = fh.name
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "2629", "-R", "example-org/example-repo",
         "--from-json", bad],
        capture_output=True, encoding="utf-8", check=False,
    )
    Path(bad).unlink(missing_ok=True)
    check("malformed JSON exits 2", res.returncode == 2)

    res = subprocess.run(
        [sys.executable, str(SCRIPT), "2629", "-R", "example-org/example-repo",
         "--from-json", "/nonexistent/payload.json"],
        capture_output=True, encoding="utf-8", check=False,
    )
    check("a missing payload file exits 2", res.returncode == 2)

    # --- unit-level fetcher behaviour ---
    f = PayloadFetcher(base_payload())
    check(
        "check_runs accepted as a bare list",
        json.loads(f(["gh", "api", "repos/o/r/commits/deadbeef/check-runs?per_page=100"]))
        ["check_runs"][0]["name"] == "validate",
    )
    f2 = PayloadFetcher({**base_payload(), "check_runs": {"check_runs": [{"name": "x"}]}})
    check(
        "check_runs accepted as a REST envelope",
        json.loads(f2(["gh", "api", "repos/o/r/commits/d/check-runs"]))["check_runs"][0]["name"] == "x",
    )
    check(
        "gh repo view returns the bare repo string",
        PayloadFetcher(base_payload())(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
        ) == "example-org/example-repo",
    )

    # The deliberate asymmetry: an absent Actions-run entry is tolerated,
    # because the workflow-path lookup is a refinement and the payload cannot
    # be built by someone who does not yet know the run ids. Everything else
    # is fail-closed. If this ever becomes an error, a payload will be
    # unbuildable in practice.
    check(
        "an absent actions_runs entry returns {} rather than raising",
        json.loads(PayloadFetcher(base_payload())(
            ["gh", "api", "repos/o/r/actions/runs/12345"])) == {},
    )
    check(
        "a present actions_runs entry is served",
        json.loads(PayloadFetcher({**base_payload(),
                                   "actions_runs": {"9": {"path": ".github/workflows/v.yml"}}})(
            ["gh", "api", "repos/o/r/actions/runs/9"]))["path"] == ".github/workflows/v.yml",
    )

    for bad_cmd, label in [
        (["gh", "issue", "list"], "an unmapped gh subcommand"),
        (["git", "status"], "a non-gh command"),
        (["gh", "api", "repos/o/r/pulls/1/files"], "an unmapped gh api path"),
    ]:
        try:
            PayloadFetcher(base_payload())(bad_cmd)
            check(f"{label} raises", False)
        except PayloadError:
            check(f"{label} raises", True)

    try:
        PayloadFetcher("not a dict")
        check("a non-dict payload raises at construction", False)
    except PayloadError:
        check("a non-dict payload raises at construction", True)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
