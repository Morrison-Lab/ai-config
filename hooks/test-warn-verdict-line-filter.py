#!/usr/bin/env python3
"""Tests for warn-verdict-line-filter.py.

Verifies that PreToolUse warning fires when a Bash command fetches PR review
comments and filters the comment body down to verdict lines without mentioning
findings or review-data (ai-config#3493, 2026-09-09).
Filter files passed via -f / --from-file are also tested (ai-config#3494).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(__file__), "warn-verdict-line-filter.py")
)


def bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def run_hook(
    raw_or_payload: str | dict | list | None, env: dict | None = None
) -> subprocess.CompletedProcess:
    inp = raw_or_payload if isinstance(raw_or_payload, str) else json.dumps(raw_or_payload)
    hook_env = os.environ.copy()
    if env:
        hook_env.update(env)
    return subprocess.run(
        [sys.executable, HOOK],
        input=inp,
        capture_output=True,
        text=True,
        timeout=10,
        env=hook_env,
    )


def test_suite() -> list[str]:
    failures: list[str] = []

    # Case 1: command fetches issue comments, pipes to jq split and test filter -> warns
    cmd_warn = (
        'gh api repos/owner/repo/issues/123/comments | '
        'jq \'.[] | .body | split("\\n") | map(select(test("Verdict|Ready for merge")))\''
    )
    res1 = run_hook(bash_payload(cmd_warn))
    if res1.returncode != 0:
        failures.append(f"case 1 non-zero exit: {res1.returncode}")
    elif not res1.stdout.strip():
        failures.append("case 1 failed to warn: stdout is empty")
    else:
        try:
            payload = json.loads(res1.stdout)
            hso = payload.get("hookSpecificOutput", {})
            if hso.get("hookEventName") != "PreToolUse":
                failures.append(f"case 1 wrong hookEventName: {hso.get('hookEventName')}")
            ctx = hso.get("additionalContext", "")
            if "this filter narrows a review round's body to a few lines" not in ctx:
                failures.append(f"case 1 missing expected note text in additionalContext: {ctx}")
            if "findings" not in ctx:
                failures.append(f"case 1 additionalContext missing findings explanation: {ctx}")
        except json.JSONDecodeError as exc:
            failures.append(f"case 1 invalid json: {exc}")
    print(f"  {'FAIL' if failures else 'ok  '} case 1: comment fetch with split and test filter warns")

    # Additional warn cases: pulls/comments with slice, --json comments with NOT CLEAN, --json reviews with Reviewed commit
    more_warns = [
        ("--json comments with NOT CLEAN", 'gh pr view 42 --json comments --jq \'.comments[].body | split("\\n") | map(select(test("NOT CLEAN")))\''),
        ("--json reviews with Reviewed commit", 'gh pr view 42 --json reviews --jq \'.reviews[].body | test("Reviewed commit")\''),
        ("--json state,comments with verdict filter", 'gh pr view 42 --json state,comments --jq \'.comments[].body | split("\\n") | map(select(test("Verdict")))\''),
        ("--json comments with NOT_CLEAN", 'gh pr view 42 --json comments --jq \'.comments[].body | split("\\n") | map(select(test("NOT_CLEAN")))\''),
        ("--json reviews,comments,number with Needs more work", 'gh pr view 42 --json reviews,comments,number --jq \'.comments[].body | split("\\n") | map(select(test("Needs more work")))\''),
    ]
    for label, cmd in more_warns:
        prev = len(failures)
        res = run_hook(bash_payload(cmd))
        if res.returncode != 0:
            failures.append(f"{label} non-zero exit: {res.returncode}")
        elif not res.stdout.strip():
            failures.append(f"{label} failed to warn: stdout is empty")
        else:
            try:
                payload = json.loads(res.stdout)
                hso = payload.get("hookSpecificOutput", {})
                if "additionalContext" not in hso:
                    failures.append(f"{label} missing additionalContext")
            except json.JSONDecodeError as exc:
                failures.append(f"{label} invalid json: {exc}")
        print(f"  {'FAIL' if len(failures) > prev else 'ok  '} warn case: {label}")

    # Case 2: same command but contains the word findings -> silent
    cmd_with_findings = cmd_warn + " # check findings array"
    res2 = run_hook(bash_payload(cmd_with_findings))
    prev = len(failures)
    if res2.returncode != 0 or res2.stdout.strip() != "":
        failures.append(f"case 2 failed: returncode={res2.returncode}, stdout={res2.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 2: contains 'findings' stays silent")

    # Additional silent: contains review-data
    cmd_with_review_data = cmd_warn + " # parse review-data"
    res_rd = run_hook(bash_payload(cmd_with_review_data))
    prev = len(failures)
    if res_rd.returncode != 0 or res_rd.stdout.strip() != "":
        failures.append(f"contains review-data failed: returncode={res_rd.returncode}, stdout={res_rd.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} silent case: contains 'review-data' stays silent")

    # Case 3: verdict filter without comments fetch (e.g. local file grep) -> silent
    cmd_local_file = 'grep -E "Verdict|Ready for merge" local-review.txt | jq \'.[] | split("\\n")\''
    res3 = run_hook(bash_payload(cmd_local_file))
    prev = len(failures)
    if res3.returncode != 0 or res3.stdout.strip() != "":
        failures.append(f"case 3 failed: returncode={res3.returncode}, stdout={res3.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 3: verdict filter without comments fetch stays silent")

    # Case 4: comments fetch with plain .[-1].body and no line filter -> silent
    cmd_plain_body = 'gh api repos/owner/repo/issues/123/comments | jq ".[-1].body"'
    res4 = run_hook(bash_payload(cmd_plain_body))
    prev = len(failures)
    if res4.returncode != 0 or res4.stdout.strip() != "":
        failures.append(f"case 4 failed: returncode={res4.returncode}, stdout={res4.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 4: comments fetch with plain body stays silent")

    # Case 4b: a bare jq slice over the comments array is paging, not a
    # verdict-line read; without a split of the body it must stay silent
    cmd_bare_slice = 'gh api repos/owner/repo/issues/123/comments | jq ".[0:5]"'
    res4b = run_hook(bash_payload(cmd_bare_slice))
    prev = len(failures)
    if res4b.returncode != 0 or res4b.stdout.strip() != "":
        failures.append(f"case 4b failed: returncode={res4b.returncode}, stdout={res4b.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 4b: bare slice over the comments array stays silent")

    # Case 4c: a split of the body with no verdict test and no slice (a line
    # count) is not a verdict-line read -> silent
    cmd_split_len = 'gh api repos/owner/repo/issues/123/comments | jq ".[] | .body | split(\"\\n\") | length"'
    res4c = run_hook(bash_payload(cmd_split_len))
    prev = len(failures)
    if res4c.returncode != 0 or res4c.stdout.strip() != "":
        failures.append(f"case 4c failed: returncode={res4c.returncode}, stdout={res4c.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 4c: split-and-count stays silent")

    # Case 4d: split then a slice of the lines is a verdict-line read -> warns
    cmd_split_slice = 'gh api repos/owner/repo/issues/123/comments | jq ".[-1].body | split(\"\\n\") | .[0:4]"'
    res4d = run_hook(bash_payload(cmd_split_slice))
    prev = len(failures)
    if res4d.returncode != 0 or "additionalContext" not in res4d.stdout:
        failures.append(f"case 4d failed to warn: returncode={res4d.returncode}, stdout={res4d.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 4d: split then slice warns")

    # Case 4e: open-ended and negative slice bounds are still a slice of the
    # split lines -> warns for each shape
    for shape in (".[:4]", ".[-4:]", ".[-4:-1]"):
        cmd_shape = 'gh api repos/owner/repo/issues/123/comments | jq ".[-1].body | split(\"\\n\") | ' + shape + '"'
        res4e = run_hook(bash_payload(cmd_shape))
        prev = len(failures)
        if res4e.returncode != 0 or "additionalContext" not in res4e.stdout:
            failures.append(f"case 4e {shape} failed to warn: returncode={res4e.returncode}, stdout={res4e.stdout!r}")
        print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 4e: split then slice {shape} warns")

    # Additional silent: --json commentsX (not a real comments field) stays silent
    cmd_comments_x = (
        'gh pr view 42 --json commentsX --jq \'.comments[].body | split("\\n") | map(select(test("Verdict")))\''
    )
    res_cx = run_hook(bash_payload(cmd_comments_x))
    prev = len(failures)
    if res_cx.returncode != 0 or res_cx.stdout.strip() != "":
        failures.append(f"--json commentsX failed: returncode={res_cx.returncode}, stdout={res_cx.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} silent case: --json commentsX stays silent")

    # Case 5: tool_name not Bash -> silent
    non_bash_payload = {
        "tool_name": "Edit",
        "tool_input": {"command": cmd_warn},
    }
    res5 = run_hook(non_bash_payload)
    prev = len(failures)
    if res5.returncode != 0 or res5.stdout.strip() != "":
        failures.append(f"case 5 failed: returncode={res5.returncode}, stdout={res5.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 5: tool_name not Bash stays silent")

    # Case 6: empty or invalid stdin -> exit 0 silent
    res6_empty = run_hook("")
    prev = len(failures)
    if res6_empty.returncode != 0 or res6_empty.stdout.strip() != "":
        failures.append(f"case 6 empty failed: returncode={res6_empty.returncode}, stdout={res6_empty.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 6a: empty stdin exits 0 silently")

    res6_invalid = run_hook("{not valid json")
    prev = len(failures)
    if res6_invalid.returncode != 0 or res6_invalid.stdout.strip() != "":
        failures.append(f"case 6 invalid json failed: returncode={res6_invalid.returncode}, stdout={res6_invalid.stdout!r}")
    print(f"  {'FAIL' if len(failures) > prev else 'ok  '} case 6b: invalid json stdin exits 0 silently")

    # Case 7: file-carried split+test filter warns
    with tempfile.TemporaryDirectory() as tmpdir:
        verdict_jq = os.path.join(tmpdir, "verdict.jq").replace("\\", "/")
        with open(verdict_jq, "w", encoding="utf-8") as fh:
            fh.write('split("\\n") | map(select(test("Verdict|Ready for merge")))')

        cmd_file_warn = (
            f"gh api repos/owner/repo/issues/123/comments | jq -f {verdict_jq}"
        )
        res7 = run_hook(bash_payload(cmd_file_warn))
        prev = len(failures)
        if res7.returncode != 0:
            failures.append(f"case 7 non-zero exit: {res7.returncode}")
        elif not res7.stdout.strip():
            failures.append("case 7 failed to warn: stdout is empty")
        else:
            try:
                payload = json.loads(res7.stdout)
                hso = payload.get("hookSpecificOutput", {})
                if "additionalContext" not in hso:
                    failures.append("case 7 missing additionalContext")
            except json.JSONDecodeError as exc:
                failures.append(f"case 7 invalid json: {exc}")
        print(
            f"  {'FAIL' if len(failures) > prev else 'ok  '} case 7: file-carried split+test filter warns"
        )

        # Case 8: file-carried plain filter stays silent
        plain_jq = os.path.join(tmpdir, "plain.jq").replace("\\", "/")
        with open(plain_jq, "w", encoding="utf-8") as fh:
            fh.write(".[-1].body\n")

        cmd_file_plain = (
            f"gh api repos/owner/repo/issues/123/comments | jq -f {plain_jq}"
        )
        res8 = run_hook(bash_payload(cmd_file_plain))
        prev = len(failures)
        if res8.returncode != 0 or res8.stdout.strip() != "":
            failures.append(
                f"case 8 failed: returncode={res8.returncode}, stdout={res8.stdout!r}"
            )
        print(
            f"  {'FAIL' if len(failures) > prev else 'ok  '} case 8: file-carried plain filter stays silent"
        )


    # Case 9: file-carried filter via ~-prefixed path warns
    with tempfile.TemporaryDirectory() as tmpdir:
        home_filter = os.path.join(tmpdir, "verdict.jq")
        with open(home_filter, "w", encoding="utf-8") as fh:
            fh.write('split("\\n") | map(select(test("Verdict|Ready for merge")))')

        cmd_tilde_warn = (
            "gh api repos/owner/repo/issues/123/comments | jq -f ~/verdict.jq"
        )
        tilde_env = {"HOME": tmpdir, "USERPROFILE": tmpdir}
        res9 = run_hook(bash_payload(cmd_tilde_warn), env=tilde_env)
        prev = len(failures)
        if res9.returncode != 0:
            failures.append(f"case 9 non-zero exit: {res9.returncode}")
        elif not res9.stdout.strip():
            failures.append("case 9 failed to warn: stdout is empty")
        else:
            try:
                payload = json.loads(res9.stdout)
                hso = payload.get("hookSpecificOutput", {})
                if "additionalContext" not in hso:
                    failures.append("case 9 missing additionalContext")
            except json.JSONDecodeError as exc:
                failures.append(f"case 9 invalid json: {exc}")
        print(
            f"  {'FAIL' if len(failures) > prev else 'ok  '} case 9: file-carried filter via ~ path warns"
        )
    return failures


def main() -> int:
    failures = test_suite()
    if failures:
        print("\nFAILED:")
        for fail in failures:
            print(f"  {fail}")
        return 1
    print("\nall tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
