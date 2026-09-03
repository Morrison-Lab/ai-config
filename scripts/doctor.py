#!/usr/bin/env python3
"""Unified preflight and health check diagnostic for ai-config.

Inspects repository health, git worktree status, generated wrapper
freshness, hook catalogs, context budgets, and submodule integrity in a
single fast pass.

Consumer symlink *freshness* is no longer part of this check: `bootstrap.sh`
no longer symlinks skills/commands into a consumer's home directory (Claude
Code and Cursor now install this repo as a native plugin instead, and Codex
has no replacement install path yet -- see ai-config#2352), so there is
nothing left for a `check-install.py`-style comparison to audit.

Consumer *leftovers* are a separate question, and this check still sweeps for
them: a replacement install does not remove what earlier installs placed. A
`~/.claude/skills` symlink predating the plugin survived one such change and
listed every skill twice (ai-config#2405). `check_consumer_leftovers` reports
what it finds and never deletes -- `~/.claude/skills` also holds a user's own
skills and the client's account-level `synced/` bucket, so removal is a human
decision.

Usage:
    python3 scripts/doctor.py
    python3 scripts/doctor.py --json
    python3 scripts/doctor.py --strict
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str], cwd: Optional[Path] = None, timeout: int = 15) -> tuple[int, str, str]:
    """Execute a subprocess command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def check_git_status() -> Dict[str, Any]:
    """Check Git status, current branch, worktree, and clean state."""
    code, out, _ = run_cmd(["git", "rev-parse", "--is-inside-work-tree"])
    if code != 0 or out != "true":
        return {
            "name": "git_status",
            "ok": False,
            "status": "FAIL",
            "details": "Not inside a valid Git repository worktree.",
        }

    _, branch, _ = run_cmd(["git", "branch", "--show-current"])
    _, status_out, _ = run_cmd(["git", "status", "--porcelain"])
    _, worktrees_out, _ = run_cmd(["git", "worktree", "list", "--porcelain"])

    is_dirty = bool(status_out)
    num_worktrees = sum(1 for line in worktrees_out.splitlines() if line.startswith("worktree "))

    return {
        "name": "git_status",
        "ok": True,
        "status": "OK",
        "branch": branch or "detached HEAD",
        "clean": not is_dirty,
        "worktrees_count": num_worktrees,
        "details": f"Branch '{branch or 'detached'}' ({'clean' if not is_dirty else 'dirty'}), {num_worktrees} active worktree(s)",
    }


def check_submodules() -> Dict[str, Any]:
    """Check if git submodules (e.g. shared/sembr-skills) are initialized."""
    code, out, err = run_cmd(["git", "submodule", "status"])
    if code != 0:
        return {
            "name": "submodules",
            "ok": False,
            "status": "FAIL",
            "details": f"git submodule status failed: {err or out}",
        }

    uninitialized = []
    for line in out.splitlines():
        if line.startswith("-"):
            uninitialized.append(line.split()[1] if len(line.split()) > 1 else line)

    if uninitialized:
        return {
            "name": "submodules",
            "ok": False,
            "status": "WARN",
            "uninitialized": uninitialized,
            "details": f"{len(uninitialized)} uninitialized submodule(s): {', '.join(uninitialized)}. Run 'git submodule update --init'",
        }

    return {
        "name": "submodules",
        "ok": True,
        "status": "OK",
        "details": "All Git submodules initialized.",
    }


def check_codex_wrappers() -> Dict[str, Any]:
    """Check if generated Codex skill wrappers are in sync with skills/."""
    code, out, err = run_cmd([sys.executable, str(REPO_ROOT / "scripts" / "sync-codex-skill-wrappers.py"), "--check"])
    if code == 0:
        return {
            "name": "codex_wrappers",
            "ok": True,
            "status": "OK",
            "details": "Codex skill wrappers and tool-mappings.md are in sync with skills/.",
        }
    return {
        "name": "codex_wrappers",
        "ok": False,
        "status": "FAIL",
        "details": f"Codex wrappers out of sync: {err or out}. Run 'python3 scripts/sync-codex-skill-wrappers.py'",
    }


def check_hook_catalog() -> Dict[str, Any]:
    """Check if hooks/hooks.json and README.md catalog agree."""
    code, out, err = run_cmd([sys.executable, str(REPO_ROOT / "scripts" / "check-hook-catalog.py")])
    if code == 0:
        return {
            "name": "hook_catalog",
            "ok": True,
            "status": "OK",
            "details": "hooks/hooks.json bindings match README.md Enforcement hooks table.",
        }
    return {
        "name": "hook_catalog",
        "ok": False,
        "status": "FAIL",
        "details": f"Hook catalog mismatch: {err or out}",
    }


def check_context_closure() -> Dict[str, Any]:
    """Check if CLAUDE.md context closure budget passes."""
    code, out, err = run_cmd([sys.executable, str(REPO_ROOT / "scripts" / "check-context-closure.py")])
    if code == 0:
        return {
            "name": "context_budget",
            "ok": True,
            "status": "OK",
            "details": "Context closure character and fragment budgets are satisfied.",
        }
    return {
        "name": "context_budget",
        "ok": False,
        "status": "FAIL",
        "details": f"Context budget exceeded: {err or out}",
    }


def strip_jsonc_comments(text: str) -> str:
    """Strip comments and trailing commas from JSONC text while preserving string literals."""
    out = []
    i = 0
    n = len(text)
    in_string = False
    escape = False

    while i < n:
        char = text[i]

        if in_string:
            out.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            out.append(char)
            i += 1
            continue

        if char == "/" and i + 1 < n:
            next_char = text[i + 1]
            if next_char == "/":
                i += 2
                while i < n and text[i] != "\n":
                    i += 1
                continue
            elif next_char == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue

        out.append(char)
        i += 1

    no_comments = "".join(out)

    # Second pass: strip trailing commas before } or ] outside string literals
    out2 = []
    i = 0
    n2 = len(no_comments)
    in_string = False
    escape = False

    while i < n2:
        char = no_comments[i]

        if in_string:
            out2.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            out2.append(char)
            i += 1
            continue

        if char == ",":
            j = i + 1
            while j < n2 and no_comments[j] in " \t\r\n":
                j += 1
            if j < n2 and no_comments[j] in ("}", "]"):
                i += 1
                continue

        out2.append(char)
        i += 1

    return "".join(out2)


def check_jsonc_configs() -> Dict[str, Any]:
    """Validate JSON and JSONC configuration files across repository and environment."""
    candidate_paths: List[Path] = [
        REPO_ROOT / "opencode.json",
        REPO_ROOT / "hooks" / "hooks.json",
        REPO_ROOT / "plugins" / "ai-config" / "plugin.json",
        REPO_ROOT / "plugins" / "ai-config" / "hooks.json",
        REPO_ROOT / "shared" / "vendored" / "MANIFEST.json",
        REPO_ROOT / "skills" / "register-oaicopilot-models" / "models-template.jsonc",
    ]

    user_configs = [
        Path(os.path.expanduser("~/.config/opencode/opencode.jsonc")),
        Path(os.path.expanduser("~/.gemini/config/plugins.json")),
    ]
    for uc in user_configs:
        if uc.is_file():
            candidate_paths.append(uc)

    checked = 0
    failed: List[str] = []

    for path in candidate_paths:
        if not path.is_file():
            continue
        checked += 1
        try:
            raw = path.read_text(encoding="utf-8")
            clean = strip_jsonc_comments(raw)
            json.loads(clean)
        except Exception as exc:
            failed.append(f"{path} ({exc})")

    if failed:
        return {
            "name": "jsonc_configs",
            "ok": False,
            "status": "FAIL",
            "failed_files": failed,
            "details": f"Invalid JSON/JSONC in {len(failed)} file(s): {'; '.join(failed)}",
        }

    return {
        "name": "jsonc_configs",
        "ok": True,
        "status": "OK",
        "checked_count": checked,
        "details": f"Validated {checked} JSON/JSONC configuration file(s).",
    }


def check_ai_clis() -> Dict[str, Any]:
    """Check availability of AI CLI subagents and developer tools."""
    from lib import ai_cli

    report = ai_cli.get_tool_status_report()
    available_engines = report.get("available_engines", [])
    gh_available = report.get("forge_tools", {}).get("gh", {}).get("available", False)

    if not available_engines:
        return {
            "name": "ai_clis",
            "ok": False,
            "status": "WARN",
            "available_engines": [],
            "gh_available": gh_available,
            "details": "No local AI CLI subagents detected (claude, cursor, codex, opencode, antigravity).",
        }

    return {
        "name": "ai_clis",
        "ok": True,
        "status": "OK",
        "available_engines": available_engines,
        "gh_available": gh_available,
        "details": f"Available AI engines: {', '.join(available_engines)}; GitHub CLI (gh): {'available' if gh_available else 'not found'}",
    }


# `bootstrap.sh` placed these three under `~/.claude` before the plugin
# install replaced it, and no plugin equivalent has landed (ai-config#2352),
# so a copy or symlink found there today was placed by an earlier install.
LEFTOVER_NAMES = ("shared", "hooks", "memories")

# The client populates this bucket under `~/.claude/skills` with an
# account-level sync whose directory names match this repo's skills without
# any of them being a leftover, so a name test has to skip it.
CLIENT_SKILL_SYNC_DIR = "synced"


def claude_home() -> Path:
    """Return the consumer Claude Code home, honoring CLAUDE_HOME."""
    return Path(os.environ.get("CLAUDE_HOME") or (Path.home() / ".claude"))


def read_settings(path: Path) -> tuple[Dict[str, Any], Optional[str]]:
    """Return (settings, parse_error) for a Claude Code settings file.

    A missing file is not an error -- it simply enables no plugin. A file
    that exists and does not parse is reported rather than swallowed: it
    leaves the sweep unable to say whether the plugin route is in use.
    """
    if not path.is_file():
        return {}, None
    try:
        data = json.loads(strip_jsonc_comments(path.read_text(encoding="utf-8")))
    except Exception as exc:
        return {}, str(exc)
    return (data if isinstance(data, dict) else {}), None


def describe_path(path: Path) -> str:
    """Describe a leftover path as a symlink (with its target) or a copy."""
    if path.is_symlink():
        try:
            return f"symlink -> {os.readlink(path)}"
        except OSError:
            return "symlink"
    return "copy"


def points_into_ai_config(path: Path) -> bool:
    """Report whether `path` resolves inside something shaped like this repo.

    Provenance, not a name or content test: the account-level skill sync
    carries this repo's skill names and differing contents alike, so only a
    link that lands in a checkout identifies a leftover install.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for candidate in (resolved, *resolved.parents):
        if (candidate / "CLAUDE.md").is_file() and (candidate / "hooks" / "hooks.json").is_file():
            return True
    return False


def find_skill_leftovers(home: Path) -> tuple[List[str], List[str]]:
    """Return (linked, doubled) skill leftovers under `home`/skills.

    `linked` entries resolve into an ai-config checkout, so their provenance
    is settled. `doubled` entries only share a name with this repo's skills,
    which is the doubled-listing symptom rather than proof of a leftover --
    a user's own skill may legitimately carry the same name.
    """
    skills = home / "skills"
    if skills.is_symlink() and points_into_ai_config(skills):
        return ([f"{skills} ({describe_path(skills)})"], [])
    if not skills.is_dir():
        return ([], [])

    repo_skills = {p.name for p in (REPO_ROOT / "skills").iterdir() if p.is_dir()}
    linked: List[str] = []
    doubled: List[str] = []
    for entry in sorted(skills.iterdir()):
        if entry.name == CLIENT_SKILL_SYNC_DIR:
            continue
        if entry.is_symlink():
            if points_into_ai_config(entry):
                linked.append(f"{entry} ({describe_path(entry)})")
        elif entry.is_dir() and entry.name in repo_skills:
            doubled.append(entry.name)
    return (linked, doubled)


def check_consumer_leftovers() -> Dict[str, Any]:
    """Report `~/.claude` copies and symlinks left by pre-plugin installs."""
    from lib.plugin_overlap import enabled_ai_config_plugins

    home = claude_home()
    settings_path = home / "settings.json"
    settings, parse_error = read_settings(settings_path)
    if parse_error is not None:
        return {
            "name": "consumer_leftovers",
            "ok": False,
            "status": "WARN",
            "plugin_enabled": None,
            "leftovers": [],
            "doubled_skills": [],
            "details": f"Not swept: {settings_path} did not parse ({parse_error}), so whether the plugin route is in use is unknown.",
        }

    enabled = enabled_ai_config_plugins(settings)
    if not enabled:
        return {
            "name": "consumer_leftovers",
            "ok": True,
            "status": "OK",
            "plugin_enabled": False,
            "leftovers": [],
            "doubled_skills": [],
            "details": f"Skipped: {settings_path} enables no ai-config plugin, so a ~/.claude copy may be this machine's only install.",
        }

    leftovers = [
        f"{home / name} ({describe_path(home / name)})"
        for name in LEFTOVER_NAMES
        if (home / name).is_symlink() or (home / name).exists()
    ]
    linked_skills, doubled_skills = find_skill_leftovers(home)
    leftovers.extend(linked_skills)

    if not leftovers and not doubled_skills:
        return {
            "name": "consumer_leftovers",
            "ok": True,
            "status": "OK",
            "plugin_enabled": True,
            "leftovers": [],
            "doubled_skills": [],
            "details": f"No pre-plugin install leftovers under {home}.",
        }

    parts = []
    if leftovers:
        parts.append(f"{len(leftovers)} leftover(s): {'; '.join(leftovers)}")
    if doubled_skills:
        parts.append(
            f"{len(doubled_skills)} skill name(s) shared with this repo, so the listing may be doubled: {', '.join(doubled_skills)}"
        )
    return {
        "name": "consumer_leftovers",
        "ok": False,
        "status": "WARN",
        "plugin_enabled": True,
        "leftovers": leftovers,
        "doubled_skills": doubled_skills,
        "details": f"Under {home}: {'. '.join(parts)}. Reported only -- inspect each by hand before removing anything, since ~/.claude/skills also holds your own skills (see shared/workflow/keep-checkouts-fresh.md).",
    }


def run_doctor() -> Dict[str, Any]:
    """Execute all diagnostic health checks."""
    checks = [
        check_git_status(),
        check_submodules(),
        check_codex_wrappers(),
        check_hook_catalog(),
        check_context_closure(),
        check_jsonc_configs(),
        check_ai_clis(),
        check_consumer_leftovers(),
    ]

    all_ok = all(c["ok"] for c in checks)
    has_fail = any(c.get("status") == "FAIL" for c in checks)
    has_warn = any(c.get("status") == "WARN" for c in checks)

    overall_status = "HEALTHY" if all_ok else ("DEGRADED" if not has_fail else "CRITICAL")

    return {
        "overall_status": overall_status,
        "all_ok": all_ok,
        "has_failures": has_fail,
        "has_warnings": has_warn,
        "checks": checks,
    }


def format_text_report(report: Dict[str, Any]) -> str:
    """Format diagnostic report for human terminal reading."""
    lines = []
    lines.append("=" * 60)
    lines.append("ai-config Doctor Diagnostic Report")
    lines.append("=" * 60)

    for c in report["checks"]:
        badge = f"[{c['status']}]"
        lines.append(f"{badge:8} {c['name']:20} : {c['details']}")

    lines.append("-" * 60)
    lines.append(f"Overall System Health: {report['overall_status']}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any check failure or warning")
    args = parser.parse_args()

    report = run_doctor()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_text_report(report))

    if args.strict and not report["all_ok"]:
        return 1
    if report["has_failures"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
