#!/usr/bin/env python3
"""Tests for hooks/no-cross-repo-copy.py, on throwaway git checkouts in a temp dir.

Run: python3 hooks/test-no-cross-repo-copy.py [hooks/no-cross-repo-copy.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-cross-repo-copy.py")
WORKFLOW = "".join(f"      - name: step {i}\n        run: echo running step number {i}\n" for i in range(12))
CALLER = "jobs:\n" + "".join(
    f"  job{i}:\n    uses: Morrison-Lab/gha/.github/workflows/check-{i}.yml@v1\n    secrets: inherit\n"
    for i in range(8))


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def git(*args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                   capture_output=True)


def write(path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def denied(payload):
    p = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True, text=True)
    out = json.loads(p.stdout) if p.stdout else {}
    return p.returncode, out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def main():
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:  # checkouts under vendor/: only in-repo paths are exempt
        lds, mcsg = os.path.join(tmp, "vendor", "lds"), os.path.join(tmp, "vendor", "mcsg")
        for repo in (lds, mcsg):
            git("init", "-q", "-b", "main", repo)
        put(os.path.join(lds, ".github", "workflows", "publish.yml"), WORKFLOW)
        put(os.path.join(lds, ".github", "workflows", "callers.yml"), CALLER)
        for name in ("filter.lua", "notes.md"):
            put(os.path.join(lds, name), WORKFLOW)
        git("-C", lds, "add", "-A")
        git("-C", lds, "commit", "-qm", "x")
        git("-C", lds, "worktree", "add", "-q", os.path.join(lds, ".claude", "wt"))
        put(os.path.join(mcsg, "old", "publish.yml"), "name: old\n")
        put(os.path.join(mcsg, "README"), "x\n")
        git("-C", mcsg, "add", "-A")
        git("-C", mcsg, "commit", "-qm", "x")
        git("-C", mcsg, "worktree", "add", "-q", os.path.join(mcsg, ".claude", "wt"))
        dst = os.path.join(mcsg, ".github", "workflows", "publish.yml")
        wt_dst = os.path.join(mcsg, ".claude", "wt", ".github", "workflows", "publish.yml")
        cases = [
            (write(dst, WORKFLOW), True, "a verbatim copy of a sibling repo's file"),
            (write(dst, WORKFLOW.replace("step 3", "step three")), True, "a lightly edited copy"),
            (write(wt_dst, WORKFLOW), True, "a copy written from a linked worktree"),
            (write(os.path.join(lds, ".claude", "wt", "x", "publish.yml"), WORKFLOW), False,
             "a worktree of the same repository is not another repository"),
            (write(os.path.join(mcsg, "other.yml"), WORKFLOW), False, "another name is not judged"),
            (write(os.path.join(mcsg, "old", "publish.yml"), WORKFLOW), False, "a Write over an existing file"),
            (write(dst, "name: x\non: push\n"), False, "a short file is not judged"),
            (write(dst, "# decompose: allow differs per repo\n" + WORKFLOW), False, "the allow comment passes"),
            (write(dst, "name: decompose: allow x\n" + WORKFLOW), True, "the marker outside a comment"),
            (write(os.path.join(mcsg, "filter.lua"), "-- decompose: allow port\n" + WORKFLOW), False,
             "a Lua line comment carries the marker"),
            (write(os.path.join(mcsg, "notes.md"), "# decompose: allow x\n" + WORKFLOW), True,
             "a Markdown heading is not a comment"),
            (write(os.path.join(mcsg, "notes.md"), "<!-- decompose: allow port -->\n" + WORKFLOW), False,
             "a Markdown HTML comment carries the marker"),
            (write(os.path.join(mcsg, ".github", "workflows", "callers.yml"), CALLER), False,
             "a thin gha caller is the decomposed form"),
            (write(os.path.join(mcsg, ".github", "workflows", "callers.yml"),
                   CALLER + "  own:\n    steps:\n      - uses: actions/checkout@v4\n"), True,
             "a caller that also runs its own steps"),
            (write(os.path.join(mcsg, "_extensions", "publish.yml"), WORKFLOW), False, "a vendored path"),
            (write(os.path.join(lds, "x", "publish.yml"), WORKFLOW), False, "a copy within one repository"),
            ({"tool_name": "Edit", "tool_input": {"file_path": dst}}, False, "Edit is not judged"),
        ]
        for payload, block, label in cases:
            rc, blocked = denied(json.dumps(payload))
            ok = rc == 0 and blocked == block
            print(("  ok      " if ok else "  FAIL    ") + label)
            fails += 0 if ok else 1
    rc, blocked = denied("not json")
    ok = rc == 0 and not blocked
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    print(f"\n{len(cases) + 1 - fails}/{len(cases) + 1} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
