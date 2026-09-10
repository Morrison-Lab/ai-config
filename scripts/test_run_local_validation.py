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
        run: exit 3
      - name: Multi-line step
        run: |
          echo one
          echo two > touched
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
  unknown-uses:
    uses: Morrison-Lab/gha/unknown.yml@v2
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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
        check("--list tally counts the listed and the broken files apart from the derived steps",
              "plus 1 other workflow file(s) listed as NOT RUN, plus 1 other workflow file(s) BROKEN" in text
              and "step(s) derived from" in text)
        check("--list tags an unparseable other file BROKEN", "BROKEN   [workflow] broken.yaml" in text)
        out = io.StringIO()
        with redirect_stdout(out):
            rlv.main(["--workflow", str(wf), "--list", "--no-other-workflows", "--root", tmp])
        check("--no-other-workflows drops them and the tally has no plus clause",
              "review.yml" not in out.getvalue() and "plus" not in out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            rlv.main(["--workflow", str(wf), "--list", "--only", "workflow", "--root", tmp])
        only_text = out.getvalue()
        check("a job whose ID is literally `workflow` is filtered like any derived step, not as a file notice",
              "PARTIAL  [workflow] workflow:" in only_text and "plus 1 other workflow file(s) listed" in only_text
              and "BROKEN   [workflow] broken.yaml" in only_text)
        check("_denominator with no other files is the plain derived count",
              rlv._denominator(5, 0, "w.yml") == "5 step(s) derived from w.yml")
        out = io.StringIO()
        with redirect_stdout(out):
            rlv.main(["--workflow", str(wf), "--list", "--only", "Passing", "--skip", "review", "--root", tmp])
        text = out.getvalue()
        check("--only keeps the other-workflow notices in the denominator",
              "NOT RUN  [workflow] review.yml" in text and "plus 1 other workflow file(s) listed" in text)
        check("--skip never marks an other-workflow notice SKIP",
              "SKIP     [workflow]" not in text)
        # Run mode builds its tally separately from --list, so pin it too.
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = rlv.main(["--workflow", str(wf), "--only", "Passing", "--root", tmp])
        text = out.getvalue()
        check("run-mode tally counts the other files apart from the derived steps",
              "plus 1 other workflow file(s) listed as NOT RUN, plus 1 other workflow file(s) BROKEN" in text
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
    check("multi-line run kept whole", by["Multi-line step"].command == 'echo one\necho two > touched')
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
    check("lint-markdown is PARTIAL: names the checks it misses",
          by["lint-markdown"].partial == rlv.MARKDOWNLINT_UNCOVERED)
    check("a uses: job with no local equivalent is listed as not runnable",
          not by["unknown-uses"].runnable and "unknown.yml" in by["unknown-uses"].note)


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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        wf = _write_fixture(tmp)
        out_file = Path(tmp) / "touched"
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "step$"])
        text = out.getvalue()
        check("overall exit is 1 when a step fails", rc == 1)
        check("the failing step's own exit code appears in the table", "Failing step" in text and " 3 " in text.replace("\n", " "))
        check("the multi-line step ran under bash and executed its second line", out_file.read_text() == "two\n")
        check("working-directory is honoured", "Sub-directory step" in text)
        check("the summary carries the denominator", "of 6 step(s) derived" in text and "2 not runnable" in text)


def test_only_and_skip_filters():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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


def test_equivalents_table_covers_all_uses_jobs():
    workflows_dir = Path(__file__).parent.parent / ".github" / "workflows"
    missing = []
    wfs = list(workflows_dir.glob("*.yml"))
    check("workflow files exist", len(wfs) > 0)
    for path in wfs:
        wf = path.name
        doc = rlv.load_workflow(path)
        for job_name, job in (doc.get("jobs") or {}).items():
            uses = rlv._uses_of(job)
            if uses:
                covered = any(k in uses for k in rlv.LOCAL_EQUIVALENTS)
                if not covered:
                    missing.append(f"{wf} ({job_name}): {uses}")
    check("the local equivalents table covers every uses: job in the live workflows", missing == [])
    if missing:
        print("    missing:", missing)


def test_empty_changed_list_selects_all():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        wf = _write_fixture(tmp)
        out = io.StringIO()
        err = io.StringIO()
        old_cf = rlv.changed_files
        try:
            rlv.changed_files = lambda root, base: []
            with redirect_stdout(out), redirect_stderr(err):
                rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--changed", "--list"])
        finally:
            rlv.changed_files = old_cf
        text_out = out.getvalue()
        text_err = err.getvalue()
        check("info printed when changed list is empty", "no files changed against" in text_err)
        check("no scoped files changed skip reason is absent", "no scoped files changed" not in text_out)

def test_missing_tool_skips():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        wf = _write_fixture(tmp)
        old_run = subprocess.run
        def mock_run(*args, **kwargs):
            if args[0] == ["bash", "-c", "npx --no-install markdownlint-cli2 --help"]:
                class MockProc:
                    returncode = 1
                    stdout = ""
                    stderr = "markdownlint-cli2 missing"
                return MockProc()
            return old_run(*args, **kwargs)
        try:
            subprocess.run = mock_run
            rlv._REQUIRES_CACHE.clear()
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "lint-markdown"])
        finally:
            subprocess.run = old_run
            rlv._REQUIRES_CACHE.clear()

        text_out = out.getvalue()
        check("gate skipped when requires exits 1", "skipped: lint-markdown (missing tool; fix:" in text_out)

def test_list_shows_availability_note():
    """Under --list a step with a requires probe says availability is unchecked."""
    with tempfile.TemporaryDirectory() as tmp:
        wf = Path(tmp) / "validate.yml"
        wf.write_text(FIXTURE)
        rlv._REQUIRES_CACHE.clear()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rlv.main(["--workflow", str(wf), "--root", tmp, "--only", "lint-markdown", "--list"])
        check("--list renders the availability note on the PARTIAL step",
              "(availability checked at run time)" in out.getvalue())


def test_scope_matching():
    import yaml
    wf_doc = yaml.safe_load(FIXTURE)

    # Check job_scope
    job_md = wf_doc["jobs"]["lint-markdown"]
    globs, ignore = rlv.job_scope(job_md)
    check("job_scope parses lint-markdown globs from default", globs == ["*.md"])

    job_qmd = wf_doc["jobs"]["lint-qmd"]
    globs_qmd, ignore_qmd = rlv.job_scope(job_qmd)
    check("job_scope parses lint-qmd globs from default", globs_qmd == ["*.qmd"])

    # Unit tests for matches_scope
    check("matches_scope matches md file for lint-markdown", rlv.matches_scope("file.md", globs, ignore))
    check("matches_scope does not match qmd file for lint-markdown", not rlv.matches_scope("file.qmd", globs, ignore))

    check("matches_scope matches qmd file for lint-qmd", rlv.matches_scope("file.qmd", globs_qmd, ignore_qmd))
    check("matches_scope does not match md file for lint-qmd", not rlv.matches_scope("file.md", globs_qmd, ignore_qmd))

    # A markdown-only change set must select lint-markdown and new-line-breaks and not lint-qmd
    steps = rlv.derive_steps(wf_doc, "validate", "origin/main")
    def is_selected(step, changed_files):
        if not step.globs:
            return True
        return any(rlv.matches_scope(f, step.globs, step.paths_ignore) for f in changed_files)

    md_step = next(s for s in steps if s.name == "lint-markdown")
    nlb_step = next(s for s in steps if s.name == "new-line-breaks")
    qmd_step = next(s for s in steps if s.name == "lint-qmd")

    check("md change selects lint-markdown", is_selected(md_step, ["test.md"]))
    check("md change selects new-line-breaks", is_selected(nlb_step, ["test.md"]))
    check("md change does not select lint-qmd", not is_selected(qmd_step, ["test.md"]))

    check("qmd change selects lint-qmd", is_selected(qmd_step, ["test.qmd"]))
    check("qmd change does not select lint-markdown", not is_selected(md_step, ["test.qmd"]))

def test_changed_end_to_end():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        wf = _write_fixture(tmp)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp, check=True)
        # Create a file and commit it
        (Path(tmp) / "test.md").write_text("x")
        subprocess.run(["git", "add", "test.md"], cwd=tmp, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp, check=True)
        # Create a new branch
        subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=tmp, check=True)
        # Modify the file and commit
        (Path(tmp) / "test.md").write_text("y")
        subprocess.run(["git", "commit", "-q", "-am", "mod"], cwd=tmp, check=True)

        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            # base is main
            rc = rlv.main(["--workflow", str(wf), "--root", tmp, "--changed", "--base", "main", "--list"])

        text = out.getvalue()
        # md file changed, lint-markdown should be RUN/PARTIAL/NOT RUN, not skipped
        check("lint-markdown is not skipped by file scope", "SKIP     [validate] lint-markdown: no scoped files changed" not in text)
        check("lint-qmd is skipped because no qmd file changed", "SKIP     [lint-qmd] lint-qmd: no scoped files changed" in text)


def main():
    print('running test_expression_regex_edge_cases()', flush=True)
    test_expression_regex_edge_cases()
    print('running test_other_workflow_files()', flush=True)
    test_other_workflow_files()
    print('running test_derive_steps()', flush=True)
    test_derive_steps()
    print('running test_missing_job_is_exit_2()', flush=True)
    test_missing_job_is_exit_2()
    print('running test_list_does_not_execute()', flush=True)
    test_list_does_not_execute()
    print('running test_run_reports_each_rc_and_fails_overall()', flush=True)
    test_run_reports_each_rc_and_fails_overall()
    print('running test_only_and_skip_filters()', flush=True)
    test_only_and_skip_filters()
    print('running test_require_clean_on_dirty_tree()', flush=True)
    test_require_clean_on_dirty_tree()
    print('running test_empty_changed_list_selects_all()', flush=True)
    test_empty_changed_list_selects_all()
    print('running test_missing_tool_skips()', flush=True)
    test_missing_tool_skips()
    print('running test_scope_matching()', flush=True)
    test_scope_matching()
    test_list_shows_availability_note()
    print('running test_changed_end_to_end()', flush=True)
    test_changed_end_to_end()
    print('running test_live_workflow_derives_every_python_test_suite()', flush=True)
    test_live_workflow_derives_every_python_test_suite()
    print('running test_equivalents_table_covers_all_uses_jobs()', flush=True)
    test_equivalents_table_covers_all_uses_jobs()
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
