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
`the repository owner/.claude-plugin/marketplace.json` declare a plugin named
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

This inspects the settings files it is handed and no others, and it resolves
them by Claude Code's documented precedence, which is easy to get backwards:

    managed (enterprise) > command line > .claude/settings.local.json
      > .claude/settings.json > ~/.claude/settings.json

So the **user** scope is the LOWEST of the five, not a personal override of
the repo. Setting a plugin to `false` in `~/.claude/settings.json` does not
switch off one a checked-in `.claude/settings.json` enables; the per-user
opt-out is `.claude/settings.local.json`.
(<https://code.claude.com/docs/en/settings>, "How scopes interact" and
`enabledPlugins`; read 2026-08-12.)

`enabledPlugins` resolves by precedence rather than by union, so
`resolve_enabled` treats a later explicit `false` as clearing an earlier
`true`. Without that, this module would report an overlap for exactly the
opt-out this repo's own README recommends.

**Managed settings are not readable here.** A plugin force-enabled by
enterprise managed settings cannot be switched off in `settings.local.json`
at all, and this check cannot see it -- so it under-reports rather than
inventing an overlap, which is the safe direction. `describe_overlap` names
the files it read so the gap is visible in the output instead of being a
property a reader has to know.
"""
from __future__ import annotations

import json
from pathlib import Path

# The plugin name both marketplaces publish. Matching is on the part before
# `@` so any marketplace suffix is caught -- `ai-config@Morrison-Lab`,
# `ai-config@the repository owner`, and a locally added marketplace alike.
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


def ai_config_entries(settings: dict) -> dict[str, bool]:
    """Return every `ai-config@*` entry in this settings dict, value included.

    Both polarities, deliberately. An explicit `false` is not the same as no
    entry at all: Claude Code resolves `enabledPlugins` by scope precedence
    rather than by unioning, so a `false` in a higher-precedence scope really
    does switch off a plugin a lower one enabled. A helper that returned only
    the truthy names could not express that, and would report an overlap for
    the exact opt-out this repo's own README recommends.

    Order follows `enabledPlugins` insertion order so output is stable.
    """
    plugins = settings.get("enabledPlugins")
    if not isinstance(plugins, dict):
        return {}
    return {name: bool(on) for name, on in plugins.items()
            if name.split("@", 1)[0] == PLUGIN_NAME}


def enabled_ai_config_plugins(settings: dict) -> list[str]:
    """Return every truthy `ai-config@*` entry in this single settings dict.

    Single-scope convenience over `ai_config_entries`, kept for callers that
    genuinely only read one file (`install-hooks.py`). For a precedence-aware
    answer across scopes, fold with `resolve_enabled` instead.

    No false positives -- an entry only counts when it is truthy *and* its
    name before `@` is exactly `ai-config`.
    """
    return [name for name, on in ai_config_entries(settings).items() if on]


def resolve_enabled(scopes: list[dict]) -> list[str]:
    """Fold per-scope entries into the names that end up enabled.

    `scopes` must be ordered by ASCENDING precedence, so a later dict wins.
    Last writer per plugin name, matching Claude Code's documented order
    (user < project < project-local); an explicit `false` late in the list
    therefore clears an earlier `true`.

    Names keep the order in which they were first seen, so a report over two
    colliding marketplaces lists them the way the files do.
    """
    state: dict[str, bool] = {}
    for settings in scopes:
        for name, on in ai_config_entries(settings).items():
            state[name] = on
    return [name for name, on in state.items() if on]


def describe_overlap(settings_paths: list[Path], *, symlink_install_live: bool,
                     ) -> list[str]:
    """Return advisory lines about stacked installs; empty when there are none.

    `settings_paths` must be ordered by ASCENDING precedence -- see
    `resolve_enabled`, which does the folding. Unreadable paths are skipped
    rather than treated as empty scopes, so a missing project file cannot
    clear a user-scope entry.

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
    scopes: list[dict] = []

    for path in settings_paths:
        settings = load_settings(path)
        if settings is None:
            continue
        read.append(path)
        scopes.append(settings)

    enabled = resolve_enabled(scopes)

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
