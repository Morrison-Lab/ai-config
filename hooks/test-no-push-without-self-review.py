#!/usr/bin/env python3
"""Test the no-push-without-self-review guard."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def run_hook(cmd: str, transcript_events: list | None = None) -> tuple[int, dict]:
    tpath = None
    if transcript_events is not None:
        tf = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        for ev in transcript_events:
            tf.write(json.dumps(ev) + "\n")
        tf.close()
        tpath = tf.name

    try:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": cmd},
            "transcript_path": tpath or "",
        }
        res = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        data = {}
        if res.stdout.strip():
            try:
                data = json.loads(res.stdout)
            except Exception:
                pass
        return res.returncode, data
    finally:
        if tpath and os.path.exists(tpath):
            os.remove(tpath)


def agent_call(agent_name="adversarial-reviewer"):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Agent",
                    "input": {
                        "subagent_type": agent_name,
                        "prompt": "Review local diff against main",
                    },
                }
            ]
        },
    }


def clean_verdict():
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": "### Summary of Changes\nReviewed diff.\n\n### Findings\nNo actionable findings identified.\n\n### Verdict: Ready for merge",
                }
            ]
        },
    }


def blocking_verdict():
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": "### Findings\n- [Defect]: Bug found.\n\n### Verdict: Needs more work",
                }
            ]
        },
    }


CASES = [
    # (command, transcript_events, should_block, label)
    ("git push", [], True, "bare git push with empty transcript blocks"),
    ("git push -u origin feat/my-feature", [], True, "git push with remote and branch blocks without self-review"),
    ("git push origin main", [agent_call()], False, "git push allowed when adversarial-reviewer was invoked"),
    ("git push", [clean_verdict()], False, "git push allowed when clean verdict was recorded"),
    ("git push", [blocking_verdict()], True, "git push blocked when review verdict was Needs more work"),
    ("git push", [blocking_verdict(), clean_verdict()], False, "git push allowed when Needs more work was followed by Ready for merge"),
    ("ALLOW_UNREVIEWED_PUSH=1 git push", [], False, "ALLOW_UNREVIEWED_PUSH=1 prefix overrides the block"),
    ("export FOO=1 ALLOW_UNREVIEWED_PUSH=1 git push", [], False, "ALLOW_UNREVIEWED_PUSH=1 with env prefix overrides"),
    ("git push --allow-unreviewed-push", [], False, "--allow-unreviewed-push flag overrides"),
    ("echo 'git push' > file.txt", [], False, "echoing git push to file does not trigger"),
    ("cat << 'EOF'\ngit push\nEOF", [], False, "git push in heredoc does not trigger"),
    ("git status", [], False, "git status is unaffected"),
    ("git commit -m 'feat: something'", [], False, "git commit is unaffected"),
]


def main():
    failed = 0
    for cmd, events, should_block, label in CASES:
        rc, out = run_hook(cmd, events)
        blocked = (
            (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"
        )
        if rc != 0:
            print(f"FAIL (exit {rc}): {label}")
            failed += 1
        elif blocked != should_block:
            print(f"FAIL (expected blocked={should_block}, got {blocked}): {label}")
            print(f"   output: {out}")
            failed += 1
        else:
            print(f"PASS: {label}")

    if failed:
        print(f"\n{failed}/{len(CASES)} cases failed")
        sys.exit(1)
    else:
        print(f"\nAll {len(CASES)} cases passed")


if __name__ == "__main__":
    main()
