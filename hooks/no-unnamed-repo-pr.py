#!/usr/bin/env python3
"""PreToolUse deny: no PR in a repository the user never named (ai-config#5780).

- Denies the MCP create_pull_request tools, `gh pr create|new` and `glab mr create|new` when the target
  (`-R`/`--repo`, a `GH_REPO`/`GITLAB_REPO` prefix or environment value, else gh's pick in the command's
  directory) is neither home (gh's pick in the first transcript `cwd`) nor named: a whole word in a
  message the user wrote (`no-unrequested-sweep-pr.py`'s helpers; reminders and pastes dropped,
  slash-command args and queued messages kept). Override: `ALLOW_UNNAMED_REPO_PR=1` in the hook's
  own environment only. Fails open with a note: unreadable transcript, no user message, unresolved target.
- Known limits: a repo named only as precedent passes; new-branch pushes are not guarded (a push opens
  no PR); `gh api` POST to /pulls, `gh api graphql` createPullRequest and `glab api` merge_requests POST
  are not parsed (ai-config#5784).
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

MCP_CREATE = ("mcp__github__create_pull_request", "mcp__github__create_pull_request_with_copilot")
LOOKS_LIKE_CREATE = re.compile(r"\b(?:gh\s+pr|glab\s+mr)\s+(?:create|new)\b")
PASTED = re.compile(r"<(system-reminder|pasted_content)\b[^>]*>.*?(?:</\1>|\Z)", re.S)
REPO_ENV = {"gh": "GH_REPO", "glab": "GITLAB_REPO"}
GH_REMOTE_ORDER = ("upstream", "github", "origin")


def _key(path):
    """`owner/repo`, lowercased, from a repo path or URL; None with fewer than two parts."""
    m = re.match(r"\A[\w.+-]+://[^/]*/(.*)\Z", path or "") or re.match(r"\A[^/@\s]+@[^:/\s]+:(.*)\Z", path or "")
    parts = [p for p in (m.group(1) if m else path or "").split("/") if p]
    return f"{parts[-2]}/{re.sub(r'[.]git$', '', parts[-1])}".lower() if len(parts) > 1 else None


def gh_target(directory):
    """The repo key gh targets from the checkout at `directory`, or None."""
    if not directory or not os.path.isdir(directory):
        return None
    out = subprocess.run(["git", "-C", directory, "config", "--get-regexp", r"^remote\..*\.(url|gh-resolved)$"],
                         capture_output=True, encoding="utf-8", timeout=5).stdout
    remotes = {}
    for m in re.finditer(r"^remote\.(.+)\.(url|gh-resolved) (.*)$", out, re.M):
        remotes.setdefault(m.group(1), {})[m.group(2)] = m.group(3).strip()
    for conf in remotes.values():
        if conf.get("gh-resolved"):
            return _key(conf.get("url") if conf["gh-resolved"] == "base" else conf["gh-resolved"])
    order = sorted(remotes, key=lambda n: GH_REMOTE_ORDER.index(n) if n in GH_REMOTE_ORDER else 99)
    return _key(remotes[order[0]].get("url")) if order else None


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
        found += [(None, "an unparsed command")] if cmds is None and LOOKS_LIKE_CREATE.search(piece) else []
        assigns = [t for _, argv in cmds or [] for t in argv if re.match(r"\A(?:GH_REPO|GITLAB_REPO)=", t)]
        for argv, _env, _rest, cur in walk_dirs(cmds or [], start if depth == 0 else None):
            prog, lead = _program(argv)
            if not prog or prog[1:2] != [("pr", "mr")[prog[0] == "glab"]] or prog[2:3] not in (["create"], ["new"]):
                continue
            args, var = prog[3:], REPO_ENV[prog[0]]
            flag = [b if a in ("-R", "--repo") else a.split("=", 1)[1] if a.startswith("--repo=") else a[2:]
                    for a, b in zip(args, args[1:] + [""]) if re.match(r"\A(?:-R|--repo)(?:\Z|=)|\A-R.", a)]
            repo = (flag or [None])[-1] or env_value(lead, var)
            if not repo and any(t not in lead for t in assigns):
                found.append((None, f"`{prog[0]} {prog[1]} create` ({var} set elsewhere in the line)"))
                continue
            repo = repo or os.environ.get(var)
            found.append((_key(repo) if repo else gh_target(cur), f"`{prog[0]} {prog[1]} create`"))
    return found


def read_session(path, prompt_text, user_bodies):
    """(texts the user wrote, first record's cwd) from the transcript at `path`."""
    texts, prompts, first_cwd = [], [], None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = dict(json.loads(line))
            except (ValueError, TypeError):
                continue
            first_cwd = first_cwd or (rec.get("cwd") if isinstance(rec.get("cwd"), str) else None)
            att = rec.get("attachment") if isinstance(rec.get("attachment"), dict) else {}
            if att.get("type") == "queued_command" and att.get("commandMode") != "task-notification" \
                    and (att.get("origin") or {}).get("kind") != "peer":
                prompts.append(str(att.get("prompt") or ""))
            msg = rec.get("message")
            if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain") \
                    or rec.get("isCompactSummary") or not isinstance(msg, dict):
                continue
            prompts.append(prompt_text(msg.get("content")) or "")
    for text in (PASTED.sub(" ", p) for p in prompts):  # a typed slash command's args, else the user's bodies
        texts += (re.findall(r"<command-args>(.*?)</command-args>", text, re.S)
                  if re.match(r"\s*<command-(?:message|name)>", text) else user_bodies(text) if text.strip() else [])
    return [t for t in texts if t.strip()], first_cwd


def named(key, texts):
    rx = re.compile(r"(?<![\w.-])" + re.escape(key.split("/")[-1]) + r"(?:\.git)?(?![\w-])(?!\.\w)", re.I)
    return any(rx.search(t) for t in texts)


def decide(payload):
    """(decision, text): decision in {"deny", "note", None}."""
    tool, inp = payload.get("tool_name") or "", payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    cmd = inp.get("command") if tool == "Bash" and isinstance(inp.get("command"), str) else ""
    found = ([(_key(f"{inp.get('owner') or ''}/{inp.get('repo') or ''}"), f"`{tool}`")] if tool in MCP_CREATE
             else creations(cmd, payload.get("cwd") or None) if re.search(r"\b(?:gh|glab)\b", cmd) else [])
    if not found or os.environ.get("ALLOW_UNNAMED_REPO_PR") == "1":
        return None, ""
    tpath, sweep = payload.get("transcript_path"), load_sibling(__file__, "no-unrequested-sweep-pr.py")
    try:
        texts, first_cwd, err = *read_session(tpath, sweep.prompt_text, sweep.load_user_bodies()[0]), ""
    except Exception as exc:  # noqa: BLE001 -- reported in the note
        texts, first_cwd, err = [], None, f" ({exc})"
    if not texts:
        return "note", ("no-unnamed-repo-pr: this opens a PR, and no message the user wrote could be read from the "
                        f"transcript{err}; open it only in a repo the user named (ai-config#5780).")
    home = gh_target(first_cwd or payload.get("cwd"))
    denied = [f"`{k}` ({label})" for k, label in found if k and k != home and not named(k, texts)]
    if denied:
        return "deny", (
            f"MECHANISTIC PROHIBITION: no PR in a repository the user never named (ai-config#5780). Target: "
            f"{', '.join(denied)}; home repo: `{home}`. No message the user wrote this session names it, and "
            "\"we did similar things in X\" is precedent, not a request. Ask the user whether they want a PR "
            "there, naming the repo, and wait.")
    unresolved = [label for k, label in found if k is None]
    if unresolved:
        return "note", (f"no-unnamed-repo-pr: could not tell which repo {', '.join(unresolved)} targets "
                        "(ai-config#5780); pass `-R <owner>/<repo>`.")
    return None, ""


def main():
    try:
        decision, text = decide(json.load(sys.stdin))
    except Exception as exc:  # noqa: BLE001 -- fail open, but say so
        decision, text = "note", f"no-unnamed-repo-pr: the check failed ({exc}) (ai-config#5780)."
    out = {"permissionDecision": "deny", "permissionDecisionReason": text} if decision == "deny" else (
        {"additionalContext": text} if decision else None)
    if out:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **out},
                          **({"systemMessage": text} if decision == "note" else {})}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
