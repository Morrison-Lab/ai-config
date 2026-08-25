#!/usr/bin/env python3
"""Run local AI code review using desktop subscription quota (Antigravity / Claude / Codex).

Can run pre-push locally or post review comments/verdicts directly to GitHub PRs via gh CLI.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Optional, Tuple


def get_git_root() -> str:
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        log_error("Not inside a git repository.")
        sys.exit(1)
    return res.stdout.strip()


def get_current_pr() -> Optional[int]:
    """Auto-detect PR number for current branch if one exists."""
    res = subprocess.run(
        ["gh", "pr", "view", "--json", "number"],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            return data.get("number")
        except Exception:
            return None
    return None


def resolve_diff(pr_number: Optional[int], explicit_base: str = "") -> Tuple[str, str]:
    """Get the diff and the base reference string."""
    if pr_number:
        res = subprocess.run(
            ["gh", "pr", "diff", str(pr_number)],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return res.stdout, f"PR #{pr_number}"

    # Fallback to local git diff
    base_ref = explicit_base
    if not base_ref:
        for cand in ["origin/main", "origin/master", "main", "master"]:
            r = subprocess.run(["git", "rev-parse", "--verify", cand], capture_output=True, text=True)
            if r.returncode == 0:
                base_ref = cand
                break
        if not base_ref:
            base_ref = "HEAD~1"

    mb_res = subprocess.run(["git", "merge-base", "HEAD", base_ref], capture_output=True, text=True)
    base_sha = mb_res.stdout.strip() if mb_res.returncode == 0 else base_ref
    diff_res = subprocess.run(["git", "diff", base_sha, "HEAD"], capture_output=True, text=True)
    if diff_res.returncode != 0:
        log_error(f"Could not compute diff against {base_ref}: {diff_res.stderr}")
        sys.exit(1)
    return diff_res.stdout, base_ref


def get_repo_guidelines(root: str) -> str:
    candidate_files = ["AGENTS.md", "CLAUDE.md", "GEMINI.md"]
    guidelines = []
    for fname in candidate_files:
        p = os.path.join(root, fname)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        guidelines.append(f"--- Repository Guidelines ({fname}) ---\n{content[:4000]}")
            except Exception:
                pass
    return "\n\n".join(guidelines)


def log_error(msg: str):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error::{msg}", file=sys.stderr)
    else:
        print(f"Error: {msg}", file=sys.stderr)


def run_antigravity_review(prompt: str, model: str = "") -> str:
    agy_path = shutil.which("agy") or os.path.expanduser("~/.local/bin/agy")
    if not os.path.isfile(agy_path) and not shutil.which("agy"):
        log_error("Antigravity CLI (`agy`) not found. Ensure agy is in PATH.")
        sys.exit(1)

    cmd = [agy_path, "--dangerously-skip-permissions", "-p", prompt]
    if model:
        cmd.extend(["--model", model])

    print("Running local code review via Antigravity (Google AI Ultra quota)...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        log_error(f"Antigravity review failed: {err}")
        sys.exit(1)
    return res.stdout.strip()


def run_claude_review(prompt: str, model: str = "") -> str:
    claude_path = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    if not os.path.isfile(claude_path) and not shutil.which("claude"):
        log_error("Claude CLI (`claude`) not found. Ensure claude is in PATH.")
        sys.exit(1)

    cmd = [claude_path, "--dangerously-skip-permissions", "-p", prompt]
    if model:
        cmd.extend(["--model", model])

    print("Running local adversarial review via Claude CLI...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        log_error(f"Claude review failed: {err}")
        sys.exit(1)
    return res.stdout.strip()


def run_codex_review(prompt: str) -> str:
    codex_path = shutil.which("codex") or os.path.expanduser("~/.local/bin/codex")
    if not os.path.isfile(codex_path) and not shutil.which("codex"):
        log_error("Codex CLI (`codex`) not found.")
        sys.exit(1)

    print("Running local code review via Codex CLI (ChatGPT subscription quota)...")
    cmd = [codex_path, "exec", "-s", "read-only", "--skip-git-repo-check", prompt]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        log_error(f"Codex review failed: {err}")
        sys.exit(1)
    return res.stdout.strip()


def detect_engine() -> Optional[str]:
    """Auto-detect available local AI engine in priority order: agy -> claude -> codex."""
    if shutil.which("agy") or os.path.isfile(os.path.expanduser("~/.local/bin/agy")):
        return "antigravity"
    if shutil.which("claude") or os.path.isfile(os.path.expanduser("~/.local/bin/claude")):
        return "claude"
    if shutil.which("codex") or os.path.isfile(os.path.expanduser("~/.local/bin/codex")):
        return "codex"
    return None


def format_review_body(report: str, engine_name: str) -> str:
    """Format the review report for GitHub PR posting adhering to lab disclosure policy."""
    return (
        f"### Local Adversarial AI Review ({engine_name})\n\n"
        f"{report}\n\n"
        "---\n"
        f"_Posted by {engine_name} (AI agent) --- not written by a human._"
    )


def post_review_to_github(pr_number: int, report: str, engine_name: str):
    """Post the review report directly to GitHub PR via gh CLI."""
    formatted_body = format_review_body(report, engine_name)

    res = subprocess.run(
        ["gh", "pr", "review", str(pr_number), "--comment", "--body", formatted_body],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        print(f"✅ Successfully posted review to PR #{pr_number} via `gh pr review`!")
        return

    res_comment = subprocess.run(
        ["gh", "pr", "comment", str(pr_number), "--body", formatted_body],
        capture_output=True,
        text=True,
    )
    if res_comment.returncode == 0:
        print(f"✅ Successfully posted review comment to PR #{pr_number} via `gh pr comment`!")
    else:
        log_error(f"Failed to post to GitHub PR #{pr_number}: {res_comment.stderr}")


def main():
    parser = argparse.ArgumentParser(
        description="Run local AI code review using desktop subscriptions and optionally post to GitHub PR."
    )
    parser.add_argument(
        "--pr",
        type=int,
        default=None,
        help="Pull Request number to review and post to (auto-detected if omitted)",
    )
    parser.add_argument(
        "--base",
        default="",
        help="Base git reference to diff against (defaults to PR base or origin/main)",
    )
    parser.add_argument(
        "--engine",
        choices=["auto", "antigravity", "agy", "claude", "codex"],
        default="auto",
        help="AI engine: 'auto' (default: agy -> claude -> codex), 'antigravity', 'claude', or 'codex'",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Model override (optional)",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Post the review comment/verdict directly to the GitHub PR",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="",
        help="Path to save the review markdown report locally",
    )
    args = parser.parse_args()

    git_root = get_git_root()
    pr_num = args.pr or get_current_pr()
    diff, ref_name = resolve_diff(pr_num if args.pr else None, explicit_base=args.base)

    if not diff.strip():
        print(f"✅ Clean: No outgoing changes compared to {ref_name}.")
        sys.exit(0)

    engine = args.engine
    if engine == "auto":
        detected = detect_engine()
        if not detected:
            log_error("No supported AI CLI found (`agy`, `claude`, or `codex`).")
            sys.exit(1)
        engine = detected

    guidelines = get_repo_guidelines(git_root)
    branch_name = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    prompt_parts = [
        "You are an ADVERSARIAL AI CODE REVIEWER conducting an independent, rigorous code audit.",
        f"Context: {branch_name} (diff against {ref_name})",
        f"Reviewed-Commit: {head_sha}",
        "Review Standards & Expectations:",
        "1. Be adversarial: actively search for regressions, edge-case failures, schema mismatches, syntax errors, omitted instances, and breaking contract changes.",
        "2. Do NOT rubber-stamp. Scrutinize whether any other files or callers suffer from identical bugs.",
        "3. Review the code strictly on what the diff and codebase state, not on assumptions.",
        "4. Structure your response with:",
        "   - ### Summary Verdict (APPROVE vs NEEDS WORK with reason)",
        "   - ### Critical Findings (blocking bugs / regressions)",
        "   - ### Observations & Non-Blocking Suggestions",
        "   - ### Verification Steps",
    ]

    if guidelines:
        prompt_parts.append(f"\nRepository Guidelines:\n{guidelines}")

    prompt_parts.append(f"\nDiff to Review:\n```diff\n{diff}\n```")
    full_prompt = "\n\n".join(prompt_parts)

    if engine in ("antigravity", "agy"):
        engine_label = "Google Antigravity"
        report = run_antigravity_review(full_prompt, model=args.model)
    elif engine == "claude":
        engine_label = "Claude Code (Local)"
        report = run_claude_review(full_prompt, model=args.model)
    else:
        engine_label = "OpenAI Codex"
        report = run_codex_review(full_prompt)

    print("\n" + "=" * 60)
    print(f"📋 LOCAL ADVERSARIAL REVIEW REPORT ({engine_label})")
    print("=" * 60 + "\n")
    print(report)
    print("\n" + "=" * 60)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"Saved report to: {args.output}")

    if args.post:
        if not pr_num:
            print("::warning::Could not determine PR number to post to. Use --pr <number>.", file=sys.stderr)
        else:
            post_review_to_github(pr_num, report, engine_label)


if __name__ == "__main__":
    main()

