#!/usr/bin/env python3
"""Regression: bootstrap collision hints must stay consumer-specific.

check-install.py --fix is a Claude-root repair. Pointing --consumer-dir at a
VS Code Copilot memory directory or a Gemini skills directory treats that
directory as a complete Claude consumer and creates unrelated top-level
links there (ai-config#2286).

This suite runs the real bootstrap.sh against colliding real paths so a
leaked Claude hint cannot hide behind a helper that is never wired.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = ROOT / "bootstrap.sh"
CLAUDE_HINT = "check-install.py --fix"

passes = 0
failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += condition
    failures += not condition


def collision_hint(output: str, dest: Path) -> str | None:
    """Return the skip-line hint for *dest*, or None if no skip was printed."""
    needle = f"(real path exists at {dest} -- "
    for line in output.splitlines():
        if needle in line:
            return line.split(needle, 1)[1].removesuffix(")")
    return None


def run_bootstrap(tmp: Path) -> tuple[dict[str, Path], str]:
    claude = tmp / "claude"
    codex = tmp / "codex"
    gemini = tmp / "gemini"
    cursor = tmp / "cursor"
    copilot = tmp / "copilot-memory"
    for path in (claude, copilot, cursor / "rules", gemini / "skills",
                 codex / "skills"):
        path.mkdir(parents=True, exist_ok=True)

    (claude / "CLAUDE.md").write_text("local claude copy\n", encoding="utf-8")
    (claude / "skills" / "ardi").mkdir(parents=True)
    (claude / "skills" / "ardi" / "SKILL.md").write_text(
        "local skill copy\n", encoding="utf-8"
    )
    (copilot / "git.md").write_text("local copilot memory\n", encoding="utf-8")
    (gemini / "skills" / "ardi").mkdir()
    (gemini / "GEMINI.md").write_text("local gemini md\n", encoding="utf-8")
    (codex / "skills" / "ardi").mkdir()
    (codex / "AGENTS.md").write_text("local codex agents\n", encoding="utf-8")
    (cursor / "rules" / "000-global-workflow.mdc").write_text(
        "local cursor rule\n", encoding="utf-8"
    )

    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    scontrol = bin_dir / "scontrol"
    scontrol.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
    scontrol.chmod(0o755)

    env = os.environ | {
        "HOME": str(tmp / "home"),
        "CLAUDE_HOME": str(claude),
        "CODEX_HOME": str(codex),
        "GEMINI_HOME": str(gemini),
        "GEMINI_CONFIG_HOME": str(tmp / "gemini-config"),
        "CURSOR_HOME": str(cursor),
        "COPILOT_MEMORY_DIR": str(copilot),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        ["bash", str(BOOTSTRAP)], cwd=ROOT, env=env, text=True,
        capture_output=True, check=True,
    )
    dests = {
        "claude_md": claude / "CLAUDE.md",
        "claude_skill": claude / "skills" / "ardi",
        "copilot": copilot / "git.md",
        "gemini_skill": gemini / "skills" / "ardi",
        "gemini_md": gemini / "GEMINI.md",
        "codex_skill": codex / "skills" / "ardi",
        "codex_agents": codex / "AGENTS.md",
        "cursor_rule": cursor / "rules" / "000-global-workflow.mdc",
    }
    return dests, result.stdout


# --- Source-level leak check -----------------------------------------------
# A file-scope LINK_ONE_FIX_HINT assignment is how the Claude hint leaked
# into Copilot/Gemini. Comments may mention the forbidden command; an
# unindented assignment must not.

src = BOOTSTRAP.read_text(encoding="utf-8")
file_scope_hint_lines = []
for lineno, line in enumerate(src.splitlines(), 1):
    stripped = line.lstrip()
    if stripped.startswith("#"):
        continue
    if CLAUDE_HINT not in line:
        continue
    if not line[:1].isspace():
        file_scope_hint_lines.append(f"{lineno}:{line}")
check(
    "bootstrap.sh does not assign the Claude hint at file scope",
    file_scope_hint_lines == [],
)
if file_scope_hint_lines:
    print("  " + "\n  ".join(file_scope_hint_lines))

# The Claude wrapper must exist so the file-scope check cannot pass by simply
# deleting the hint from Claude collisions too.
check(
    "bootstrap.sh still names check-install.py --fix for Claude collisions",
    bool(re.search(r"^link_one_claude\(\)", src, flags=re.M))
    and CLAUDE_HINT in src,
)


# --- Behavioral check against the real bootstrap ---------------------------
with tempfile.TemporaryDirectory() as raw:
    dests, output = run_bootstrap(Path(raw))

    claude_md_hint = collision_hint(output, dests["claude_md"])
    claude_skill_hint = collision_hint(output, dests["claude_skill"])
    check("Claude CLAUDE.md collision printed a skip", claude_md_hint is not None)
    check("Claude skills/ardi collision printed a skip", claude_skill_hint is not None)
    check(
        "Claude CLAUDE.md skip recommends check-install.py --fix",
        claude_md_hint is not None and CLAUDE_HINT in claude_md_hint,
    )
    check(
        "Claude skills/ardi skip recommends check-install.py --fix",
        claude_skill_hint is not None and CLAUDE_HINT in claude_skill_hint,
    )

    non_claude = (
        ("VS Code Copilot memory", dests["copilot"]),
        ("Gemini skill", dests["gemini_skill"]),
        ("Gemini.md", dests["gemini_md"]),
        ("Codex skill wrapper", dests["codex_skill"]),
        ("Codex AGENTS.md", dests["codex_agents"]),
        ("Cursor rule", dests["cursor_rule"]),
    )
    for label, dest in non_claude:
        hint = collision_hint(output, dest)
        check(f"{label} collision printed a skip", hint is not None)
        check(
            f"{label} skip does not recommend check-install.py --fix",
            hint is not None and CLAUDE_HINT not in hint,
        )
        check(
            f"{label} skip names a manual replace/link repair",
            hint is not None and bool(re.search(r"link|symlink|replace|remove", hint, re.I)),
        )


print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
