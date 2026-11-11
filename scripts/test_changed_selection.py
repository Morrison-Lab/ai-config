#!/usr/bin/env python3
"""Tests for scripts/lib/changed_selection.py and its use in scripts/test_hooks.py (ai-config#5087)."""
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib.changed_selection import Selector  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
    "hooks/deep_helper.py": "# imports nothing; names other-tool.py in a comment\n",
    "hooks/other-tool.py": "# never imported\n",
    "hooks/rules.json": "{}\n",
    "hooks/unrelated.py": "\n",
    "hooks/stale.py": "\n",
    "scripts/lib/shared.py": "\n",
    "AGENTS.md": "# names guard.py, which a markdown file cannot pull in\n",
}


def _repo(tmp):
    root = Path(tmp)
    for rel, text in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    (root / "hooks" / "brand-new.py").write_text("\n", encoding="utf-8")  # untracked
    (root / "hooks" / "stale.py").unlink()  # tracked, deleted without git rm
    return root


def test_selector():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = _repo(tmp)
        sel = Selector(root)
        seeds = ["hooks/test-guard.py", "hooks/guard.py"]
        check("a change to the subject selects the suite", sel.needed(seeds, ["hooks/guard.py"]))
        check("a change to an imported module selects it", sel.needed(seeds, ["hooks/helper.py"]))
        check("imports are followed transitively", sel.needed(seeds, ["hooks/deep_helper.py"]))
        check("an imported package's __init__.py selects it", sel.needed(seeds, ["hooks/pkg/__init__.py"]))
        check("a data file the subject names selects it", sel.needed(seeds, ["hooks/rules.json"]))
        check("a name ending a sentence still matches", sel.needed(seeds, ["hooks/notes.txt"]))
        check("a dotfile name matches", sel.needed(seeds, ["hooks/.guardrc"]))
        check("siblings loaded by path are followed like imports", sel.needed(seeds, ["hooks/far.py"]))
        check("a deleted path selects every suite", sel.needed(seeds, ["hooks/gone.py"]))
        check("a deletion not yet staged selects every suite", sel.needed(seeds, ["hooks/stale.py"]))
        check("an unrelated change does not select it (negative control)",
              not sel.needed(seeds, ["hooks/unrelated.py"]))
        check("a name mentioned two levels down is not followed",
              not sel.needed(seeds, ["hooks/other-tool.py"]))
        check("a markdown file naming the subject does not select it", not sel.needed(seeds, ["AGENTS.md"]))
        check("a change under scripts/lib/ selects every suite", sel.needed(seeds, ["scripts/lib/shared.py"]))
        check("untracked, non-ignored files are indexed", "hooks/brand-new.py" in sel.files)


def test_test_hooks_selection():
    """Dogfood on the live tree, and the RLV_CHANGED_FILES entry point in a child process."""
    th = _load("test_hooks_under_test", HERE / "test_hooks.py")
    sys.modules.pop("test_hooks_under_test")
    hooks = HERE.parent / "hooks"
    runnable = [(str(t), str(hooks / (t.name[len("test-"):]))) for t in sorted(hooks.glob("test-*.py"))
                if (hooks / t.name[len("test-"):]).is_file()]
    out = io.StringIO()
    with redirect_stdout(out):
        kept = th.select_for_change(runnable, ["hooks/flag-cop-out-offer.py"])
    names = {Path(t).name for t, _ in kept}
    check("the changed hook's own suite is kept", "test-flag-cop-out-offer.py" in names)
    check("a suite whose subject loads it by path is kept", "test-flag-tool-gap-handling.py" in names)
    check("most suites are dropped and the count is printed",
          len(kept) < len(runnable) / 2 and f"of {len(runnable)} hook suites" in out.getvalue())
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        empty, listing = Path(tmp) / "empty.txt", Path(tmp) / "changed.txt"
        empty.write_text("\n", encoding="utf-8")
        listing.write_text("hooks/flag-cop-out-offer.py\n", encoding="utf-8")
        refused = _run("test_hooks.py", empty)
        check("an empty list is refused, not a vacuous pass",
              refused.returncode != 0 and "empty list" in refused.stderr)
        check("tests driving run_suites() do not inherit the list",
              _run("test_test_hooks.py", listing).returncode == 0)


def _run(script, listing):
    env = {**os.environ, "RLV_CHANGED_FILES": str(listing)}
    return subprocess.run([sys.executable, str(HERE / script)], env=env, capture_output=True, text=True)


def main():
    for test in (test_selector, test_test_hooks_selection):
        print(f"running {test.__name__}()", flush=True)
        test()
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
