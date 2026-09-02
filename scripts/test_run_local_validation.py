#!/usr/bin/env python3
"""Tests for scripts/run-local-validation.py (Morrison-Lab/ai-config#1940, #1262)."""
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

SCRIPT = Path(__file__).parent / "run-local-validation.py"
spec = importlib.util.spec_from_file_location("run_local_validation", SCRIPT)
rlv = importlib.util.module_from_spec(spec)
# Registered before exec: the script uses dataclasses under
# `from __future__ import annotations`, and dataclasses resolves the
# module's namespace through sys.modules.
sys.modules[spec.name] = rlv
spec.loader.exec_module(rlv)

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


FIXTURE = """
name: validate
on: [push]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@abc
      - name: Install dependencies
        run: pip install pyyaml
      - name: Passing step
        run: exit 0
      - name: Failing step
        env:
          RC: "3"
        run: exit "$RC"
      - name: Multi-line step
        run: |
          echo one
          echo two > "$OUT_FILE"
      - name: Runner-only step
        run: echo "${{ github.event.pull_request.base.sha }}"
      - name: Sub-directory step
        working-directory: sub
        run: test "$(basename "$PWD")" = sub
      - name: Token-env step
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: echo "$GITHUB_TOKEN"
  new-line-breaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@abc
      - name: Check new markdown lines
        uses: Morrison-Lab/gha/check-new-line-breaks@deadbeef
        with:
          globs: '*.md *.qmd'
          paths-ignore: 'codex-skills/**,docs/**'
          fail: 'true'
  lint-markdown:
    uses: Morrison-Lab/gha/.github/workflows/lint-markdown.yml@v2
    with:
      config-file: '.markdownlint-cli2.jsonc'
  lint-qmd:
    uses: Morrison-Lab/gha/.github/workflows/lint-qmd.yml@v2
  workflow:
    uses: Morrison-Lab/gha/.github/workflows/lint-qmd.yml@v2
"""


def _write_fixture(tmp):
    wf = Path(tmp) / "validate.yml"
    wf.write_text(FIXTURE, encoding="utf-8")
    (Path(tmp) / "sub").mkdir()
    return wf


SIBLING = """
name: review
on:
  pull_request:
    types: [opened, synchronize]
  workflow_dispatch:
jobs:
  review:
    uses: Morrison-Lab/gha/.github/workflows/claude-review.yml@v2
"""


def test_other_workflow_files():
    """#1881: every other workflow file beside the target is listed as NOT RUN
    with its triggers, so a check living outside validate.yml is visible in
    the denominator rather than silently absent from it."""
    with tempfile.TemporaryDirectory() as tmp:
        wf = _write_fixture(tmp)
        (Path(tmp) / "review.yml").write_text(SIBLING, encoding="utf-8")
        (Path(tmp) / "broken.yaml").write_text("jobs: [unclosed", encoding="utf-8")
        sib = rlv.other_workflow_files(wf)
        names = [s.name for s in sib]
        check("other_workflow_files lists every other workflow file and never the target",
              names == ["broken.yaml", "review.yml"])
        check("every other file is NOT RUN, sourced as [workflow], kind workflow-file",
              all(not s.runnable and s.source == "workflow" and s.kind == "workflow-file" for s in sib))
        review = next(s for s in sib if s.name == "review.yml")
        check("an other file's note names its on: triggers",
              "pull_request" in review.note and "workflow_dispatch" in review.note)
        broken = next(s for s in sib if s.name == "broken.yaml")
        check("an unparseable other file is listed with the parse error rather than dropped",
              "could not be parsed" in broken.note and broken.broken)
        # PyYAML reads a bare `on:` key as True; the trigger reader must see it.
        check("_triggers reads the YAML-1.1 True spelling of on:",
              rlv._triggers({True: ["push", "pull_request"]}) == "push, pull_request")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = rlv.main(["--workflow", str(wf), "--list", "--root", tmp])
        text = out.getvalue()
        check("--list prints the other file as NOT RUN [workflow]",
              rc == 0 and "NOT RUN  [workflow] review.yml: other workflow file, not derived (on: pull_request, workflow_dispatch)" in text)
        check("--list tally counts the other files apart from the derived steps",
              "plus 2 other workflow file(s) listed as NOT RUN" in text and "step(s) derived from" in text)
        out = io.StringIO()
        with redirect_stdout(out):
            rlv.main(["--workflow", str(wf), "--list", "--no-other-workflows", "--root", tmp])
        check("--no-other-workflows drops them and the tally has no plus clause",
              "review.yml" not in out.getvalue() and "plus" not in out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            rlv.main(["--workflow", str(wf), "--list", "--only", "workflow", "--root", tmp])
        check("a job whose ID is literally `workflow` is filtered like any derived step, not as a file notice",
              "NOT RUN  [workflow] workflow:" in out.getvalue() and "plus 2 other" in out.getvalue())
        check("--list tags an unparseable other file BROKEN", "BROKEN   [workflow] broken.yaml" in text)
        check("_denominator with no other files is the plain derived count",
              rlv._denominator(5, 0, "w.yml") == "5 step(s) derived from w.yml")
        out = io.StringIO()
        with redirect_stdout(out):
            rlv.main(["--workflow", str(wf), "--list", "--only", "Passing", "--skip", "review", "--root", tmp])
        text = out.getvalue()
        check("--only keeps the other-workflow notices in the denominator",
              "NOT RUN  [workflow] review.yml" in text and "plus 2 other workflow file(s)" in text)
        check("--skip never marks an other-workflow notice SKIP",
              "SKIP     [workflow]" not in text)
        # Run mode builds its tally separately from --list, so pin it too.
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = rlv.main(["--workflow", str(wf), "--only", "Passing", "--root", tmp])
        text = out.getvalue()
        check("run-mode tally counts the other files apart from the derived steps",
              "plus 2 other workflow file(s) listed as NOT RUN" in text
              and "1 step(s) derived from" in text)
        check("run mode exits 1 while an other workflow file is unparseable, and names it",
              rc == 1 and "broken: broken.yaml" in text)
        check("run-mode not-run report names the other files",
              "not run: review.yml (other workflow file, not derived (on: pull_request, workflow_dispatch))" in text)


def test_derive_steps():
    import yaml
    steps = rlv.derive_steps(yaml.safe_load(FIXTURE), "validate", "origin/main")
    names = [s.name for s in steps]
    check("run: steps derived in file order, uses:-only checkout dropped",
          names[:7] == ["Install dependencies", "Passing step", "Failing step", "Multi-line step",
                        "Runner-only step", "Sub-directory step", "Token-env step"])
    by = {s.name: s for s in steps}
    check("step env carried", by["Failing step"].env == {"RC": "3"})
    check("multi-line run kept whole", by["Multi-line step"].command == 'echo one\necho two > "$OUT_FILE"')
    check("working-directory carried", by["Sub-directory step"].cwd == "sub")
    check("a ${{ ... }} step is not runnable and the note names the expression that matched",
          not by["Runner-only step"].runnable
          and "${{ github.event.pull_request.base.sha }}" in by["Runner-only step"].note)
    check("new-line-breaks job maps to the vendored script with the job's globs and the base ref",
          by["new-line-breaks"].command.endswith("gha-check-new-line-breaks.py")
          and by["new-line-breaks"].env["NLB_GLOBS"] == "*.md *.qmd"
          and by["new-line-breaks"].env["NLB_BASE_REF"] == "origin/main")
    check("an env value carrying ${{ secrets.* }} is not runnable and the note names that expression, not github.*",
          not by["Token-env step"].runnable and "${{ secrets.GITHUB_TOKEN }}" in by["Token-env step"].note)
    check("new-line-breaks forwards the job's paths-ignore input",
          by["new-line-breaks"].env.get("NLB_PATHS_IGNORE") == "codex-skills/**,docs/**")
    check("lint-markdown is NOT RUN: a markdownlint-only stand-in would report a clean zero for three of the action's four checks",
          not by["lint-markdown"].runnable and "lint-markdown.yml" in by["lint-markdown"].note)
    check("a uses: job with no local equivalent is listed as not runnable",
          not by["lint-qmd"].runnable and "lint-qmd.yml" in by["lint-qmd"].note)


def test_expression_regex_edge_cases():
    rx = rlv.GITHUB_EXPRESSION
    nested = "echo ${{ toJSON(fromJSON('{\"a\":1}')) }}"
    m = rx.search(nested)
    check("an expression whose body contains a literal } is still detected",
          m is not None and m.group(0).startswith("${{ toJSON(") and m.group(0).endswith("}}"))
    two = "${{ github.actor }} ${{ secrets.GITHUB_TOKEN }}"
    check("two expressions on one line: the first is named", rx.search(two).group(0) == "${{ github.actor }}")
    check("a plain shell brace expansion is not an expression", rx.search("echo ${HOME} {a,b}") is None)


def test_missing_job_is_exit_2():
    with tempfile.TemporaryDirectory() as tmp:
        wf = _write_fixture(tmp)
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            rc = rlv.main(["--workflow", str(wf), "--job", "nope", "--root", tmp])
        check("an unknown job exits 2 and names the jobs that exist", rc == 2 and "validate" in err.getvalue())
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            rc = rlv.main(["--workflow", str(Path(tmp) / "absent.yml"), "--root", tmp])
        check("a missing workflow exits 2", rc == 2)
        bad = Path(tmp) / "bad.yml"
        bad.write_text("jobs:\n  validate:\n    steps: [\n", encoding="utf-8")
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            rc = rlv.main(["--workflow", str(bad), "--root", tmp])
        check("a malformed workflow exits 2 with the parse error named", rc == 2 and "cannot parse" in err.getvalue())


def test_list_does_not_execute():
    with tempfile.TemporaryDirectory() as tmp:
        wf = _write_fixture(tmp)
        out_file = Path(tmp) / "touched"
        os.environ["OUT_FILE"] = str(out_file)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--list"])
        finally:
            del os.environ["OUT_FILE"]
        text = out.getvalue()
        check("--list exits 0 and prints the plan with the denominator", rc == 0 and "step(s) derived" in text)
        check("--list runs nothing", not out_file.exists())
        check("--list marks the install step SKIP and the runner-only step NOT RUN",
              "SKIP     [validate] Install dependencies" in text and "NOT RUN  [validate] Runner-only step" in text)


def test_run_reports_each_rc_and_fails_overall():
    with tempfile.TemporaryDirectory() as tmp:
        wf = _write_fixture(tmp)
        out_file = Path(tmp) / "touched"
        os.environ["OUT_FILE"] = str(out_file)
        try:
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "step$"])
        finally:
            del os.environ["OUT_FILE"]
        text = out.getvalue()
        check("overall exit is 1 when a step fails", rc == 1)
        check("the failing step's own exit code appears in the table", "Failing step" in text and " 3 " in text.replace("\n", " "))
        check("the multi-line step ran under bash and executed its second line", out_file.read_text() == "two\n")
        check("working-directory is honoured", "Sub-directory step" in text)
        check("the summary carries the denominator", "of 6 step(s) derived" in text and "2 not runnable" in text)


def test_only_and_skip_filters():
    with tempfile.TemporaryDirectory() as tmp:
        wf = _write_fixture(tmp)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "Passing"])
        check("--only restricts to matching steps and passes", rc == 0 and "1 passed, 0 failed" in out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "Passing|Failing", "--skip", "Failing"])
        check("--skip removes a step from execution and counts it", rc == 0 and "1 skipped" in out.getvalue())


def test_require_clean_on_dirty_tree():
    with tempfile.TemporaryDirectory() as tmp:
        wf = _write_fixture(tmp)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp, check=True)
        (Path(tmp) / "dirty.txt").write_text("x")
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "Passing", "--require-clean"])
        check("--require-clean exits 2 on a dirty tree and says so", rc == 2 and "uncommitted" in err.getvalue())
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "Passing"])
        check("without --require-clean a dirty tree only warns", rc == 0 and "warning" in err.getvalue())
    with tempfile.TemporaryDirectory() as tmp:
        wf = _write_fixture(tmp)
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "Passing"])
        check("a root that is not a git repo is reported, not silently read as clean",
              rc == 0 and "could not read git status" in err.getvalue())


def test_live_workflow_derives_every_python_test_suite():
    """Dogfood: the derived plan names every scripts/test_*.py the live workflow runs."""
    live = Path(__file__).parent.parent / ".github" / "workflows" / "validate.yml"
    steps = rlv.derive_steps(rlv.load_workflow(live), "validate", "origin/main")
    commands = "\n".join(s.command for s in steps)
    suites = sorted(p.name for p in (Path(__file__).parent).glob("test_*.py"))
    missing = [s for s in suites if s not in commands]
    check(f"every test suite in scripts/ appears in the derived plan ({len(suites)} suites)", missing == [])
    if missing:
        print("    missing:", missing)


def main():
    test_expression_regex_edge_cases()
    test_other_workflow_files()
    test_derive_steps()
    test_missing_job_is_exit_2()
    test_list_does_not_execute()
    test_run_reports_each_rc_and_fails_overall()
    test_only_and_skip_filters()
    test_require_clean_on_dirty_tree()
    test_live_workflow_derives_every_python_test_suite()
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
