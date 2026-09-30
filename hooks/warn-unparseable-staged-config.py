#!/usr/bin/env python3
r"""PreToolUse guard: parse staged TOML/JSON/YAML config files before git commit.

## The incident

On 2026-09-28 on Morrison-Lab/mds#24, sds#15, and pds#21, a perl substitution
wrote `\.` into double-quoted strings in `lychee.toml`. That is an illegal TOML
escape, so the whole config failed to load and the link-checker job errored on
all three PRs. Two local adversarial reviews passed the diff, and only the
@claude review bot caught it after the push.

## Why a hook rather than a prose rule

The condition is decidable from the staged content alone, so a hook can catch it
before the commit, where a prose rule would not.

## Why this warns rather than blocks

README's "A hook that misfires is worse than a missing one": while invalid syntax
in standard config files is almost certainly unintended, a warning provides
immediate surfacing without blocking legitimate emergencies or specialized
tooling workflows. It emits `additionalContext` (and `systemMessage` when not
under `ANTIGRAVITY_AGENT`) and returns 0.

## The match condition

  M1  the tool is `Bash` (or aliases `bash`, `run_command`, `execute_command`,
      `terminal`, `shell`) and the command invokes `git commit` (via `shellcmd`).
  M2  staged files ending in `.toml`, `.json`, `.yaml`, or `.yml` are examined:
      `git diff --cached --name-only --diff-filter=d -z` (plus `git diff HEAD`
      when `-a`/`--all` is given). Deleted files (`--diff-filter=d`) are excluded.
  M3  content is read from the staged index (`git show :<path>`), or from the
      working tree when `-a`/`--all` stages working tree modifications.
  M4  each file format is parsed by its corresponding parser:
      - `.toml`: `tomllib.loads`
      - `.json`: `json.loads`
      - `.yaml`/`.yml`: `yaml.safe_load_all`
  M5  if any staged config file fails to parse, a warning detailing the file
      and the parser error is emitted.

Fails OPEN on any parse trouble, when git is unreachable, or outside a git repo.

## CLI mode

When passed paths on the command line, this validates each file directly:

    python3 warn-unparseable-staged-config.py path/to/file.toml path/to/file.yaml

Exits 0 if all are valid (or not config files), and 1 if any syntax error is found.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

try:
    import yaml
except ImportError:
    yaml = None

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import git_subcommand, native_path, simple_commands
except Exception as _exc:
    print(f"warn-unparseable-staged-config: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    git_subcommand = native_path = simple_commands = None

CONFIG_EXTS = {".toml", ".json", ".yaml", ".yml"}
OVERRIDE = "ALLOW_UNPARSEABLE_CONFIG"

NOTE_TEMPLATE = """\
PreToolUse warning: unparseable staged config file(s) before commit.

{items}

A syntax error in a config file can break CI pipelines and toolchains.
Fix the parser error before committing, or unstage the file."""


def check_toml(content_bytes: bytes) -> str | None:
    if tomllib is None:
        return None
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return f"UTF-8 decode error: {exc}"
    try:
        tomllib.loads(text)
    except Exception as exc:
        return str(exc)
    return None


def check_json(content_bytes: bytes) -> str | None:
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return f"UTF-8 decode error: {exc}"
    try:
        json.loads(text)
    except Exception as exc:
        return str(exc)
    return None


def check_yaml(content_bytes: bytes) -> str | None:
    if yaml is None:
        return None
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return f"UTF-8 decode error: {exc}"
    try:
        list(yaml.safe_load_all(text))
    except Exception as exc:
        return str(exc)
    return None


def parse_config_content(path: str, content_bytes: bytes) -> str | None:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".toml":
        return check_toml(content_bytes)
    if ext == ".json":
        return check_json(content_bytes)
    if ext in (".yaml", ".yml"):
        return check_yaml(content_bytes)
    return None


def get_repo_toplevel(cwd: str | None) -> str | None:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def get_staged_config_files(cwd: str | None, stages_tracked: bool) -> list[str]:
    args = ["git", "diff", "--cached", "--name-only", "--diff-filter=d", "-z"]
    try:
        res = subprocess.run(args, cwd=cwd, capture_output=True, timeout=5)
        if res.returncode != 0:
            return []
        cached_files = [
            p for p in res.stdout.decode("utf-8", errors="replace").split("\0") if p
        ]
    except Exception:
        return []

    files = set(cached_files)
    if stages_tracked:
        args_head = ["git", "diff", "HEAD", "--name-only", "--diff-filter=d", "-z"]
        try:
            res_head = subprocess.run(args_head, cwd=cwd, capture_output=True, timeout=5)
            if res_head.returncode == 0:
                head_files = [
                    p for p in res_head.stdout.decode("utf-8", errors="replace").split("\0") if p
                ]
                files.update(head_files)
        except Exception:
            pass

    target_files = []
    for f in sorted(files):
        ext = os.path.splitext(f)[1].lower()
        if ext in CONFIG_EXTS:
            target_files.append(f)
    return target_files


def get_file_content(path: str, cwd: str | None, repo_root: str | None, stages_tracked: bool) -> bytes | None:
    if stages_tracked and repo_root:
        full_path = os.path.join(repo_root, path)
        if os.path.isfile(full_path):
            try:
                with open(full_path, "rb") as fp:
                    return fp.read()
            except Exception:
                pass
    try:
        norm_path = path.replace("\\", "/")
        res = subprocess.run(
            ["git", "show", f":{norm_path}"],
            cwd=cwd,
            capture_output=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    return None


def find_commit_invocations(command: str, session_cwd: str | None) -> list[tuple[str | None, bool, list[str]]]:
    """Find (cwd, stages_tracked, env_tokens) for each `git commit` in command."""
    if simple_commands is None:
        return []
    try:
        cmds = simple_commands(command)
    except Exception:
        return []
    if not cmds:
        return []

    invocations = []
    for argv in cmds:
        if not argv:
            continue
        cdirs = []
        for i, tok in enumerate(argv):
            if tok == "-C" and i + 1 < len(argv):
                cdirs.append(argv[i + 1])
        res = git_subcommand(argv)
        if res is None:
            continue
        subcmd, rest, env_tokens = res
        if subcmd != "commit":
            continue

        if any(tok in ("-h", "--help") for tok in rest):
            continue

        target_cwd = session_cwd
        for cdir in cdirs:
            if os.path.isabs(cdir):
                target_cwd = cdir
            elif target_cwd:
                target_cwd = os.path.join(target_cwd, cdir)
            else:
                target_cwd = cdir
        if target_cwd and native_path:
            try:
                target_cwd = native_path(target_cwd)
            except Exception:
                pass

        stages_tracked = any(
            tok in ("-a", "--all")
            or (tok.startswith("-") and not tok.startswith("--") and "a" in tok[1:])
            for tok in rest
        )
        invocations.append((target_cwd, stages_tracked, env_tokens))
    return invocations


def run_cli(paths: list[str]) -> int:
    has_err = False
    for p in paths:
        if not os.path.isfile(p):
            print(f"File not found: {p}", file=sys.stderr)
            has_err = True
            continue
        ext = os.path.splitext(p)[1].lower()
        if ext not in CONFIG_EXTS:
            continue
        try:
            with open(p, "rb") as fp:
                content = fp.read()
        except Exception as exc:
            print(f"Could not read {p}: {exc}", file=sys.stderr)
            has_err = True
            continue
        err = parse_config_content(p, content)
        if err:
            print(f"{p}: {err}")
            has_err = True
    return 1 if has_err else 0


def main() -> int:
    if len(sys.argv) > 1:
        return run_cli(sys.argv[1:])

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 0
    except Exception:
        return 0

    is_dry_run = bool(payload.get("dryRun") or payload.get("dry_run"))
    tool_name = payload.get("tool_name")
    if tool_name not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    session_cwd = payload.get("cwd") or inp.get("cwd") or inp.get("Cwd")
    invocations = find_commit_invocations(command, session_cwd)
    if not invocations:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    all_findings = []
    for target_cwd, stages_tracked, env_tokens in invocations:
        if os.environ.get(OVERRIDE) == "1" or any(tok == f"{OVERRIDE}=1" for tok in env_tokens):
            continue

        repo_root = get_repo_toplevel(target_cwd)
        staged = get_staged_config_files(target_cwd, stages_tracked)
        for rel_path in staged:
            content = get_file_content(rel_path, target_cwd, repo_root, stages_tracked)
            if content is None:
                continue
            err = parse_config_content(rel_path, content)
            if err:
                all_findings.append((rel_path, err))

    if not all_findings:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    seen = set()
    unique_findings = []
    for p, err in all_findings:
        if p not in seen:
            seen.add(p)
            unique_findings.append((p, err))

    items_str = "\n".join(f"  - {p}: {err}" for p, err in unique_findings)
    context_msg = NOTE_TEMPLATE.format(items=items_str)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context_msg,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        names = ", ".join(p for p, _ in unique_findings)
        out["systemMessage"] = f"Unparseable staged config file(s) before commit: {names}"

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
