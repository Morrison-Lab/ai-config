#!/usr/bin/env python3
"""Regression tests for validate-skills.py.

Covers the marketplace plugin-source check -- the interesting behaviour is
the split between the two failure modes: an uninitialized submodule warns
(so a fresh clone can still commit), while any other missing or empty
source path is a hard error -- and the skill-description length guard
added for ai-config#1263 (a description over the cloud marketplace's
1024-char limit passes locally but fails marketplace sync with no useful
error).
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


def run_check_skill(tmpdir: Path, name: str, description: str):
    """Point validate-skills.py's check_skill() at a single fake skill dir.

    Returns the errors collected for that run.
    """
    skill_dir = tmpdir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "{description}"\n---\n\nbody\n',
        encoding="utf-8",
    )
    original_root = vs.ROOT
    vs.ROOT = tmpdir
    vs.errors.clear()
    try:
        vs.check_skill(skill_dir)
        return list(vs.errors)
    finally:
        vs.ROOT = original_root
        vs.errors.clear()


def run_listing_budget(tmpdir: Path, entries: list[tuple[str, str]]):
    """Run the aggregate guard against a synthetic skill catalog.

    Returns (errors, warnings) collected for that run, matching `run_check`
    above. The guard reports over-budget as an error and near-budget as a
    warning, so a caller that could only see one of the two would need a
    second, near-identical harness to reach the other.
    """
    paths = []
    for name, description in entries:
        skill_dir = tmpdir / name
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            f'---\nname: {name}\ndescription: "{description}"\n---\n\nbody\n',
            encoding="utf-8",
        )
        paths.append(skill_md)
    original_root = vs.ROOT
    vs.ROOT = tmpdir
    vs.errors.clear()
    vs.warnings.clear()
    try:
        vs.check_listing_budget(paths, "synthetic/")
        return list(vs.errors), list(vs.warnings)
    finally:
        vs.ROOT = original_root
        vs.errors.clear()
        vs.warnings.clear()



def run_skills_check(tmpdir: Path):
    """Point validate-skills.py at a fake repo root and run check_skills."""
    original_root = vs.ROOT
    vs.ROOT = tmpdir
    vs.errors.clear()
    vs.warnings.clear()
    try:
        vs.check_skills()
        return list(vs.errors), list(vs.warnings)
    finally:
        vs.ROOT = original_root

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

        # ai-config#1263: a description matching the real incident's length
        # (1524 chars) must error, naming the marketplace limit.
        length_dir = tmp / "length"
        errs = run_check_skill(length_dir, "detect-hypothetical-examples", "x" * 1524)
        check(
            "1524-char description (the real #1263 incident length) errors",
            len(errs) == 1 and "over the marketplace" in errs[0],
        )

        # A normal short description must not trip the new check at all --
        # the existing empty-description check must still be the only one
        # that can fire on ordinary content.
        errs = run_check_skill(length_dir, "ok-skill", "A short, fine description.")
        check("short description does not trip the length guard", errs == [])

        # Routing receives the whole installed catalog, not one description at
        # a time. Its budget must therefore be enforced in aggregate.
        check(
            "listing at the context budget is clean",
            vs.listing_chars([("a", "x" * (vs.SKILL_LISTING_BUDGET_CHARS - 9))])
            == vs.SKILL_LISTING_BUDGET_CHARS,
        )
        check(
            "listing over the context budget is detectable",
            vs.listing_chars([("a", "x" * (vs.SKILL_LISTING_BUDGET_CHARS - 8))])
            > vs.SKILL_LISTING_BUDGET_CHARS,
        )
        # Derive the entry count from the cap rather than hard-coding a
        # total that happens to exceed it. A literal 8 entries was 8,120
        # chars: over the old 8,000 cap and under the 9,000 it became in
        # #1853, so this test silently stopped testing what it claims the
        # moment the constant moved, and failed rather than adapting.
        over_budget_count = vs.SKILL_LISTING_BUDGET_CHARS // 1_000 + 1
        entries = [
            (f"skill-{index}", "x" * 1_000) for index in range(over_budget_count)
        ]
        errs, _ = run_listing_budget(tmp / "over-budget", entries)
        check(
            "aggregate listing over the context budget errors",
            len(errs) == 1 and "context budget" in errs[0],
        )

        # The message has to name an offender. Without this the failure lands
        # on whoever adds the next skill and points at nobody, which is the
        # whole complaint in #1702.
        check(
            "over-budget error names its largest consumer",
            len(errs) == 1 and "skill-0" in errs[0],
        )
        check(
            "over-budget error reports the per-entry overhead",
            len(errs) == 1
            and str(len(entries) * vs.LISTING_ENTRY_OVERHEAD_CHARS) in errs[0],
        )

        # Ties must break deterministically, or the reported offenders differ
        # between two runs over the same catalog and read as flapping.
        tied = [("b-skill", "x" * 50), ("a-skill", "x" * 50), ("c-skill", "x" * 50)]
        check(
            "top consumers break ties on name, not dict order",
            [name for _, name in vs.top_listing_consumers(tied)]
            == ["a-skill", "b-skill", "c-skill"],
        )
        check(
            "top consumers are capped at the reported limit",
            len(vs.top_listing_consumers([(f"s{i}", "x" * 10) for i in range(50)]))
            == vs.TOP_CONSUMERS_REPORTED,
        )

        # Warn BEFORE the cap breaks, and only then. The negative control is
        # the second half: a warning that fires on a comfortably-small catalog
        # would be indistinguishable from one that never fires at all.
        near = vs.SKILL_LISTING_BUDGET_CHARS - 40
        _, warns = run_listing_budget(
            tmp / "near-cap", [("near", "x" * (near - 8 - len("near")))]
        )
        check(
            "listing near the cap warns before it breaks",
            len(warns) == 1 and "headroom" in warns[0],
        )
        check(
            "near-cap warning names its largest consumer",
            len(warns) == 1 and "near" in warns[0],
        )
        _, warns = run_listing_budget(
            tmp / "far-from-cap", [("small", "x" * 20)]
        )
        check("listing far below the cap does not warn", warns == [])
        _, warns = run_listing_budget(tmp / "empty-catalog", [])
        check("empty catalog neither warns nor divides by zero", warns == [])

        # Boundary: exactly the limit passes, one character over fails --
        # proves the guard fires on ">", not ">=", the real limit.
        errs = run_check_skill(length_dir, "boundary-at-limit", "x" * vs.MARKETPLACE_DESCRIPTION_LIMIT)
        check("description at exactly the limit is clean", errs == [])
        errs = run_check_skill(length_dir, "boundary-over-limit", "x" * (vs.MARKETPLACE_DESCRIPTION_LIMIT + 1))
        check(
            "description one char over the limit errors",
            len(errs) == 1 and "over the marketplace" in errs[0],
        )

    # --- skills-directory plugin exemption (ai-config#2004) ---
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        plugin = tmp / "skills" / "hooks-only"
        (plugin / ".claude-plugin").mkdir(parents=True)
        manifest = plugin / ".claude-plugin" / "plugin.json"
        manifest.write_text(
            json.dumps({"name": "hooks-only", "description": "d"}),
            encoding="utf-8",
        )
        errors, _ = run_skills_check(tmp)
        check("skills-dir plugin without SKILL.md is not an error", errors == [])

        manifest.write_text(
            json.dumps({"name": "other", "description": "d"}), encoding="utf-8"
        )
        errors, _ = run_skills_check(tmp)
        check(
            "skills-dir plugin whose name != directory is an error",
            any("!= directory" in e for e in errors),
        )

        manifest.write_text(
            json.dumps({"name": "hooks-only", "description": "d"}),
            encoding="utf-8",
        )
        (tmp / "skills" / "bare").mkdir()
        errors, _ = run_skills_check(tmp)
        check(
            "skill dir with neither SKILL.md nor manifest is still an error",
            any("no SKILL.md" in e for e in errors),
        )


    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
