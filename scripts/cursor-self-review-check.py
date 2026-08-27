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

    A missing or broken hook is an ENVIRONMENT error (exit 2), never a
    refusal: this CLI exists to retire the hand parse, so it must not let
    its own breakage read as a verdict about the report.
    """
    hook_path = (
        Path(__file__).resolve().parent.parent
        / "hooks"
        / "no-push-without-self-review.py"
    )
    if not hook_path.is_file():
        die(f"hook not found at {hook_path}")
    try:
        spec = importlib.util.spec_from_file_location(
            "no_push_without_self_review", hook_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        die(f"could not load {hook_path.name}: {exc}")
    return module


def _extract_last_assistant_text(payload) -> str | None:
    """Last non-empty assistant `text` from a batch-fetch-details transcript.

    The measured shape (2026-08-26 PDT, memories/cursor.md) is a dict with a
    `messages` list of records carrying a `role`; iterate that list ONLY and
    filter `role == assistant` on the top-level records. A recursive walk
    over the whole structure would let an assistant-shaped object nested
    inside a later user record -- a harness echo, a quoted example -- win
    over the real report, in the false-clean direction.
    """
    if not isinstance(payload, dict):
        return None
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return None
    found: str | None = None
    for record in messages:
        if not isinstance(record, dict):
            continue
        if str(record.get("role") or "").lower() != "assistant":
            continue
        text = record.get("text")
        if isinstance(text, str) and text.strip():
            found = text
    return found


# The decoder's heading check, which parse_report deliberately does not do
# (it matches only the verdict line and the fingerprint). A last assistant
# text that lacks the report shape is a plan, an apology, or a status line
# -- not a report -- and calling parse_report on it grades the wrong thing.
def _missing_report_headings(body: str) -> list[str]:
    missing = [
        h for h in ("Summary", "Findings", "Verdict")
        if not re.search(rf"(?im)^#{{1,6}}[ \t]*{h}\b", body)
    ]
    if not re.search(r"(?im)^\*{0,2}Reviewed-Commit\*{0,2}[ \t]*:", body):
        missing.append("Reviewed-Commit")
    return missing


def cmd_verdict(args) -> int:
    if bool(args.report) == bool(args.transcript):
        die("pass exactly one of --report or --transcript")

    if args.report:
        source = Path(args.report)
        if not source.is_file():
            die(f"no such file: {source}")
        try:
            body = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            die(f"could not read {source}: {exc}")
    else:
        source = Path(args.transcript)
        if not source.is_file():
            die(f"no such file: {source}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            die(f"could not read {source}: {exc}")
        except json.JSONDecodeError as exc:
            die(f"transcript is not valid JSON: {exc}")
        body = _extract_last_assistant_text(payload)
        if body is None:
            die("no assistant text found in the transcript")

    # The decoder's own gate, ahead of parse_report (memories/cursor.md:
    # "Do not call parse_report() on a body that failed the heading check").
    # A refusal, not an environment error: the transcript was read fine and
    # what it holds is not a report.
    missing = _missing_report_headings(body)
    if missing:
        print(f"REFUSE: not a report -- missing {', '.join(missing)} "
              "(a plan or apology restating the brief lands here)")
        return 1

    hook = _load_hook()
    verdict, reviewed_commit = hook.parse_report(body)

    print(f"verdict: {verdict or 'NONE'}")
    print(f"reviewed-commit: {reviewed_commit or 'NONE'}")

    if verdict is None:
        print("REFUSE: no verdict line parse_report() recognizes "
              "(an unclosed fence also lands here)")
        return 1

    if not reviewed_commit:
        # The hook refuses a fingerprint-less report unconditionally ("a
        # report cut short before its fingerprint is not a verdict"), so
        # this wrapper must not be laxer with --expect-head omitted.
        print("REFUSE: no Reviewed-Commit fingerprint after the verdict")
        return 1

    if args.expect_head:
        expect = args.expect_head.lower()
        if not re.fullmatch(r"[0-9a-f]{7,40}", expect):
            die(f"--expect-head is not a 7-40 hex sha: {args.expect_head}")
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
          if args.expect_head else "PASS: clean fingerprinted verdict "
          "(no expected head given; compare the fingerprint yourself)")
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
        # Real porcelain flag characters: ' ' fast-forward, '+' forced,
        # '-' deleted, '*' new ref, '=' up to date, '!' rejected.
        rows = [
            line for line in dry.stdout.splitlines()
            if line[:1] in "*+-=! " and "\t" in line
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
            from_ref = parts[1].partition(":")[0]
            summary = parts[2].strip()
            if line[:1] == "!":
                # The remote moved (or the push is otherwise refused).
                # This is check-before-pushing's own condition: refuse and
                # name it, rather than reading it as an output-shape change.
                print(f"FAIL gate 3: dry-run push of {from_ref!r} was "
                      f"rejected ({summary}); fetch and reconcile first")
                failures += 1
                continue
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
