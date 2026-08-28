#!/usr/bin/env python3
"""Match `ai-config@*` entries in a Claude Code `enabledPlugins` dict.

The one live consumer is `scripts/install-hooks.py`, which warns before
`--fix` when the ai-config **plugin** is already enabled: the plugin loader
loads every hook in `hooks/hooks.json` on its own, so registering the same
hooks directly in `~/.claude/settings.json` as well would make each one fire
twice. That check needs an exact answer to "which `ai-config@*` entries does
this settings dict enable", which is what this module computes.

The wider stacked-install detector this module once fed (`describe_overlap`,
`resolve_enabled`, and the `check-plugin-overlap.py` CLI, ai-config#1409)
was removed along with the symlink install it compared against -- the plugin
route is the only install left, so there is no second route to overlap with.

Matching is on the part before `@` so any marketplace suffix is caught --
`ai-config@Morrison-Lab`, `ai-config@<other-marketplace>`, and a locally
added marketplace alike.
"""
from __future__ import annotations

# The plugin name every ai-config marketplace entry publishes.
PLUGIN_NAME = "ai-config"


def ai_config_entries(settings: dict) -> dict[str, bool]:
    """Return every `ai-config@*` entry in this settings dict, value included.

    Both polarities, deliberately. An explicit `false` is not the same as no
    entry at all: Claude Code resolves `enabledPlugins` by scope precedence
    rather than by unioning, so a `false` in a higher-precedence scope really
    does switch off a plugin a lower one enabled. A helper that returned only
    the truthy names could not express that.

    Order follows `enabledPlugins` insertion order so output is stable.
    """
    plugins = settings.get("enabledPlugins")
    if not isinstance(plugins, dict):
        return {}
    return {name: bool(on) for name, on in plugins.items()
            if name.split("@", 1)[0] == PLUGIN_NAME}


def enabled_ai_config_plugins(settings: dict) -> list[str]:
    """Return every truthy `ai-config@*` entry in this single settings dict.

    Single-scope convenience over `ai_config_entries`, for callers that
    genuinely only read one file (`install-hooks.py`).

    No false positives -- an entry only counts when it is truthy *and* its
    name before `@` is exactly `ai-config`.
    """
    return [name for name, on in ai_config_entries(settings).items() if on]
