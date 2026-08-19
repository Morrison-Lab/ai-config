#!/usr/bin/env python3
"""Exit successfully when an ai-config Codex plugin is enabled.

Codex records plugin enablement in ``config.toml``.  Bootstrap needs only this
small, stable part of the file so that it can avoid installing the same skill
catalog as both a plugin and bare wrapper symlinks.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


PLUGIN_SECTION = re.compile(
    r'^\s*\[plugins\.(?:"ai-config@[^"\n]+"|\'ai-config@[^\'\n]+\')\]\s*(?:#.*)?$'
)
TABLE_SECTION = re.compile(r"^\s*\[")
ENABLED = re.compile(r"^\s*enabled\s*=\s*true\s*(?:#.*)?$", re.IGNORECASE)


def ai_config_plugin_enabled(config: Path) -> bool:
    """Whether *config* enables any ``ai-config@*`` plugin."""
    try:
        lines = config.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    in_ai_config_plugin = False
    for line in lines:
        if PLUGIN_SECTION.match(line):
            in_ai_config_plugin = True
            continue
        if TABLE_SECTION.match(line):
            in_ai_config_plugin = False
            continue
        if in_ai_config_plugin and ENABLED.match(line):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    return 0 if ai_config_plugin_enabled(args.config) else 1


if __name__ == "__main__":
    raise SystemExit(main())
