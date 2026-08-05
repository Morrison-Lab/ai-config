#!/usr/bin/env python3
"""Regression tests for validate-skills.py's marketplace plugin-source check.

The interesting behaviour is the split between the two failure modes: an
uninitialized submodule warns (so a fresh clone can still commit), while any
other missing or empty source path is a hard error.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "vs", Path(__file__).parent / "validate-skills.py"
)
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def run_check(tmpdir: Path, plugins: list, gitmodules: str | None = None):
    """Point validate-skills.py at a fake repo root and run the source check.

    Returns (errors, warnings) collected for that run.
    """
    manifest = tmpdir / ".claude-plugin"
    manifest.mkdir(parents=True, exist_ok=True)
    (manifest / "marketplace.json").write_text(
        json.dumps({"name": "t", "owner": {"name": "t"}, "plugins": plugins}),
        encoding="utf-8",
    )
    if gitmodules is not None:
        (tmpdir / ".gitmodules").write_text(gitmodules, encoding="utf-8")

    original_root = vs.ROOT
    vs.ROOT = tmpdir
    vs.errors.clear()
    vs.warnings.clear()
    try:
        vs.check_plugin_sources(".claude-plugin/marketplace.json")
        return list(vs.errors), list(vs.warnings)
    finally:
        vs.ROOT = original_root
        vs.errors.clear()
        vs.warnings.clear()


GITMODULES = '[submodule "shared/sub"]\n\tpath = shared/sub\n\turl = https://example.invalid/x.git\n'


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        # A populated source directory is clean.
        populated = tmp / "populated"
        (populated / "shared" / "sub").mkdir(parents=True)
        (populated / "shared" / "sub" / "SKILL.md").write_text("x", encoding="utf-8")
        errs, warns = run_check(
            populated,
            [{"name": "sub", "source": "./shared/sub"}],
            GITMODULES,
        )
        check("populated submodule source is clean", errs == [] and warns == [])

        # An empty directory registered in .gitmodules warns, naming the fix.
        uninit = tmp / "uninit"
        (uninit / "shared" / "sub").mkdir(parents=True)
        errs, warns = run_check(
            uninit,
            [{"name": "sub", "source": "./shared/sub"}],
            GITMODULES,
        )
        check("uninitialized submodule warns, does not error", errs == [] and len(warns) == 1)
        check(
            "warning names the remediation command",
            warns and "git submodule update --init -- shared/sub" in warns[0],
        )

        # The same empty directory with no .gitmodules entry is an error.
        empty = tmp / "empty"
        (empty / "shared" / "sub").mkdir(parents=True)
        errs, warns = run_check(empty, [{"name": "sub", "source": "./shared/sub"}])
        check("empty non-submodule source errors", len(errs) == 1 and warns == [])

        # A source path that does not exist at all is an error.
        missing = tmp / "missing"
        missing.mkdir()
        errs, warns = run_check(missing, [{"name": "gone", "source": "./nowhere"}])
        check("absent source path errors", len(errs) == 1 and warns == [])

        # The repo-root source every marketplace has is always clean.
        root_source = tmp / "root_source"
        root_source.mkdir()
        errs, warns = run_check(root_source, [{"name": "self", "source": "./"}])
        check("repo-root source is clean", errs == [] and warns == [])

        # An unreadable source directory reports the cause, not a traceback.
        # Whether mode 000 actually denies a read depends on the environment
        # (root ignores it, and Windows does not enforce it), so ask rather
        # than assume -- a silent pass here would mean nothing was exercised.
        unreadable = tmp / "unreadable"
        locked = unreadable / "shared" / "sub"
        locked.mkdir(parents=True)
        locked.chmod(0o000)
        try:
            try:
                any(locked.iterdir())
                enforced = False
            except PermissionError:
                enforced = True
            if enforced:
                errs, warns = run_check(
                    unreadable,
                    [{"name": "sub", "source": "./shared/sub"}],
                    GITMODULES,
                )
                check(
                    "unreadable source errors, naming readability",
                    len(errs) == 1 and "not readable" in errs[0],
                )
            else:
                print("SKIP: unreadable source errors (mode 000 is not enforced here)")
        finally:
            locked.chmod(0o700)

        # Malformed entries fail loudly rather than being skipped.
        errs, warns = run_check(root_source, [{"name": "no-source"}])
        check("plugin without a source errors", len(errs) == 1)
        errs, warns = run_check(root_source, ["not-an-object"])
        check("non-object plugin entry errors", len(errs) == 1)

        # Allowlisted non-operation tokens (e.g. GEMINI_API_KEY) are recognized.
        check("NON_OPERATION_TOKENS contains GEMINI_API_KEY", "GEMINI_API_KEY" in vs.NON_OPERATION_TOKENS)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
