"""Tool names that harnesses spell differently, shared by the hooks.

Claude Code, Antigravity, Codex and Cursor name the same tool differently
(`Agent`, `Task`, `invoke_subagent`; `Write`, `write_to_file`), and most hooks
that recognise a tool still keep their own copy of these lists. Each copy gets
them partly wrong: `remind-record-standing-guidance` accepted `task` and
`agent` but not `invoke_subagent`, so a subagent launched under that name never
cleared its reminder (ai-config#4266). New hooks import the sets from here;
moving the existing copies here is ai-config#3740.

Every set is lowercase; compare with `name.lower()`, or use the `is_*` helpers.
Generic write names (`create`, `update`) are left out: they mean other things
in other harnesses, so only a hook that knows its harness should accept them.
"""
from __future__ import annotations

import json

# Tools that launch a subagent with a written brief. `collaboration.spawn_agent`
# has not been seen in a real transcript yet (ai-config#3741).
SUBAGENT_TOOLS = frozenset({
    "agent", "task", "invoke_subagent", "dispatch_agent", "run_agent",
    "spawn_agent", "collaboration.spawn_agent",
})

# Tools that write a file (`write_file` is unmeasured).
WRITE_TOOLS = frozenset({
    "write", "edit", "multiedit", "notebookedit", "write_to_file", "write_file",
    "replace_file_content", "apply_diff", "strreplace", "editnotebook",
    "edit_file", "create_file", "apply_patch", "str_replace_editor",
})

# Tools that run a shell command.
SHELL_TOOLS = frozenset({
    "bash", "powershell", "run_command", "execute_command", "terminal", "shell",
})

# Keys naming a write tool's target file, in lookup order (`Path` unmeasured).
WRITE_TARGET_KEYS = (
    "file_path", "notebook_path", "path", "Path", "TargetFile", "target_file",
    "filePath", "target_notebook",
)

# Input keys that carry a shell tool's command, in lookup order.
SHELL_COMMAND_KEYS = ("command", "CommandLine", "cmd")

# Keys of a subagent launch, and of each entry of its `Subagents` list,
# whose text is part of the brief. Which key carries the brief of a
# `spawn_agent` launch has not been measured (ai-config#3741).
_BRIEF_KEYS = ("prompt", "Prompt", "description", "Description",
               "toolAction", "toolSummary")
_ENTRY_KEYS = ("Prompt", "prompt", "Role", "role", "TypeName", "typeName")


def _lower(name) -> str:
    return name.lower() if isinstance(name, str) else ""


def is_subagent_tool(name) -> bool:
    """True when `name` launches a subagent, in any harness's spelling."""
    return _lower(name) in SUBAGENT_TOOLS


def is_write_tool(name) -> bool:
    """True when `name` writes or edits a file, in any harness's spelling."""
    return _lower(name) in WRITE_TOOLS


def is_shell_tool(name) -> bool:
    """True when `name` runs a shell command, in any harness's spelling."""
    return _lower(name) in SHELL_TOOLS


def _first(inp, keys) -> str:
    if not isinstance(inp, dict):
        return ""
    for key in keys:
        value = inp.get(key)
        if value:
            return str(value)
    return ""


def write_target(inp) -> str:
    """The file a write tool's input names, or ''."""
    return _first(inp, WRITE_TARGET_KEYS)


def shell_command(inp) -> str:
    """The command a shell tool's input carries, or ''."""
    return _first(inp, SHELL_COMMAND_KEYS)


def subagent_brief(inp) -> str:
    """Every piece of brief text a subagent launch carries, joined by spaces.

    Covers the single-agent form (`prompt`, `description`) and Antigravity's
    `invoke_subagent` form: a `Subagents` list (as flag-unassigned-worktree
    reads it) of dicts or strings, or a JSON string of either.
    """
    if not isinstance(inp, dict):
        return ""
    parts = [str(inp[k]) for k in _BRIEF_KEYS if inp.get(k)]
    subagents = inp.get("Subagents") or inp.get("subagents")
    if isinstance(subagents, str):
        try:
            parsed = json.loads(subagents)
        except (ValueError, RecursionError):
            parsed = None
        if isinstance(parsed, (list, dict)):
            subagents = parsed
        else:
            parts.append(parsed if isinstance(parsed, str) else subagents)
            subagents = None
    if isinstance(subagents, dict):
        subagents = [subagents]
    if isinstance(subagents, list):
        for entry in subagents:
            if isinstance(entry, dict):
                parts.extend(str(entry[k]) for k in _ENTRY_KEYS if entry.get(k))
            elif isinstance(entry, str):
                parts.append(entry)
    return " ".join(parts)


# Reply tools, keyed by the input field holding the text the user reads. A
# Claude project thread replies only through these, not in `text` blocks.
REPLY_TOOLS = {
    "mcp__hearthbot__post_message": "text",
    "mcp__hearthbot__edit_message": "text",
    "mcp__hearthbot__reply": "text",
    "mcp__hearthbot__update_message": "text",
    "mcp__hearthbot__message_coordinator": "text",
    "mcp__hearthbot__message_thread": "text",
}


def reply_text(name, inp) -> str:
    """The reply text a reply tool's input carries, or ''."""
    key = REPLY_TOOLS.get(name) if isinstance(name, str) else None
    if not key or not isinstance(inp, dict):
        return ""
    value = inp.get(key)
    return value if isinstance(value, str) else ""
