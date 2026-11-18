"""Hand git config to child processes through GIT_CONFIG_COUNT pairs.

Shared by scripts/run-local-validation.py and scripts/test_hooks.py so both
build the pairs one way.
"""
from typing import Dict


def add_git_config(env: Dict[str, str], key: str, value: str) -> None:
    """Append one `-c key=value` to env through GIT_CONFIG_COUNT, keeping any pairs already set."""
    count = int(env.get("GIT_CONFIG_COUNT") or 0)
    env[f"GIT_CONFIG_KEY_{count}"] = key
    env[f"GIT_CONFIG_VALUE_{count}"] = value
    env["GIT_CONFIG_COUNT"] = str(count + 1)


def disable_signing(env: Dict[str, str]) -> None:
    """Pin commit and tag signing off for every git a child process runs.

    A cloud session's global gitconfig sets commit.gpgsign=true with a signing
    server that is intermittently unreachable, so a suite that commits in a
    temp fixture repo failed for a reason unrelated to the code under test
    (ai-config#5789). Test suites never assert on signatures, and a pair here
    outranks repo-local config, so one place covers every suite that commits.
    """
    add_git_config(env, "commit.gpgsign", "false")
    add_git_config(env, "tag.gpgsign", "false")
