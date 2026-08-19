#!/usr/bin/env python3
"""Exercise bootstrap's skills.json alias-exclude derivation."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = ROOT / "bootstrap.sh"

passes = 0
failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += condition
    failures += not condition


def derive_ground_truth_aliases(skills_dir: Path) -> set[str]:
    """Compute the ground-truth set of alias skills from frontmatter."""
    aliases: set[str] = set()
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        first_lines = "\n".join(skill_md.read_text(encoding="utf-8").splitlines()[:8])
        if re.search(r"^description:\s*\"?(?:→|->|Alias for\b)", first_lines, re.IGNORECASE | re.MULTILINE):
            aliases.add(skill_dir.name)
    return aliases


def run_bootstrap(tmp: Path) -> tuple[Path, Path, str]:
    gemini_home = tmp / "gemini"
    gemini_config = tmp / "gemini-config"
    codex = tmp / "codex"
    bin_dir = tmp / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    scontrol = bin_dir / "scontrol"
    scontrol.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
    scontrol.chmod(0o755)

    env = os.environ | {
        "HOME": str(tmp / "home"),
        "CLAUDE_HOME": str(tmp / "claude"),
        "CODEX_HOME": str(codex),
        "GEMINI_HOME": str(gemini_home),
        "GEMINI_CONFIG_HOME": str(gemini_config),
        "CURSOR_HOME": str(tmp / "cursor"),
        "COPILOT_MEMORY_DIR": str(tmp / "copilot-memory"),
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
    }
    result = subprocess.run(
        ["bash", str(BOOTSTRAP)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return gemini_home, gemini_config, result.stdout


with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    gemini_home, gemini_config, output = run_bootstrap(tmp / "initial")
    skills_json_file = gemini_config / "skills.json"

    check("skills.json is generated", skills_json_file.is_file())

    try:
        data = json.loads(skills_json_file.read_text(encoding="utf-8"))
        is_valid_json = True
    except Exception:
        data = {}
        is_valid_json = False
    check("skills.json is valid JSON", is_valid_json)

    entries = data.get("entries", [])
    check("skills.json has entries array", isinstance(entries, list) and len(entries) > 0)

    first_entry = entries[0] if entries else {}
    expected_skills_path = str(gemini_home / "skills")
    check("entries[0].path matches GEMINI_DIR/skills", first_entry.get("path") == expected_skills_path)

    exclude_patterns = first_entry.get("exclude", [])
    check("entries[0].exclude is a non-empty list", isinstance(exclude_patterns, list) and len(exclude_patterns) > 0)

    # Patterns are anchored as "^skill-name$"
    excluded_names = {re.sub(r"^\^|\$$", "", p) for p in exclude_patterns}
    ground_truth_aliases = derive_ground_truth_aliases(ROOT / "skills")

    check("derived exclude set is non-empty (negative control)", len(excluded_names) > 0)
    check(
        f"derived exclude set matches ground-truth alias skills exactly ({len(excluded_names)} == {len(ground_truth_aliases)})",
        excluded_names == ground_truth_aliases,
    )

    # Canonical skills must NOT be excluded
    check("canonical skill 'skill-builder' is not excluded", "skill-builder" not in excluded_names)
    check("canonical skill 'rescue-closed' is not excluded", "rescue-closed" not in excluded_names)
    check("canonical skill 'clean-branches' is not excluded", "clean-branches" not in excluded_names)
    check("canonical skill 'slide-tag' is not excluded", "slide-tag" not in excluded_names)

    # Aliases MUST be excluded
    check("alias 'revive-closed' is excluded", "revive-closed" in excluded_names)
    check("alias 'antigravity-review-workflow' is excluded", "antigravity-review-workflow" in excluded_names)
    check("alias 'do-as-you-think-best' is excluded", "do-as-you-think-best" in excluded_names)
    check("alias 'rct' is excluded", "rct" in excluded_names)
    check("alias 'ts' is excluded", "ts" in excluded_names)
    check("alias 'cb' is excluded", "cb" in excluded_names)

    # Idempotency check: re-running when skills.json exists and registers path
    _, _, output_second = run_bootstrap(tmp / "initial")
    check("re-running bootstrap reports skills.json already registered", "already registered" in output_second)

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
