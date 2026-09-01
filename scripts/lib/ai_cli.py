"""AI CLI and developer tool availability detection with caching.

Provides robust detection and path resolution for AI coding assistant CLIs
(Claude, Cursor, Codex, OpenCode, Antigravity/Gemini, Ollama, Grok, Aider)
and developer forge tools (gh, glab, git).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# Default user-local fallback directories where CLI tools are commonly
# installed when not explicitly present on active PATH.
DEFAULT_FALLBACK_DIRS = (
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.cargo/bin"),
)

# Canonical AI CLIs and their standard executable name aliases.
AI_CLI_ALIASES: Dict[str, Tuple[str, ...]] = {
    "claude": ("claude",),
    "cursor": ("agent", "cursor"),
    "codex": ("codex",),
    "opencode": ("opencode",),
    "antigravity": ("agy", "antigravity"),
    "gemini": ("gemini",),
    "ollama": ("ollama",),
    "grok": ("grok",),
    "aider": ("aider",),
}

# Forge and developer tools
FORGE_TOOL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "gh": ("gh",),
    "glab": ("glab",),
    "git": ("git",),
}

# Preferred default fallback priority for AI review engines
DEFAULT_ENGINE_PRIORITY = ("claude", "cursor", "codex", "opencode", "antigravity")

# In-memory path cache to avoid repeated disk or PATH lookups
_EXECUTABLE_CACHE: Dict[str, Optional[str]] = {}


def clear_executable_cache() -> None:
    """Clear the cached executable path resolutions."""
    _EXECUTABLE_CACHE.clear()


def is_executable_file(path_str: Any) -> bool:
    """Return True if path_str points to an existing executable file."""
    if not path_str:
        return False
    if path_str is True:
        return True
    try:
        p = Path(str(path_str)).expanduser()
        if not os.path.isfile(p):
            return False
        if p.exists() and not sys.platform.startswith("win"):
            return os.access(p, os.X_OK)
        return True
    except (OSError, PermissionError, ValueError, TypeError):
        return False


def find_executable(
    name: str,
    extra_paths: Optional[Sequence[Union[str, Path]]] = None,
    fallback_to_dirs: bool = True,
    use_cache: bool = True,
) -> Optional[str]:
    """Resolve the absolute path to an executable by name.

    Resolution order:
    1. Direct environment variable override (<NAME>_PATH or <NAME>_BIN).
    2. shutil.which(name) against active PATH.
    3. Custom extra_paths if supplied.
    4. Default user fallback directories (~/.local/bin, ~/.cargo/bin) if fallback_to_dirs is True.

    Results are cached in-memory unless use_cache is False.
    """
    name_clean = str(name).strip()
    if not name_clean:
        return None

    cache_key = f"{name_clean}:fb={fallback_to_dirs}:extra={','.join(str(p) for p in (extra_paths or []))}"
    if use_cache and cache_key in _EXECUTABLE_CACHE:
        return _EXECUTABLE_CACHE[cache_key]

    resolved: Optional[str] = None

    # 1. Environment variable override
    env_keys = [
        f"{name_clean.upper()}_PATH",
        f"{name_clean.upper()}_BIN",
        f"{name_clean.upper().replace('-', '_')}_PATH",
        f"{name_clean.upper().replace('-', '_')}_BIN",
    ]
    for env_key in env_keys:
        env_val = os.environ.get(env_key)
        if env_val and is_executable_file(env_val):
            resolved = str(Path(env_val).expanduser().resolve())
            break

    # 2. System PATH lookup
    if not resolved:
        which_path = shutil.which(name_clean)
        if which_path:
            resolved = str(which_path)

    # 3. Extra paths and fallback directories
    if not resolved:
        candidate_dirs: List[Union[str, Path]] = []
        if extra_paths:
            candidate_dirs.extend(extra_paths)
        if fallback_to_dirs:
            candidate_dirs.extend(DEFAULT_FALLBACK_DIRS)

        for directory in candidate_dirs:
            try:
                candidate = Path(directory).expanduser() / name_clean
                if is_executable_file(str(candidate)):
                    resolved = str(candidate.resolve())
                    break
                # On Windows, check with .exe suffix
                if sys.platform == "win32" and not name_clean.lower().endswith(".exe"):
                    candidate_exe = candidate.with_suffix(".exe")
                    if is_executable_file(str(candidate_exe)):
                        resolved = str(candidate_exe.resolve())
                        break
            except (OSError, ValueError):
                continue

    if use_cache:
        _EXECUTABLE_CACHE[cache_key] = resolved

    return resolved


def is_tool_available(name: str, fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Return True if executable `name` is found and executable."""
    return find_executable(name, fallback_to_dirs=fallback_to_dirs, use_cache=use_cache) is not None


# Convenience predicates for specific AI CLIs and forge tools


def find_ai_cli(cli_name: str, fallback_to_dirs: bool = True, use_cache: bool = True) -> Optional[str]:
    """Find executable for a recognized AI CLI, checking known aliases."""
    normalized = cli_name.lower().strip()
    aliases = AI_CLI_ALIASES.get(normalized, (normalized,))
    for alias in aliases:
        path = find_executable(alias, fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)
        if path:
            return path
    return None


def is_ai_cli_available(cli_name: str, fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if a recognized AI CLI is available."""
    return find_ai_cli(cli_name, fallback_to_dirs=fallback_to_dirs, use_cache=use_cache) is not None


def is_gh_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if GitHub CLI (gh) is available."""
    return is_tool_available("gh", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_glab_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if GitLab CLI (glab) is available."""
    return is_tool_available("glab", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_git_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if Git (git) is available."""
    return is_tool_available("git", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_claude_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if Claude Code CLI is available."""
    return is_ai_cli_available("claude", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_cursor_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if Cursor Agent CLI is available."""
    return is_ai_cli_available("cursor", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_codex_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if OpenAI Codex CLI is available."""
    return is_ai_cli_available("codex", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_opencode_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if OpenCode CLI is available."""
    return is_ai_cli_available("opencode", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_agy_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if Google Antigravity / Gemini CLI is available."""
    return is_ai_cli_available("antigravity", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_gemini_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if Gemini CLI is available."""
    return is_ai_cli_available("gemini", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_ollama_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if Ollama CLI is available."""
    return is_ai_cli_available("ollama", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_grok_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if Grok CLI is available."""
    return is_ai_cli_available("grok", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def is_aider_available(fallback_to_dirs: bool = True, use_cache: bool = True) -> bool:
    """Check if Aider CLI is available."""
    return is_ai_cli_available("aider", fallback_to_dirs=fallback_to_dirs, use_cache=use_cache)


def detect_available_engines(
    priority_order: Optional[Sequence[str]] = None,
    fallback_to_dirs: bool = True,
    use_cache: bool = True,
) -> List[str]:
    """Return available local engines in priority order."""
    order = priority_order or DEFAULT_ENGINE_PRIORITY
    available = []
    for engine in order:
        if is_ai_cli_available(engine, fallback_to_dirs=fallback_to_dirs, use_cache=use_cache):
            available.append(engine)
    return available


def get_tool_status_report() -> Dict[str, Any]:
    """Inspect and return detailed status of AI CLIs and forge tools."""
    ai_clis_report: Dict[str, Dict[str, Any]] = {}
    for name in sorted(AI_CLI_ALIASES):
        path = find_ai_cli(name)
        ai_clis_report[name] = {
            "available": path is not None,
            "path": path,
        }

    forge_tools_report: Dict[str, Dict[str, Any]] = {}
    for name in sorted(FORGE_TOOL_ALIASES):
        path = find_executable(name)
        forge_tools_report[name] = {
            "available": path is not None,
            "path": path,
        }

    # Detect current session / environment hints
    env_markers = {
        "claude_session": bool(os.environ.get("CLAUDE_SESSION_ID")),
        "antigravity_session": bool(
            os.environ.get("GEMINI_SESSION_ID") or os.environ.get("ANTIGRAVITY_AGENT")
        ),
        "codex_session": bool(os.environ.get("CODEX_THREAD_ID")),
        "opencode_session": bool(os.environ.get("OPENCODE_SESSION_ID")),
        "agent_name": os.environ.get("AGENT_NAME", ""),
    }

    return {
        "platform": sys.platform,
        "available_engines": detect_available_engines(),
        "ai_clis": ai_clis_report,
        "forge_tools": forge_tools_report,
        "environment_markers": env_markers,
    }


def format_tool_status_table(report: Dict[str, Any]) -> str:
    """Format tool status report as a human-readable text summary table."""
    lines = []
    lines.append("=" * 65)
    lines.append("AI CLI & Developer Tool Availability")
    lines.append("=" * 65)

    lines.append("AI CLIs:")
    lines.append(f"  {'CLI Name':<16} {'Status':<12} {'Resolved Path'}")
    lines.append("  " + "-" * 60)
    for name, info in sorted(report["ai_clis"].items()):
        status = "[AVAILABLE]" if info["available"] else "[NOT FOUND]"
        path_str = info["path"] or "-"
        lines.append(f"  {name:<16} {status:<12} {path_str}")

    lines.append("\nForge & Developer Tools:")
    lines.append(f"  {'Tool Name':<16} {'Status':<12} {'Resolved Path'}")
    lines.append("  " + "-" * 60)
    for name, info in sorted(report["forge_tools"].items()):
        status = "[AVAILABLE]" if info["available"] else "[NOT FOUND]"
        path_str = info["path"] or "-"
        lines.append(f"  {name:<16} {status:<12} {path_str}")

    lines.append("\nAvailable Review Engines (in priority order):")
    engines = report.get("available_engines", [])
    if engines:
        lines.append("  " + " -> ".join(engines))
    else:
        lines.append("  (None detected)")

    lines.append("=" * 65)
    return "\n".join(lines)
