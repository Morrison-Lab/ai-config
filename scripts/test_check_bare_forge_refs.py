#!/usr/bin/env python3
"""Tests for check-bare-forge-refs.py (ai-config#5132).

The negative control is the first case: a branch that adds a bare `pds#364`
must exit 1.  Without it, a zero from the checker proves nothing.
"""
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "check-bare-forge-refs.py")
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
failures = 0


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=ENV)


def branch_adding(added, base_text="old [pds#1](https://x.test/1) and bare pds#2\n"):
    """A repo whose branch appends `added` to doc.md; returns (dir, exit code, stdout)."""
    d = tempfile.mkdtemp()
    git(d, "init", "-q", "-b", "main")
    with open(os.path.join(d, "doc.md"), "w", encoding="utf-8") as f:
        f.write(base_text)
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "base")
    git(d, "switch", "-q", "-c", "feature")
    with open(os.path.join(d, "doc.md"), "a", encoding="utf-8") as f:
        f.write(added)
    git(d, "commit", "-qam", "change")
    p = subprocess.run([sys.executable, SCRIPT, "main"], cwd=d, capture_output=True,
                       text=True, encoding="utf-8")
    return p.returncode, p.stdout


def check(label, ok):
    global failures
    print(("  ok      " if ok else "  FAIL    ") + label)
    failures += 0 if ok else 1


def main():
    rc, out = branch_adding("Seen on pds#364 today.\n")
    check("bare repo#N on an added line fails", rc == 1 and "pds#364" in out)
    rc, out = branch_adding("Seen on Morrison-Lab/pds#364 today.\n")
    check("bare owner/repo#N fails", rc == 1)
    rc, _ = branch_adding("Seen on [pds#364](https://github.com/Morrison-Lab/pds/pull/364).\n")
    check("a linked reference passes", rc == 0)
    rc, _ = branch_adding("Write `pds#364` as a link.\n")
    check("a reference in a code span passes", rc == 0)
    rc, _ = branch_adding("```\npds#364\n```\n")
    check("a reference in a fenced block passes", rc == 0)
    rc, _ = branch_adding("See https://github.com/Morrison-Lab/pds/pull/364#issuecomment-1 now.\n")
    check("a URL with a fragment passes", rc == 0)
    rc, _ = branch_adding("Seen on pds#364 <!-- bare-ref: allow -->\n")
    check("the allow marker exempts a line", rc == 0)
    rc, _ = branch_adding("intro\n<!--\nSeen on pds#364 in a comment\n-->\noutro\n")
    check("a reference inside a multi-line HTML comment passes", rc == 0)
    rc, _ = branch_adding("The pre-#2085 reformatter and v1.2.3#4 differ.\n")
    check("pre-#N and v1.2.3#4 are not gating", rc == 0)
    rc, out = branch_adding("Closes #5132 here.\n")
    check("a bare #N is advisory, exit 0", rc == 0 and "advisory" in out)
    rc, out = branch_adding("Plain prose.\n")
    check("a clean branch passes and reports its scope", rc == 0 and "1 added line" in out)
    rc, _ = branch_adding("Plain prose.\n", base_text="old bare pds#2 stays\n")
    check("an old bare reference on an unchanged line is not flagged", rc == 0)
    d = tempfile.mkdtemp()
    p = subprocess.run([sys.executable, SCRIPT, "nosuchref"], cwd=d, capture_output=True, text=True)
    check("an unusable base fails loudly", p.returncode == 1)
    print(f"\n{'FAIL' if failures else 'all ok'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
