#!/usr/bin/env python3
"""PreToolUse deny: no PR in a repository the user never named (ai-config#5780).

- Denies: `mcp__github__create_pull_request` (and `_with_copilot`), Bash `gh pr create|new`
  and `glab mr create|new`, when the target is neither named nor home.
- Target: `-R`/`--repo`, else a `GH_REPO`/`GITLAB_REPO` prefix or environment value, else the
  repo gh picks in the command's directory (`cd` followed; `gh-resolved`, then upstream, github, origin).
- Named: the target's bare name is a whole word in a message the user wrote, read with
  `no-unrequested-sweep-pr.py`'s helpers (no tool results, isMeta, sidechains,
  `<system-reminder>` or `<pasted_content>`); a typed slash command's `<command-args>` and a
  queued message count.
- Home: the checkout of the first transcript record that has a `cwd`.
- Override: `ALLOW_UNNAMED_REPO_PR=1` in the hook's own environment; no agent-side bypass.
- Fails open with a note: unreadable transcript, no user message, missing helper, or an unresolved
  target (including `GH_REPO` set elsewhere in the line).
- Known limits: a repo named only as precedent passes; new-branch pushes are not guarded (a push opens
  no PR); `gh api` POST to `/pulls`, `gh api graphql` createPullRequest and `glab api` merge_requests
  POST are not parsed (ai-config#5784).
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"))
from shellcmd import (COMMAND_WRAPPERS, ENV_ASSIGNMENT, SHELL_KEYWORDS, env_value,  # noqa: E402
                      shell_c_expansions, simple_commands_with_scope, walk_dirs)
from sibling import load_sibling  # noqa: E402

OVERRIDE_ENV = "ALLOW_UNNAMED_REPO_PR"
MCP_CREATE = ("mcp__github__create_pull_request", "mcp__github__create_pull_request_with_copilot")
LOOKS_LIKE_CREATE = re.compile(r"\b(?:gh\s+pr|glab\s+mr)\s+(?:create|new)\b")
PASTED = re.compile(r"<(system-reminder|pasted_content)\b[^>]*>.*?(?:</\1>|\Z)", re.S)
COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
REPO_ENV = {"gh": "GH_REPO", "glab": "GITLAB_REPO"}
GH_REMOTE_ORDER = ("upstream", "github", "origin")


def _key(path):
    """`owner/repo`, lowercased, from a repo path or URL; None with fewer than two parts."""
    m = re.match(r"\A[\w.+-]+://[^/]*/(.*)\Z", path or "") or re.match(r"\A[^/@\s]+@[^:/\s]+:(.*)\Z", path or "")
    parts = [p for p in (m.group(1) if m else path or "").split("/") if p]
    if len(parts) < 2:
        return None
    return f"{parts[-2]}/{re.sub(r'[.]git$', '', parts[-1])}".lower()


def _remotes(directory):
    out = subprocess.run(["git", "-C", directory, "config", "--get-regexp", r"^remote\..*\.(url|gh-resolved)$"],
                         capture_output=True, encoding="utf-8", timeout=5).stdout
    remotes = {}
    for line in out.splitlines():
        m = re.match(r"\Aremote\.(.+)\.(url|gh-resolved) (.*)\Z", line)
        if m:
            remotes.setdefault(m.group(1), {})[m.group(2)] = m.group(3).strip()
    return remotes


def gh_target(directory):
    """The repo key gh targets from the checkout at `directory`, or None."""
    if not directory or not os.path.isdir(directory):
        return None
    remotes = _remotes(directory)
    for conf in remotes.values():
        if conf.get("gh-resolved"):
            return _key(conf.get("url") if conf["gh-resolved"] == "base" else conf["gh-resolved"])
    order = sorted(remotes, key=lambda n: GH_REMOTE_ORDER.index(n) if n in GH_REMOTE_ORDER else 99)
    return _key(remotes[order[0]].get("url")) if order else None


def _repo_flag(args):
    value = None
    for i, tok in enumerate(args):
        if tok in ("-R", "--repo") and i + 1 < len(args):
            value = args[i + 1]
        elif tok.startswith("--repo="):
            value = tok[7:]
        elif tok.startswith("-R") and len(tok) > 2:
            value = tok[2:]
    return value


def _program(argv):
    """(argv from its gh or glab word on, the assignments before it), or (None, [])."""
    while argv and argv[0] in SHELL_KEYWORDS:
        argv = argv[1:]
    for i, tok in enumerate(argv[:7]):
        if os.path.basename(tok) in REPO_ENV:
            lead = argv[:i]
            if all(ENV_ASSIGNMENT.match(t) for t in lead) or any(t in COMMAND_WRAPPERS for t in lead):
                return [os.path.basename(tok)] + argv[i + 1:], [t for t in lead if ENV_ASSIGNMENT.match(t)]
            break
    return None, []


def creations(command, start):
    """[(target key or None, label)] for each PR creation in a Bash `command`."""
    found = []
    for depth, piece in enumerate(shell_c_expansions(command)):
        cmds = simple_commands_with_scope(piece)
        if cmds is None:
            found += [(None, "a command this hook could not parse")] if LOOKS_LIKE_CREATE.search(piece) else []
            continue
        assigns = [t for _, argv in cmds for t in argv if re.match(r"\A(?:GH_REPO|GITLAB_REPO)=", t)]
        for argv, _env, _rest, cur in walk_dirs(cmds, start if depth == 0 else None):
            prog, lead = _program(argv)
            if not prog or len(prog) < 3 or prog[1] != ("pr", "mr")[prog[0] == "glab"] \
                    or prog[2] not in ("create", "new"):
                continue
            label, var = f"`{prog[0]} {prog[1]} create`", REPO_ENV[prog[0]]
            repo = _repo_flag(prog[3:]) or env_value(lead, var)
            if not repo and len(assigns) > len(lead):
                found.append((None, label + f" ({var} is set elsewhere in the line)"))
                continue
            repo = repo or os.environ.get(var)
            found.append((_key(repo) if repo else gh_target(cur), label))
    return found


def read_session(path, prompt_text, user_bodies):
    """(texts the user wrote, first record's cwd) from the transcript at `path`."""
    texts, first_cwd = [], None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            first_cwd = first_cwd or (rec.get("cwd") if isinstance(rec.get("cwd"), str) else None)
            att = rec.get("attachment") if isinstance(rec.get("attachment"), dict) else {}
            if att.get("type") == "queued_command" and att.get("commandMode") != "task-notification" \
                    and (att.get("origin") or {}).get("kind") != "peer":
                texts.append(str(att.get("prompt") or ""))
            msg = rec.get("message")
            if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain") \
                    or rec.get("isCompactSummary") or not isinstance(msg, dict):
                continue
            text = prompt_text(msg.get("content"))
            if text:
                texts += COMMAND_ARGS.findall(text) if "<command-name>" in text else user_bodies(text)
    return [PASTED.sub(" ", t) for t in texts if t.strip()], first_cwd


def named(key, texts):
    """True when the bare name of repo `key` is a whole word in one of `texts`."""
    rx = re.compile(r"(?<![\w.-])" + re.escape(key.split("/")[-1]) + r"(?:\.git)?(?![\w-])(?!\.\w)", re.I)
    return any(rx.search(t) for t in texts)


def decide(payload):
    """(decision, text): decision in {"deny", "note", None}."""
    tool, inp = payload.get("tool_name") or "", payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    if tool in MCP_CREATE:
        found = [(_key(f"{inp.get('owner') or ''}/{inp.get('repo') or ''}"), f"`{tool}`")]
    elif tool == "Bash" and isinstance(inp.get("command"), str) and re.search(r"\b(?:gh|glab)\b", inp["command"]):
        found = creations(inp["command"], payload.get("cwd") or None)
    else:
        found = []
    if not found or os.environ.get(OVERRIDE_ENV) == "1":
        return None, ""
    tpath, why = payload.get("transcript_path"), None
    sweep = load_sibling(__file__, "no-unrequested-sweep-pr.py")
    try:
        if sweep is None or not isinstance(tpath, str) or not os.path.isfile(tpath):
            why = "the transcript or its helper could not be read"
        else:
            texts, first_cwd = read_session(tpath, sweep.prompt_text, sweep.load_user_bodies()[0])
            why = None if texts else "the transcript holds no message the user wrote"
    except Exception as exc:  # noqa: BLE001 -- reported in the note
        why = f"reading the transcript failed ({exc})"
    if why:
        return "note", f"no-unnamed-repo-pr: this opens a PR and {why}; open it only in a repo the user named (#5780)."
    home = gh_target(first_cwd or payload.get("cwd"))
    denied = [f"`{k}` ({label})" for k, label in found if k and k != home and not named(k, texts)]
    if denied:
        return "deny", (
            "MECHANISTIC PROHIBITION: no PR in a repository the user never named (ai-config#5780; Ezra, "
            "2026-11-17: \"never broaden your scope like that again without my direct instructions\").\n\n"
            f"    Target: {', '.join(denied)}; home repo: `{home}`.\n\n"
            "No message the user wrote this session names it. \"We did similar things in X\" is precedent, "
            "not a request. Ask the user whether they want a PR there, naming the repo, and wait.")
    unresolved = [label for k, label in found if k is None]
    if unresolved:
        return "note", ("no-unnamed-repo-pr: could not tell which repo " + ", ".join(unresolved)
                        + " targets (#5780); pass `-R <owner>/<repo>`.")
    return None, ""


def main():
    try:
        payload = json.load(sys.stdin)
        decision, text = decide(payload) if isinstance(payload, dict) else (None, "")
    except Exception as exc:  # noqa: BLE001 -- fail open, but say so
        decision, text = "note", f"no-unnamed-repo-pr: the check failed ({exc}) (#5780)."
    out = {"hookEventName": "PreToolUse"}
    if decision == "deny":
        out.update(permissionDecision="deny", permissionDecisionReason=text)
    elif decision == "note":
        out["additionalContext"] = text
    else:
        return 0
    print(json.dumps({"hookSpecificOutput": out, **({"systemMessage": text} if decision == "note" else {})}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
