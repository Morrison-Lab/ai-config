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
  4. Runs `git diff <tag>..origin/<default> -- .github/workflows/` and for each changed
     reusable workflow (`workflow_call:` in its `on:` block), structurally parses
     permissions between <tag> and origin/<default>. Scans for added or escalated
     permissions matching `(read|write|none)` at either workflow root or job level.
  5. Denies when found, naming the file, permission line, and the remedy: land caller
     grants in every consumer first (suggesting `gh search code "uses: <owner>/<repo>/.github/workflows/<file>@"`),
     then slide.

`ALLOW_BREAKING_SLIDE=1` as an env assignment on the command records a deliberate override.

Fails CLOSED (denies) when a changed workflow containing workflow_call cannot be
parsed as valid YAML or when PyYAML is unavailable, preventing undetected breaking
releases.

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

try:
    import yaml
except ImportError:
    yaml = None

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)
_SHELL_OPS = set("();|&")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {
    "then", "do", "else", "elif", "!", "time", "sudo", "command",
    "exec", "nohup", "env", "{", "}",
}

RX_PERM_VAL = re.compile(r"^(read|write|none)$")

PERM_RANK: dict[str | None, int] = {
    None: 0,
    "none": 1,
    "read": 2,
    "write": 3,
}


def _extract_permissions_from_data(data: dict) -> dict[str, dict[str, str] | str]:
    """Extract workflow-level and job-level permissions from parsed YAML data."""
    perms: dict[str, dict[str, str] | str] = {}

    root_p = data.get("permissions")
    if isinstance(root_p, dict):
        perms["workflow"] = {
            str(k): str(v)
            for k, v in root_p.items()
            if isinstance(k, (str, int)) and RX_PERM_VAL.match(str(v).strip())
        }
    elif isinstance(root_p, str) and root_p.strip() in ("read-all", "write-all"):
        perms["workflow"] = root_p.strip()
    elif isinstance(root_p, dict) and not root_p:
        perms["workflow"] = {}

    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        for job_id, job_data in jobs.items():
            if isinstance(job_data, dict):
                jp = job_data.get("permissions")
                job_key = f"job:{job_id}"
                if isinstance(jp, dict):
                    perms[job_key] = {
                        str(k): str(v)
                        for k, v in jp.items()
                        if isinstance(k, (str, int)) and RX_PERM_VAL.match(str(v).strip())
                    }
                elif isinstance(jp, str) and jp.strip() in ("read-all", "write-all"):
                    perms[job_key] = jp.strip()
                elif isinstance(jp, dict) and not jp:
                    perms[job_key] = {}
    return perms


def _extract_permissions(content: str) -> dict[str, dict[str, str] | str]:
    """Extract workflow and job permissions via PyYAML; raises RuntimeError if PyYAML is unavailable."""
    if yaml is None:
        raise RuntimeError("PyYAML is not installed")
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        return {}
    return _extract_permissions_from_data(data)


def _find_added_permissions(
    old_perms: dict[str, dict[str, str] | str],
    new_perms: dict[str, dict[str, str] | str],
) -> list[tuple[str, str]]:
    """Return list of (scope, perm_str) for any permissions added or escalated."""
    added: list[tuple[str, str]] = []
    for scope, perms in new_perms.items():
        old_scope = old_perms.get(scope)
        if isinstance(perms, str):
            if old_scope != perms:
                added.append((scope, perms))
        elif isinstance(perms, dict):
            old_dict = old_scope if isinstance(old_scope, dict) else {}
            for key, val in perms.items():
                old_val = old_dict.get(key)
                clean_old = old_val.strip() if isinstance(old_val, str) else old_val
                clean_new = val.strip() if isinstance(val, str) else val
                if PERM_RANK[clean_new] > PERM_RANK[clean_old]:
                    added.append((scope, f"{key}: {val}"))
    return added


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


def _has_workflow_call(data: dict) -> bool:
    """True if parsed workflow YAML has workflow_call in its on: trigger block."""
    on_trigger = data.get("on") if "on" in data else data.get(True)
    if on_trigger is None:
        return False
    if isinstance(on_trigger, str):
        return on_trigger.strip() == "workflow_call"
    if isinstance(on_trigger, list):
        return any(isinstance(item, str) and item.strip() == "workflow_call" for item in on_trigger)
    if isinstance(on_trigger, dict):
        return "workflow_call" in on_trigger
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

        new_content = _git(["show", f"{remote_ref}:{filepath}"], cwd=cwd)
        if not new_content:
            continue

        if yaml is None:
            reason = (
                "Blocked: slide-major-tag cannot verify reusable workflow permissions because "
                f"PyYAML is not installed in the Python environment running this guard ({filepath}).\n\n"
                "In GitHub Actions, a called reusable workflow job cannot request permissions "
                "that its caller does not grant. Adding a permission breaks every consumer "
                "caller with startup_failure until the caller grants the new permission "
                "(gha#830 / ucdavis/bcs#966; same class as gha#685).\n\n"
                "Remedy:\n"
                "1. Install PyYAML in the Python environment running this hook:\n"
                "     pip install pyyaml\n"
                "2. If this release is deliberate and consumers have already been prepared, "
                "ALLOW_BREAKING_SLIDE=1 as an env assignment on the command records a deliberate override:\n\n"
                f"    ALLOW_BREAKING_SLIDE=1 {command.strip()}"
            )
            return "deny", reason

        try:
            new_data = yaml.safe_load(new_content)
        except Exception as exc:
            # The raw scan is a last resort for files that cannot be parsed at all:
            # if the raw token is absent, assume it is not a reusable workflow and skip.
            # If the token is present, fail closed because permissions cannot be verified.
            if "workflow_call" not in new_content:
                continue
            reason = (
                "Blocked: slide-major-tag cannot verify reusable workflow permissions because "
                f"{filepath} could not be parsed as valid YAML ({exc}).\n\n"
                "In GitHub Actions, a called reusable workflow job cannot request permissions "
                "that its caller does not grant. Adding a permission breaks every consumer "
                "caller with startup_failure until the caller grants the new permission "
                "(gha#830 / ucdavis/bcs#966; same class as gha#685).\n\n"
                "Remedy:\n"
                "1. Fix the YAML syntax in the workflow file.\n"
                "2. If this release is deliberate and consumers have already been prepared, "
                "ALLOW_BREAKING_SLIDE=1 as an env assignment on the command records a deliberate override:\n\n"
                f"    ALLOW_BREAKING_SLIDE=1 {command.strip()}"
            )
            return "deny", reason

        if new_data is None:
            continue

        if not isinstance(new_data, dict):
            # A file that parses into a non-mapping cannot be a valid workflow.
            # The raw scan is a last resort for files that cannot be parsed into a mapping.
            if "workflow_call" not in new_content:
                continue
            reason = (
                "Blocked: slide-major-tag cannot verify reusable workflow permissions because "
                f"{filepath} does not contain a top-level YAML mapping.\n\n"
                "In GitHub Actions, a workflow file must be a mapping (dictionary) at the top level.\n\n"
                "Remedy:\n"
                "1. Fix the structure of the workflow file.\n"
                "2. If this release is deliberate and consumers have already been prepared, "
                "ALLOW_BREAKING_SLIDE=1 as an env assignment on the command records a deliberate override:\n\n"
                f"    ALLOW_BREAKING_SLIDE=1 {command.strip()}"
            )
            return "deny", reason

        # For parseable files, the parsed mapping is the sole relevance test:
        # no raw text scan involved, so YAML key encodings cannot defeat detection.
        if not _has_workflow_call(new_data):
            continue

        new_perms = _extract_permissions_from_data(new_data)

        old_content = _git(["show", f"{tag}:{filepath}"], cwd=cwd)
        old_perms: dict[str, dict[str, str] | str] = {}
        if old_content:
            try:
                old_data = yaml.safe_load(old_content)
            except Exception as exc:
                reason = (
                    "Blocked: slide-major-tag cannot verify reusable workflow permissions because "
                    f"{filepath} at {tag} could not be parsed as valid YAML ({exc}).\n\n"
                    "In GitHub Actions, a called reusable workflow job cannot request permissions "
                    "that its caller does not grant. Adding a permission breaks every consumer "
                    "caller with startup_failure until the caller grants the new permission "
                    "(gha#830 / ucdavis/bcs#966; same class as gha#685).\n\n"
                    "Remedy:\n"
                    "1. Fix the YAML syntax in the tag ref or pass ALLOW_BREAKING_SLIDE=1.\n"
                    "2. If this release is deliberate and consumers have already been prepared, "
                    "ALLOW_BREAKING_SLIDE=1 as an env assignment on the command records a deliberate override:\n\n"
                    f"    ALLOW_BREAKING_SLIDE=1 {command.strip()}"
                )
                return "deny", reason
            if isinstance(old_data, dict):
                old_perms = _extract_permissions_from_data(old_data)

        added_perms = _find_added_permissions(old_perms, new_perms)
        if added_perms:
            scope, perm_line = added_perms[0]
            repo_nwo = _repo_nwo(cwd)
            filename = os.path.basename(filepath)
            scope_label = "workflow-level" if scope == "workflow" else "job-level"
            reason = (
                f"Blocked: slide-major-tag would release a breaking {scope_label} permission addition "
                f"in a reusable workflow ({filepath}).\n\n"
                f"  file:            {filepath}\n"
                f"  permission line: {perm_line}\n\n"
                "In GitHub Actions, a called reusable workflow job cannot request permissions "
                "that its caller does not grant. Adding a permission breaks every consumer "
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
