#!/usr/bin/env python3
"""Tests for scripts/lib/changed_selection.py and its two callers (ai-config#5087)."""
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
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


passes = 0
failures = 0


def check(name, cond):
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name}")


FILES = {
    "hooks/guard.py": "import helper\nCONFIG = 'rules.json'\n",
    "hooks/test-guard.py": "# runs hooks/guard.py\n",
    "hooks/helper.py": "import deep_helper\n",
    "hooks/deep_helper.py": "# imports nothing; names other-tool.py in a comment\n",
    "hooks/other-tool.py": "# never imported\n",
    "hooks/rules.json": "{}\n",
    "hooks/unrelated.py": "\n",
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
    return root


def test_selector():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = _repo(tmp)
        sel = Selector(root)
        seeds = ["hooks/test-guard.py", "hooks/guard.py"]
        check("a change to the subject selects the suite", sel.needed(seeds, ["hooks/guard.py"]))
        check("a change to an imported module selects it", sel.needed(seeds, ["hooks/helper.py"]))
        check("imports are followed transitively", sel.needed(seeds, ["hooks/deep_helper.py"]))
        check("a data file the subject names selects it", sel.needed(seeds, ["hooks/rules.json"]))
        check("an unrelated change does not select it (negative control)",
              not sel.needed(seeds, ["hooks/unrelated.py"]))
        check("a name mentioned two levels down is not followed",
              not sel.needed(seeds, ["hooks/other-tool.py"]))
        check("a markdown file naming the subject does not select it", not sel.needed(seeds, ["AGENTS.md"]))
        check("a change under scripts/lib/ selects every suite", sel.needed(seeds, ["scripts/lib/shared.py"]))
        check("untracked, non-ignored files are indexed", "hooks/brand-new.py" in sel.files)


def test_test_hooks_selection():
    """Dogfood on the live tree: one hook's change keeps its own suite and drops most others."""
    th = _load("test_hooks_under_test", HERE / "test_hooks.py")
    hooks = HERE.parent / "hooks"
    runnable = [(str(t), str(hooks / (t.name[len("test-"):]))) for t in sorted(hooks.glob("test-*.py"))
                if (hooks / t.name[len("test-"):]).is_file()]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        listing = Path(tmp) / "changed.txt"
        listing.write_text("hooks/flag-cop-out-offer.py\n", encoding="utf-8")
        os.environ["RLV_CHANGED_FILES"] = str(listing)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                kept = th.select_for_change(runnable)
        finally:
            del os.environ["RLV_CHANGED_FILES"]
    names = {Path(t).name for t, _ in kept}
    check("the changed hook's own suite is kept", "test-flag-cop-out-offer.py" in names)
    check("most suites are dropped and the count is printed",
          len(kept) < len(runnable) / 2 and f"of {len(runnable)} hook suites" in out.getvalue()
          and th._SELECTED == len(kept))
    th._SELECTED = None
    check("without RLV_CHANGED_FILES every suite runs", th.select_for_change(runnable) == runnable)


def test_runner_skips_unaffected_suite_steps():
    rlv = _load("run_local_validation_under_test", HERE / "run-local-validation.py")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = _repo(tmp)
        (root / "scripts" / "test_guard.py").write_text("# checks hooks/guard.py\n", encoding="utf-8")
        (root / "scripts" / "test_other.py").write_text("# checks hooks/unrelated.py\n", encoding="utf-8")
        wf = root / "wf.yml"
        wf.write_text("jobs:\n  validate:\n    steps:\n"
                      "      - name: Guard tests\n        run: python3 scripts/test_guard.py\n"
                      "      - name: Other tests\n        run: python3 scripts/test_other.py\n"
                      "      - name: Repo-wide check\n        run: 'true'\n", encoding="utf-8")
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True, env=env)
        (root / "hooks" / "guard.py").write_text("import helper\n# edited\n", encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = rlv.main(["--workflow", str(wf), "--root", str(root), "--changed", "--base", "main",
                           "--no-other-workflows", "--list"])
        text = out.getvalue()
        check("--changed keeps the suite whose subject changed", rc == 0 and "RUN      [validate] Guard tests" in text)
        check("--changed skips a suite none of whose inputs changed, with the reason",
              "SKIP     [validate] Other tests: none of the suite's inputs changed" in text)
        check("a step that is not a single suite always runs", "RUN      [validate] Repo-wide check" in text)


def main():
    for test in (test_selector, test_test_hooks_selection, test_runner_skips_unaffected_suite_steps):
        print(f"running {test.__name__}()", flush=True)
        test()
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
