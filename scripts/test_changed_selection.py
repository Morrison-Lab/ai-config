#!/usr/bin/env python3
"""Tests for scripts/lib/changed_selection.py (ai-config#5087)."""
import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib.changed_selection import Selector  # noqa: E402


passes = failures = 0


def check(name, cond):
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name}")


FILES = {
    "hooks/guard.py": "import helper, pkg\nCONFIG = 'rules.json'\nSIBLING = 'sibling.py'\n",
    "hooks/test-guard.py": "# runs hooks/guard.py and reads notes.txt.\n# reads .guardrc\n",
    "hooks/sibling.py": "FAR = 'hooks/far.py'  # a sibling loaded by path, as _sibling() does\n",
    "hooks/far.py": "\n",
    "hooks/notes.txt": "\n",
    "hooks/.guardrc": "\n",
    "hooks/pkg/__init__.py": "\n",
    "hooks/helper.py": "import deep_helper\n",
    "hooks/deep_helper.py": "import deeper  # names other-tool.py in a comment\n",
    "hooks/deeper.py": "\n",
    "hooks/other-tool.py": "# never imported\n",
    "hooks/rules.json": "{}\n",
    "hooks/unrelated.py": "\n",
    "hooks/stale.py": "\n",
    "hooks/broken.py": "def (\n",
    "hooks/uses_broken.py": "import broken\n",
    "hooks/nul.py": "x = 1\0\n",
    "hooks/run.sh": "cat shellcfg.txt\n",
    "hooks/shellcfg.txt": "\n",
    "scripts/lib/shared.py": "\n",
    "hooks/hooks.json": "{}\n",
    "scripts/test_hooks.py": "\n",
    "scripts/run-local-validation.py": "\n",
    ".github/workflows/validate.yml": "\n",
    "AGENTS.md": "# names guard.py, which a markdown file cannot pull in\n",
    ".gitignore": "*.log\n",
}


def _repo(tmp):
    root = Path(tmp)
    for rel, text in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}  # never an outer repo
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    (root / "hooks" / "brand-new.py").write_text("\n", encoding="utf-8")  # untracked
    (root / "hooks" / "ignored.log").write_text("\n", encoding="utf-8")  # untracked and ignored
    (root / "hooks" / "stale.py").unlink()  # tracked, deleted without git rm
    return root


def test_selector():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = _repo(tmp)
        sel = Selector(root)
        seeds = ["hooks/test-guard.py", "hooks/guard.py"]
        check("a change to the subject selects the suite", sel.needed(seeds, ["hooks/guard.py"]))
        check("a change to the test selects the suite", sel.needed(seeds, ["hooks/test-guard.py"]))
        check("a change to an imported module selects it", sel.needed(seeds, ["hooks/helper.py"]))
        check("imports are followed transitively", sel.needed(seeds, ["hooks/deeper.py"]))
        check("an imported package's __init__.py selects it", sel.needed(seeds, ["hooks/pkg/__init__.py"]))
        check("a data file the subject names selects it", sel.needed(seeds, ["hooks/rules.json"]))
        check("a name ending a sentence still matches", sel.needed(seeds, ["hooks/notes.txt"]))
        check("a dotfile name matches", sel.needed(seeds, ["hooks/.guardrc"]))
        check("siblings loaded by path are followed like imports", sel.needed(seeds, ["hooks/far.py"]))
        check("a deleted path selects every suite", sel.needed(seeds, ["hooks/gone.py"]))
        check("a deletion not yet staged selects every suite", sel.needed(seeds, ["hooks/stale.py"]))
        check("an unrelated change does not select it (negative control)",
              not sel.needed(seeds, ["hooks/unrelated.py"]))
        check("a name an imported (non-seed) module mentions is not followed",
              not sel.needed(seeds, ["hooks/other-tool.py"]))
        check("a markdown file naming the subject does not select it", not sel.needed(seeds, ["AGENTS.md"]))
        for shared in ("scripts/lib/shared.py", "hooks/hooks.json", "scripts/test_hooks.py",
                       "scripts/run-local-validation.py", ".github/workflows/validate.yml"):
            check(f"a change to {shared} selects every suite", sel.needed(seeds, [shared]))
        err = io.StringIO()
        with redirect_stderr(err):
            check("a suite reaching an unparsable file always runs, and says so",
                  sel.needed(["hooks/broken.py"], ["hooks/unrelated.py"]) and "hooks/broken.py" in err.getvalue())
            check("so does a suite importing one", sel.needed(["hooks/uses_broken.py"], ["hooks/unrelated.py"]))
            check("a file with a NUL byte counts as unparsable", sel.needed(["hooks/nul.py"], ["hooks/unrelated.py"]))
        check("a shell seed's mentions are read", sel.needed(["hooks/run.sh"], ["hooks/shellcfg.txt"])
              and not sel.needed(["hooks/run.sh"], ["hooks/unrelated.py"]))
        check("scripts/lib without its slash selects every suite", sel.needed(seeds, ["scripts/lib"]))
        for var in ("GIT_DIR", "GIT_COMMON_DIR"):
            old = os.environ.get(var)
            os.environ[var] = str(root / "no-such-git-dir")
            try:
                check(f"a caller's {var} does not redirect git", "hooks/helper.py" in Selector(root).files)
            finally:
                os.environ.pop(var)
                if old is not None:
                    os.environ[var] = old
        check("untracked, non-ignored files are indexed", "hooks/brand-new.py" in sel.files)
        check("ignored files are not indexed", "hooks/ignored.log" not in sel.files)
        check("./ and a/../ spellings are normalised", sel.needed(seeds, ["./hooks/pkg/../helper.py"])
              and not sel.needed(seeds, ["./hooks/unrelated.py"]))
        check("one matching path among several selects it",
              sel.needed(seeds, ["hooks/unrelated.py", "hooks/helper.py"]))
        check("one deleted path among several selects it", sel.needed(seeds, ["hooks/unrelated.py", "hooks/gone.py"]))
        check("several unrelated paths do not (negative control)",
              not sel.needed(seeds, ["hooks/unrelated.py", "AGENTS.md"]))
        for bad in ([], [""], ["."], ["/etc/passwd"], ["../elsewhere.py"]):
            try:
                sel.needed(seeds, bad)
                check(f"a changed list of {bad} is refused", False)
            except ValueError:
                check(f"a changed list of {bad} is refused", True)


def test_live_tree():
    """A hook two path-loads away from a suite's subject still selects it."""
    sel = Selector(HERE.parent)
    seeds = ["hooks/test-flag-blocker-without-retry.py", "hooks/flag-blocker-without-retry.py"]
    used = seeds + ["hooks/no-unfiled-finding.py", "hooks/no-fable-subagent.py"]
    check("live: every path these checks use exists", set(used) <= set(sel.files))
    check("live: a sibling's sibling selects the suite", sel.needed(seeds, ["hooks/no-unfiled-finding.py"]))
    check("live: an unrelated hook does not (negative control)",
          not sel.needed(seeds, ["hooks/no-fable-subagent.py"]))


def main():
    for test in (test_selector, test_live_tree):
        print(f"running {test.__name__}()", flush=True)
        test()
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
