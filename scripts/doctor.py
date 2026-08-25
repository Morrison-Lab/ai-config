#!/usr/bin/env python3
"""Unified preflight and health check diagnostic for ai-config.

Inspects repository health, git worktree status, consumer symlinks, generated
wrapper freshness, hook catalogs, context budgets, and submodule integrity in
a single fast pass.

Usage:
    python3 scripts/doctor.py
    python3 scripts/doctor.py --fix
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


def check_consumer_installs(fix: bool = False) -> Dict[str, Any]:
    """Check installed consumer symlinks in ~/.claude or $CLAUDE_HOME."""
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "check-install.py"), "--strict"]
    if fix:
        cmd.append("--fix")

    code, out, err = run_cmd(cmd)
    if code == 0:
        return {
            "name": "consumer_install",
            "ok": True,
            "status": "OK",
            "details": "Consumer installation is fresh and tracks this repository.",
            "output": out,
        }
    return {
        "name": "consumer_install",
        "ok": False,
        "status": "WARN",
        "details": "Consumer installation contains stale, unlinked, or missing entries. Re-run doctor with --fix to repair.",
        "output": out,
    }


def run_doctor(fix: bool = False) -> Dict[str, Any]:
    """Execute all diagnostic health checks."""
    checks = [
        check_git_status(),
        check_submodules(),
        check_codex_wrappers(),
        check_hook_catalog(),
        check_context_closure(),
        check_consumer_installs(fix=fix),
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
    parser.add_argument("--fix", action="store_true", help="Attempt automatic repair of repairable defects")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any check failure or warning")
    args = parser.parse_args()

    report = run_doctor(fix=args.fix)

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
