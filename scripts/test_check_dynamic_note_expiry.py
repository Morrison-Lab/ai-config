#!/usr/bin/env python3
"""Tests for scripts/check-dynamic-note-expiry.py (ai-config#5018).

Run: python3 scripts/test_check_dynamic_note_expiry.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-dynamic-note-expiry.py"
spec = importlib.util.spec_from_file_location("cdne", SCRIPT)
cdne = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cdne)

FAILS = []


def check(name, got, want):
    ok = got == want
    print(("  ok      " if ok else "  FAIL    ") + name)
    if not ok:
        print(f"          got {got!r}, want {want!r}")
        FAILS.append(name)


def flagged(text, changed=None):
    return bool(cdne.violations(text.splitlines(), changed))


CLAIM = "- OpenCode quota is currently exhausted."
CASES = [
    ("undated state claim is flagged", CLAIM, True),
    ("dated state claim passes", CLAIM + " expires 2026-11-13", False),
    ("expires: form passes", CLAIM + " (expires: 2026-11-13)", False),
    ("allow marker passes", CLAIM + " <!-- dynamic-note: allow -->", False),
    ("malformed date is flagged", CLAIM + " expires soon", True),
    ("agy runner is down", "- The cf463-02 runner is down.", True),
    ("right now form", "- Right now the cluster is unreachable.", True),
    ("conditional is a mechanism", "- When the quota is exhausted, switch routes.", False),
    ("instruction is a mechanism", "- Diagnose a runner that is down by reading logs.", False),
    ("reviewer is a resource", "- The cross-harness reviewer is currently unavailable.", True),
    ("past tense is history, not a claim", "- GitHub Pages was unavailable on a private fork.", False),
    ("no resource is no claim", "- The cafeteria is unavailable.", False),
    ("plural runners", "- All self-hosted runners are currently offline.", True),
    ("plural clusters", "- Both clusters are currently down.", True),
    ("plural quotas", "- Model quotas are currently exhausted.", True),
    ("until is a duration, not a mechanism", "- OpenCode quota is currently exhausted until Monday.", True),
    ("while is a duration, not a mechanism", "- The cf463-02 runner is down while maintenance finishes.", True),
    ("quoted example is no claim", '- **Don\'t:** read "this reviewer is blocked" as "no review is reachable".', False),
    ("claim outside the quotes still flagged", '- He wrote "see below"; the runner is down.', True),
    ("no state word is no claim", "- The runner handles builds.", False),
    ("wrapped bullet is one unit", "- Quota note:\n  agy is currently exhausted.", True),
    ("wrapped bullet date on 2nd line", "- Quota note:\n  agy is currently exhausted. expires 2026-11-13", False),
    ("claim in second sentence", "- Background. The runner is offline.", True),
    ("empty text", "", False),
]


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def main():
    for name, text, want in CASES:
        check(name, flagged(text), want)

    # Diff scoping: only a unit holding a changed line is checked.
    text = "- Old: agy is currently exhausted.\n\n- New note about nothing.\n"
    check("unchanged claim not reflagged", flagged(text, {3}), False)
    check("changed claim flagged", flagged(text, {1}), True)

    # End to end in a scratch repo, with negative controls.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        git(root, "init", "-q", "-b", "main")
        git(root, "config", "user.email", "t@example.com")
        git(root, "config", "user.name", "t")
        mem = root / "memories"
        mem.mkdir()
        note = mem / "n.md"
        note.write_text("- Old: agy is currently exhausted.\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "base")
        git(root, "checkout", "-qb", "work")
        cdne.REPO = root

        def run(*argv):
            return cdne.main(list(argv))

        note.write_text("- Old: agy is currently exhausted.\n\n- Fine note.\n", encoding="utf-8")
        git(root, "commit", "-qam", "touch other unit")
        check("untouched old claim passes in diff mode", run("--base", "main"), 0)
        check("--all still finds the old claim", run("--all"), 1)

        note.write_text(note.read_text(encoding="utf-8") + "\n- The cf463-02 runner is down.\n", encoding="utf-8")
        git(root, "commit", "-qam", "add claim")
        check("new undated claim fails in diff mode", run("--base", "main"), 1)

        note.write_text(note.read_text(encoding="utf-8").replace("is down.", "is down. expires 2026-11-13"), encoding="utf-8")
        git(root, "commit", "-qam", "date it")
        check("dated claim passes in diff mode", run("--base", "main"), 0)

        check("bad base ref is an error", run("--base", "nonexistent-ref"), 2)

        note.unlink()
        git(root, "commit", "-qam", "remove")
        mem.rmdir() if not any(mem.iterdir()) else None
        check("empty search space exits 2", run("--all"), 2)

    total = len(CASES) + 2 + 6
    print(f"\n{total - len(FAILS)}/{total} correct")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
