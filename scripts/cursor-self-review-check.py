#!/usr/bin/env python3
"""Interim CLI for the Cursor Cloud self-review recipe (ai-config#2299, #2310).

Until ai-config#2241 restores `no-push-without-self-review.py` on this repo's
Cursor adapter, the Cursor Cloud `Task` recipe in `memories/cursor.md` asks a
model to re-derive by hand what the hook already computes: the report's last
verdict line, the `Reviewed-Commit` fingerprint after it, and five refusal
gates that plain `git` output decides. Hand-run derivations drift; this CLI
runs the same code paths deterministically.

Two subcommands:

  verdict  --report FILE | --transcript FILE  [--expect-head SHA]
      Parse an adversarial-review report through the hook's own
      `parse_report()` (last verdict LINE, first fingerprint after it) and
      print both. With --expect-head, refuse on a missing or mismatched
      fingerprint. --transcript takes a Cursor Cloud `batch-fetch-details`
      transcript JSON and extracts the last assistant text (already a
      markdown string; it is NOT double-decoded -- memories/cursor.md).

  gates    --recorded-head SHA --recorded-branch NAME
           [--remote origin] [--refspec HEAD] [-C DIR] [--skip-dry-run]
      Run the git-decidable refusal gates from the recipe (#2310):
        1. `git status --short` is empty
        2. HEAD still equals the recorded sha
        3. same-argv `git push --dry-run --porcelain` new tip
           prefix-matches HEAD
        4. the dry-run source ref is HEAD or the recorded branch
        5. `git diff origin/<default-branch>...HEAD` emptiness, printed as
           the `pr-on-claim` carve-out status (informational, never a
           refusal by itself)

Exit status is three-valued, per `shared/coding/errexit-is-not-uniform.md`:
0 = pass, 1 = refuse (a gate failed, or the verdict/fingerprint refuses),
2 = usage or environment error (the check could not answer). Consumers must
not collapse 2 into either verdict.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

USAGE_EXIT = 2


def die(msg: str) -> "NoReturn":  # noqa: F821 - py<3.11 typing not needed
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(USAGE_EXIT)


def _load_hook():
    """Load hooks/no-push-without-self-review.py as a module, by path.

    Import errors propagate as environment errors: a missing or broken hook
    must fail loudly rather than silently degrade to a hand parse -- the
    hand parse is the failure mode this CLI exists to retire.
    """
    hook_path = (
        Path(__file__).resolve().parent.parent
        / "hooks"
        / "no-push-without-self-review.py"
    )
    if not hook_path.is_file():
        die(f"hook not found at {hook_path}")
    spec = importlib.util.spec_from_file_location(
        "no_push_without_self_review", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_last_assistant_text(payload) -> str | None:
    """Last non-empty assistant `text` from a transcript JSON structure.

    Cursor Cloud `batch-fetch-details` transcripts store the report as a
    markdown string in an assistant message's `text` field (measured
    2026-08-26 PDT; see memories/cursor.md). The container shape is not
    pinned by any contract, so this walks the structure for objects whose
    role/type says assistant and takes the last non-empty `text`.
    """
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            role = str(node.get("role") or node.get("type") or "").lower()
            text = node.get("text")
            if "assistant" in role and isinstance(text, str) and text.strip():
                found.append(text)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found[-1] if found else None


def cmd_verdict(args) -> int:
    if bool(args.report) == bool(args.transcript):
        die("pass exactly one of --report or --transcript")

    if args.report:
        source = Path(args.report)
        if not source.is_file():
            die(f"no such file: {source}")
        body = source.read_text(encoding="utf-8", errors="replace")
    else:
        source = Path(args.transcript)
        if not source.is_file():
            die(f"no such file: {source}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            die(f"transcript is not valid JSON: {exc}")
        body = _extract_last_assistant_text(payload)
        if body is None:
            die("no assistant text found in the transcript")

    hook = _load_hook()
    verdict, reviewed_commit = hook.parse_report(body)

    print(f"verdict: {verdict or 'NONE'}")
    print(f"reviewed-commit: {reviewed_commit or 'NONE'}")

    if verdict is None:
        print("REFUSE: no verdict line parse_report() recognizes "
              "(a restated brief or an unclosed fence both land here)")
        return 1

    if args.expect_head:
        expect = args.expect_head.lower()
        if not re.fullmatch(r"[0-9a-f]{7,40}", expect):
            die(f"--expect-head is not a 7-40 hex sha: {args.expect_head}")
        if not reviewed_commit:
            print("REFUSE: no Reviewed-Commit fingerprint after the verdict")
            return 1
        # parse_report already constrains the fingerprint to 7-40 hex; the
        # comparison is prefix-tolerant in either direction so an abbreviated
        # recording matches a full one.
        if not (expect.startswith(reviewed_commit)
                or reviewed_commit.startswith(expect)):
            print(f"REFUSE: fingerprint {reviewed_commit} does not match "
                  f"expected head {expect}")
            return 1

    if verdict != "clean":
        print("REFUSE: verdict is not clean")
        return 1

    print("PASS: clean verdict at the expected head"
          if args.expect_head else "PASS: clean verdict (no head expected)")
    return 0


def _git(args_list: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args_list], cwd=cwd, capture_output=True, text=True
    )


def _default_branch(cwd: str, remote: str) -> str | None:
    r = _git(["symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD"], cwd)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().split("/", 1)[-1]
    for cand in ("main", "master"):
        if _git(["rev-parse", "--verify", f"{remote}/{cand}"], cwd).returncode == 0:
            return cand
    return None


def cmd_gates(args) -> int:
    cwd = args.directory or "."
    if _git(["rev-parse", "--git-dir"], cwd).returncode != 0:
        die(f"not a git repository: {cwd}")

    recorded_head = args.recorded_head.lower()
    if not re.fullmatch(r"[0-9a-f]{7,40}", recorded_head):
        die(f"--recorded-head is not a 7-40 hex sha: {args.recorded_head}")

    failures = 0

    # Gate 1: clean tree.
    status = _git(["status", "--short"], cwd)
    if status.returncode != 0:
        die(f"git status failed: {status.stderr.strip()}")
    if status.stdout.strip():
        print("FAIL gate 1: working tree not clean:")
        print(status.stdout.rstrip())
        failures += 1
    else:
        print("PASS gate 1: working tree clean")

    # Gate 2: HEAD unchanged.
    head = _git(["rev-parse", "HEAD"], cwd)
    if head.returncode != 0:
        die(f"git rev-parse HEAD failed: {head.stderr.strip()}")
    head_sha = head.stdout.strip().lower()
    if not head_sha.startswith(recorded_head):
        print(f"FAIL gate 2: HEAD {head_sha[:12]} is not the recorded "
              f"{recorded_head[:12]}")
        failures += 1
    else:
        print(f"PASS gate 2: HEAD still {head_sha[:12]}")

    # Gates 3 and 4: dry-run tip and source ref.
    if args.skip_dry_run:
        print("SKIP gates 3-4: --skip-dry-run given")
    else:
        dry = _git(
            ["push", "--dry-run", "--porcelain", args.remote, args.refspec],
            cwd,
        )
        if dry.returncode != 0 and not dry.stdout.strip():
            die(f"git push --dry-run failed: {dry.stderr.strip()}")
        rows = [
            line for line in dry.stdout.splitlines()
            if line[:1] in "*+- " and "\t" in line
        ]
        if not rows:
            print("FAIL gate 3: dry-run reported no refspec rows "
                  "(nothing would be pushed, or the output shape changed)")
            failures += 1
        for line in rows:
            parts = line.split("\t")
            if len(parts) < 3:
                print(f"FAIL gate 3: unparseable dry-run row: {line!r}")
                failures += 1
                continue
            from_ref, _, to_ref = parts[1].partition(":")
            summary = parts[2].strip()
            # Gate 3: the new tip must be HEAD. Resolve the source ref
            # locally rather than trusting the abbreviated summary alone.
            src = _git(["rev-parse", from_ref], cwd)
            new_tip = src.stdout.strip().lower() if src.returncode == 0 else ""
            if new_tip and new_tip == head_sha:
                print(f"PASS gate 3: dry-run new tip {new_tip[:12]} is HEAD "
                      f"({summary})")
            else:
                print(f"FAIL gate 3: dry-run would push {new_tip[:12] or '?'} "
                      f"which is not HEAD {head_sha[:12]} ({summary})")
                failures += 1
            # Gate 4: source ref is HEAD or the recorded branch.
            short = from_ref.removeprefix("refs/heads/")
            if from_ref == "HEAD" or short == args.recorded_branch:
                print(f"PASS gate 4: source ref {from_ref!r} is HEAD or the "
                      f"recorded branch")
            else:
                print(f"FAIL gate 4: source ref {from_ref!r} is neither HEAD "
                      f"nor the recorded branch {args.recorded_branch!r}")
                failures += 1

    # Gate 5 (informational): the pr-on-claim empty-diff carve-out.
    default = _default_branch(cwd, args.remote)
    if default is None:
        print("NOTE gate 5: no default branch resolvable; carve-out unknown")
    else:
        diff = _git(
            ["diff", "--quiet", f"{args.remote}/{default}...HEAD"], cwd
        )
        if diff.returncode == 0:
            print(f"NOTE gate 5: diff against {args.remote}/{default} is "
                  "empty -- the pr-on-claim carve-out applies "
                  "(no report to parse; do not refuse for lack of a verdict)")
        elif diff.returncode == 1:
            print(f"NOTE gate 5: non-empty diff against "
                  f"{args.remote}/{default} -- a review is owed")
        else:
            print(f"NOTE gate 5: diff failed ({diff.stderr.strip()}); "
                  "carve-out unknown")

    if failures:
        print(f"REFUSE: {failures} gate check(s) failed")
        return 1
    print("PASS: all decidable gates passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cursor self-review fingerprint and git gates (interim CLI)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_verdict = sub.add_parser("verdict", help="parse a review report")
    p_verdict.add_argument("--report", help="report file (markdown)")
    p_verdict.add_argument(
        "--transcript",
        help="Cursor Cloud batch-fetch-details transcript JSON",
    )
    p_verdict.add_argument(
        "--expect-head", help="sha the fingerprint must match"
    )
    p_verdict.set_defaults(func=cmd_verdict)

    p_gates = sub.add_parser("gates", help="run the git refusal gates")
    p_gates.add_argument("--recorded-head", required=True)
    p_gates.add_argument("--recorded-branch", required=True)
    p_gates.add_argument("--remote", default="origin")
    p_gates.add_argument("--refspec", default="HEAD")
    p_gates.add_argument("-C", dest="directory", default=None,
                         help="run in this checkout")
    p_gates.add_argument("--skip-dry-run", action="store_true",
                         help="skip gates 3-4 (no network)")
    p_gates.set_defaults(func=cmd_gates)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
