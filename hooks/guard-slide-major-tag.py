#!/usr/bin/env python3
"""PreToolUse guard: deny a slide-major-tag dispatch that adds a reusable-workflow job permission.

## Incident (gha#830 / ucdavis/bcs#966)

On 2026-09-05, Morrison-Lab/gha#830 added `checks: read` to the reusable
`claude-code-review.yml`'s `claude-review` job. Merging it and dispatching
`slide-major-tag` moved `v2` to it immediately. In GitHub Actions, a called
job may not request more than its caller grants; no consumer caller had granted
`checks: read` yet, so every consumer's review dispatch began failing with
`startup_failure` (ucdavis/bcs#966; same failure class as gha#685 in 2026-08).
Sliding a major-version tag is a release to all consumers, not a post-merge chore.

## Rule and Mechanism

A PreToolUse guard on Bash that fires when a command dispatches a major-tag slide:
  - `gh workflow run slide-major-tag.yml` (any argument order, optional -R/--repo)
  - Or a command invoking the slide-tag / ts skill script if present.

When matched, it:
  1. Resolves the repository directory from the payload cwd / CLAUDE_PROJECT_DIR.
  2. Finds the floating tag: `git tag --list 'v[0-9]*' | grep -E '^v[0-9]+$' | sort -V | tail -1`
     (defaulting to v2 if none).
  3. Resolves the default branch from `git symbolic-ref refs/remotes/origin/HEAD`
     falling back to main.
  4. Runs `git diff <tag>..origin/<default> -- .github/workflows/` and scans added lines
     for a job-level permission entry inside a workflow that has `workflow_call:` in its `on:`
     block: an added line matching `^\\+\\s{4,}[a-z-]+:\\s*(read|write|none)\\s*(#.*)?$`
     that follows (within the same hunk or file) a `permissions:` line.
  5. Denies when found, naming the file, permission line, and the remedy: land caller
     grants in every consumer first (suggesting `gh search code "uses: <owner>/<repo>/.github/workflows/<file>@"`),
     then slide.

`ALLOW_BREAKING_SLIDE=1` as an env assignment on the command records a deliberate override.

Fails OPEN (with a stderr note) when git is unavailable, the tag or remote branch does not
resolve, or the command is not a slide. Never reads the transcript.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)
_SHELL_OPS = set("();|&")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {
    "then", "do", "else", "elif", "!", "time", "sudo", "command",
    "exec", "nohup", "env", "{", "}",
}

RX_PERM_ENTRY = re.compile(r"^\+\s{4,}[a-z-]+:\s*(read|write|none)\s*(#.*)?$")
RX_PERM_HEADER = re.compile(r"^\+?\s*permissions:\s*(#.*)?$")


def _git(args: list[str], cwd: str | None = None, timeout: int = 8) -> str | None:
    """Run a git command; return stdout on success, else None."""
    try:
        res = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout


def _simple_commands(cmd: str) -> list[list[str]] | None:
    """Split a shell command into simple command argv lists; None on parse error."""
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = cmd.replace("\n", ";")
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _is_slide_dispatch(argv: list[str]) -> tuple[bool, bool]:
    """Return (is_slide, has_override) for a simple command argv.

    Recognizes:
      `gh workflow run slide-major-tag.yml` (any argument order, optional -R/--repo)
      or invocations of slide-tag / ts skill scripts.
    """
    has_override = os.environ.get("ALLOW_BREAKING_SLIDE") == "1"
    i = 0
    while i < len(argv) and (ASSIGNMENT.match(argv[i]) or argv[i] in LEAD_WORDS):
        if argv[i].startswith("ALLOW_BREAKING_SLIDE="):
            val = argv[i].split("=", 1)[1].strip().strip("'\"")
            if val == "1":
                has_override = True
        i += 1

    if i >= len(argv):
        return False, has_override

    cmd_name = os.path.basename(argv[i])
    args = argv[i + 1:]

    # Check for skill script invocation (e.g. slide-tag.sh, slide-tag.py)
    if cmd_name in ("slide-tag.sh", "slide-tag.py", "slide-tag") or any(
        a.endswith(("slide-tag.sh", "slide-tag.py")) or "skills/slide-tag" in a for a in argv[i:]
    ):
        return True, has_override

    # Check for `gh workflow run slide-major-tag.yml` in any argument order
    if cmd_name == "gh":
        if "workflow" in args and "run" in args:
            if args.index("workflow") < args.index("run"):
                for arg in args:
                    base = os.path.basename(arg)
                    if base in ("slide-major-tag.yml", "slide-major-tag.yaml", "slide-major-tag"):
                        return True, has_override

    return False, has_override


def _floating_tag(cwd: str) -> str:
    """Find floating major tag (e.g. v2, v3), defaulting to v2 if none."""
    out = _git(["tag", "--list", "v[0-9]*"], cwd=cwd)
    if out:
        tags = []
        for line in out.splitlines():
            t = line.strip()
            if re.match(r"^v[0-9]+$", t):
                tags.append(t)
        if tags:
            tags.sort(key=lambda x: int(x[1:]))
            return tags[-1]
    return "v2"


def _default_branch(cwd: str) -> str:
    """Resolve default branch from origin/HEAD symbolic ref, falling back to main."""
    out = _git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], cwd=cwd)
    if out:
        ref = out.strip()
        prefix = "refs/remotes/origin/"
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return "main"


def _repo_nwo(cwd: str) -> str:
    """Resolve <owner>/<repo> from git remote origin URL, or fallback."""
    url = _git(["config", "--get", "remote.origin.url"], cwd=cwd)
    if url:
        url = url.strip()
        m = re.search(r"github\.com[:/]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$", url)
        if m:
            return m.group(1)
    return "<owner>/<repo>"


def _has_workflow_call(content: str) -> bool:
    """True if workflow YAML has workflow_call in its on: trigger block."""
    lines = content.splitlines()
    in_on_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m_inline = re.match(r"^on:\s*\[(.*)\]", stripped)
        if m_inline:
            events = [e.strip() for e in m_inline.group(1).split(",")]
            if "workflow_call" in events:
                return True
            continue
        if re.match(r"^on:\s*workflow_call\b", stripped):
            return True
        if re.match(r"^on:\s*$", stripped):
            in_on_block = True
            continue
        if in_on_block:
            if re.match(r"^[a-zA-Z0-9_-]+:", line) and not line.startswith(" "):
                in_on_block = False
                continue
            if re.match(r"^\s+workflow_call\b", line):
                return True
    return False


def evaluate(command: str, base_cwd: str | None = None) -> tuple[str, str] | None:
    """Evaluate command; returns ('deny', reason) or None."""
    cmds = _simple_commands(command)
    if cmds is None:
        return None

    is_slide = False
    has_override = False
    for argv in cmds:
        matched, override = _is_slide_dispatch(argv)
        if matched:
            is_slide = True
            if override:
                has_override = True

    if not is_slide:
        return None

    if has_override:
        return None

    cwd = base_cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    inside_git = _git(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
    if not inside_git:
        print("guard-slide-major-tag: not a git repository or git unavailable; failing open", file=sys.stderr)
        return None

    tag = _floating_tag(cwd)
    tag_sha = _git(["rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}"], cwd=cwd)
    if not tag_sha:
        print(f"guard-slide-major-tag: tag {tag} does not resolve; failing open", file=sys.stderr)
        return None

    default_branch = _default_branch(cwd)
    remote_ref = f"origin/{default_branch}"
    remote_sha = _git(["rev-parse", "--verify", "--quiet", f"{remote_ref}^{{commit}}"], cwd=cwd)
    if not remote_sha:
        print(f"guard-slide-major-tag: remote branch {remote_ref} does not resolve; failing open", file=sys.stderr)
        return None

    diff_out = _git(["diff", f"{tag}..{remote_ref}", "--", ".github/workflows/"], cwd=cwd)
    if diff_out is None:
        print("guard-slide-major-tag: git diff failed; failing open", file=sys.stderr)
        return None

    if not diff_out.strip():
        return None

    file_diffs = re.split(r"^diff --git ", diff_out, flags=re.MULTILINE)
    for chunk in file_diffs:
        if not chunk.strip():
            continue
        m_dst = re.search(r"^\+\+\+ b/(.+)$", chunk, flags=re.MULTILINE)
        if not m_dst:
            continue
        filepath = m_dst.group(1).strip()
        if filepath == "/dev/null":
            continue
        if not (filepath.endswith(".yml") or filepath.endswith(".yaml")):
            continue

        file_content = _git(["show", f"{remote_ref}:{filepath}"], cwd=cwd)
        if not file_content:
            continue
        if not _has_workflow_call(file_content):
            continue

        # Check for job-level permission additions
        file_has_perms = bool(re.search(r"^\s*permissions:\s*(#.*)?$", file_content, flags=re.MULTILINE))
        chunk_saw_perms = False

        for line in chunk.splitlines():
            if RX_PERM_HEADER.match(line):
                chunk_saw_perms = True
            if (chunk_saw_perms or file_has_perms) and RX_PERM_ENTRY.match(line):
                perm_line = line.lstrip("+").strip()
                repo_nwo = _repo_nwo(cwd)
                filename = os.path.basename(filepath)
                reason = (
                    "Blocked: slide-major-tag would release a breaking job-level permission addition "
                    f"in a reusable workflow ({filepath}).\n\n"
                    f"  file:            {filepath}\n"
                    f"  permission line: {perm_line}\n\n"
                    "In GitHub Actions, a called reusable workflow job cannot request permissions "
                    "that its caller does not grant. Adding a job permission breaks every consumer "
                    "caller with startup_failure until the caller grants the new permission "
                    "(gha#830 / ucdavis/bcs#966; same class as gha#685).\n\n"
                    "Remedy:\n"
                    "1. Land caller grants in every consumer first:\n"
                    f'     gh search code "uses: {repo_nwo}/.github/workflows/{filename}@"\n'
                    "2. Once consumers have granted the permission, slide the major tag.\n\n"
                    "If this release is deliberate and consumers have already been prepared, "
                    "ALLOW_BREAKING_SLIDE=1 as an env assignment on the command records a deliberate override:\n\n"
                    f"    ALLOW_BREAKING_SLIDE=1 {command.strip()}"
                )
                return "deny", reason

    return None


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"guard-slide-major-tag: unreadable hook input ({exc})", file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input") or {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        verdict = evaluate(command, payload.get("cwd"))
    except Exception as exc:
        print(f"guard-slide-major-tag: could not evaluate command ({exc})", file=sys.stderr)
        return 0

    if verdict is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    kind, text = verdict
    hso = {"hookEventName": "PreToolUse"}
    if kind == "deny":
        hso["permissionDecision"] = "deny"
        hso["permissionDecisionReason"] = text
    else:
        hso["additionalContext"] = text
    print(json.dumps({"hookSpecificOutput": hso}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
