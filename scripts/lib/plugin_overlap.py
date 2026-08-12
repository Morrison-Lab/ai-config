#!/usr/bin/env python3
"""Detect ai-config installs that stack instead of replacing each other.

This repo can reach a Claude Code session by two independent routes, and
nothing in the harness reports when both are live at once:

  * the **symlink install** -- `bootstrap.sh` points `~/.claude/skills` at
    this checkout, publishing every skill under its **bare** name (`/ardi`);
  * the **plugin install** -- a marketplace entry in `enabledPlugins`
    publishes the same set under a **prefixed** name (`/ai-config:ardi`).

Both routes serve the same corpus, so running both lists every skill twice.
That is not merely untidy. The skill listing is budgeted at roughly 1% of the
context window, and past that budget descriptions get truncated and skill
routing degrades -- so the second copy costs capability, not just tokens.
Measured on one machine (ai-config#1409, 2026-08-12), the listing ran ~3.8x
over budget at ~37,700 est. tokens and dropped to ~16,700 once the plugin
entries were disabled, with every skill still served by the bare-name copy.

A second, independent overlap sits inside `enabledPlugins` alone. Both
`Morrison-Lab/.claude-plugin/marketplace.json` and
`d-morrison/.claude-plugin/marketplace.json` declare a plugin named
`ai-config` sourced from `./`, so enabling both cannot load two corpora --
only one can own the `ai-config:` namespace. The extra entry is a no-op
collision, and nothing warns about it.

Per `shared/workflow/algorithmatize-checks.md`, "are two installs of the same
corpus live at once" is decidable from data already on disk, so it belongs in
an instrument rather than in anyone's memory. Per
`shared/principles/fail-fast.md`, every entry point here reports what it
examined: a caller must be able to tell "no overlap found" from "no settings
file was read", because those call for opposite responses.

## Scope, stated rather than implied

This inspects the settings files it is handed and no others. Claude Code
merges enterprise, user, project, and local settings, so a plugin enabled in
a **project** `.claude/settings.json` is invisible to a caller that passes
only `~/.claude/settings.json`. That is a real blind spot and it fails in the
safe direction: the check under-reports an overlap rather than inventing one.
`describe_overlap` names the files it read so the gap is visible in the
output instead of being a property a reader has to know.
"""
from __future__ import annotations

import json
from pathlib import Path

# The plugin name both marketplaces publish. Matching is on the part before
# `@` so any marketplace suffix is caught -- `ai-config@Morrison-Lab`,
# `ai-config@d-morrison`, and a locally added marketplace alike.
PLUGIN_NAME = "ai-config"


def load_settings(path: Path) -> dict | None:
    """Return a parsed settings.json, or None when it cannot be read.

    None means "no answer", not "no plugins". A missing, unreadable, or
    malformed settings file must not be reported as an absence of overlap --
    that is the failure/pass collapse `fail-fast.md` warns about, and here it
    would silently clear the very defect this module exists to find.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def enabled_ai_config_plugins(settings: dict) -> list[str]:
    """Return every truthy `ai-config@*` entry in this settings dict.

    A list rather than a single name, deliberately: the marketplace collision
    above is invisible to any caller that stops at the first match, and that
    collision is one of the two defects this module reports. Order follows
    `enabledPlugins` insertion order so the output is stable across runs.

    No false positives -- an entry only counts when it is truthy *and* its
    name before `@` is exactly `ai-config`.
    """
    plugins = settings.get("enabledPlugins")
    if not isinstance(plugins, dict):
        return []
    return [name for name, on in plugins.items()
            if on and name.split("@", 1)[0] == PLUGIN_NAME]


def describe_overlap(settings_paths: list[Path], *, symlink_install_live: bool,
                     ) -> list[str]:
    """Return advisory lines about stacked installs; empty when there are none.

    `symlink_install_live` is the caller's answer to "does the consumer
    directory already serve these skills under their bare names", since only
    the caller knows how it established that. Passing False disables the
    first check rather than guessing.

    Every return path either reports a finding or reports what was examined,
    so an empty list from a caller that printed nothing can never be mistaken
    for a check that did not run.
    """
    lines: list[str] = []
    read: list[Path] = []
    enabled: list[str] = []

    for path in settings_paths:
        settings = load_settings(path)
        if settings is None:
            continue
        read.append(path)
        for name in enabled_ai_config_plugins(settings):
            if name not in enabled:
                enabled.append(name)

    if not read:
        # Distinguishable from "checked and clean" on purpose. Reported by the
        # caller as an examined-nothing note rather than as a clean bill.
        looked = ", ".join(str(p) for p in settings_paths) or "(no paths given)"
        return [f"no readable settings.json among: {looked} "
                f"-- plugin overlap NOT checked"]

    if len(enabled) > 1:
        lines.append(
            f"{len(enabled)} marketplaces both enable an '{PLUGIN_NAME}' plugin: "
            f"{', '.join(enabled)}.\n"
            f"  Both publish this same repo, so only one can own the "
            f"'{PLUGIN_NAME}:' namespace; the rest are no-op collisions.\n"
            f"  Disable all but one."
        )

    if enabled and symlink_install_live:
        lines.append(
            f"the symlink install and the '{enabled[0]}' plugin are BOTH live, "
            f"so every skill is listed twice\n"
            f"  (bare '/ardi' from the symlink, prefixed '/{PLUGIN_NAME}:ardi' "
            f"from the plugin).\n"
            f"  They are alternatives, not complements. The skill listing is "
            f"budgeted at ~1% of the\n"
            f"  context window, and past it descriptions are truncated and "
            f"skill routing degrades.\n"
            f"  Pick one: disable the plugin entries (the symlink still serves "
            f"every skill), or drop\n"
            f"  the symlink install and use the prefixed names."
        )

    return lines
