#!/usr/bin/env python3
"""Offline tests for check-mwc-carry.py (ai-config#5967), over throwaway git repos."""
import importlib.util
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("check_mwc_carry", HERE / "check-mwc-carry.py")
carry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(carry)


def g(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def write(repo, name, text, msg=None):
    """Stage `name`; commit it as `msg` when one is given, returning the SHA."""
    (repo / name).write_text(text, encoding="utf-8")
    g(repo, "add", name)
    if msg:
        g(repo, "commit", "-q", "-m", msg)
        return g(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    """main with a.txt and b.txt; branch pr adds c.txt; returns (repo, approved sha)."""
    g(tmp_path, "init", "-q", "-b", "main")
    g(tmp_path, "config", "user.email", "t@example.com")
    g(tmp_path, "config", "user.name", "t")
    write(tmp_path, "a.txt", "a1\na2\na3\n")
    write(tmp_path, "b.txt", "b1\n", "base")
    g(tmp_path, "checkout", "-q", "-b", "pr")
    approved = write(tmp_path, "c.txt", "pr content\n", "pr work")
    return tmp_path, approved


def main_gains(repo, name, text, msg="main change"):
    g(repo, "checkout", "-q", "main")
    write(repo, name, text, msg)
    g(repo, "checkout", "-q", "pr")


def merge_main(repo):
    g(repo, "merge", "-q", "--no-edit", "main")
    return g(repo, "rev-parse", "HEAD")


def check(repo, approved, head="pr"):
    return carry.verdict(str(repo), approved, head, "main")


def test_clean_main_merges_carry(repo):
    path, approved = repo
    main_gains(path, "caller.yml", "on: pull_request\n")
    merge_main(path)
    main_gains(path, "a.txt", "a1\na2 changed on main\na3\n")
    merge_main(path)
    carries, reasons = check(path, approved)
    assert carries and len(reasons) == 2
    assert reasons[0].startswith("clean main merge")


def test_main_edit_next_to_pr_hunk_still_carries(repo):
    """A main edit beside a PR hunk changes context lines only (ai-config#6028)."""
    path, approved = repo
    approved = write(path, "a.txt", "a1\na2\na3 from pr\n", "pr edits a3")
    main_gains(path, "a.txt", "a1 from main\na2\na3\n")
    merge_main(path)
    assert check(path, approved)[0]


def test_changed_pr_diff_voids(repo):
    """main already carries the PR's file, so the PR diff against main shrinks to nothing."""
    path, approved = repo
    main_gains(path, "c.txt", "pr content\n")
    merge_main(path)
    carries, reasons = check(path, approved)
    assert not carries and "diff against the base changed" in reasons[0]


def test_new_commit_voids(repo):
    path, approved = repo
    main_gains(path, "x.yml", "x\n")
    merge_main(path)
    write(path, "c.txt", "changed\n", "edit")
    carries, reasons = check(path, approved)
    assert not carries and "not a merge commit" in reasons[0]


def test_conflict_resolved_merge_voids(repo):
    path, approved = repo
    approved = write(path, "b.txt", "pr side\n", "pr edits b")
    main_gains(path, "b.txt", "main side\n")
    subprocess.run(["git", "-C", str(path), "merge", "-q", "main"], capture_output=True)
    write(path, "b.txt", "resolved\n", "resolve")
    carries, reasons = check(path, approved)
    assert not carries and "conflict resolution" in reasons[0]


def test_edit_inside_clean_merge_voids(repo):
    path, approved = repo
    main_gains(path, "x.yml", "x\n")
    g(path, "merge", "-q", "--no-commit", "main")
    write(path, "c.txt", "smuggled\n", "evil merge")
    carries, reasons = check(path, approved)
    assert not carries and "automatic merge" in reasons[0]


def test_merge_of_other_branch_voids(repo):
    path, approved = repo
    g(path, "checkout", "-q", "-b", "other", "main")
    write(path, "o.txt", "o\n", "other")
    g(path, "checkout", "-q", "pr")
    g(path, "merge", "-q", "--no-edit", "other")
    carries, reasons = check(path, approved)
    assert not carries and "not on the base branch" in reasons[0]


def test_rebase_voids(repo):
    path, approved = repo
    main_gains(path, "x.yml", "x\n")
    g(path, "rebase", "-q", "main")
    carries, reasons = check(path, approved)
    assert not carries and "not an ancestor" in reasons[0]


def test_pr_as_second_parent_voids(repo):
    path, approved = repo
    main_gains(path, "x.yml", "x\n")
    g(path, "checkout", "-q", "-b", "flipped", "main")
    g(path, "merge", "-q", "--no-edit", "pr")
    assert not carry.verdict(str(path), approved, "flipped", "main")[0]


def test_hex_named_branch_is_not_a_sha(repo):
    path, approved = repo
    g(path, "branch", "deadbeef", "pr")
    with pytest.raises(carry.GitError):
        check(path, "deadbeef")
    assert check(path, approved[:10])[0]


def test_shallow_clone_refused(repo, tmp_path_factory):
    path, approved = repo
    shallow = tmp_path_factory.mktemp("shallow")
    subprocess.run(["git", "clone", "-q", "--depth", "1", "-b", "pr", f"file://{path}", str(shallow)],
                   check=True)
    assert carry.main(["--pr", "1", "--approved-sha", approved, "--repo-dir", str(shallow),
                       "--no-fetch", "--head-ref", "HEAD"]) == 2


def test_cli_exit_codes(repo, capsys):
    path, approved = repo
    main_gains(path, "x.yml", "x\n")
    head = merge_main(path)
    assert carry.main(["--pr", "1", "--approved-sha", approved, "--repo-dir", str(path),
                       "--no-fetch", "--head-ref", "pr"]) == 0
    assert f"CARRIES: mwc line for PR 1 (approved {approved[:8]}) to head {head}" in capsys.readouterr().out
    write(path, "c.txt", "changed\n", "edit")
    assert carry.main(["--pr", "1", "--approved-sha", approved, "--repo-dir", str(path),
                       "--no-fetch", "--head-ref", "pr"]) == 1
    assert carry.main(["--pr", "1", "--approved-sha", "not-a-sha", "--repo-dir", str(path),
                       "--no-fetch", "--head-ref", "pr"]) == 2
