"""Test the flag-unassigned-worktree guard.

The payloads below are not invented. Every `tool_input` key set here was
observed in real `Agent` tool_use records in this machine's Claude Code
transcripts (`~/.claude/projects/**/*.jsonl`), across 121 launches:

    48  (description, prompt, subagent_type)
    33  (description, prompt, run_in_background, subagent_type)
    27  (description, isolation, prompt, subagent_type)
     9  (description, isolation, prompt, run_in_background, subagent_type)
     3  (description, prompt)                      <- no subagent_type at all
     1  (description, model, prompt, run_in_background, subagent_type)

Building the fixture from real records rather than from a guess is the point.
A sibling hook shipped with two regex patterns that never matched anything,
because it searched the tool *input* while the verb it wanted lived in the tool
*name*; only a real-transcript fixture would have caught that. The two facts
this fixture pinned down that a guess would have missed:

  - `subagent_type` is genuinely optional (3 records omit it), so a classifier
    that skips on a missing value silently exempts real launches.
  - `isolation` never appears on an `Explore` launch, so exempting the
    read-only types costs no real coverage.

Run:  python3 hooks/test-flag-unassigned-worktree.py hooks/flag-unassigned-worktree.py
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1]

# (payload, description)
SHOULD_WARN = [
    ({"tool_name": "Agent",
      "tool_input": {"description": "Corpus search", "prompt": "find X",
                     "subagent_type": "general-purpose"}},
     "the 48-record shape: general-purpose, no isolation"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "Sweep", "prompt": "do X",
                     "run_in_background": True, "subagent_type": "general-purpose"}},
     "the 33-record shape: backgrounded general-purpose, no isolation"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "PR #266 status", "prompt": "Gather status"}},
     "the 3-record shape: subagent_type ABSENT entirely"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "Docs", "prompt": "look up hooks",
                     "subagent_type": "claude-code-guide"}},
     "claude-code-guide: no Edit/Write but has Bash, so not exempt"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "Custom", "prompt": "x",
                     "subagent_type": "some-project-defined-agent"}},
     "unknown subagent_type defaults to write-capable"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "x", "prompt": "x",
                     "subagent_type": "general-purpose", "isolation": ""}},
     "empty-string isolation is not an assignment"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "x", "prompt": "x",
                     "subagent_type": "general-purpose", "isolation": None}},
     "explicit null isolation is not an assignment"),
]

SHOULD_STAY_SILENT = [
    ({"tool_name": "Agent",
      "tool_input": {"description": "x", "prompt": "x", "isolation": "worktree",
                     "subagent_type": "general-purpose"}},
     "the 27-record shape: isolation assigned"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "x", "prompt": "x", "isolation": "worktree",
                     "run_in_background": True, "subagent_type": "general-purpose"}},
     "the 9-record shape: backgrounded and assigned"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "x", "prompt": "x", "isolation": "remote",
                     "subagent_type": "general-purpose"}},
     "isolation: remote also counts as assigned"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "Search", "prompt": "x",
                     "subagent_type": "Explore"}},
     "the 26-record shape: Explore is a declared read-only role"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "Plan it", "prompt": "x",
                     "subagent_type": "Plan"}},
     "Plan is a declared read-only role"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "x", "model": "sonnet", "prompt": "x",
                     "run_in_background": True, "subagent_type": "Explore"}},
     "the 1-record shape carrying model=, read-only"),
    ({"tool_name": "Bash", "tool_input": {"command": "git worktree list"}},
     "a different tool entirely"),
    ({"tool_name": "Edit",
      "tool_input": {"file_path": "/x", "old_string": "a", "new_string": "b"}},
     "Edit is not an agent launch"),
    ({"tool_name": "Agent", "tool_input": None},
     "malformed tool_input fails OPEN, does not warn"),
    ({"tool_name": "Agent"},
     "absent tool_input fails OPEN, does not warn"),
]

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
             "read as 'silent' on every case and print a perfect pass")


def verdict(payload):
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    # a crashed hook must NOT read as 'silent' -- that is the failure mode where
    # the pass path and the broken path print the same thing
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode} on {payload!r}\n{p.stderr.strip()}")
    if not p.stdout.strip():
        return "silent"
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: hook emitted non-JSON on stdout ({exc}): {p.stdout!r}")

    hso = out.get("hookSpecificOutput") or {}
    # the hook must never make the harness MORE permissive than it was without it
    if "permissionDecision" in hso:
        sys.exit(f"FATAL: hook emitted permissionDecision="
                 f"{hso['permissionDecision']!r}; this guard must only ever add "
                 "context, never allow/deny/ask")
    return "WARN" if hso.get("additionalContext") else "silent"


wrong = 0
print("should WARN:")
for payload, desc in SHOULD_WARN:
    v = verdict(payload)
    wrong += v != "WARN"
    print(f"  {v:<6} {desc}")

print("\nshould STAY SILENT:")
for payload, desc in SHOULD_STAY_SILENT:
    v = verdict(payload)
    wrong += v != "silent"
    print(f"  {v:<6} {desc}")

total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
