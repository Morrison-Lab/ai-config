#!/usr/bin/env python3
"""Offline tests for mwc-batch.py (ai-config#5578).

The pure functions are tested over payload shapes; the two that read other
files (the infra repository list and INFRA_PATH_PATTERNS) are tested against
the real merge-infra-pr and merge hook, so a change to either that breaks the
parse fails here instead of silently classifying every PR as content.
"""
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("mwc_batch", HERE / "mwc-batch.py")
mwc_batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mwc_batch)


def run(status, conclusion=None):
    return {"status": status, "conclusion": conclusion}


def test_ci_state_cancelled_is_not_failing():
    # A concurrency-cancelled run is superseded, not failed (pr-sweep.py's rule).
    assert mwc_batch.ci_state([run("completed", "success"), run("completed", "cancelled")]) == "green"


def test_ci_state_running_beats_failing():
    assert mwc_batch.ci_state([run("in_progress"), run("completed", "failure")]) == "running"


def test_ci_state_failing_and_none():
    assert mwc_batch.ci_state([run("completed", "timed_out")]) == "failing"
    assert mwc_batch.ci_state([]) == "none"


def test_infra_repos_read_from_merge_infra_pr():
    repos = mwc_batch.infra_repos(mwc_batch.MERGE_INFRA_PR.read_text(encoding="utf-8"))
    assert {"gha", "macros", "ai-config"} <= repos


def test_infra_repos_missing_list_fails_fast():
    with pytest.raises(SystemExit) as exc:
        mwc_batch.infra_repos("#!/bin/sh\necho no case arm here\n")
    assert exc.value.code == 2


@pytest.fixture(scope="module")
def patterns():
    return mwc_batch.infra_patterns()


def test_scope_workflow_only_pr_is_infra(patterns):
    files = [".github/workflows/x.yml", "CLAUDE.md"]
    assert mwc_batch.scope("lds", files, {"gha"}, patterns) == "infra"


def test_scope_one_content_file_makes_content(patterns):
    files = [".github/workflows/x.yml", "chapters/intro.qmd"]
    assert mwc_batch.scope("lds", files, {"gha"}, patterns) == "content"


def test_scope_infra_repo_is_infra_whatever_the_paths(patterns):
    assert mwc_batch.scope("gha", ["anything.qmd"], {"gha"}, patterns) == "infra"


def test_scope_canvas_wins_even_in_infra_repo(patterns):
    # merge-infra-pr refuses any canvas/ path in every repository.
    assert mwc_batch.scope("gha", ["canvas/sync.py"], {"gha"}, patterns) == "canvas"


def test_scope_no_files_is_content(patterns):
    assert mwc_batch.scope("lds", [], {"gha"}, patterns) == "content"


CHECKER_OUTPUT = """\
Some heading
  - Check run 'page-banners' passed but carries 1 annotation(s) not yet read: run `gh api repos/Morrison-Lab/sds/check-runs/131542553930/annotations` (for many runs, ...)
  - NOTE: own job still running
  - Maintainer feedback newer than the last push: comment 123
"""


def test_checker_reasons_splits_unread_annotations():
    reasons, unread = mwc_batch.checker_reasons(CHECKER_OUTPUT)
    assert unread == ["131542553930"]
    assert reasons == ["Maintainer feedback newer than the last push: comment 123"]


def test_parse_annotations_read():
    assert mwc_batch.parse_annotations_read(["sds#607=1,2", "lds#9=all"]) == {
        "sds#607": "1,2", "lds#9": "all"}
    with pytest.raises(SystemExit):
        mwc_batch.parse_annotations_read(["sds#607=1;rm -rf"])


def test_render_lines():
    sha = "a" * 40
    results = [
        {"repo": "lds", "number": 1, "sha": sha, "title": "t1", "status": "content", "reasons": []},
        {"repo": "lds", "number": 2, "sha": sha, "title": "t2", "status": "infra", "reasons": []},
        {"repo": "sds", "number": 3, "sha": sha, "title": "t3", "status": "waiting", "reasons": ["CI running"]},
    ]
    text = mwc_batch.render(results, ["Morrison-Lab/lds", "Morrison-Lab/sds"], 4)
    assert "3 open non-draft PRs examined" in text
    assert "(4 drafts skipped)" in text
    assert "mwc lds 1 aaaaaaaa" in text
    assert "merge-infra-pr lds 2" in text
    assert "sds#3 aaaaaaaa waiting: CI running" in text
