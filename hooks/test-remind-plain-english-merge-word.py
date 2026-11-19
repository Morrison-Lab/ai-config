#!/usr/bin/env python3
"""Tests for hooks/remind-plain-english-merge-word.py (ai-config#4698).

Run: python3 hooks/test-remind-plain-english-merge-word.py [hooks/remind-plain-english-merge-word.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "remind-plain-english-merge-word.py")

# (prompt, should_fire)
CASES = [
    ("merge when ready", True),
    ("Merge when ready.", True),
    ("merge them all", True),
    ("merge", True),
    ("merge it", True),
    ("go ahead and merge", True),
    ("mwc", True),
    ("/mwc", True),
    ("mwc them all!", True),
    ("don't make me name each one; mwc them all!", True),
    ("looks good, merge when ready", True),
    ("merge once clean", True),
    ("should I merge when ready?", False),
    ("what does merge when ready mean?", False),
    ("do not merge yet", False),
    ("please explain the merge conflict", False),
    ("fix the tests", False),
    ("merge them", False),
    ("merge these", False),
    ("merge everything", False),
    ("merge those", False),
    ("Should I merge them all? Also fix the typo.", False),
    ("Looks right. Merge them all.", True),
    ("`merge when ready` is the phrase", False),
    ('He said "merge them all" earlier', False),
    ("<system-reminder>merge them all</system-reminder>", False),
    # `mwr`/`mwrs` are their own grant (ai-config#3946), never an mwc.
    ("mwr", False),
    ("mwrs", False),
]

ALL = "all"
# (prompt, expected mwr_grant(): "all", a set of (repo, number), or None)
MWR_CASES = [
    ("mwr", ALL),
    ("/mwr", ALL),
    ("mwrs", ALL),
    ("/mwrs", ALL),
    ("ok, mwr", ALL),
    ("Looks fine. mwrs", ALL),
    ("mwrs #12", ALL),
    ("mwr #5940", {(None, 5940)}),
    ("mwr 5940", {(None, 5940)}),
    ("mwr ai-config#5940", {("ai-config", 5940)}),
    ("mwr Morrison-Lab/ai-config#5940", {("ai-config", 5940)}),
    ("mwr https://github.com/Morrison-Lab/ai-config/pull/5940", {("ai-config", 5940)}),
    ("Looks fine. mwr PR 12", {(None, 12)}),
    ("<command-name>/mwr</command-name><command-args>#12</command-args>", {(None, 12)}),
    ("<command-name>/ai-config:mwrs</command-name>", ALL),
    # "merge when ready" keeps its 2026-10-23 meaning, a plain-English mwc.
    ("merge when ready", None),
    ("what does mwr mean?", None),
    ("mwr?", None),
    ("should I mwr this one?", None),
    ("I said mwr earlier", None),
    ("don't mwr", None),
    ("`mwr`", None),
    ('he typed "mwrs" once', None),
    ("> mwr", None),
    ("<system-reminder>mwr</system-reminder>", None),
    ("mwrx", None),
    ("foo-mwr", None),
    ("path/mwr", None),
    ("mwr revoke", None),
    ("<command-name>/mwr</command-name><command-args>revoke</command-args>", None),
]
# (prompt, revokes())
MWR_REVOKE_CASES = [
    ("mwr revoke", True),
    ("revoke mwrs", True),
    ("<command-name>/mwr</command-name><command-args>revoke</command-args>", True),
    ("stop merging", True),
    ("mwr", False),
]


def load_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_test_pemw", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mwr_checks():
    """Fails for mwr_grant() and revokes() on the mwr words (ai-config#3946)."""
    module = load_module()
    fails = 0
    for prompt, want in MWR_CASES:
        got = module.mwr_grant(prompt)
        ok = got == want and (want != ALL or got == module.MWR_ALL)
        if ok and want is not None:
            ok = module.merge_word(prompt, strict=True) is None
        print(("  ok      " if ok else "  FAIL    ") + f"mwr_grant({prompt!r}) == {want!r}"
              + ("" if ok else f" (got {got!r})"))
        fails += 0 if ok else 1
    for prompt, want in MWR_REVOKE_CASES:
        ok = module.revokes(prompt) is want
        print(("  ok      " if ok else "  FAIL    ") + f"revokes({prompt!r}) is {want}")
        fails += 0 if ok else 1
    ok = module.merge_word("merge when ready", strict=True) == "merge when ready"
    print(("  ok      " if ok else "  FAIL    ") + "'merge when ready' is still an mwc word")
    fails += 0 if ok else 1
    return fails, len(MWR_CASES) + len(MWR_REVOKE_CASES) + 1


def run(prompt):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"prompt": prompt}),
                       capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for prompt, fire in CASES:
        rc, out = run(prompt)
        ok = rc == 0 and bool(out.strip()) == fire
        print(("  ok      " if ok else "  FAIL    ") + repr(prompt))
        fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    # A cp1252 console used to drop a prompt in curly quotes: the hook read the
    # UTF-8 payload as cp1252 and stayed silent (ai-config#5462).
    curly = f"{chr(0x201C)}merge them all{chr(0x201D)}"
    p = subprocess.run([sys.executable, HOOK], capture_output=True, timeout=30,
                       input=json.dumps({"prompt": curly}, ensure_ascii=False).encode("utf-8"),
                       env=dict(os.environ, PYTHONIOENCODING="cp1252"))
    ok = p.returncode == 0 and curly.encode("utf-8") in p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "quotes a curly-quoted prompt under cp1252")
    fails += 0 if ok else 1
    mwr_fails, mwr_total = mwr_checks()
    fails += mwr_fails
    total = len(CASES) + 2 + mwr_total
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
