#!/usr/bin/env python3
"""PreToolUse guard: warn before `git push` carrying a new-line-breaks violation.

## The incident

Hit twice in one GIA session (2026-08-29, wave 2): PR #2583
(`shared/principles/fail-fast.md`) and PR #2585 (`README.md`) each pushed a
prose commit that failed CI's `new-line-breaks` job, despite this repo's own
`CLAUDE.md` extensively documenting the pre-push habit of running
`NLB_BASE_REF=origin/main python3 scripts/vendor/gha-check-new-line-breaks.py`
first. Both were fixed the same way (`scripts/semantic-line-breaks.py <file>
--write` plus a follow-up commit), but the recurrence cost a CI round-trip
each time on a check that is cheap and fast to run locally.

Recorded as `memories/mistake-patterns.md` Pattern 25.

## Why a hook rather than a rule

A passive prose reminder to run the checker before pushing only fires if you
remember to read it as you compose the push command. A hook runs on the
command itself at the PreToolUse boundary, catching the violation at the
moment of the push before network transit.

## Why this warns rather than blocks

Per this repo's fail-open hook convention, this guard WARNS (attaching
`additionalContext` and a `systemMessage`, with no `permissionDecision`).
A warning surfaces the violation and names the files and lines alongside the
exact `scripts/semantic-line-breaks.py --write` remediation command so the fix
is one call away.

## The match condition

  M1  the tool is `Bash` (or harness equivalent) and `tool_input.command`
      contains at least one genuine `git push` simple command
  M2  the target directory is inside a git repository
  M3  the repository vendors or contains the new-line-breaks checker script
      (`scripts/vendor/gha-check-new-line-breaks.py` or
      `scripts/check-new-line-breaks.py`)
  M4  a base ref (e.g. `origin/main`) resolves and differs from HEAD
  M5  running the checker against the diff produces one or more violations

Fails OPEN on any parse trouble, non-git directory, missing checker,
unresolvable base ref, or checker execution error.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys


def _load_sibling():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "no-push-without-self-review.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("no_push_without_self_review", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


_SIBLING = _load_sibling()

CHECKER_CANDIDATES = (
    os.path.join("scripts", "vendor", "gha-check-new-line-breaks.py"),
    os.path.join("scripts", "check-new-line-breaks.py"),
)

ERROR_LINE = re.compile(
    r"^::error file=(?P<path>[^,]+),line=(?P<line>\d+)::(?P<msg>[^:]+):\s*(?P<preview>.*)$"
)


def _git(args: list[str], cwd: str | None = None, timeout: int = 5) -> str | None:
    """Run git with args; return stripped stdout on success, else None."""
    try:
        res = subprocess.run(
            ["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip()


def _git_root(directory: str | None) -> str | None:
    """Resolve top-level git directory for a path, or None."""
    root = _git(["rev-parse", "--show-toplevel"], cwd=directory)
    return root if root else None


def _resolve_base_ref(git_root: str) -> str | None:
    """Find the default base ref to diff against (e.g. origin/main)."""
    env_base = os.environ.get("NLB_BASE_REF", "").strip()
    if env_base:
        return env_base
    for candidate in ("origin/main", "origin/master", "refs/remotes/origin/HEAD", "main", "master"):
        if _git(["rev-parse", "--verify", "--quiet", candidate + "^{commit}"], cwd=git_root):
            return candidate
    return None


def _find_checker(git_root: str) -> str | None:
    """Locate the new-line-breaks checker script within git_root."""
    for rel in CHECKER_CANDIDATES:
        full = os.path.join(git_root, rel)
        if os.path.isfile(full):
            return full
    return None


def check_repo_nlb(
    git_root: str, base_ref: str, checker_path: str, timeout: int = 10
) -> list[dict[str, str | int]]:
    """Run the checker against base_ref and return parsed violations."""
    env = {**os.environ, "NLB_BASE_REF": base_ref, "NLB_FAIL": "false"}
    try:
        proc = subprocess.run(
            [sys.executable, checker_path],
            capture_output=True,
            text=True,
            cwd=git_root,
            env=env,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    violations = []
    for line in proc.stdout.splitlines():
        m = ERROR_LINE.match(line.strip())
        if m:
            violations.append({
                "path": m.group("path"),
                "line": int(m.group("line")),
                "msg": m.group("msg"),
                "preview": m.group("preview"),
            })
    return violations


def format_warning(
    violations: list[dict[str, str | int]], base_ref: str, git_root: str
) -> tuple[str, str]:
    """Format additionalContext note and systemMessage summary."""
    shown = violations[:20]
    lines = []
    for v in shown:
        lines.append(f"  * {v['path']}:{v['line']}: {v['msg']} -- \"{v['preview']}\"")
    if len(violations) > len(shown):
        lines.append(f"  * ... and {len(violations) - len(shown)} more")
    violations_table = "\n".join(lines)

    unique_files = sorted({str(v["path"]) for v in violations})
    sembr_script = os.path.join(git_root, "scripts", "semantic-line-breaks.py")
    if os.path.isfile(sembr_script):
        files_arg = " ".join(unique_files)
        fix_cmd = f"python3 scripts/semantic-line-breaks.py {files_arg} --write"
        remediation_advice = (
            f"To fix before pushing, run:\n\n"
            f"    {fix_cmd}\n\n"
            f"and commit the formatted files."
        )
        summary = (
            f"`git push` carries {len(violations)} semantic line break violation(s) "
            f"in {len(unique_files)} file(s) against `{base_ref}`; run `{fix_cmd}` before pushing."
        )
    else:
        remediation_advice = (
            "To fix before pushing, break long lines into one sentence/clause "
            "per line and commit the formatted files."
        )
        summary = (
            f"`git push` carries {len(violations)} semantic line break violation(s) "
            f"in {len(unique_files)} file(s) against `{base_ref}`; reformat violating lines before pushing."
        )

    note = (
        f"This `git push` carries Markdown additions with semantic line break "
        f"(new-line-breaks) violations against `{base_ref}`:\n\n"
        f"{violations_table}\n\n"
        f"CI will fail on the `new-line-breaks` check for these lines.\n\n"
        f"{remediation_advice}"
    )
    return note, summary


def evaluate(command: str) -> tuple[str, str] | None:
    """Evaluate whether command pushes commits with NLB violations."""
    if _SIBLING is None:
        return None
    try:
        pushes = list(_SIBLING.iter_pushes(command))
    except Exception:
        return None
    if not pushes:
        return None

    redirected = getattr(_SIBLING, "REDIRECTED", object())
    for _env, _rest, directory in pushes:
        if directory is redirected:
            continue
        target_dir = directory if directory is not None else os.getcwd()
        git_root = _git_root(target_dir)
        if not git_root:
            continue
        checker = _find_checker(git_root)
        if not checker:
            continue
        base_ref = _resolve_base_ref(git_root)
        if not base_ref:
            continue

        head_sha = _git(["rev-parse", "--verify", "--quiet", "HEAD^{commit}"], cwd=git_root)
        base_sha = _git(["rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"], cwd=git_root)
        if head_sha and base_sha and head_sha == base_sha:
            continue

        violations = check_repo_nlb(git_root, base_ref, checker)
        if violations:
            return format_warning(violations, base_ref, git_root)

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"warn-new-line-breaks-on-push: unreadable hook input ({exc})", file=sys.stderr)
        return 0

    if not isinstance(payload, dict) or payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell"
    ):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or tool_input.get("cmd")
        or tool_input.get("script")
    )
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        verdict = evaluate(command)
    except Exception as exc:
        print(f"warn-new-line-breaks-on-push: evaluation failed ({exc})", file=sys.stderr)
        return 0

    if verdict is None:
        return 0

    note, summary = verdict
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = summary
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
