"""Shared regex patterns and helpers for recognizing git commands."""
import re

# _ENV tolerates leading NAME=value assignments before the command word.
_ENV = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"

# Global git flags between 'git' and subcommand.
# Explicitly disjoint alternatives to avoid catastrophic backtracking (ReDoS):
# 1. -[Cc] flags with attached or separate value: -C <path>, -c <name>=<value>, -C<path>, -c<name>=<value>
# 2. Other single-dash flags starting with any allowed char except '-', 'C', 'c': e.g. -v, -p, -q, -d
# 3. Double-dash flags: --[a-zA-Z0-9_][a-zA-Z0-9_-]*(?:=\S*)?
_GIT_FLAGS = (
    r"(?:"
    r"-[Cc]\s*\S+\s+|"
    r"-[a-bd-zA-BD-Z0-9_][a-zA-Z0-9_-]*(?:=\S*)?\s+|"
    r"--[a-zA-Z0-9_][a-zA-Z0-9_-]*(?:=\S*)?\s+"
    r")*"
)

COMMIT = re.compile(
    r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+" + _GIT_FLAGS + r"commit(?![\w-])",
    re.MULTILINE,
)
PUSH = re.compile(
    r"(?:^|[;&|\n])\s*" + _ENV + r"git\s+" + _GIT_FLAGS + r"push(?![\w-])",
    re.MULTILINE,
)
CREATE = re.compile(
    r"(?:^|[;&|\n])\s*" + _ENV + r"gh\s+pr\s+create\b",
    re.MULTILINE,
)
