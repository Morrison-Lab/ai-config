#!/usr/bin/env python3
"""Validate ai-config skills and plugin manifests.

Clean-room reimplementation inspired by the MIT-licensed validators in
terrylica/cc-skills (`validate-plugins.mjs`) and
jeremylongshore/claude-code-plugins-plus-skills (`validate-skills-schema.py`).
No source was copied; see CREDITS.md.

Checks:
  * every skills/<name>/ has a SKILL.md with parseable YAML frontmatter,
    except a skills-directory plugin (a .claude-plugin/plugin.json and no
    SKILL.md), whose manifest must name its directory
  * frontmatter has non-empty `name` and `description`
  * `name` matches the directory name
  * `user-invocable` (if present) is a bool
  * `allowed-tools` (if present) is a list of strings
  * .claude-plugin/marketplace.json and plugin.json are valid JSON with the
    required top-level keys
  * .cursor-plugin/marketplace.json and plugin.json are valid JSON with the
    required top-level keys
  * every marketplace plugin `source` resolves to a non-empty directory
    (an uninitialized submodule warns instead of erroring)

Exits non-zero if any error is found.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("validate-skills: PyYAML is required --- run `pip install pyyaml`.")

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []
warnings: list[str] = []


FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)

# The cloud plugin-marketplace Skills validator hard-rejects (`failed_content`)
# any skill whose `description` exceeds this many characters. The local
# Claude Code CLI only *truncates* an over-length description (at 1536
# chars) and never errors, so a violation here passes locally and only
# surfaces as a cryptic marketplace sync failure -- see ai-config#1263.
MARKETPLACE_DESCRIPTION_LIMIT = 1024

# Claude Code includes every installed skill's name and description in its
# routing prompt, so this caps the whole catalog to keep the list routable
# rather than truncated by the harness.
#
# Re-derived 2026-08-21 (ai-config#1702). The previous 8,000 was "roughly 1%
# of a 200k-token context window at four characters per token" -- arithmetic
# that checks out, against an assumption that had gone stale. It left two
# characters of headroom on a 186-entry catalog, so the next skill added
# anywhere in the repo turned `validate` red for every open PR, and the first
# one to hit it (ai-config#1849) was 70 over with a single entry and no alias.
#
# 9,000 is the same 1% reasoning re-priced against a 225k-token budget, and it
# is deliberately a modest step rather than a comfortable one: it restores
# about 23 skills of runway, which is enough that a normal PR stops tripping
# the cap and short enough that the catalog's growth stays visible.
#
# This buys time; it does not fix the cause. The budget is consumed by ENTRY
# COUNT, not by verbose descriptions -- per-entry overhead alone is ~16.5% of
# the cap -- so the lever that actually scales is having fewer entries. Alias
# directories are the obvious candidates, being a second listing entry apiece
# for a skill already listed; ai-config#1852 tracks that work. If routing
# quality degrades before then, this number comes back down rather than up.
#
# Stepped again 2026-09-03 (ai-config#2928). The 9,000 step lasted about two
# weeks: the catalog reached 7 characters of headroom, so the next skill added
# anywhere in the repo was blocked with nothing wrong in it -- the same failure
# the 8,000 cap produced. 9,400 is the same deliberately modest step, restoring
# about nine entries of runway rather than a comfortable cushion, so the
# catalog's growth stays visible. It buys time again and still does not fix the
# cause; #1852 remains the lever that scales.
SKILL_LISTING_BUDGET_CHARS = 9_400
LISTING_ENTRY_OVERHEAD_CHARS = 8

# How close to the cap counts as "nearly spent", expressed in ENTRIES rather
# than characters. The budget is consumed by entry count rather than by verbose
# descriptions -- as of 2026-08-21, 186 entries average 43 chars each, and the
# per-entry overhead alone is 16.5% of the cap -- so headroom is only meaningful
# as "how many more skills fit". Deriving the threshold from the catalog's own
# mean entry cost keeps it honest as the catalog changes, instead of pinning a
# character count that silently stops meaning what it meant.
SKILL_LISTING_WARN_ENTRIES = 6
TOP_CONSUMERS_REPORTED = 5


def parse_frontmatter(text: str, where: str):
    match = FRONTMATTER.match(text)
    if not match:
        errors.append(
            f"{where}: missing or unterminated YAML frontmatter "
            "(expected a '---' block at the very top of the file)"
        )
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"{where}: invalid YAML frontmatter: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{where}: frontmatter is not a mapping")
        return None
    return data


def is_skills_dir_plugin(child: Path) -> bool:
    """A `skills/<name>/` with a plugin manifest and no SKILL.md is a plugin.

    Claude Code loads such a folder in place as `<name>@skills-dir` (with its
    own hooks, agents, and skills) rather than as one skill, so it carries no
    SKILL.md of its own. `skills/ai-config-hooks/` is the one in this repo
    (ai-config#2004).
    """
    return ((child / ".claude-plugin" / "plugin.json").is_file()
            and not (child / "SKILL.md").exists())


def check_skills_dir_plugin(plugin_dir: Path) -> None:
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    rel = manifest.relative_to(ROOT)
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: invalid JSON ({exc})")
        return
    if data.get("name") != plugin_dir.name:
        errors.append(f"{rel}: name {data.get('name')!r} != directory "
                      f"{plugin_dir.name!r}")
    if not data.get("description"):
        errors.append(f"{rel}: empty description")


def check_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    rel = skill_md.relative_to(ROOT)
    if not skill_md.is_file():
        errors.append(f"{skill_dir.relative_to(ROOT)}: no SKILL.md")
        return
    fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"), str(rel))
    if fm is None:
        return
    name = fm.get("name")
    if not name or not str(name).strip():
        errors.append(f"{rel}: frontmatter `name` is missing or empty")
    elif name != skill_dir.name:
        errors.append(f"{rel}: `name: {name}` does not match directory `{skill_dir.name}`")
    desc = fm.get("description")
    if not desc or not str(desc).strip():
        errors.append(f"{rel}: frontmatter `description` is missing or empty")
    elif len(str(desc)) > MARKETPLACE_DESCRIPTION_LIMIT:
        errors.append(
            f"{rel}: frontmatter `description` is {len(str(desc))} chars, "
            f"over the marketplace's {MARKETPLACE_DESCRIPTION_LIMIT}-char limit "
            "(the local CLI truncates instead of erroring, so this only "
            "surfaces as a cloud marketplace sync failure -- see #1263)"
        )
    if "user-invocable" in fm and not isinstance(fm["user-invocable"], bool):
        errors.append(f"{rel}: `user-invocable` must be true or false")
    tools = fm.get("allowed-tools")
    if tools is not None and (
        not isinstance(tools, list) or not all(isinstance(t, str) for t in tools)
    ):
        errors.append(f"{rel}: `allowed-tools` must be a list of strings")


def listing_chars(entries: list[tuple[str, str]]) -> int:
    """Return the approximate routing-prompt cost of a skill catalog."""
    return sum(
        len(name) + len(description) + LISTING_ENTRY_OVERHEAD_CHARS
        for name, description in entries
    )


def top_listing_consumers(
    entries: list[tuple[str, str]], limit: int = TOP_CONSUMERS_REPORTED
) -> list[tuple[int, str]]:
    """The entries costing the most listing budget, largest first.

    Ties break on name so the reported order is stable across runs. A check
    that names different offenders on two runs over the same catalog would be
    read as flapping rather than as a tie.
    """
    costs = [
        (len(name) + len(description) + LISTING_ENTRY_OVERHEAD_CHARS, name)
        for name, description in entries
    ]
    costs.sort(key=lambda pair: (-pair[0], pair[1]))
    return costs[:limit]


def describe_consumers(entries: list[tuple[str, str]]) -> str:
    """Render the biggest consumers, so a budget message names an offender."""
    return ", ".join(
        f"{name} ({cost} chars)" for cost, name in top_listing_consumers(entries)
    )


def check_listing_budget(skill_mds: list[Path], label: str) -> None:
    """Reject a catalog whose metadata would exceed Claude's routing budget."""
    entries = []
    for skill_md in skill_mds:
        fm = parse_frontmatter(
            skill_md.read_text(encoding="utf-8"), str(skill_md.relative_to(ROOT))
        )
        if fm is None:
            continue
        name = fm.get("name")
        description = fm.get("description")
        if isinstance(name, str) and isinstance(description, str):
            entries.append((name, description))
    total = listing_chars(entries)
    overhead = len(entries) * LISTING_ENTRY_OVERHEAD_CHARS
    if total > SKILL_LISTING_BUDGET_CHARS:
        errors.append(
            f"{label}: skill listing is {total} chars, over the "
            f"{SKILL_LISTING_BUDGET_CHARS}-char context budget by "
            f"{total - SKILL_LISTING_BUDGET_CHARS}. "
            f"{len(entries)} entries, of which {overhead} chars is per-entry "
            f"overhead. Largest: {describe_consumers(entries)}"
        )
    else:
        print(f"  {label} listing: {total}/{SKILL_LISTING_BUDGET_CHARS} chars")

    # Warn BEFORE the cap is breached. Without this the failure lands on
    # whoever adds the next skill rather than on whoever spent the budget,
    # and its message names no offender -- so the fix reached for under time
    # pressure is to shorten whatever description that author happens to be
    # holding, which is the wrong lever (#1702).
    headroom = SKILL_LISTING_BUDGET_CHARS - total
    mean_entry = total / len(entries) if entries else 0
    if 0 <= headroom < SKILL_LISTING_WARN_ENTRIES * mean_entry:
        fits = int(headroom // mean_entry)
        room = (
            "not enough for one more entry"
            if fits == 0
            else f"room for about {fits} more"
        )
        warnings.append(
            f"{label}: skill listing has {headroom} chars of headroom, "
            f"{room} at the current mean of {mean_entry:.0f} chars per entry. "
            f"Largest: {describe_consumers(entries)}"
        )


def check_skills() -> None:
    skills_dir = ROOT / "skills"
    if not skills_dir.is_dir():
        warnings.append("no skills/ directory")
        return
    count = 0
    plugins = 0
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if is_skills_dir_plugin(child):
            plugins += 1
            check_skills_dir_plugin(child)
            continue
        count += 1
        check_skill(child)
    print(f"  checked {count} skills, {plugins} skills-directory plugins")
    check_listing_budget(sorted(skills_dir.glob("*/SKILL.md")), "skills/")


TOKEN_PATTERN = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")

# Backtick-wrapped ALL_CAPS_WITH_UNDERSCORE tokens already in skill prose for
# reasons unrelated to the tool-mappings.yml abstract-operation-token pilot
# (ai-config#195) --- env vars, git refs, API constants. Not every such token is
# meant to resolve via the registry, so they're exempted rather than flagged.
NON_OPERATION_TOKENS = {
    # env var: names a session to ai-session.sh, and is where
    # no-unauthorized-merge.py resolves the session from
    "AI_SESSION_ID",
    "ALLOWED_TOOLS",
    "ANTHROPIC_API_KEY",
    "CHANGES_REQUESTED",  # GitHub review state constant, not an operation token
    "CHERRY_PICK_HEAD",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_PROJECT_DIR",  # env var, one of the roots the .mwc marker is resolved from
    "CLAUDE_SESSION_ID",  # env var, the harness's own session id; AI_SESSION_ID's fallback
    "ENTITY_NUMBER",
    "MORATORIUM_END",  # hooks/no-unreviewed-pr.py constant, not an operation token
    "EPI202_TOKEN",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "GEMINI_API_KEY",
    "GITHUB_OUTPUT",
    "GITHUB_TOKEN",
    "GITLAB_TOKEN",
    "NOT_CRAN",
    "NOT_PLANNED",
    # env var: one of the two auth routes delegate-to-opencode names for the
    # openrouter provider
    "OPENROUTER_API_KEY",
    "PROJECT_ID",
    "PR_NUMBER",
    # env vars: the chores skill's scope inputs (aliases of the invoking user,
    # PR numbers named in the request), per memories/reviewing-prs.md
    "PR_SCOPE_ALIASES",
    "PR_SCOPE_EXCLUDED",
    "PR_SCOPE_REQUESTED",
    "REBASE_HEAD",
    "REVERT_HEAD",
    "R_LIBS_USER",
    "SHA_PLACEHOLDER",
    # Python constant in no-unauthorized-merge.py: the allowlist of repos whose
    # PRs carry a standing merge grant (ai-config#1352), not an operation
    "STANDING_MERGE_GRANT_REPOS",
    "SUBMODULES_TOKEN",
    "WORKFLOW_TOKEN",
}


def load_operation_ids() -> set[str]:
    mappings_file = ROOT / "tool-mappings.yml"
    if not mappings_file.is_file():
        return set()
    data = yaml.safe_load(mappings_file.read_text(encoding="utf-8"))
    return {op["id"] for op in (data or {}).get("operations", [])}


# Command fields whose values are meant to be copy-pasted into a shell. A
# `<...>` placeholder left unquoted there is read by the shell as a redirect
# rather than passed to the command -- see the convention comment at the top
# of tool-mappings.yml for the measured behaviour (ai-config#671, #1476,
# #1480).
COMMAND_FIELDS = ("cli", "github_mcp")


def unquoted_angle_brackets(command: str) -> bool:
    """True if `command` has a `<` or `>` outside single or double quotes.

    Tests the EFFECT (does the shell see a redirect operator?) rather than
    matching particular command spellings -- #671's 2-site count and #1476's
    first 6-site derivation each came up short by anchoring on a spelling.
    """
    quote = None
    for char in command:
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char in ("<", ">"):
            return True
    return False


def check_mapping_placeholders() -> None:
    mappings_file = ROOT / "tool-mappings.yml"
    if not mappings_file.is_file():
        warnings.append("tool-mappings.yml not found; skipping placeholder validation")
        return
    data = yaml.safe_load(mappings_file.read_text(encoding="utf-8"))
    operations = (data or {}).get("operations", [])
    checked = 0
    for op in operations:
        for field in COMMAND_FIELDS:
            value = op.get(field)
            if not isinstance(value, str):
                continue
            checked += 1
            if unquoted_angle_brackets(value):
                errors.append(
                    f"tool-mappings.yml: {op.get('id', '<unknown>')}.{field} has an "
                    f"unquoted `<` or `>` the shell would read as a redirect: "
                    f"{value!r} -- quote the operand carrying the placeholder"
                )
    print(f"  checked {checked} command fields for unquoted placeholders")


def check_operation_tokens() -> None:
    # Every backtick-wrapped ALL_CAPS operation-shaped token in a skill body
    # must be a real tool-mappings.yml operation id (or a known non-operation
    # constant) -- catches typos in the abstract-operation-token pilot from
    # ai-config#195 before they silently fail to resolve for non-Claude models.
    operation_ids = load_operation_ids()
    skills_dir = ROOT / "skills"
    if not skills_dir.is_dir():
        return
    if not operation_ids:
        warnings.append("tool-mappings.yml has no operations; skipping token validation")
        return
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        rel = skill_md.relative_to(ROOT)
        for match in TOKEN_PATTERN.finditer(skill_md.read_text(encoding="utf-8")):
            token = match.group(1)
            if token in operation_ids or token in NON_OPERATION_TOKENS:
                continue
            errors.append(
                f"{rel}: `{token}` looks like an operation token but isn't in "
                "tool-mappings.yml or the NON_OPERATION_TOKENS allowlist in "
                "scripts/validate-skills.py"
            )
    print(f"  checked operation tokens ({len(operation_ids)} known operations)")


def check_codex_wrappers() -> None:
    wrappers_dir = ROOT / "codex-skills"
    if not wrappers_dir.is_dir():
        warnings.append("no codex-skills/ directory")
        return

    count = 0
    for child in sorted(wrappers_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        count += 1
        skill_md = child / "SKILL.md"
        rel = skill_md.relative_to(ROOT)
        if not skill_md.is_file():
            errors.append(f"{child.relative_to(ROOT)}: no SKILL.md")
            continue
        fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"), str(rel))
        if fm is None:
            continue
        extra = sorted(set(fm) - {"name", "description"})
        if extra:
            errors.append(f"{rel}: Codex wrapper frontmatter has extra key(s): {', '.join(extra)}")
        name = fm.get("name")
        if not name or not str(name).strip():
            errors.append(f"{rel}: frontmatter `name` is missing or empty")
        elif name != child.name:
            errors.append(f"{rel}: `name: {name}` does not match directory `{child.name}`")
        desc = fm.get("description")
        if not desc or not str(desc).strip():
            errors.append(f"{rel}: frontmatter `description` is missing or empty")

    print(f"  checked {count} Codex wrappers")
    check_listing_budget(sorted(wrappers_dir.glob("*/SKILL.md")), "codex-skills/")

    sync = subprocess.run(
        [sys.executable, str(ROOT / "scripts/sync-codex-skill-wrappers.py"), "--check"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print("  " + sync.stdout.strip().replace("\n", "\n  "))
    if sync.returncode != 0:
        errors.append("codex-skills/ is out of sync; run scripts/sync-codex-skill-wrappers.py")


def check_json(rel: str, required: list[str]) -> None:
    path = ROOT / rel
    if not path.is_file():
        errors.append(f"{rel}: missing")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: invalid JSON: {exc}")
        return
    for key in required:
        if key not in data:
            errors.append(f"{rel}: missing required key `{key}`")


def submodule_paths() -> set[str]:
    """Repo-root-relative paths registered as submodules in .gitmodules."""
    if not (ROOT / ".gitmodules").is_file():
        return set()
    try:
        listed = subprocess.run(
            ["git", "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        warnings.append(".gitmodules: git is not on PATH; cannot read submodule paths")
        return set()
    if listed.returncode == 1:
        return set()  # .gitmodules exists but registers no paths
    if listed.returncode != 0:
        # Don't silently treat "couldn't ask git" as "no submodules": that
        # would downgrade every uninitialized submodule below into an error.
        warnings.append(
            f".gitmodules: could not read submodule paths: "
            f"{listed.stderr.strip() or f'git exited {listed.returncode}'}"
        )
        return set()
    # Each line is "submodule.<name>.path <value>".
    return {
        line.split(" ", 1)[1].strip()
        for line in listed.stdout.splitlines()
        if " " in line
    }


def check_plugin_sources(marketplace_rel: str) -> None:
    """Every marketplace plugin `source` must resolve to a non-empty directory.

    A plugin whose source is an empty directory loads with no skills in it, and
    nothing else in CI notices. The one case that isn't an error is a source
    that is a registered submodule nobody has initialized yet (a fresh clone
    without `--recurse-submodules`, or the pre-commit hook running there): that
    warns with the exact command to fix it, since `validate-skills.py` also runs
    as a pre-commit hook and shouldn't block a commit over it.
    """
    path = ROOT / marketplace_rel
    if not path.is_file():
        return  # check_json already reported the missing file
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return  # check_json already reported the parse error
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        errors.append(f"{marketplace_rel}: `plugins` must be a list")
        return
    submodules = submodule_paths()
    # Resolve the root too: on a checkout reached through a symlink, resolving
    # only the source would leave the two sides incomparable and silently
    # demote every submodule below to the error branch.
    root = ROOT.resolve()
    for plugin in plugins:
        if not isinstance(plugin, dict):
            errors.append(f"{marketplace_rel}: plugin entry is not an object: {plugin!r}")
            continue
        name = plugin.get("name", "<unnamed>")
        source = plugin.get("source")
        if not isinstance(source, str) or not source.strip():
            errors.append(f"{marketplace_rel}: plugin '{name}' has no `source` path")
            continue
        resolved = (root / source).resolve()
        try:
            populated = resolved.is_dir() and any(resolved.iterdir())
        except PermissionError:
            # Report the real cause rather than letting an unreadable directory
            # surface as a traceback from a pre-commit hook.
            errors.append(
                f"{marketplace_rel}: plugin '{name}' source '{source}' is not readable"
            )
            continue
        if populated:
            continue
        try:
            rel_source = resolved.relative_to(root).as_posix()
        except ValueError:
            rel_source = source
        if rel_source in submodules:
            warnings.append(
                f"{marketplace_rel}: plugin '{name}' source '{source}' is an "
                f"uninitialized submodule -- run: "
                f"git submodule update --init -- {rel_source}"
            )
        else:
            errors.append(
                f"{marketplace_rel}: plugin '{name}' source '{source}' "
                f"does not exist or is empty"
            )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Validating skills…")

    check_skills()
    check_operation_tokens()
    check_mapping_placeholders()
    print("Validating Codex wrappers…")
    check_codex_wrappers()
    print("Validating manifests…")
    check_json(".claude-plugin/marketplace.json", ["name", "owner", "plugins"])
    check_plugin_sources(".claude-plugin/marketplace.json")
    check_json(".claude-plugin/plugin.json", ["name"])
    check_json(".cursor-plugin/marketplace.json", ["name", "owner", "plugins"])
    check_plugin_sources(".cursor-plugin/marketplace.json")
    check_json(".cursor-plugin/plugin.json", ["name"])

    for w in warnings:
        print(f"  warning: {w}")
    if errors:
        print(f"\n✗ {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\n✓ all skills and manifests valid")


if __name__ == "__main__":
    main()
