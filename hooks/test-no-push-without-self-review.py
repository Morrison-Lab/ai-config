#!/usr/bin/env python3
"""Test the no-push-without-self-review guard.

Two families of case, and the second is the one this guard exists to survive.

COMMAND DETECTION -- does the text contain a real `git push` at all.
VERDICT ATTRIBUTION -- is there a current clean verdict from the reviewer's own
output, as opposed to the phrase appearing somewhere in the transcript. The
`poison_*` cases below are the reproduction from the first review of
ai-config#1911: the guard's own denial message, and this repo's own prose,
carry the verdict phrase, so a transcript-wide search authorized every retry
after the first block.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

_next_id = [0]


def _fresh_id() -> str:
    _next_id[0] += 1
    return f"toolu_{_next_id[0]:04d}"


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


CLEAN_BODY = (
    "### Summary of Changes\nReviewed diff.\n\n"
    "### Findings\nNo actionable findings identified.\n\n"
    "### Verdict: Ready for merge"
)
BLOCKING_BODY = "### Findings\n- [Defect]: Bug found.\n\n### Verdict: Needs more work"


def agent_call(agent_name="adversarial-reviewer", call_id=None, tool="Agent"):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": call_id or _fresh_id(),
                    "name": tool,
                    "input": {
                        "subagent_type": agent_name,
                        "prompt": "Review local diff against main",
                    },
                }
            ]
        },
    }


def agent_result(call_id, body, as_list=False):
    content = [{"type": "text", "text": body}] if as_list else body
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": call_id, "content": content}
            ]
        },
    }


def reviewed(body=CLEAN_BODY, agent_name="adversarial-reviewer", as_list=False):
    """A complete dispatch: the call, then its own result carrying a verdict."""
    call_id = _fresh_id()
    return [agent_call(agent_name, call_id), agent_result(call_id, body, as_list)]


def file_edit(tool="Edit"):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": _fresh_id(),
                    "name": tool,
                    "input": {"file_path": "a.py", "old_string": "x", "new_string": "y"},
                }
            ]
        },
    }


def poison_denial():
    """The guard's own denial, surfaced back as the blocked call's result.

    This is verbatim the shape that made the first revision self-defeating: the
    reason text names the phrase the guard was searching for.
    """
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": _fresh_id(),
                    "content": (
                        "git push blocked by pre-push self-review policy:\n"
                        "obtain a clean verdict (`### Verdict: Ready for merge`) before pushing."
                    ),
                }
            ]
        },
    }


def poison_file_read():
    """`Read`ing this repo's own prose, which quotes the verdict phrase."""
    call_id = _fresh_id()
    return [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": call_id,
                        "name": "Read",
                        "input": {"file_path": "skills/push/SKILL.md"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": "Confirm the review concludes with:\n\n### Verdict: Ready for merge\n",
                    }
                ]
            },
        },
    ]


def poison_assistant_prose():
    """The session asserting its own verdict in prose, with no reviewer run."""
    return {
        "type": "assistant",
        "message": {
            "content": [{"type": "text", "text": "Self-reviewed. Verdict: Ready for merge"}]
        },
    }


CASES = [
    # --- command detection ---
    ("git push", [], True, "bare git push with empty transcript blocks"),
    ("git push -u origin feat/my-feature", [], True,
     "git push with remote and branch blocks without self-review"),
    ("ALLOW_UNREVIEWED_PUSH=1 git push", [], False,
     "ALLOW_UNREVIEWED_PUSH=1 prefix overrides the block"),
    ("export FOO=1 ALLOW_UNREVIEWED_PUSH=1 git push", [], False,
     "ALLOW_UNREVIEWED_PUSH=1 with env prefix overrides"),
    ("git push --allow-unreviewed-push", [], False,
     "--allow-unreviewed-push flag overrides"),
    ("echo 'git push' > file.txt", [], False,
     "echoing git push to file does not trigger"),
    ("cat << 'EOF'\ngit push\nEOF", [], False,
     "git push in heredoc does not trigger"),
    ("git status", [], False, "git status is unaffected"),
    ("git commit -m 'feat: something'", [], False, "git commit is unaffected"),

    # --- verdict attribution: the reviewer's own result ---
    ("git push origin main", reviewed(), False,
     "a clean verdict returned by the reviewer's own call allows the push"),
    ("git push", reviewed(as_list=True), False,
     "a clean verdict allows the push when the result content is a block list"),
    ("git push", reviewed(BLOCKING_BODY), True,
     "a blocking verdict from the reviewer blocks the push"),
    ("git push", reviewed(BLOCKING_BODY) + reviewed(), False,
     "a later clean verdict supersedes an earlier blocking one"),
    ("git push", reviewed() + reviewed(BLOCKING_BODY), True,
     "a later blocking verdict supersedes an earlier clean one"),
    ("git push", reviewed(BLOCKING_BODY + "\n\n" + CLEAN_BODY), False,
     "within one body the LAST verdict wins (clean after quoted blocking)"),
    ("git push", [agent_call()], True,
     "dispatching the reviewer without a returned verdict does not authorize the push"),
    ("git push", reviewed(agent_name="general-purpose"), True,
     "another subagent's clean verdict does not count as the reviewer's"),
    ("git push", reviewed(agent_name="adversarial_reviewer"), False,
     "the underscore spelling of the subagent name is accepted"),
    ("git push", reviewed(agent_name="write me an adversarial critique"), True,
     "a prompt-like string in subagent_type does not match the reviewer name"),
    ("git push", reviewed(agent_name="adversarial-reviewer", as_list=False), False,
     "sanity: the plain-string result shape still passes"),

    # --- verdict attribution: the poisoning regressions ---
    ("git push", [poison_denial()], True,
     "the guard's own denial message in the transcript does not authorize a retry"),
    ("git push", poison_file_read(), True,
     "reading a repo file that quotes the verdict phrase does not authorize a push"),
    ("git push", [poison_assistant_prose()], True,
     "the session asserting the verdict itself does not authorize a push"),
    ("git push", reviewed(BLOCKING_BODY) + [poison_denial()], True,
     "a denial message does not overturn the reviewer's blocking verdict"),

    # --- verdict attribution: staleness ---
    ("git push", reviewed() + [file_edit()], True,
     "an edit after the clean verdict makes it stale"),
    ("git push", reviewed() + [file_edit("Write")], True,
     "a Write after the clean verdict makes it stale"),
    ("git push", reviewed() + [file_edit()] + reviewed(), False,
     "re-reviewing after the edit clears the staleness block"),
    ("git push", [file_edit()] + reviewed(), False,
     "an edit BEFORE the clean verdict is what the reviewer read, so it is fine"),
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
