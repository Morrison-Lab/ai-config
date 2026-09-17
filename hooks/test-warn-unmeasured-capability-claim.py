#!/usr/bin/env python3
"""Tests for warn-unmeasured-capability-claim.py.

Run: python3 hooks/test-warn-unmeasured-capability-claim.py [path-to-hook]

The positive fixtures are the two claims that actually shipped to GitHub on
2026-09-17 and had to be retracted, verbatim. Using the real sentences rather
than invented ones is the point: an invented fixture is written by the same
understanding that writes the matcher, so it proves the matcher matches itself
(`shared/workflow/fixtures-are-not-evidence.md`).
"""
import json
import os
import subprocess
import sys

HOOK = os.path.realpath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "warn-unmeasured-capability-claim.py"))

failures = 0
ran = 0


def check(label, ok):
    global failures, ran
    ran += 1
    if ok:
        print(f"PASS: {label}")
    else:
        failures += 1
        print(f"FAIL: {label}")


def run(payload, env=None):
    """(fired, stdout) for one PreToolUse payload."""
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        capture_output=True, text=True,
        env={**os.environ, **(env or {})})
    out = proc.stdout.strip()
    if proc.returncode != 0:
        return None, out
    if not out:
        return False, ""
    try:
        data = json.loads(out)
    except Exception:
        return None, out
    fired = bool((data.get("hookSpecificOutput") or {}).get("additionalContext"))
    return fired, out


def mcp(body, tool="mcp__github__add_issue_comment"):
    return {"tool_name": tool, "tool_input": {"body": body}}


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# --- 1. The real retracted claims, verbatim ---------------------------------
REAL_1 = (
    "Foreground dispatch, the remedy the guard prints, is unavailable -- the "
    "harness backgrounds every `Agent` call regardless of "
    "`run_in_background: false`.")
REAL_2 = (
    "The provenance chain is unbuildable in this harness as the records "
    "currently stand, independent of any spelling the guard learns.")
REAL_3 = (
    "No key this guard could learn will authorize this session's push.")

for i, body in enumerate((REAL_1, REAL_2, REAL_3), start=1):
    fired, _ = run(mcp(body))
    check(f"the real retracted claim #{i} fires", fired is True)

# --- 2. Both factors are required -------------------------------------------
# An absolute idiom with no tooling noun is ordinary prose.
fired, _ = run(mcp(
    "There is no way to know which wording the author preferred, so I kept "
    "both and let the reader choose."))
check("an absolute idiom with no tooling noun stays silent", fired is False)

# A tooling noun with no absolute idiom is a normal status comment.
fired, _ = run(mcp(
    "The harness backgrounds this dispatch, so the guard reads the agent id "
    "from the tool result and the review lands separately."))
check("a tooling noun with no absolute idiom stays silent", fired is False)

# --- 3. The window actually bounds the pairing ------------------------------
# Same two factors, far apart: not one claim.
far = ("There is no way to tell.\n" + ("filler line about prose style.\n" * 60)
       + "The harness is fine.\n")
fired, _ = run(mcp(far))
check("factors separated by more than the window stay silent", fired is False)

near = "There is no way to tell whether the harness dispatched it."
fired, _ = run(mcp(near))
check("factors inside the window fire", fired is True)

# --- 4. Surfaces -------------------------------------------------------------
for tool in ("mcp__github__issue_write", "mcp__github__update_pull_request",
             "mcp__github__create_pull_request"):
    fired, _ = run(mcp(REAL_2, tool=tool))
    check(f"`{tool}` is in scope", fired is True)

fired, _ = run(bash(
    'gh issue comment 1 --body "the provenance chain is unbuildable in this harness"'))
check("a gh issue comment is in scope", fired is True)

# A local commit is NOT this surface -- durability is the whole criterion.
fired, _ = run(bash(
    'git commit -m "the provenance chain is unbuildable in this harness"'))
check("a local git commit is out of scope", fired is False)

# The `gh|glab` test must be exercised on its own. The commit above also fails
# the verb filter ("commit" is not comment/create/edit), so it passed even with
# the forge-name check deleted -- the second filter masked the first, and a
# mutant dropping the first survived. This command clears the verb filter and
# must still be rejected for not being a forge write.
fired, _ = run(bash(
    'git commit -m "edit the guard: this dispatch is unavailable"'))
check("a non-forge command clearing the verb filter is still out of scope",
      fired is False)

# A read-only forge call carries no body to judge.
fired, _ = run({"tool_name": "mcp__github__issue_read",
                "tool_input": {"issue_number": 1}})
check("a read-only forge call stays silent", fired is False)

# --- 5. Never blocks, never raises ------------------------------------------
for label, payload in (
        ("empty payload", {}),
        ("no tool_input", {"tool_name": "mcp__github__add_issue_comment"}),
        ("non-dict tool_input", {"tool_name": "mcp__github__add_issue_comment",
                                 "tool_input": "oops"}),
        ("non-str body", {"tool_name": "mcp__github__add_issue_comment",
                          "tool_input": {"body": ["a", "b"]}}),
        ("non-str command", {"tool_name": "Bash",
                             "tool_input": {"command": 17}}),
):
    fired, out = run(payload)
    check(f"{label} exits 0 without firing", fired is False)

proc = subprocess.run([sys.executable, HOOK], input="not json at all",
                      capture_output=True, text=True)
check("garbage stdin exits 0", proc.returncode == 0)

# The output never carries a deny decision, whatever it says. The body must be
# UNIQUE: reusing REAL_1 here made the dedupe suppress the call, so `out` was
# "" and the assertion passed against nothing. A mutant adding a deny decision
# survived the whole suite until this line stopped being vacuous.
fired, out = run(mcp(REAL_1 + " (deny probe, unique text b7e04)"))
check("a firing emits no permissionDecision",
      fired is True and "permissionDecision" not in out)

# --- 6. Dedupe ---------------------------------------------------------------
unique = REAL_2 + "  (dedupe probe, unique text 8f21c)"
first, _ = run(mcp(unique))
second, _ = run(mcp(unique))
check("the same body fires once, not twice", first is True and second is False)

# --- 7. ANTIGRAVITY_AGENT suppresses only the systemMessage -----------------
fired, out = run(mcp(REAL_3 + " (antigravity probe 4c19a)"),
                 env={"ANTIGRAVITY_AGENT": "1"})
check("under ANTIGRAVITY_AGENT it still injects context",
      fired is True and "systemMessage" not in out)

print()
print(f"{ran - failures}/{ran} cases passed"
      if failures else f"All {ran} cases passed")
sys.exit(1 if failures else 0)
