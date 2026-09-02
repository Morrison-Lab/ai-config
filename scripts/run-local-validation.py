#!/usr/bin/env python3
"""Run the CI validators locally, deriving the list from .github/workflows/validate.yml.

Morrison-Lab/ai-config#1940 and #1262.

Before every push the same question comes up -- which local checks predict
CI? -- and the answer was assembled from memory, per PR, and was wrong three
times in one session (#1940: a wrapper sync missed, then semantic-line-breaks,
then a test suite whose dogfood assertion the production script never runs).
memories/preferences.md already says to take the list from validate.yml
"rather than from this bullet"; this script IS that derivation, so the list
cannot drift from CI and the ordering (#1262: every check after every edit,
in one block, with a visible denominator) cannot depend on anyone's memory.

What it runs, in order:

  1. Every `run:` step of the `validate` job (or the job named with --job),
     with the step's own `env:` and `working-directory:`. Multi-line `run: |`
     blocks execute under `bash -e -o pipefail`, the shell GitHub uses.
  2. A local equivalent for each sibling job that only `uses:` a reusable
     workflow or composite action, where one is known (the table below):
     the diff-scoped new-line-breaks check, whose script is vendored here. A
     `uses:` job with no vendored equivalent (lint-markdown and lint-qmd
     today) is listed as NOT RUN, and so is a `run:` step that reads a
     `${{ github.* }}` expression, so the denominator shows what CI checks
     that this run did not.

Steps whose name matches --skip (default: the dependency install, which needs
the network and is already satisfied locally) are skipped and counted.

A dirty working tree is reported before anything runs: a check measured
against a tree an edit is about to change expires with the edit (#1262).
--require-clean turns that report into exit 2.

Exit codes:
  0  every step that ran passed
  1  at least one step failed (its exit code is in the table)
  2  the workflow could not be read or parsed, no job matched, --require-clean
     failed, or PyYAML is missing

Usage:
  python3 scripts/run-local-validation.py                  # run everything
  python3 scripts/run-local-validation.py --list           # show the derived plan
  python3 scripts/run-local-validation.py --only 'links|punctuation'
  python3 scripts/run-local-validation.py --base origin/main   # base for diff-scoped checks
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
DEFAULT_SKIP = r"^Install dependencies$"
# Non-greedy to the closing `}}`, so a body carrying its own `}` (a fromJSON
# literal) still matches; `[^}]*` would silently pass such a step as runnable.
GITHUB_EXPRESSION = re.compile(r"\$\{\{.*?\}\}")

# Local equivalents for jobs that only `uses:` a reusable workflow or a
# composite action. Keyed by a substring of the `uses:` reference; the value
# is a function of (job dict, args) returning (command, env) or None.
# `{base}` is the --base ref; `{globs}`, `{config}` come from the job's `with:`.


def _nlb_equivalent(job: Dict[str, Any], base: str) -> Optional[Dict[str, Any]]:
    step = next((s for s in job.get("steps", []) if "check-new-line-breaks" in str(s.get("uses", ""))), None)
    if step is None:
        return None
    with_ = step.get("with") or {}
    env = {
        "NLB_BASE_REF": base,
        "NLB_GLOBS": str(with_.get("globs") or "*.md"),
        "NLB_FAIL": str(with_.get("fail", "true")),
    }
    # Every input the composite action takes is forwarded; the vendored script
    # reads the same NLB_* names, so a job input this misses would make the
    # local run diverge from CI in one direction or the other (#1940 review
    # round 1 found paths-ignore missing: 201 generated codex-skills/*.md files
    # CI skips were being scanned locally).
    if with_.get("paths-ignore"):
        env["NLB_PATHS_IGNORE"] = str(with_["paths-ignore"])
    return {"command": "python3 scripts/vendor/gha-check-new-line-breaks.py", "env": env}


# Only a job whose exact check is vendored into this repo gets a local
# equivalent. new-line-breaks qualifies: scripts/vendor/gha-check-new-line-breaks.py
# is the pinned copy of the composite action's script. lint-markdown and
# lint-qmd do not: gha's lint-markdown action runs four checks (markdownlint,
# code-block length, list-item splices, table splits), and a local
# `markdownlint-cli2` call reproduces one of them while reporting a clean
# zero for the other three -- the guessed-equivalent failure this runner
# exists to avoid. Both are listed as NOT RUN so the denominator names them.
LOCAL_EQUIVALENTS = {
    "check-new-line-breaks": _nlb_equivalent,
}


@dataclass
class Step:
    name: str
    command: str
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    source: str = "validate"      # job the step was derived from
    runnable: bool = True          # False for a uses: job with no local equivalent
    note: str = ""


def _uses_of(job: Dict[str, Any]) -> str:
    if job.get("uses"):
        return str(job["uses"])
    for s in job.get("steps", []) or []:
        u = str(s.get("uses", ""))
        if u and not u.startswith("actions/"):
            return u
    return ""


def derive_steps(workflow: Dict[str, Any], job_name: str, base: str) -> List[Step]:
    """Derive the ordered step list from a parsed workflow document."""
    jobs = workflow.get("jobs") or {}
    if job_name not in jobs:
        raise KeyError(f"job {job_name!r} not found; jobs are: {', '.join(jobs) or '(none)'}")
    steps: List[Step] = []
    for s in jobs[job_name].get("steps", []) or []:
        run = s.get("run")
        if run is None:
            continue
        env = {k: str(v) for k, v in (s.get("env") or {}).items()}
        step = Step(
            name=str(s.get("name") or run.strip().splitlines()[0]),
            command=str(run).rstrip("\n"),
            env=env,
            cwd=s.get("working-directory"),
            source=job_name,
        )
        expression = GITHUB_EXPRESSION.search(step.command) or next(
            (m for m in (GITHUB_EXPRESSION.search(v) for v in env.values()) if m), None
        )
        if expression:
            # Name the expression that matched: `${{ secrets.GITHUB_TOKEN }}` is
            # something a user can supply locally, `${{ github.event.* }}` is not,
            # and a note that said `github.*` for both misdescribed the first.
            step.runnable = False
            step.note = f"reads `{expression.group(0)}`, which only a runner supplies"
        steps.append(step)
    for name, job in jobs.items():
        if name == job_name:
            continue
        uses = _uses_of(job)
        if not uses:
            continue
        equivalent = None
        for key, fn in LOCAL_EQUIVALENTS.items():
            if key in uses:
                equivalent = fn(job, base)
                break
        if equivalent is None:
            steps.append(Step(name=name, command="", source=name, runnable=False,
                              note=f"no local equivalent for {uses}"))
        else:
            steps.append(Step(name=name, command=equivalent["command"], env=equivalent["env"], source=name))
    return steps


def load_workflow(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError("PyYAML is required: pip install pyyaml") from exc
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RuntimeError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise RuntimeError(f"{path} did not parse to a mapping")
    return doc


def run_step(step: Step, root: Path, timeout: Optional[float]) -> int:
    env = dict(os.environ)
    env.update(step.env)
    cwd = root / step.cwd if step.cwd else root
    proc = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step.command],
        cwd=str(cwd), env=env, timeout=timeout,
    )
    return proc.returncode


def dirty_tree(root: Path) -> List[str]:
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=str(root),
                             capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        # Observable, never silent: the caller's dirty-tree report is skipped,
        # and this line says so (shared/principles/fail-fast.md).
        print(f"warning: could not read git status in {root} ({exc}); "
              "skipping the dirty-tree check", file=sys.stderr)
        return []
    return [ln for ln in out.splitlines() if ln.strip()]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--workflow", default=str(DEFAULT_WORKFLOW))
    p.add_argument("--job", default="validate", help="job whose run: steps to execute (default: validate)")
    p.add_argument("--base", default="origin/main", help="base ref for diff-scoped checks (default: origin/main)")
    p.add_argument("--only", default=None, help="regex; run only steps whose name matches")
    p.add_argument("--skip", default=DEFAULT_SKIP, help=f"regex; skip steps whose name matches (default: {DEFAULT_SKIP!r})")
    p.add_argument("--list", action="store_true", help="print the derived plan and exit 0")
    p.add_argument("--require-clean", action="store_true", help="exit 2 instead of warning when the working tree is dirty")
    p.add_argument("--timeout", type=float, default=None, help="per-step timeout in seconds")
    p.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    try:
        workflow = load_workflow(Path(args.workflow))
        steps = derive_steps(workflow, args.job, args.base)
    except (RuntimeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    only = re.compile(args.only) if args.only else None
    skip = re.compile(args.skip) if args.skip else None

    plan = []
    for s in steps:
        if only and not only.search(s.name):
            continue
        skipped = bool(skip and skip.search(s.name))
        plan.append((s, skipped))

    if args.list:
        for s, skipped in plan:
            tag = "SKIP" if skipped else ("NOT RUN" if not s.runnable else "RUN")
            detail = s.note if not s.runnable else s.command.splitlines()[0]
            print(f"{tag:8} [{s.source}] {s.name}: {detail}")
        print(f"{len(plan)} step(s) derived from {args.workflow}")
        return 0

    dirty = dirty_tree(root)
    if dirty:
        msg = f"working tree has {len(dirty)} uncommitted change(s); a result measured now expires with the next edit (#1262)"
        if args.require_clean:
            print(f"error: {msg}", file=sys.stderr)
            return 2
        print(f"warning: {msg}", file=sys.stderr)

    results = []
    for s, skipped in plan:
        if skipped:
            results.append((s, "skip", 0.0))
            continue
        if not s.runnable:
            results.append((s, "not run", 0.0))
            continue
        print(f"==> [{s.source}] {s.name}", flush=True)
        t0 = time.monotonic()
        try:
            rc = run_step(s, root, args.timeout)
        except subprocess.TimeoutExpired:
            rc = "timeout"
        results.append((s, rc, time.monotonic() - t0))

    print()
    print(f"{'step':60} {'rc':>8} {'seconds':>8}")
    for s, rc, secs in results:
        print(f"{s.name[:60]:60} {str(rc):>8} {secs:8.1f}")
    failed = [r for r in results if r[1] not in (0, "skip", "not run")]
    skipped_n = sum(1 for r in results if r[1] == "skip")
    not_run = [r for r in results if r[1] == "not run"]
    ran = len(results) - skipped_n - len(not_run)
    print(f"\n{ran - len(failed)} passed, {len(failed)} failed, {skipped_n} skipped, "
          f"{len(not_run)} not runnable locally, of {len(results)} step(s) derived from {args.workflow}")
    for s, _, _ in not_run:
        print(f"  not run: {s.name} ({s.note})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
