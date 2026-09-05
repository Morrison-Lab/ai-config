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

The 2026-09-04 escalation (DENY on no-isolation + off-default-branch +
something-to-strand) added its own fixtures below the original ones: every
ORIGINAL payload above and below now carries a `cwd` pointing at a scratch
repo with NO `origin` remote configured, so `_default_branch()` resolves to
`None` and the deny path always falls through to the WARN/SILENT behaviour
those cases were written to test -- this file's job for THOSE cases is
unchanged from before the escalation. The escalation's own DENY/no-DENY
cases build their own repos with a real `origin` HEAD, a real branch, and
real dirty/clean state, the same way `test-no-clobbering-push.py` builds a
real remote to test against.

One of the new cases deliberately contradicts a premise this task was
DISPATCHED with. The brief asked for "read-only/non-write-capable agent
(unchanged behaviour)" as a DENY-path test, i.e. that `READ_ONLY` should
still exempt `adversarial-reviewer` from the escalation. That is what the
2026-09-04 incident's own launch WAS -- `adversarial-reviewer`, exempt from
the WARN by design, silently -- so a DENY that keeps the same exemption
would not have caught the incident it exists for; this was verified by
literally running the pre-escalation hook against an `adversarial-reviewer`
payload and observing silence, not a warning. `test_deny_readonly_role`
below tests the corrected behaviour (READ_ONLY roles ARE subject to DENY)
instead, and `test_readonly_role_unchanged_when_safe` covers what "unchanged
behaviour" correctly means: READ_ONLY roles stay silent on a clean,
on-default-branch checkout, exactly as before.

Run:  python3 hooks/test-flag-unassigned-worktree.py hooks/flag-unassigned-worktree.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
_TMPDIRS = []


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=check)


def _write(path, name, content):
    with open(os.path.join(path, name), "w", encoding="utf-8") as fh:
        fh.write(content)


def _no_origin_repo():
    """A plain repo with NO `origin` remote -- `_default_branch()` resolves
    to None here, so the DENY path always falls through, unchanged, for
    every ORIGINAL (pre-escalation) case built against this fixture."""
    path = tempfile.mkdtemp()
    _TMPDIRS.append(path)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@t.com")
    _git(path, "config", "user.name", "t")
    _write(path, "base.txt", "base\n")
    _git(path, "add", "base.txt")
    _git(path, "commit", "-qm", "base")
    return path


def _repo_with_default(default="main"):
    """A repo whose `origin/HEAD` resolves to `default`, one commit, no
    dirty state, no unpushed commits -- the clean baseline the escalation's
    own cases build ON TOP OF."""
    bare = tempfile.mkdtemp()
    _TMPDIRS.append(bare)
    _git(bare, "init", "-q", "--bare", "-b", default)

    path = tempfile.mkdtemp()
    _TMPDIRS.append(path)
    _git(path, "init", "-q", "-b", default)
    _git(path, "config", "user.email", "t@t.com")
    _git(path, "config", "user.name", "t")
    _write(path, "base.txt", "base\n")
    _git(path, "add", "base.txt")
    _git(path, "commit", "-qm", "base")
    _git(path, "remote", "add", "origin", bare)
    _git(path, "push", "-q", "-u", "origin", default)
    return path


NO_ORIGIN_REPO = _no_origin_repo()

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
      "tool_input": {"description": "Review diff", "prompt": "x",
                     "subagent_type": "adversarial-reviewer"}},
     "adversarial-reviewer is a repo-declared read-only dispatch (#2276)"),
    ({"tool_name": "Agent",
      "tool_input": {"description": "Review diff", "prompt": "x",
                     "run_in_background": True,
                     "subagent_type": "adversarial-reviewer"}},
     "a backgrounded adversarial-reviewer dispatch is exempt too"),
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

# Every ORIGINAL case above is pinned to the no-origin repo, so
# `_default_branch()` is always None there and the escalation always falls
# through -- these cases test WARN/SILENT exactly as before the escalation.
for _payload, _desc in SHOULD_WARN + SHOULD_STAY_SILENT:
    _payload.setdefault("cwd", NO_ORIGIN_REPO)


# ---------------------------------------------------- the 2026-09-04 escalation

def _dirty_feature_branch_repo():
    path = _repo_with_default("main")
    _git(path, "checkout", "-q", "-b", "feat/x")
    _write(path, "base.txt", "changed\n")
    _git(path, "add", "base.txt")  # tracked, uncommitted
    return path


def _unpushed_clean_feature_branch_repo():
    path = _repo_with_default("main")
    _git(path, "checkout", "-q", "-b", "feat/y")
    _write(path, "extra.txt", "extra\n")
    _git(path, "add", "extra.txt")
    _git(path, "commit", "-qm", "first push")
    _git(path, "push", "-q", "-u", "origin", "feat/y")  # establish an upstream
    _write(path, "extra2.txt", "extra2\n")
    _git(path, "add", "extra2.txt")
    _git(path, "commit", "-qm", "unpushed")  # ahead of that upstream, no push
    return path


def _clean_default_branch_repo():
    return _repo_with_default("main")


def _dirty_but_isolated_repo():
    return _dirty_feature_branch_repo()


def unisolated(subagent_type):
    return {"tool_name": "Agent",
           "tool_input": {"description": "x", "prompt": "x",
                          "subagent_type": subagent_type}}


def isolated(subagent_type):
    return {"tool_name": "Agent",
           "tool_input": {"description": "x", "prompt": "x",
                          "subagent_type": subagent_type, "isolation": "worktree"}}


SHOULD_DENY = [
    ({**unisolated("general-purpose"), "cwd": _dirty_feature_branch_repo()},
     "feature branch + uncommitted TRACKED changes + no isolation"),
    ({**unisolated("general-purpose"), "cwd": _unpushed_clean_feature_branch_repo()},
     "feature branch + UNPUSHED commits, clean tree + no isolation"),
    ({**unisolated("adversarial-reviewer"), "cwd": _dirty_feature_branch_repo()},
     "the 2026-09-04 incident's own launch type: adversarial-reviewer is "
     "READ_ONLY-exempt from the WARN, and NOT exempt here -- see the module "
     "docstring's 'One narrow case now DENIES instead' and this file's own "
     "header note about the contradicted brief premise"),
]

SHOULD_NOT_DENY = [
    ({**unisolated("general-purpose"), "cwd": _clean_default_branch_repo()},
     "default branch + clean tree + no isolation -- WARN, not DENY"),
    ({**isolated("general-purpose"), "cwd": _dirty_but_isolated_repo()},
     "feature branch + dirty + isolation PRESENT -- silent, not DENY"),
    ({**unisolated("Explore"), "cwd": _clean_default_branch_repo()},
     "test_readonly_role_unchanged_when_safe: READ_ONLY role, safe repo "
     "state -- silent, unchanged from before the escalation"),
]

# The escape hatch needs an env var on the SUBPROCESS rather than a payload
# key, so it is exercised separately below rather than through the
# declarative SHOULD_NOT_DENY list.
ESCAPE_HATCH_PAYLOAD = {**unisolated("general-purpose"),
                        "cwd": _dirty_feature_branch_repo()}


if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
             "read as 'silent' on every case and print a perfect pass")


def verdict(payload, env=None):
    run_env = dict(os.environ)
    run_env.pop("ALLOW_UNISOLATED_AGENT_LAUNCH", None)
    if env:
        run_env.update(env)
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True, text=True,
        env=run_env,
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
    if hso.get("permissionDecision") == "deny":
        return "DENY"
    # the hook must never make the harness MORE permissive than it was without it
    if "permissionDecision" in hso:
        sys.exit(f"FATAL: hook emitted permissionDecision="
                 f"{hso['permissionDecision']!r}; only 'deny' (the 2026-09-04 "
                 "escalation) or no permissionDecision at all are valid here")
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

print("\nshould DENY (2026-09-04 escalation):")
for payload, desc in SHOULD_DENY:
    v = verdict(payload)
    wrong += v != "DENY"
    print(f"  {v:<6} {desc}")

print("\nshould NOT deny (2026-09-04 escalation):")
for payload, desc in SHOULD_NOT_DENY:
    v = verdict(payload)
    wrong += v != "silent" and v != "WARN"
    print(f"  {v:<6} {desc}")

print("\nescalation edge cases (must not crash; must not deny):")
_DETACHED_REPO = _repo_with_default("main")
_git(_DETACHED_REPO, "checkout", "-q", "--detach", "HEAD")
_write(_DETACHED_REPO, "base.txt", "changed\n")
_git(_DETACHED_REPO, "add", "base.txt")
_NONGIT_DIR = tempfile.mkdtemp()
_TMPDIRS.append(_NONGIT_DIR)
for payload, desc in [
    ({**unisolated("general-purpose"), "cwd": _DETACHED_REPO},
     "detached HEAD -- no branch to compare, must not deny or crash"),
    ({**unisolated("general-purpose"), "cwd": _NONGIT_DIR},
     "non-git cwd -- must not deny or crash"),
]:
    v = verdict(payload)
    wrong += v == "DENY"
    print(f"  {v:<6} {desc}")

print("\nescape hatch:")
v_denied = verdict(ESCAPE_HATCH_PAYLOAD)
v_cleared = verdict(ESCAPE_HATCH_PAYLOAD, env={"ALLOW_UNISOLATED_AGENT_LAUNCH": "1"})
wrong += v_denied != "DENY"
wrong += v_cleared == "DENY"
print(f"  {v_denied:<6} without the override -- must DENY")
print(f"  {v_cleared:<6} with ALLOW_UNISOLATED_AGENT_LAUNCH=1 -- must clear the deny")

total = (len(SHOULD_WARN) + len(SHOULD_STAY_SILENT) + len(SHOULD_DENY)
        + len(SHOULD_NOT_DENY) + 2 + 2)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
