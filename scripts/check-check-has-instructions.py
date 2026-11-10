#!/usr/bin/env python3
"""Fail when a PR adds an algorithmic check without a writer and a reviewer instruction.

ai-config#5174.  Ezra, 2026-11-09 (ai-config#5171): "every algorithmic check
should also have corresponding writer and reviewer instructions, to create
defense in depth".  The rule is in
shared/workflow/checks-need-writer-and-reviewer-instructions.md; this is its
mechanical half, decided from the diff alone.

A PR *adds a check* when it adds a file (status A) that is a
`scripts/check-*.py` or `scripts/gha-check-*.py` script, or a hook
`hooks/<name>.py` that is not a test (`test-*`) or a private helper (`_*`).

Such a PR must also touch both layers:

- a writer instruction: a changed `.md` under `shared/`, `AGENTS.md`,
  `CLAUDE.md` or a `skills/*/SKILL.md`;
- a reviewer instruction: a changed `.claude/agents/*.md`.

A PR that cannot supply a layer says why in its body, on a line
`check-instructions: exempt - <reason>`.  An empty reason does not exempt.
The body arrives in the PR_BODY environment variable or `--body-file`.

Usage:
  check-check-has-instructions.py [--base REF] [--body-file FILE]
  check-check-has-instructions.py --self-test

Exit codes: 0 clean, 1 a check lacks a layer, 2 the diff could not be read.
"""
import argparse
import os
import re
import subprocess
import sys

CHECK_SCRIPT = re.compile(r"^scripts/(?:gha-)?check-[^/]+\.py$")
HOOK = re.compile(r"^hooks/(?!test-|_)[^/]+\.py$")
WRITER = re.compile(
    r"^(?:shared/.+\.md|AGENTS\.md|CLAUDE\.md|skills/[^/]+/SKILL\.md)$")
REVIEWER = re.compile(r"^\.claude/agents/[^/]+\.md$")
EXEMPT = re.compile(r"^\s*check-instructions:\s*exempt\s*-\s*(\S.*)$", re.M | re.I)


def added_checks(changes):
    """Paths of checks this diff adds. `changes` is [(status, path)]."""
    return sorted(p for s, p in changes
                  if s.startswith("A") and (CHECK_SCRIPT.match(p) or HOOK.match(p)))


def missing_layers(changes):
    paths = [p for _, p in changes]
    missing = []
    if not any(WRITER.match(p) for p in paths):
        missing.append("writer instruction (shared/**/*.md, AGENTS.md, CLAUDE.md or a SKILL.md)")
    if not any(REVIEWER.match(p) for p in paths):
        missing.append("reviewer instruction (.claude/agents/*.md)")
    return missing


def evaluate(changes, body):
    """(exit code, message) for one diff and PR body."""
    checks = added_checks(changes)
    if not checks:
        return 0, "no check added"
    if EXEMPT.search(body or ""):
        return 0, "exempt: " + EXEMPT.search(body).group(1).strip()
    missing = missing_layers(changes)
    if not missing:
        return 0, "added %d check(s), both layers touched" % len(checks)
    return 1, ("added check(s) %s without a %s. See "
               "shared/workflow/checks-need-writer-and-reviewer-instructions.md, "
               "or add `check-instructions: exempt - <reason>` to the PR body."
               % (", ".join(checks), " and a ".join(missing)))


def diff_changes(base):
    out = subprocess.run(
        ["git", "diff", "--name-status", "-M", "%s...HEAD" % base],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "git diff failed")
    changes = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changes.append((parts[0], parts[-1]))
    return changes


def self_test():
    bad = 0

    def check(name, got, want):
        nonlocal bad
        ok = got == want
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name + ("" if ok else " got %r" % (got,)))

    new = ("A", "scripts/check-foo.py")
    w = ("M", "shared/workflow/foo.md")
    r = ("M", ".claude/agents/adversarial-reviewer.md")
    code = lambda ch, body="": evaluate(ch, body)[0]
    check("no check added passes", code([("M", "README.md")]), 0)
    check("negative control: empty diff passes only as 'no check added'",
          evaluate([], ""), (0, "no check added"))
    check("check alone fails", code([new]), 1)
    check("check plus writer only fails", code([new, w]), 1)
    check("check plus reviewer only fails", code([new, r]), 1)
    check("check plus both passes", code([new, w, r]), 0)
    check("modified check is not an add", code([("M", "scripts/check-foo.py")]), 0)
    check("added hook counts", code([("A", "hooks/no-foo.py")]), 1)
    check("added hook test is not a check", code([("A", "hooks/test-no-foo.py")]), 0)
    check("added helper is not a check", code([("A", "hooks/_lib.py")]), 0)
    check("added gha-check script counts", code([("A", "scripts/gha-check-x.py")]), 1)
    check("AGENTS.md is a writer layer", code([new, ("M", "AGENTS.md"), r]), 0)
    check("README is not a writer layer", code([new, ("M", "README.md"), r]), 1)
    check("exemption with reason passes",
          code([new], "check-instructions: exempt - pure refactor"), 0)
    check("exemption without reason fails",
          code([new], "check-instructions: exempt - "), 1)
    check("rename into check path counts", code([("R100", "scripts/check-bar.py")]), 0)
    msg = evaluate([new, w], "")[1]
    check("message names the missing reviewer layer", "reviewer instruction" in msg
          and "writer instruction" not in msg, True)
    print("ok" if not bad else "%d failure(s)" % bad)
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--body-file")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    body = os.environ.get("PR_BODY", "")
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()
    try:
        changes = diff_changes(args.base)
    except (RuntimeError, OSError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    code, msg = evaluate(changes, body)
    print(("ok: " if code == 0 else "FAIL: ") + msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
