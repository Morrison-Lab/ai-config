#!/usr/bin/env python3
"""PreToolUse guard: block mutating git commands in read-only reviewer personas.

## The incidents

1. Morrison-Lab/ai-config#3602: A read-only reviewer subagent reviewing a remote
   branch ran `git checkout -b ... && git commit` against the shared main
   checkout (`C:/Users/dougm/Documents/Github/ai-config`). The branch creation
   failed, so the commit landed on that checkout's local `main`. It then
   attempted an undo with `git reset --soft HEAD~1 && git checkout -- <file>`,
   which restored staged contaminated changes from the index and polluted
   another session's branch.
2. Morrison-Lab/ai-config#3584: A read-only `adversarial-reviewer` subagent,
   dispatched against a worktree in this repository, ran a bare `git stash pop`.
   It picked up an unrelated, older stash entry belonging to another session,
   producing merge conflicts across 20 files.
3. Morrison-Lab/ai-config#3612: The reviewer persona's read-only mandate was
   previously advisory ("instruction-level discipline rather than a harness
   guarantee", .claude/agents/adversarial-reviewer.md:125) and not mechanically
   enforced by a guard.

## Why a hook rather than a rule

`.claude/agents/adversarial-reviewer.md` already instructed:
    "Do not apply a correction... Do not use any tool that writes, edits, moves,
     or deletes a file, or that posts or pushes, whatever it is named. Do not
     use Bash to work around that. Bash is here for read-only checks (git diff,
     git log, grep, running a test suite, tool --help)."

The instruction was clear and both incidents occurred anyway. When an LLM
reviewer subagent notices a problem or attempts an undo, it reaches for
`git checkout -b`, `git commit`, `git stash pop`, or `git reset`. In a shared
checkout or across shared repo resources (such as the stash stack), those
commands corrupt concurrent sessions. A rule read at session start is broken at
tool call composition time; this guard mechanically blocks the mutation before
it executes.

## What is blocked

When executing in a read-only persona (`adversarial-reviewer`, `code-reviewer`,
`security-reviewer`, `Explore`, `Plan`, or review context):

1. Mutating git subcommands:
   - `commit` (all invocations)
   - `checkout` (all branch creation, branch switching, and file restoration)
   - `switch` (all branch switching and creation)
   - `restore` (all working-tree and staged restoration)
   - `stash` (bare `git stash`, `pop`, `apply`, `drop`, `clear`, `push`,
     `save`, `store`, `create`; `git stash list` and `show` remain allowed)
   - `merge`, `rebase`, `revert`, `cherry-pick` (all invocations)
   - `reset` (`--hard`, `--soft`, `--mixed`, `HEAD`, bare reset)
   - `clean` (all invocations)
   - `branch` with deletion/mutation flags (`-d`, `-D`, `-m`, `-M`, `-c`, `-C`,
     `--delete`, `--move`, `--copy`) or branch creation arguments
   - `tag` with deletion/mutation flags (`-d`, `-a`, `-s`, etc.) or tag creation
   - `rm`, `mv` (all invocations)
   - `apply`, `am` (patch application)
   - `push` (all invocations)
2. File write tools (`Write`, `Edit`, `NotebookEdit`, `write_to_file`,
   `replace_file_content`).

Read-only inspection commands (`git diff`, `git log`, `git show`, `git status`,
`git rev-parse`, `git rev-list`, `git cat-file`, `git stash list`, `git branch`,
test suites, linters, `grep`) remain fully authorized.

## Authorized override

If a mutation is genuinely authorized and intentional, prefix the command with:
    `ALLOW_READ_ONLY_MUTATION=1` or `ALLOW_REVIEWER_MUTATION=1`
"""
from __future__ import annotations

import json
import os
import re
import sys

OVERRIDE_ENV_VARS = frozenset({
    "ALLOW_READ_ONLY_MUTATION",
    "ALLOW_REVIEWER_MUTATION",
})

READ_ONLY_PERSONA_NAMES = frozenset({
    "adversarial-reviewer",
    "adversarial reviewer",
    "code-reviewer",
    "code reviewer",
    "security-reviewer",
    "security reviewer",
    "reviewer",
    "explore",
    "plan",
})

READ_ONLY_NAME_RE = re.compile(
    r"^(?:(?:[a-z0-9_ -]+/)?(?:adversarial[-_ ]reviewer|code[-_ ]reviewer|reviewer|security[-_ ]reviewer|explore|plan))$",
    re.I,
)

REVIEW_PROMPT_RE = re.compile(
    r"\b(?:adversarial(?:[- ]code)?[- ](?:review|reviewer)|code[- ]reviewer|self-review)\b",
    re.I,
)

RX_READ_ONLY = re.compile(
    r"\bread[- ]only\b"
    r"|\bdo(?:es)? not\s+(?:(?:edit|modify|write|change|fix|commit|mutate)[,\s]+(?:and\s+|or\s+)?)*(?:edit|modify|write|change|mutate)\b.*?\b(?:anything|any\s+files?)\b(?!\s+(?:outside|other than|except)\b)"
    r"|\bdon't\s+(?:(?:edit|modify|write|change|fix|commit|mutate)[,\s]+(?:and\s+|or\s+)?)*(?:edit|modify|write|change|mutate)\b.*?\b(?:anything|any\s+files?)\b(?!\s+(?:outside|other than|except)\b)"
    r"|\bnever\s+(?:(?:edit|modify|write|change|fix|commit|mutate)[,\s]+(?:and\s+|or\s+)?)*(?:edit|modify|write|change|mutate)\b.*?\b(?:anything|any\s+files?)\b(?!\s+(?:outside|other than|except)\b)"
    r"|\bmake no changes\b"
    r"|\bwithout\s+(?:(?:editing|modifying|writing|changing|fixing|committing)[,\s]+(?:and\s+|or\s+)?)*(?:editing|modifying|writing|changing)\b.*?\b(?:anything|any\s+files?)\b(?!\s+(?:outside|other than|except)\b)",
    re.I,
)

RX_NOT_READ_ONLY = re.compile(r"\bnot\s+read[- ]only\b", re.I)

RX_AFFIRMATIVE_WRITE = re.compile(
    r"\band\s+then\s+(?:fix|commit|patch|repair|edit|modify|write|create)\b"
    r"|\band\s+(?:fix|commit|patch|repair|edit|modify|write|create)\s+(?:(?:the|a|an|any|all|every|each|new|these|those)\s+|(?:issues?|bugs?|errors?|defects?|tests?|files?|patches?|scripts?)\b)"
    r"|(?<!\bdo not\s)(?<!\bdon't\s)(?<!\bnever\s)(?<!\bwithout\s)(?<!\bnot\s)\b(?:fix|patch|repair|address)\s+(?:every|all|any|the|each|issues?|bugs?|errors?|defects?|findings?)\b"
    r"|\bcommitt?(?:ing|ed)?\s+as\s+you\s+go\b"
    r"|(?<!\bdo not\s)(?<!\bdon't\s)(?<!\bnever\s)(?<!\bwithout\s)(?<!\bnot\s)\b(?:make|apply)\s+(?:the\s+|a\s+)?(?:fixes?|changes?|edits?|patches?|modifications?)\b"
    r"|(?<!\bdo not\s)(?<!\bdon't\s)(?<!\bnever\s)(?<!\bwithout\s)(?<!\bnot\s)\b(?:write|create)\s+(?:the\s+|a\s+|an\s+|new\s+)?(?:fixes?|tests?|files?|code|patches?|scripts?)\b",
    re.I,
)

ALWAYS_MUTATING_GIT_SUBCMDS = frozenset({
    "commit",
    "checkout",
    "switch",
    "restore",
    "merge",
    "reset",
    "rebase",
    "revert",
    "cherry-pick",
    "clean",
    "rm",
    "mv",
    "apply",
    "am",
    "push",
    "init",
    "clone",
    "add",
    "stage",
    "pull",
})

MUTATING_BRANCH_FLAGS = frozenset({
    "-d", "-D", "-m", "-M", "-c", "-C",
    "--delete", "--move", "--copy",
})

READ_ONLY_BRANCH_FLAGS = frozenset({
    "-l", "--list", "-a", "--all", "-r", "--remotes",
    "--show-current", "--contains", "--no-contains",
    "--merged", "--no-merged", "--points-at", "-v", "-vv",
    "--sort", "--format",
})

MUTATING_TAG_FLAGS = frozenset({
    "-d", "--delete", "-a", "-s", "-u", "-f", "--force",
})

WRITE_TOOLS = frozenset({
    "Write",
    "Edit",
    "NotebookEdit",
    "write_to_file",
    "replace_file_content",
})

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib",
    )
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import env_value, git_subcommand, simple_commands
except Exception as _exc:  # fail open on broken install
    print(f"no-mutation-in-read-only-reviewer: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    env_value = git_subcommand = simple_commands = None


def is_mutating_stash(rest: list[str]) -> bool:
    """True if `git stash <rest>` mutates working tree or stash stack."""
    if not rest:
        # Bare `git stash` creates a stash and modifies working tree/stash.
        return True
    first_non_flag = next((tok for tok in rest if not tok.startswith("-")), None)
    if first_non_flag in ("list", "show"):
        return False
    if first_non_flag in ("pop", "apply", "drop", "clear", "push", "save", "store", "create", "branch"):
        return True
    if rest[0] in ("-h", "--help"):
        return False
    # Flags without subcommand (e.g. `git stash -u`, `git stash -m "..."`) -> shorthand for push.
    return True


def is_mutating_branch(rest: list[str]) -> bool:
    """True if `git branch <rest>` creates, renames, copies, or deletes branches."""
    if not rest:
        return False
    for tok in rest:
        if tok in MUTATING_BRANCH_FLAGS:
            return True
        if tok.startswith("-") and not tok.startswith("--"):
            # Check short cluster like `-d`, `-D`
            if any(c in "dDmM" for c in tok[1:]):
                return True
    non_flags = [tok for tok in rest if not tok.startswith("-")]
    is_list = any(tok in READ_ONLY_BRANCH_FLAGS for tok in rest)
    if non_flags and not is_list:
        # Creating a branch: `git branch <name> [<start-point>]`
        return True
    return False


def is_mutating_tag(rest: list[str]) -> bool:
    """True if `git tag <rest>` creates or deletes a tag."""
    if not rest:
        return False
    for tok in rest:
        if tok in MUTATING_TAG_FLAGS:
            return True
    non_flags = [tok for tok in rest if not tok.startswith("-")]
    is_list = any(tok in ("-l", "--list", "-v", "--verify") for tok in rest)
    if non_flags and not is_list:
        # Creating a tag: `git tag <name>`
        return True
    return False


def is_subagent_transcript_path(path: str) -> bool:
    """True if path looks like a dedicated subagent transcript file."""
    norm = path.replace("\\", "/")
    return (
        "/subagents/" in norm
        or norm.startswith("subagents/")
        or "/agent-" in norm
        or os.path.basename(norm).startswith("agent-")
    )


def is_read_only_persona(payload: dict) -> tuple[bool, str]:
    """Determine if execution is in a read-only persona or review context.

    Returns (is_read_only, persona_name_or_reason).
    """
    # 1. Environment variable override (checked early)
    for var in OVERRIDE_ENV_VARS:
        if os.environ.get(var) == "1":
            return False, ""

    # 2. Environment variable setting persona
    if any(os.environ.get(v) == "1" for v in ("READ_ONLY_PERSONA", "REVIEW_CONTEXT", "READ_ONLY_SUBAGENT")):
        return True, "environment variable"

    # 3. Direct payload fields
    keys = (
        "attributionAgent", "subagent_type", "agent_type", "subagentType",
        "TypeName", "typeName", "role", "Role", "persona", "Persona",
    )
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and (v.lower().strip() in READ_ONLY_PERSONA_NAMES or READ_ONLY_NAME_RE.match(v.strip())):
            return True, v
        ti = payload.get("tool_input")
        if isinstance(ti, dict):
            ti_v = ti.get(k)
            if isinstance(ti_v, str) and (ti_v.lower().strip() in READ_ONLY_PERSONA_NAMES or READ_ONLY_NAME_RE.match(ti_v.strip())):
                return True, ti_v
        msg = payload.get("message")
        if isinstance(msg, dict):
            msg_v = msg.get(k)
            if isinstance(msg_v, str) and (msg_v.lower().strip() in READ_ONLY_PERSONA_NAMES or READ_ONLY_NAME_RE.match(msg_v.strip())):
                return True, msg_v

    # 4. Transcript inspection
    # Main orchestrator transcripts may carry historical subagent dispatches or isSidechain
    # records that must not contaminate the orchestrator's own authoring capabilities.
    # Only dedicated subagent transcripts should be scanned for subagent persona attribution.
    transcript_path = (
        payload.get("transcript_path")
        or payload.get("transcriptPath")
        or payload.get("transcript")
        or payload.get("history_file")
        or ""
    )
    if transcript_path and os.path.exists(transcript_path):
        is_sub = is_subagent_transcript_path(transcript_path)
        if is_sub:
            try:
                with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
                    for idx, line in enumerate(f):
                        line_str = line.strip()
                        if not line_str:
                            continue
                        try:
                            record = json.loads(line_str)
                        except Exception:
                            continue

                        # Scan for attributionAgent or persona in subagent transcript
                        attr = (
                            record.get("attributionAgent")
                            or record.get("subagent_type")
                            or record.get("agent_type")
                            or record.get("persona")
                        )
                        if isinstance(attr, str) and (attr.lower().strip() in READ_ONLY_PERSONA_NAMES or READ_ONLY_NAME_RE.match(attr.strip())):
                            return True, attr

                        msg = record.get("message")
                        if isinstance(msg, dict):
                            msg_attr = (
                                msg.get("attributionAgent")
                                or msg.get("subagent_type")
                                or msg.get("agent_type")
                                or msg.get("persona")
                            )
                            if isinstance(msg_attr, str) and (msg_attr.lower().strip() in READ_ONLY_PERSONA_NAMES or READ_ONLY_NAME_RE.match(msg_attr.strip())):
                                return True, msg_attr

                        # Initial prompt / instruction inspection for subagent transcripts
                        if idx in (0, 1):
                            content = ""
                            if record.get("type") in ("user", "USER_INPUT"):
                                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                                    content = msg["content"]
                                elif isinstance(record.get("content"), str):
                                    content = record["content"]
                            if content and not RX_NOT_READ_ONLY.search(content):
                                if RX_READ_ONLY.search(content):
                                    return True, "read-only reviewer subagent"
                                if REVIEW_PROMPT_RE.search(content) and not RX_AFFIRMATIVE_WRITE.search(content):
                                    return True, "read-only reviewer subagent"
            except Exception:
                pass

    return False, ""


def offending(tool_name: str, tool_input: dict, payload: dict) -> tuple[str, str, str] | None:
    """Inspect tool execution; return (persona, offending_segment, rule_label) or None."""
    is_ro, persona = is_read_only_persona(payload)
    if not is_ro:
        return None

    # Write tools
    if tool_name in WRITE_TOOLS:
        target = tool_input.get("TargetFile") or tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        desc = f"{tool_name} {target}".strip()
        return persona, desc, f"file write tool `{tool_name}`"

    # Shell commands
    if tool_name in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if simple_commands is None or git_subcommand is None:
            return None
        command = (
            tool_input.get("command")
            or tool_input.get("CommandLine")
            or tool_input.get("cmd")
            or tool_input.get("script")
            or ""
        )
        argvs = simple_commands(command)
        if not argvs:
            return None

        for argv in argvs:
            res = git_subcommand(argv)
            if res is None:
                continue
            sub, rest, env = res

            # Check for inline override
            if any(env_value(env, v) == "1" for v in OVERRIDE_ENV_VARS):
                continue

            segment = " ".join(argv)
            if sub in ALWAYS_MUTATING_GIT_SUBCMDS:
                return persona, segment, f"mutating git command `git {sub}`"
            if sub == "stash" and is_mutating_stash(rest):
                return persona, segment, "mutating `git stash` operation"
            if sub == "branch" and is_mutating_branch(rest):
                return persona, segment, "mutating `git branch` operation"
            if sub == "tag" and is_mutating_tag(rest):
                return persona, segment, "mutating `git tag` operation"

    return None


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"no-mutation-in-read-only-reviewer: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    hit = offending(tool_name, tool_input, payload)
    if not hit:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    persona, segment, rule_label = hit
    reason = (
        f"MECHANISTIC PROHIBITION: {rule_label} is strictly blocked in read-only persona `{persona}`.\n\n"
        f"    Offending call/segment: {segment}\n\n"
        "Read-only reviewer personas (such as `adversarial-reviewer`, `Explore`, `Plan`) are "
        "mechanistically forbidden from modifying shared checkouts or git state (including "
        "`commit`, `checkout`, `switch`, `restore`, `stash`, `merge`, `reset`, `rebase`, `revert`, "
        "`clean`, `rm`, `mv`, `apply`, `push`, and write tools).\n\n"
        "Reviewers must inspect and report findings for the authoring session to disposition; "
        "reviewers do not apply fixes, switch branches, create commits, or pop stashes "
        "(Morrison-Lab/ai-config#3612, citing #3602 and #3584).\n\n"
        "If this mutation is genuinely authorized and intentional, re-run with "
        "`ALLOW_READ_ONLY_MUTATION=1`."
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
