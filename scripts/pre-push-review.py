#!/usr/bin/env python3
"""Run local AI code review using desktop subscription quota (Antigravity / Claude / Codex / OpenCode).

Computes local outgoing diff against PR base or main, runs adversarial review across available
subscription engines with automatic fallback, and optionally posts review verdicts to GitHub PRs.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple


def log_error(msg: str):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error::{msg}", file=sys.stderr)
    else:
        print(f"Error: {msg}", file=sys.stderr)


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
    """Auto-detect PR number for current branch if one exists and gh CLI is available."""
    if not shutil.which("gh"):
        return None
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


def get_pr_base_branch(pr_number: int) -> Optional[str]:
    """Get the target base branch of a GitHub PR."""
    if not shutil.which("gh"):
        return None
    res = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "baseRefName"],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            return data.get("baseRefName")
        except Exception:
            return None
    return None


def resolve_diff(pr_number: Optional[int] = None, explicit_base: str = "") -> Tuple[str, str]:
    """Compute local git diff against the PR base branch or default main.

    Always diffs local HEAD to include unpushed commits.
    """
    base_ref = explicit_base
    if not base_ref and pr_number:
        pr_base = get_pr_base_branch(pr_number)
        if pr_base:
            for cand in [f"origin/{pr_base}", pr_base]:
                r = subprocess.run(["git", "rev-parse", "--verify", cand], capture_output=True, text=True)
                if r.returncode == 0:
                    base_ref = cand
                    break

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

    label = f"{base_ref} (PR #{pr_number})" if pr_number else base_ref
    return diff_res.stdout, label


def get_repo_guidelines(root: str) -> str:
    candidate_files = ["AGENTS.md", "GEMINI.md"]
    guidelines = []
    for fname in candidate_files:
        p = os.path.join(root, fname)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        guidelines.append(f"--- Repository Guidelines ({fname}) ---\n{content}")
            except Exception as e:
                print(f"Warning: could not read {p}: {e}", file=sys.stderr)
    return "\n\n".join(guidelines)


def validate_review_output(report: Optional[str]) -> bool:
    """Validate that review output conforms to structured adversarial review standards."""
    if not report or len(report.strip()) < 50:
        return False
    has_verdict = "### Summary Verdict" in report and ("APPROVE" in report or "NEEDS WORK" in report)
    has_findings = "### Critical Findings" in report
    if not (has_verdict and has_findings):
        return False
    refusal_patterns = [
        "hit your weekly limit",
        "prepayment credits depleted",
        "unrecognized argument",
        "api key is missing",
    ]
    for pat in refusal_patterns:
        if pat in report.lower():
            return False
    return True


def run_antigravity_review(prompt: str, model: str = "") -> Optional[str]:
    agy_path = shutil.which("agy") or os.path.expanduser("~/.local/bin/agy")
    if not os.path.isfile(agy_path) and not shutil.which("agy"):
        return None

    cmd = [agy_path, "--mode", "plan", "-p", prompt]
    if model:
        cmd.extend(["--model", model])

    print("Running local adversarial review via Google Antigravity (plan mode)...")
    try:
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=360)
    except subprocess.TimeoutExpired:
        print("Notice: Antigravity review timed out after 360s.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Notice: Antigravity execution failed: {e}", file=sys.stderr)
        return None

    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        print(f"Notice: Antigravity review returned nonzero ({err})", file=sys.stderr)
        return None
    out = res.stdout.strip()
    return out if validate_review_output(out) else None


def run_claude_review(prompt: str, model: str = "") -> Optional[str]:
    claude_path = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    if not os.path.isfile(claude_path) and not shutil.which("claude"):
        return None

    cmd = [claude_path, "--permission-mode", "plan", "-p", prompt]
    if model:
        cmd.extend(["--model", model])

    print("Running local adversarial review via Claude CLI (plan mode)...")
    try:
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=360)
    except subprocess.TimeoutExpired:
        print("Notice: Claude review timed out after 360s.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Notice: Claude execution failed: {e}", file=sys.stderr)
        return None

    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        print(f"Notice: Claude review returned nonzero ({err})", file=sys.stderr)
        return None
    out = res.stdout.strip()
    return out if validate_review_output(out) else None


def run_codex_review(prompt: str, model: str = "") -> Optional[str]:
    codex_path = shutil.which("codex") or os.path.expanduser("~/.local/bin/codex")
    if not os.path.isfile(codex_path) and not shutil.which("codex"):
        return None

    print("Running local adversarial review via OpenAI Codex (read-only sandbox)...")
    cmd = [codex_path, "exec", "-s", "read-only", "--skip-git-repo-check"]
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)

    try:
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=360)
    except subprocess.TimeoutExpired:
        print("Notice: Codex review timed out after 360s.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Notice: Codex execution failed: {e}", file=sys.stderr)
        return None

    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        print(f"Notice: Codex review returned nonzero ({err})", file=sys.stderr)
        return None
    out = res.stdout.strip()
    return out if validate_review_output(out) else None


def run_opencode_review(prompt: str, model: str = "") -> Optional[str]:
    opencode_path = shutil.which("opencode") or os.path.expanduser("~/.local/bin/opencode")
    if not os.path.isfile(opencode_path) and not shutil.which("opencode"):
        return None

    print("Running local adversarial review via OpenCode (plan agent)...")
    cmd = [opencode_path, "run", "--agent", "plan"]
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)

    try:
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=360)
    except subprocess.TimeoutExpired:
        print("Notice: OpenCode review timed out after 360s.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Notice: OpenCode execution failed: {e}", file=sys.stderr)
        return None

    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        print(f"Notice: OpenCode review returned nonzero ({err})", file=sys.stderr)
        return None
    out = res.stdout.strip()
    return out if validate_review_output(out) else None


def detect_available_engines() -> List[str]:
    """Return available local engines in preferred fallback priority: claude -> codex -> opencode -> agy."""
    engines = []
    if shutil.which("claude") or os.path.isfile(os.path.expanduser("~/.local/bin/claude")):
        engines.append("claude")
    if shutil.which("codex") or os.path.isfile(os.path.expanduser("~/.local/bin/codex")):
        engines.append("codex")
    if shutil.which("opencode") or os.path.isfile(os.path.expanduser("~/.local/bin/opencode")):
        engines.append("opencode")
    if shutil.which("agy") or os.path.isfile(os.path.expanduser("~/.local/bin/agy")):
        engines.append("antigravity")
    return engines


def execute_review(engine: str, prompt: str, model: str = "") -> Tuple[Optional[str], str]:
    """Execute review with specified engine or automatic fallback chain."""
    engine_dispatch = {
        "claude": (run_claude_review, "Claude Code (Local)"),
        "codex": (run_codex_review, "OpenAI Codex"),
        "opencode": (run_opencode_review, "OpenCode"),
        "antigravity": (run_antigravity_review, "Google Antigravity"),
        "agy": (run_antigravity_review, "Google Antigravity"),
    }

    if engine != "auto":
        runner, label = engine_dispatch.get(engine, (None, engine))
        if not runner:
            log_error(f"Unknown engine: {engine}")
            return None, engine
        report = runner(prompt, model=model)
        return report, label

    available = detect_available_engines()
    if not available:
        log_error("No supported AI CLI found (`claude`, `codex`, `opencode`, `agy`).")
        return None, "None"

    for cand in available:
        runner, label = engine_dispatch[cand]
        report = runner(prompt, model=model)
        if report:
            return report, label
        print(f"Engine '{label}' was unavailable, exhausted, or produced invalid output; falling back...")

    return None, "Fallback Chain"


def format_review_body(report: str, engine_name: str, commit_sha: str = "") -> str:
    """Format review report for GitHub PR posting adhering to lab disclosure policy."""
    sha_line = f"\n**Reviewed Commit**: `{commit_sha}`\n" if commit_sha else ""
    return (
        f"### Local Adversarial AI Review ({engine_name})\n"
        f"{sha_line}\n"
        f"{report}\n\n"
        "---\n"
        f"_Posted by {engine_name} (AI agent) --- not written by a human._"
    )


def post_review_to_github(pr_number: int, report: str, engine_name: str, commit_sha: str = "") -> bool:
    """Post review report directly to GitHub PR via gh CLI."""
    formatted_body = format_review_body(report, engine_name, commit_sha=commit_sha)

    res = subprocess.run(
        ["gh", "pr", "review", str(pr_number), "--comment", "--body", formatted_body],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        print(f"Successfully posted review to PR #{pr_number} via `gh pr review`.")
        return True

    res_comment = subprocess.run(
        ["gh", "pr", "comment", str(pr_number), "--body", formatted_body],
        capture_output=True,
        text=True,
    )
    if res_comment.returncode == 0:
        print(f"Successfully posted review comment to PR #{pr_number} via `gh pr comment`.")
        return True

    log_error(f"Failed to post to GitHub PR #{pr_number}: {res_comment.stderr}")
    return False


def build_review_prompt(diff: str, ref_name: str, guidelines: str) -> str:
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
    return "\n\n".join(prompt_parts)


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
        choices=["auto", "antigravity", "agy", "claude", "codex", "opencode"],
        default="auto",
        help="AI engine: 'auto' (default: agy -> claude -> codex -> opencode), or specific engine name",
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
    diff, ref_name = resolve_diff(pr_number=pr_num, explicit_base=args.base)

    if not diff.strip():
        print(f"Clean: No outgoing changes compared to {ref_name}.")
        sys.exit(0)

    guidelines = get_repo_guidelines(git_root)
    full_prompt = build_review_prompt(diff, ref_name, guidelines)

    report, engine_label = execute_review(args.engine, full_prompt, model=args.model)

    if not report:
        log_error("Adversarial review failed to produce a report across all attempted engines.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"LOCAL ADVERSARIAL REVIEW REPORT ({engine_label})")
    print("=" * 60 + "\n")
    print(report)
    print("\n" + "=" * 60)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"Saved report to: {args.output}")

    if args.post:
        if not pr_num:
            log_error("Could not determine PR number to post to. Use --pr <number>.")
            sys.exit(1)
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        posted = post_review_to_github(pr_num, report, engine_label, commit_sha=head_sha)
        if not posted:
            sys.exit(1)


if __name__ == "__main__":
    main()
