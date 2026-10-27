#!/usr/bin/env python3
"""Dispatch one bounded, read-only brief to the `agy` CLI and verify the result.

Subscription-only: `agy` uses the Antigravity login stored on the machine,
never an API key. Run it only on a machine where Antigravity is signed in
(cf463-02 or the XPS; cf463-02 is Ezra's Linux box).

Modes:
  brief   Send the text of --brief-file; print the reply on stdout.
  review  Fetch a PR's diff with `gh`, embed it in the Argon review brief,
          and print a PR-comment body in the standard cross-harness shape.

The checks live here so every caller gets them: exit 0 from `agy` proves
nothing, so this fails on a `jetski: no output produced` denial, empty output,
a timeout, or edits in the checkout (`git status --porcelain` not empty).
See memories/delegation.md and skills/delegate-to-agy/SKILL.md.
"""

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "gemini-4-argon-high"
FOOTER = "_Posted by Antigravity (AI agent) --- not written by a human._"
MAX_BRIEF_BYTES = 100_000  # one argv entry; Linux caps it near 128 KiB

REVIEW_PREAMBLE = """You are Argon, a read-only adversarial reviewer. Use no tools.
Review the pull request diff below against the stated rules of the repository.
List what you checked even when you find nothing, then list each concrete
defect with file and line. Quote only text that appears in the diff.
End with exactly one line: `Verdict: Clean` or `Verdict: Needs more work`.

PR: {repo}#{pr}
Head: {sha}
Title: {title}

--- DIFF ---
{diff}
"""


def run(cmd, **kw):
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", **kw
    )


def dispatch(brief: str, model: str, timeout: str, cwd: str) -> str:
    if len(brief.encode()) > MAX_BRIEF_BYTES:
        sys.exit(f"brief is over {MAX_BRIEF_BYTES} bytes; split the job")
    p = run(
        ["agy", "--model", model, "--mode", "plan", "--print-timeout", timeout,
         f"--print={brief}"],
        stdin=subprocess.DEVNULL, cwd=cwd,
    )
    out = p.stdout.strip()
    if p.returncode != 0 or "jetski: no output produced" in (out + p.stderr):
        sys.exit(f"agy failed (exit {p.returncode}): {(out + p.stderr)[:500]}")
    if not out:
        sys.exit("agy returned empty output; treat as failure, not clean")
    status = run(["git", "status", "--porcelain"], cwd=cwd)
    if status.returncode != 0:
        sys.exit(f"git status failed in {cwd}: {status.stderr.strip()}")
    if status.stdout.strip():
        sys.exit(f"agy edited the checkout despite --mode plan:\n{status.stdout}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("brief", "review"):
        s = sub.add_parser(name)
        s.add_argument("--model", default=DEFAULT_MODEL)
        s.add_argument("--timeout", default="8m")
        s.add_argument("--cwd", default=".", help="scratch checkout that cannot push")
    sub.choices["brief"].add_argument("--brief-file", required=True)
    sub.choices["review"].add_argument("repo", help="owner/name")
    sub.choices["review"].add_argument("pr", type=int)
    a = ap.parse_args()

    if a.cmd == "brief":
        brief = Path(a.brief_file).read_text(encoding="utf-8")
        print(dispatch(brief, a.model, a.timeout, a.cwd))
        return

    meta = run(["gh", "pr", "view", str(a.pr), "-R", a.repo, "--json",
                "headRefOid,title"])
    if meta.returncode:
        sys.exit(meta.stderr)
    import json
    m = json.loads(meta.stdout)
    diff = run(["gh", "pr", "diff", str(a.pr), "-R", a.repo])
    if diff.returncode:
        sys.exit(diff.stderr)
    brief = REVIEW_PREAMBLE.format(repo=a.repo, pr=a.pr, sha=m["headRefOid"],
                                   title=m["title"], diff=diff.stdout)
    out = dispatch(brief, a.model, a.timeout, a.cwd)
    sha = m["headRefOid"]
    lines = out.splitlines()
    last = lines[-1].strip("`* ")
    if last.startswith("Verdict:"):
        out = chr(10).join(lines[:-1]).rstrip()
    # A one-line clean verdict is not a review.
    clean = last == "Verdict: Clean" and bool(out.strip())
    verdict = "Clean" if clean else "Needs more work"
    print(f"## Cross-harness review (Antigravity agy CLI) of {sha}\n\n"
          f"Reviewed-Commit: {sha}\n\n{out}\n\n### Verdict\n\n"
          f"Verdict: {verdict}\n\n{FOOTER}")


if __name__ == "__main__":
    main()
