#!/usr/bin/env python3
"""Tests for no-mutation-in-read-only-reviewer.py.

Verifies that read-only reviewer personas (such as adversarial-reviewer,
Explore, Plan) are mechanistically forbidden from mutating git state (commit,
checkout, switch, stash, merge, reset, etc.) or writing files, while read-only
inspection commands (git diff, git log, git status, git stash list, etc.) and
ordinary orchestrator/author sessions remain fully allowed.

Run: python3 hooks/test-no-mutation-in-read-only-reviewer.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "no-mutation-in-read-only-reviewer.py")

sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures: list[str] = []
checks_run: int = 0


def check(label: str, got: object, want: object) -> None:
    global checks_run
    checks_run += 1
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def run_hook_proc(payload: dict) -> tuple[int, dict, str]:
    """Execute the hook process with payload on stdin. Returns (returncode, json_out, stderr)."""
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    raw = proc.stdout.strip()
    data = json.loads(raw) if raw else {}
    return proc.returncode, data, proc.stderr


# ---------------------------------------------------------------------------
# Direct offending() unit tests
# ---------------------------------------------------------------------------

RO_PAYLOAD = {"subagent_type": "adversarial-reviewer"}
ORCH_PAYLOAD = {}  # Orchestrator session (not read-only)

# 1. Mutating git commands that MUST be blocked in read-only personas
MUTATING_COMMANDS = [
    # #3602 incident shape
    ("git checkout -b fix/spellcheck", "checkout -b"),
    ("git checkout -B fix/spellcheck", "checkout -B"),
    ("git checkout main", "checkout branch"),
    ("git checkout -- skills/mwc/SKILL.md", "checkout file undo"),
    ("git checkout .", "checkout dot"),
    ("git commit -m 'wip commit'", "commit -m"),
    ("git commit -am 'fix bug'", "commit -am"),
    ("git commit --amend --no-edit", "commit amend"),
    ("git switch -c fix/branch", "switch -c"),
    ("git switch -C fix/branch", "switch -C"),
    ("git switch main", "switch branch"),
    ("git restore skills/mwc/SKILL.md", "restore file"),
    ("git restore --staged .", "restore staged"),
    # #3584 incident shape
    ("git stash pop", "stash pop"),
    ("git stash apply", "stash apply"),
    ("git stash", "bare stash"),
    ("git stash push -m 'save temp'", "stash push"),
    ("git stash -u", "stash -u flag"),
    ("git stash drop stash@{0}", "stash drop"),
    ("git stash clear", "stash clear"),
    ("git reset --soft HEAD~1", "reset --soft"),
    ("git reset --hard HEAD", "reset --hard"),
    ("git reset HEAD", "reset mixed"),
    ("git reset", "bare reset"),
    ("git merge origin/main", "merge"),
    ("git rebase origin/main", "rebase"),
    ("git revert HEAD", "revert"),
    ("git cherry-pick 12345678", "cherry-pick"),
    ("git clean -fd", "clean -fd"),
    ("git rm unwanted.txt", "git rm"),
    ("git mv old_path.txt new_path.txt", "git mv"),
    ("git apply patch.diff", "git apply"),
    ("git am patch.mbox", "git am"),
    ("git push origin fix/test", "git push"),
    ("git push", "bare git push"),
    ("git branch -d dead-branch", "branch -d"),
    ("git branch -D dead-branch", "branch -D"),
    ("git branch -m old-name new-name", "branch -m"),
    ("git branch new-feature", "branch creation"),
    ("git tag -d v1.0.0", "tag -d"),
    ("git tag v1.0.0", "tag creation"),
    ("git init -b main", "git init"),
    ("git clone -b main https://example.com/repo.git", "git clone"),
    ("git pull", "git pull"),
    ("git pull origin main", "git pull with args"),
    ("git add .", "git add dot"),
    ("git add -A", "git add all"),
    ("git add file.py", "git add file"),
    ("git stage file.py", "git stage file"),
    # Wrapped and chained variations
    ("sudo git commit -m 'root commit'", "sudo git commit"),
    ("cd /path && git checkout -b fix", "chained checkout -b"),
    ("echo foo && git stash pop", "chained stash pop"),
    ("time git push origin main", "time git push"),
]

for cmd, label in MUTATING_COMMANDS:
    hit = hook.offending("Bash", {"command": cmd}, RO_PAYLOAD)
    check(f"must block in read-only persona ({label}): {cmd}", hit is not None, True)

# 2. Read-only git commands and non-git commands that MUST be allowed
READ_ONLY_COMMANDS = [
    ("git diff origin/main...HEAD", "git diff"),
    ("git diff --stat", "git diff stat"),
    ("git diff HEAD~1", "git diff commit"),
    ("git log -n 5 --oneline", "git log"),
    ("git show HEAD", "git show"),
    ("git show HEAD:skills/mwc/SKILL.md", "git show blob"),
    ("git status", "git status"),
    ("git status --short", "git status short"),
    ("git rev-parse HEAD", "git rev-parse"),
    ("git rev-parse --verify HEAD", "git rev-parse verify"),
    ("git rev-list --count origin/main..HEAD", "git rev-list"),
    ("git cat-file -p HEAD", "git cat-file"),
    ("git describe --tags", "git describe"),
    ("git ls-files", "git ls-files"),
    ("git ls-tree HEAD", "git ls-tree"),
    ("git ls-remote --heads origin", "git ls-remote"),
    ("git fetch origin", "git fetch"),
    ("git grep 'pattern'", "git grep"),
    ("git blame file.txt", "git blame"),
    ("git shortlog -s", "git shortlog"),
    ("git version", "git version"),
    ("git help status", "git help"),
    ("git config --get user.name", "git config get"),
    ("git stash list", "stash list"),
    ("git stash show -p stash@{0}", "stash show"),
    ("git stash --help", "stash help"),
    ("git branch", "bare branch list"),
    ("git branch -a", "branch -a"),
    ("git branch -r", "branch -r"),
    ("git branch --list", "branch --list"),
    ("git branch --show-current", "branch --show-current"),
    ("git tag", "bare tag list"),
    ("git tag -l", "tag -l"),
    ("git tag --list 'v*'", "tag --list"),
    ("pytest tests/", "pytest"),
    ("npm test", "npm test"),
    ("python3 scripts/check-links.py", "python script"),
    ("grep 'git commit' file.py", "grep mentioning git commit"),
    ("echo 'git commit -m wip'", "echo mentioning commit"),
    ("# git checkout -b fix", "comment with git command"),
]

for cmd, label in READ_ONLY_COMMANDS:
    hit = hook.offending("Bash", {"command": cmd}, RO_PAYLOAD)
    check(f"must allow in read-only persona ({label}): {cmd}", hit, None)

# 3. Write tools must be blocked in read-only personas
for wtool in ("Write", "Edit", "NotebookEdit", "write_to_file", "replace_file_content"):
    hit = hook.offending(wtool, {"file_path": "foo.py"}, RO_PAYLOAD)
    check(f"must block write tool in read-only persona ({wtool})", hit is not None, True)

# 4. Orchestrator and write-capable sessions must be allowed to commit/checkout/stash
for cmd in ("git commit -m 'msg'", "git checkout -b fix", "git stash pop", "git push origin main"):
    hit = hook.offending("Bash", {"command": cmd}, ORCH_PAYLOAD)
    check(f"must allow mutating command in orchestrator session: {cmd}", hit, None)

for wtool in ("Write", "Edit", "NotebookEdit", "write_to_file", "replace_file_content"):
    hit = hook.offending(wtool, {"file_path": "foo.py"}, ORCH_PAYLOAD)
    check(f"must allow write tool in orchestrator session ({wtool})", hit, None)

# 5. Non-read-only subagent types must be allowed
for write_stype in ("general-purpose", "author", "coder", "refactorer"):
    hit = hook.offending("Bash", {"command": "git commit -m 'fix'"}, {"subagent_type": write_stype})
    check(f"must allow mutating command for write-capable subagent ({write_stype})", hit, None)

# 6. Recognized read-only personas
for ro_stype in ("adversarial-reviewer", "code-reviewer", "security-reviewer", "reviewer", "Explore", "Plan", "explore", "plan"):
    hit = hook.offending("Bash", {"command": "git commit -m 'fix'"}, {"subagent_type": ro_stype})
    check(f"must recognize read-only subagent_type ({ro_stype})", hit is not None, True)

for ro_role in ("Adversarial Reviewer", "Code Reviewer", "Security Reviewer", "adversarial reviewer", "code reviewer", "security reviewer"):
    hit = hook.offending("Bash", {"command": "git commit -m 'fix'"}, {"Role": ro_role})
    check(f"must recognize read-only Role with spaces ({ro_role})", hit is not None, True)

# 7. Authorized escape valve / overrides
OVERRIDE_CASES = [
    "ALLOW_READ_ONLY_MUTATION=1 git commit -m 'override'",
    "ALLOW_REVIEWER_MUTATION=1 git checkout -b fix/emergency",
    "ALLOW_READ_ONLY_MUTATION=1 git stash pop",
]
for cmd in OVERRIDE_CASES:
    hit = hook.offending("Bash", {"command": cmd}, RO_PAYLOAD)
    check(f"must respect inline override: {cmd}", hit, None)

# 8. Transcript-based detection (Claude Code subagent transcript)
with tempfile.NamedTemporaryFile("w", delete=False, suffix=".jsonl", prefix="agent-") as tf:
    # Emulate Claude Code subagent transcript
    tf.write(json.dumps({"type": "user", "message": {"content": "Review the diff at HEAD"}}) + "\n")
    tf.write(json.dumps({
        "type": "assistant",
        "attributionAgent": "adversarial-reviewer",
        "message": {"content": "Inspecting git diff"},
    }) + "\n")
    transcript_file = tf.name

try:
    payload_with_transcript = {
        "tool_name": "Bash",
        "tool_input": {"command": "git checkout -b fix/stray"},
        "transcript_path": transcript_file,
    }
    hit = hook.offending("Bash", payload_with_transcript["tool_input"], payload_with_transcript)
    check("must detect read-only persona from transcript attributionAgent", hit is not None, True)

    # Clean inspect in same transcript must pass
    hit_read = hook.offending("Bash", {"command": "git diff origin/main...HEAD"}, payload_with_transcript)
    check("must allow git diff in transcript-detected reviewer", hit_read, None)
finally:
    try:
        os.unlink(transcript_file)
    except Exception:
        pass

# 9. Subagent transcript path with review prompt
subagent_dir = tempfile.mkdtemp()
subagent_transcript = os.path.join(subagent_dir, "subagents", "agent-a1234567.jsonl")
os.makedirs(os.path.dirname(subagent_transcript), exist_ok=True)
with open(subagent_transcript, "w", encoding="utf-8") as tf:
    tf.write(json.dumps({
        "type": "user",
        "message": {"content": "Perform an adversarial code review of the committed diff."},
    }) + "\n")

try:
    payload_sub = {
        "tool_name": "Bash",
        "tool_input": {"command": "git stash pop"},
        "transcript_path": subagent_transcript,
    }
    hit = hook.offending("Bash", payload_sub["tool_input"], payload_sub)
    check("must detect reviewer subagent from path and prompt", hit is not None, True)
finally:
    try:
        os.unlink(subagent_transcript)
        os.rmdir(os.path.dirname(subagent_transcript))
        os.rmdir(subagent_dir)
    except Exception:
        pass

# 10. Negative test: Write-capable subagent whose brief contains review words
write_subagent_dir = tempfile.mkdtemp()
write_subagent_transcript = os.path.join(write_subagent_dir, "subagents", "agent-write123.jsonl")
os.makedirs(os.path.dirname(write_subagent_transcript), exist_ok=True)
with open(write_subagent_transcript, "w", encoding="utf-8") as tf:
    tf.write(json.dumps({
        "type": "user",
        "message": {"content": "Review the diff and then fix every issue you find, committing as you go"},
    }) + "\n")

try:
    payload_write_sub = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'fix: resolved issue'"},
        "transcript_path": write_subagent_transcript,
    }
    hit = hook.offending("Bash", payload_write_sub["tool_input"], payload_write_sub)
    check("must NOT block write-capable subagent briefed to review and fix/commit", hit, None)
finally:
    try:
        os.unlink(write_subagent_transcript)
        os.rmdir(os.path.dirname(write_subagent_transcript))
        os.rmdir(write_subagent_dir)
    except Exception:
        pass

# 11. Negative test: Orchestrator session transcript with historical subagent records
orch_transcript_dir = tempfile.mkdtemp()
orch_transcript = os.path.join(orch_transcript_dir, "session-orch-main.jsonl")
with open(orch_transcript, "w", encoding="utf-8") as tf:
    tf.write(json.dumps({
        "type": "assistant",
        "isSidechain": True,
        "attributionAgent": "adversarial-reviewer",
        "message": {"content": "Historical subagent review output"},
    }) + "\n")
    tf.write(json.dumps({
        "type": "user",
        "message": {"content": "Great, please push the branch now"},
    }) + "\n")

try:
    payload_orch = {
        "tool_name": "Bash",
        "tool_input": {"command": "git push origin main"},
        "transcript_path": orch_transcript,
    }
    hit = hook.offending("Bash", payload_orch["tool_input"], payload_orch)
    check("must NOT block orchestrator session whose transcript carries historical subagent records", hit, None)
finally:
    try:
        os.unlink(orch_transcript)
        os.rmdir(orch_transcript_dir)
    except Exception:
        pass

# 12. Subagent prompt nuance: prohibitive briefs vs affirmative write briefs
prohibitive_dir = tempfile.mkdtemp()
try:
    # 12a. Prohibitive brief that mentions forbidden write words
    p1 = os.path.join(prohibitive_dir, "subagents", "agent-prohibit.jsonl")
    os.makedirs(os.path.dirname(p1), exist_ok=True)
    with open(p1, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Do not edit, fix, or commit anything. This is a read-only review; only inspect and report findings."},
        }) + "\n")
    payload_p1 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'oops'"}, "transcript_path": p1}
    hit = hook.offending("Bash", payload_p1["tool_input"], payload_p1)
    check("must detect read-only persona even when prohibitive brief mentions forbidden write words", hit is not None, True)

    # 12b. Verbatim agent prompt containing 'Edit and Write' in its read-only description
    p2 = os.path.join(prohibitive_dir, "subagents", "agent-adv-prompt.jsonl")
    with open(p2, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Read-only adversarial reviewer... Its declared allowlist omits Edit and Write. You are an adversarial reviewer."},
        }) + "\n")
    payload_p2 = {"tool_name": "Bash", "tool_input": {"command": "git checkout -b sneak"}, "transcript_path": p2}
    hit = hook.offending("Bash", payload_p2["tool_input"], payload_p2)
    check("must detect read-only persona when agent prompt mentions 'omits Edit and Write'", hit is not None, True)

    # 12c. Affirmative write instruction in review context
    p3 = os.path.join(prohibitive_dir, "subagents", "agent-affirm-write.jsonl")
    with open(p3, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Perform an adversarial review and then fix every issue you find, committing as you go."},
        }) + "\n")
    payload_p3 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p3}
    hit = hook.offending("Bash", payload_p3["tool_input"], payload_p3)
    check("must NOT block when review brief has affirmative write directive ('and then fix...')", hit, None)

    # 12d. Explicit 'not read-only' instruction alongside review terminology (Finding 1)
    p4 = os.path.join(prohibitive_dir, "subagents", "agent-not-ro.jsonl")
    with open(p4, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "This task is not read-only; perform an adversarial review and submit the findings."},
        }) + "\n")
    payload_p4 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p4}
    hit = hook.offending("Bash", payload_p4["tool_input"], payload_p4)
    check("must NOT block when brief explicitly specifies 'not read-only' even with review wording", hit, None)

    # 12e. Singular noun affirmative write directive (Finding 2)
    p5 = os.path.join(prohibitive_dir, "subagents", "agent-write-test.jsonl")
    with open(p5, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Perform an adversarial review and write a test reproducing the defect."},
        }) + "\n")
    payload_p5 = {"tool_name": "Write", "tool_input": {"TargetFile": "tests/test_repro.py"}, "transcript_path": p5}
    hit = hook.offending("Write", payload_p5["tool_input"], payload_p5)
    check("must NOT block file write when review brief directs writing a reproduction test", hit, None)

    # 12f. Reproduction script creation directive (Finding 2)
    p6 = os.path.join(prohibitive_dir, "subagents", "agent-create-script.jsonl")
    with open(p6, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Perform an adversarial code review and create a reproduction script."},
        }) + "\n")
    payload_p6 = {"tool_name": "Write", "tool_input": {"TargetFile": "repro.sh"}, "transcript_path": p6}
    hit = hook.offending("Write", payload_p6["tool_input"], payload_p6)
    check("must NOT block file write when review brief directs creating a reproduction script", hit, None)

    # 12g. Non-reviewer subagent instructed not to commit must NOT have file writes blocked (Finding 3)
    p7 = os.path.join(prohibitive_dir, "subagents", "agent-no-commit.jsonl")
    with open(p7, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Refactor parser functions in foo.py to improve performance without committing."},
        }) + "\n")
    payload_p7 = {"tool_name": "Edit", "tool_input": {"TargetFile": "foo.py"}, "transcript_path": p7}
    hit = hook.offending("Edit", payload_p7["tool_input"], payload_p7)
    check("must NOT block file write tools on coding subagent briefed without committing", hit, None)

    # 12h. Multi-verb compound negative prohibition (Finding 4)
    p8 = os.path.join(prohibitive_dir, "subagents", "agent-multi-verb.jsonl")
    with open(p8, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Do not edit, modify, or change anything; inspect the codebase only."},
        }) + "\n")
    payload_p8 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p8}
    hit = hook.offending("Bash", payload_p8["tool_input"], payload_p8)
    check("must detect read-only persona on compound multi-verb prohibition", hit is not None, True)

    # 12i. Scoped 'never edit files outside' instruction with affirmative commit directive (Claude review finding)
    p9 = os.path.join(prohibitive_dir, "subagents", "agent-never-scope.jsonl")
    with open(p9, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Never edit files outside your worktree. Fix the failing tests and commit."},
        }) + "\n")
    payload_p9 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p9}
    hit = hook.offending("Bash", payload_p9["tool_input"], payload_p9)
    check("must NOT block git commit when prompt scopes edits with 'Never edit files outside' and directs commit", hit, None)

    # 12j. Scoped 'without editing files outside' with affirmative commit
    p10 = os.path.join(prohibitive_dir, "subagents", "agent-without-scope.jsonl")
    with open(p10, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Perform the refactor without editing files outside your worktree. Fix defects and commit as you go."},
        }) + "\n")
    payload_p10 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p10}
    hit = hook.offending("Bash", payload_p10["tool_input"], payload_p10)
    check("must NOT block git commit when prompt uses 'without editing files outside' with commit directive", hit, None)

    # 12k. Prohibitive review brief with negated write verb (Finding 1)
    p11 = os.path.join(prohibitive_dir, "subagents", "agent-prohibit-write-tests.jsonl")
    with open(p11, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Adversarial code review. Do not write tests; review only."},
        }) + "\n")
    payload_p11 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p11}
    hit = hook.offending("Bash", payload_p11["tool_input"], payload_p11)
    check("must block git commit when review brief negates write verbs ('Do not write tests')", hit is not None, True)

    # 12l. Prohibitive review brief with negated code/file writing (Finding 1)
    p12 = os.path.join(prohibitive_dir, "subagents", "agent-prohibit-write-code.jsonl")
    with open(p12, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Review the code. Do not write code or edit any files."},
        }) + "\n")
    payload_p12 = {"tool_name": "Bash", "tool_input": {"command": "git checkout -b sneak"}, "transcript_path": p12}
    hit = hook.offending("Bash", payload_p12["tool_input"], payload_p12)
    check("must block git checkout when brief says 'Do not write code or edit any files'", hit is not None, True)

    # 12m. Scoped with 'any files outside' and affirmative commit (Finding 3)
    p13 = os.path.join(prohibitive_dir, "subagents", "agent-never-any-outside.jsonl")
    with open(p13, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Never edit any files outside your worktree. Fix the failing tests and commit."},
        }) + "\n")
    payload_p13 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p13}
    hit = hook.offending("Bash", payload_p13["tool_input"], payload_p13)
    check("must NOT block git commit when prompt uses 'Never edit any files outside' with commit directive", hit, None)

    # 12n. Scoped with 'Do not edit any files outside' and affirmative commit (Finding 3)
    p14 = os.path.join(prohibitive_dir, "subagents", "agent-do-not-any-outside.jsonl")
    with open(p14, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Do not edit any files outside your worktree. Fix the failing tests and commit."},
        }) + "\n")
    payload_p14 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p14}
    hit = hook.offending("Bash", payload_p14["tool_input"], payload_p14)
    check("must NOT block git commit when prompt uses 'Do not edit any files outside' with commit directive", hit, None)

    # 12o. Scoped with 'Make no changes to unrelated files' and affirmative commit (Claude review round 4)
    p15 = os.path.join(prohibitive_dir, "subagents", "agent-make-no-changes-scope.jsonl")
    with open(p15, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Make no changes to unrelated files, but fix the reported bug and commit your change."},
        }) + "\n")
    payload_p15 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p15}
    hit = hook.offending("Bash", payload_p15["tool_input"], payload_p15)
    check("must NOT block git commit when prompt scopes edits with 'Make no changes to unrelated files' and directs commit", hit, None)

    # 12p. Total 'Make no changes' prohibition (Claude review round 4)
    p16 = os.path.join(prohibitive_dir, "subagents", "agent-make-no-changes-total.jsonl")
    with open(p16, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Make no changes. Only inspect the code and report findings."},
        }) + "\n")
    payload_p16 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'oops'"}, "transcript_path": p16}
    hit = hook.offending("Bash", payload_p16["tool_input"], payload_p16)
    check("must block git commit when prompt issues total 'Make no changes' prohibition", hit is not None, True)

    # 12q. Explicit read-only reviewer with remediation advice (adversarial review round 5)
    p17 = os.path.join(prohibitive_dir, "subagents", "agent-ro-remediation-advice.jsonl")
    with open(p17, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "You are a read-only reviewer. Do not edit, change, or modify any files. Suggest how to fix the issues."},
        }) + "\n")
    payload_p17 = {"tool_name": "Write", "tool_input": {"TargetFile": "fix.py"}, "transcript_path": p17}
    hit = hook.offending("Write", payload_p17["tool_input"], payload_p17)
    check("must block write tools when explicit read-only prompt includes remediation advice", hit is not None, True)

    # 12r. Scoped with 'Make no changes to any files outside' and affirmative commit (adversarial review round 5)
    p18 = os.path.join(prohibitive_dir, "subagents", "agent-make-no-changes-any-files-outside.jsonl")
    with open(p18, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Make no changes to any files outside your worktree. Fix the failing tests and commit."},
        }) + "\n")
    payload_p18 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p18}
    hit = hook.offending("Bash", payload_p18["tool_input"], payload_p18)
    check("must NOT block git commit when prompt uses 'Make no changes to any files outside' with commit directive", hit, None)

    # 12s. Blanket 'Make no changes to files' prohibition (Claude review round 6)
    p19 = os.path.join(prohibitive_dir, "subagents", "agent-make-no-changes-to-files.jsonl")
    with open(p19, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Make no changes to files. Report findings only."},
        }) + "\n")
    payload_p19 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'oops'"}, "transcript_path": p19}
    hit = hook.offending("Bash", payload_p19["tool_input"], payload_p19)
    check("must block git commit when prompt issues blanket 'Make no changes to files' prohibition", hit is not None, True)

    # 12t. Resource-scoped 'read-only' with affirmative write directive (Claude review round 7)
    p20 = os.path.join(prohibitive_dir, "subagents", "agent-resource-scoped-ro.jsonl")
    with open(p20, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "The vendored/ directory is read-only; don't touch it. Fix the bug in mutable.py and commit your change."},
        }) + "\n")
    payload_p20 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p20}
    hit = hook.offending("Bash", payload_p20["tool_input"], payload_p20)
    check("must NOT block git commit when prompt scopes read-only to a resource and directs commit", hit, None)

    # 12u. Negator separated from verb by intervening words (Claude review round 8)
    p21 = os.path.join(prohibitive_dir, "subagents", "agent-intervening-words-negation.jsonl")
    with open(p21, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "This is an adversarial review. Do not try to fix any bugs you find; only report them."},
        }) + "\n")
    payload_p21 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p21}
    hit = hook.offending("Bash", payload_p21["tool_input"], payload_p21)
    check("must block git commit when review prompt has negator separated from verb ('Do not try to fix')", hit is not None, True)

    # 12v. Negator with comma-delimited parenthetical interjection (Claude review round 9)
    p22 = os.path.join(prohibitive_dir, "subagents", "agent-comma-interjection.jsonl")
    with open(p22, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "This is an adversarial review. You must not, regardless of what you find, fix the bug or commit the change."},
        }) + "\n")
    payload_p22 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p22}
    hit = hook.offending("Bash", payload_p22["tool_input"], payload_p22)
    check("must block git commit when review prompt has comma-bounded interjection between negator and verb", hit is not None, True)

    # 12w. Unrelated negation in preceding clause separated by comma-coordinated conjunction (Claude review round 10)
    p23 = os.path.join(prohibitive_dir, "subagents", "agent-unrelated-clause-negation.jsonl")
    with open(p23, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "This is an adversarial review. Don't skip any tests, and make sure you fix every failing test and commit your changes."},
        }) + "\n")
    payload_p23 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p23}
    hit = hook.offending("Bash", payload_p23["tool_input"], payload_p23)
    check("must NOT block git commit when prompt has unrelated negation before coordinated affirmative write directive", hit, None)

    # 12x. Oxford-comma list of prohibited actions (Adversarial review Finding 1)
    p24 = os.path.join(prohibitive_dir, "subagents", "agent-oxford-comma-prohibited.jsonl")
    with open(p24, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Review the code. Do not write code, edit, and commit any files."},
        }) + "\n")
    payload_p24 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p24}
    hit = hook.offending("Bash", payload_p24["tool_input"], payload_p24)
    check("must block git commit when prompt has Oxford-comma list of prohibited actions", hit is not None, True)

    # 12y. Motivating directive 'and commit your changes' after unrelated negation (Adversarial review Finding 2)
    p25 = os.path.join(prohibitive_dir, "subagents", "agent-commit-your-changes.jsonl")
    with open(p25, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "This is an adversarial review. Don't skip any tests, and commit your changes."},
        }) + "\n")
    payload_p25 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p25}
    hit = hook.offending("Bash", payload_p25["tool_input"], payload_p25)
    check("must NOT block git commit when prompt directs 'and commit your changes' after unrelated negation", hit, None)

    # 12z1. 'and then commit' after comma/negation (Finding 1)
    p26 = os.path.join(prohibitive_dir, "subagents", "agent-and-then-commit.jsonl")
    with open(p26, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Do not edit config.json, and then commit your changes."},
        }) + "\n")
    payload_p26 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p26}
    hit = hook.offending("Bash", payload_p26["tool_input"], payload_p26)
    check("must NOT block git commit when prompt directs 'and then commit your changes' after negation", hit, None)

    # 12z2. Oxford-comma list with add, delete (Finding 2)
    p27 = os.path.join(prohibitive_dir, "subagents", "agent-oxford-add-delete.jsonl")
    with open(p27, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Review the code. Do not add, delete, and commit any files."},
        }) + "\n")
    payload_p27 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p27}
    hit = hook.offending("Bash", payload_p27["tool_input"], payload_p27)
    check("must block git commit when Oxford-comma list uses add/delete verbs", hit is not None, True)

    # 12z3. Demonstrative 'this change' (Finding 3)
    p28 = os.path.join(prohibitive_dir, "subagents", "agent-commit-this-change.jsonl")
    with open(p28, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Don't skip any tests, and commit this change."},
        }) + "\n")
    payload_p28 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p28}
    hit = hook.offending("Bash", payload_p28["tool_input"], payload_p28)
    check("must NOT block git commit with demonstrative 'and commit this change'", hit, None)

    # 12z4. Pronoun target 'and fix it' (Finding 3)
    p29 = os.path.join(prohibitive_dir, "subagents", "agent-fix-it.jsonl")
    with open(p29, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Don't skip any tests, and fix it."},
        }) + "\n")
    payload_p29 = {"tool_name": "Edit", "tool_input": {"file_path": "main.py"}, "transcript_path": p29}
    hit = hook.offending("Edit", payload_p29["tool_input"], payload_p29)
    check("must NOT block Edit with pronoun target 'and fix it'", hit, None)

    # 12z5. Standalone 'Do not commit any files.' without review prompt words
    p30 = os.path.join(prohibitive_dir, "subagents", "agent-do-not-commit.jsonl")
    with open(p30, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Do not commit any files."},
        }) + "\n")
    payload_p30 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p30}
    hit = hook.offending("Bash", payload_p30["tool_input"], payload_p30)
    check("must block git commit when prompt states 'Do not commit any files.'", hit is not None, True)

    # 12z6. 'without committing any files'
    p31 = os.path.join(prohibitive_dir, "subagents", "agent-without-committing.jsonl")
    with open(p31, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Inspect the logs without committing any files."},
        }) + "\n")
    payload_p31 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p31}
    hit = hook.offending("Bash", payload_p31["tool_input"], payload_p31)
    check("must block git commit when prompt states 'without committing any files'", hit is not None, True)

    # 12z7. Demonstratives 'make that change' and 'apply those fixes'
    p32 = os.path.join(prohibitive_dir, "subagents", "agent-make-that-change.jsonl")
    with open(p32, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "This is an adversarial review. Don't skip tests, and make that change."},
        }) + "\n")
    payload_p32 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p32}
    hit = hook.offending("Bash", payload_p32["tool_input"], payload_p32)
    check("must NOT block git commit when prompt directs 'make that change'", hit, None)

    # 12z8. Pronouns 'this' / 'that' in 'and commit this'
    p33 = os.path.join(prohibitive_dir, "subagents", "agent-commit-this.jsonl")
    with open(p33, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Don't change config, and commit this."},
        }) + "\n")
    payload_p33 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p33}
    hit = hook.offending("Bash", payload_p33["tool_input"], payload_p33)
    check("must NOT block git commit when prompt directs 'and commit this'", hit, None)

    # 12z9. 'apply that fix' and pronoun 'and modify that'
    p34 = os.path.join(prohibitive_dir, "subagents", "agent-apply-that-fix.jsonl")
    with open(p34, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Review the code. Don't skip tests, and modify that."},
        }) + "\n")
    payload_p34 = {"tool_name": "Edit", "tool_input": {"file_path": "main.py"}, "transcript_path": p34}
    hit = hook.offending("Edit", payload_p34["tool_input"], payload_p34)
    check("must NOT block Edit when prompt directs 'and modify that'", hit, None)

    # 12z10. 'without fixing any files'
    p35 = os.path.join(prohibitive_dir, "subagents", "agent-without-fixing.jsonl")
    with open(p35, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Inspect the logs without fixing any files."},
        }) + "\n")
    payload_p35 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p35}
    hit = hook.offending("Bash", payload_p35["tool_input"], payload_p35)
    check("must block git commit when prompt states 'without fixing any files'", hit is not None, True)

    # 12z11. Interjection 'Do not, under any circumstances, edit or fix any files.'
    p36 = os.path.join(prohibitive_dir, "subagents", "agent-interjection-circumstances.jsonl")
    with open(p36, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Do not, under any circumstances, edit or fix any files. Only inspect and report."},
        }) + "\n")
    payload_p36 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p36}
    hit = hook.offending("Bash", payload_p36["tool_input"], payload_p36)
    check("must block git commit with interjection 'Do not, under any circumstances, edit or fix any files'", hit is not None, True)

    # 12z12. Interjection 'Do not, for any reason, commit any files.'
    p37 = os.path.join(prohibitive_dir, "subagents", "agent-interjection-for-any-reason.jsonl")
    with open(p37, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Do not, for any reason, commit any files."},
        }) + "\n")
    payload_p37 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p37}
    hit = hook.offending("Bash", payload_p37["tool_input"], payload_p37)
    check("must block git commit with interjection 'Do not, for any reason, commit any files'", hit is not None, True)

    # 12z13. Interjection 'Never, under any circumstances, edit any files.'
    p38 = os.path.join(prohibitive_dir, "subagents", "agent-never-interjection.jsonl")
    with open(p38, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Never, under any circumstances, edit any files."},
        }) + "\n")
    payload_p38 = {"tool_name": "Edit", "tool_input": {"file_path": "main.py"}, "transcript_path": p38}
    hit = hook.offending("Edit", payload_p38["tool_input"], payload_p38)
    check("must block Edit with interjection 'Never, under any circumstances, edit any files'", hit is not None, True)

    # 12z14. Won't negation in review brief
    p39 = os.path.join(prohibitive_dir, "subagents", "agent-wont-commit.jsonl")
    with open(p39, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "This is an adversarial review. You won't commit your changes; only report findings."},
        }) + "\n")
    payload_p39 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p39}
    hit = hook.offending("Bash", payload_p39["tool_input"], payload_p39)
    check("must block git commit when review brief states 'You won't commit your changes'", hit is not None, True)

    # 12z15. Will not negation prohibition
    p40 = os.path.join(prohibitive_dir, "subagents", "agent-will-not-edit.jsonl")
    with open(p40, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "You will not edit or commit any files."},
        }) + "\n")
    payload_p40 = {"tool_name": "Edit", "tool_input": {"file_path": "main.py"}, "transcript_path": p40}
    hit = hook.offending("Edit", payload_p40["tool_input"], payload_p40)
    check("must block Edit when prompt states 'You will not edit or commit any files.'", hit is not None, True)

    # 12z16. Subordinate conjunction 'until' with unrelated preceding modal negator allows write
    p41 = os.path.join(prohibitive_dir, "subagents", "agent-wont-stop-until.jsonl")
    with open(p41, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "This is an adversarial review, and you won't stop until you fix the bugs and commit the changes."},
        }) + "\n")
    payload_p41 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}, "transcript_path": p41}
    hit = hook.offending("Bash", payload_p41["tool_input"], payload_p41)
    check("must allow git commit when prompt contains affirmative write after subordinate conjunction 'until'", hit, None)

    # 12z17. Prohibition with subordinate clause 'until' blocks mutating commands
    p42 = os.path.join(prohibitive_dir, "subagents", "agent-do-not-commit-until.jsonl")
    with open(p42, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "type": "user",
            "message": {"content": "Do not commit any files until you are told to do so."},
        }) + "\n")
    payload_p42 = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneaky'"}, "transcript_path": p42}
    hit = hook.offending("Bash", payload_p42["tool_input"], payload_p42)
    check("must block git commit when prompt states 'Do not commit any files until you are told to do so.'", hit is not None, True)
finally:
    try:
        import shutil
        shutil.rmtree(prohibitive_dir, ignore_errors=True)
    except Exception:
        pass

# 13. Process execution & output shape verification
payload_deny = {
    "tool_name": "Bash",
    "tool_input": {"command": "git commit -m 'attempt fix'"},
    "subagent_type": "adversarial-reviewer",
}
rc, data, err = run_hook_proc(payload_deny)
check("process exit code on deny is 0", rc, 0)
hso = data.get("hookSpecificOutput") or {}
check("hookEventName is PreToolUse", hso.get("hookEventName"), "PreToolUse")
check("permissionDecision is deny", hso.get("permissionDecision"), "deny")
reason = hso.get("permissionDecisionReason") or ""
check("reason mentions MECHANISTIC PROHIBITION", "MECHANISTIC PROHIBITION" in reason, True)
check("reason cites #3612", "3612" in reason, True)
check("reason cites #3602", "3602" in reason, True)
check("reason cites #3584", "3584" in reason, True)
check("reason names ALLOW_READ_ONLY_MUTATION=1 override", "ALLOW_READ_ONLY_MUTATION=1" in reason, True)

# Allowed process execution
payload_allow = {
    "tool_name": "Bash",
    "tool_input": {"command": "git diff origin/main...HEAD"},
    "subagent_type": "adversarial-reviewer",
}
rc_allow, data_allow, _ = run_hook_proc(payload_allow)
check("process exit code on allow is 0", rc_allow, 0)
check("allowed output has no deny decision", (data_allow.get("hookSpecificOutput") or {}).get("permissionDecision"), None)

# Print test results
if failures:
    print(f"FAILED: {len(failures)} failure(s)")
    for f in failures:
        print("  -", f)
    sys.exit(1)

print(f"PASS: hooks/test-no-mutation-in-read-only-reviewer.py -- all {checks_run} assertions passed")
sys.exit(0)
