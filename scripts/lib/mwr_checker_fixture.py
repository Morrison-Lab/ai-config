"""A trusted checker root for the mwr hook tests (ai-config#3946, round 5).

block-merge-without-clean-checker.py credits the checker's MERGE-READY line
only from `$CLAUDE_PLUGIN_ROOT/scripts/check-pr-fully-clean.py`, and refuses a
plugin root that is a git checkout. This repository is a checkout, so the
tests build their own root instead: a plain directory holding a stub checker.
Set CLAUDE_PLUGIN_ROOT to it.
"""
import os

CHECKER = "check-pr-fully-clean.py"


def trusted_checker_root(root):
    """Make `root` a plain plugin root holding a checker stub; return its real path."""
    os.makedirs(os.path.join(root, "scripts"), exist_ok=True)
    with open(os.path.join(root, "scripts", CHECKER), "w", encoding="utf-8") as fh:
        fh.write("print('checker stub')\n")
    return os.path.realpath(root)
