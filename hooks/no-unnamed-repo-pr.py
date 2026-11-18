#!/usr/bin/env python3
"""PreToolUse deny: no PR in a repository the user never named (ai-config#5780).

Ezra, 2026-11-17: "never broaden your scope like that again without my
direct instructions; this counts as an unauthorized sweep." The task was one
course's repositories; the agent read "we've done similar things in mlg and
epi204" as a request and opened PRs in both.

## What it decides

A PR creation is one of:

  - `mcp__github__create_pull_request` or `..._with_copilot` (target: the
    `owner` and `repo` arguments);
  - a Bash `gh pr create` (alias `new`), whose target is its `-R`/`--repo`
    value, else `GH_REPO` (a prefix, then the environment), else the repository gh picks from the
    directory the command runs in (a remote marked `gh-resolved`, else the
    first of `upstream`, `github`, `origin`, as gh orders them);
  - a Bash `gh api repos/<owner>/<repo>/pulls` sent as POST (an explicit
    `-X POST`, or a field or `--input` with no `-X`), which is how a cloud
    session without GraphQL opens a PR;
  - a Bash `glab mr create` (alias `new`), resolved the same way.

The target passes when ANY of these holds, and is denied otherwise:

  1. NAMED: its bare name (the last path component, `mlg` for
     `Morrison-Lab/mlg`) appears as a whole word in a message the user
     wrote this session. `mlg`, `Morrison-Lab/mlg`, `mlg#423` and a PR URL
     all name it; `config` does not name `ai-config`. The user's words are
     read the way `no-unrequested-sweep-pr.py` reads them: its
     `prompt_text` and the `user_bodies` it loads keep a user record's own
     text (a principal wake message, a relay's cited user entries) and drop
     tool results, `isMeta` records (skill bodies, hook feedback, scheduled
     continuations), sidechains, compaction summaries and harness-tagged
     prompts. `<system-reminder>` and `<pasted_content>` blocks inside a
     typed message are dropped too. A message queued while a turn ran
     (`attachment.type == "queued_command"`) counts, as in
     `no-unapproved-announcement.py`, unless it is a task notification or
     a peer's.
  2. HOME: it is the session's own checkout, the `origin` of (or gh's pick
     from) the directory of the transcript's first record that carries a
     `cwd`. A session
     started in a repository is working that repository. The command's own
     directory does not count: a `cd` into another clone is the very move
     this hook exists to catch.
  3. ALREADY HAS A PR: an earlier PR creation in this transcript, of any of
     the kinds above, returned without `is_error`, and its result carries a
     `/pull/<N>` or `/-/merge_requests/<N>` URL in that repository (or, for
     the MCP tool, its `owner`/`repo` arguments name it). That PR either
     passed this hook or carried the override.

Repositories are compared by their last two path components, lowercased.

## Known limits

  - A repository named in a precedent clause ("we did similar things in
    mlg") still passes rule 1. The hook catches the commonest case, a
    repository nobody mentioned, not every case.
  - A bare name that is also an ordinary word (`notes`, `test`) passes when
    the user uses the word.
  - A cloud session's other attached repositories count only once named;
    the transcript does not record which repositories the session was
    created with.
  - Pushing a new branch is NOT guarded, though the issue proposes it. Two
    things make it unsound as a PreToolUse check. "New" is a property of
    the remote, so deciding it needs a network round trip on every push.
    And a pushed branch opens nothing: the PR that would carry it is a
    separate creation, which this hook already denies. A push to the home
    repository is always allowed anyway, so the guard would only ever fire
    on a push into another clone. `mcp__github__create_branch` and
    `push_files` are left out for the second reason.
  - `curl` or another HTTP client posting to the pulls endpoint is not
    parsed. A nested `bash -c` piece is checked for a `-R`/`--repo` or
    `gh api` target only, since its directory is unknown.

## Failure direction

A creation is always detected first, from the tool input alone. Deciding it
then needs the transcript. When the transcript cannot be read, the sibling
helper cannot load, the transcript holds no message from the user at all (a
subagent's own transcript), or a target cannot be resolved, the hook does
NOT deny: it adds a note saying what it could not check and leaves the PR to
the user's judgment. This is the convention `no-fable-subagent.py` and
`no-unrequested-sweep-pr.py` use. A guard that blocks every PR whenever a
file is unreadable would stop work on a guess.

## The override is a grant, not a habit

`ALLOW_UNNAMED_REPO_PR=1` as a prefix on the one Bash command
(`ALLOW_UNNAMED_REPO_PR=1 gh api repos/o/r/pulls ...`) lets a creation the
user asked for in words this hook cannot see proceed. Set it only when the
user's message names the repository, and quote that message in the PR body.
As in `no-fable-subagent.py`, the variable in the hook's own environment is
also honoured, which is the only way an MCP call can carry it; exporting it
for a session is the anti-pattern the directive names.

Run with `--dry-run '<payload json>'` to see the verdict without acting.
"""
import json
import os
import re
import subprocess
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from shellcmd import (COMMAND_WRAPPERS, ENV_ASSIGNMENT, env_value,  # noqa: E402
                      shell_c_expansions, simple_commands_with_scope, walk_dirs)
from sibling import load_sibling  # noqa: E402

OVERRIDE_ENV = "ALLOW_UNNAMED_REPO_PR"
MCP_CREATE = ("mcp__github__create_pull_request", "mcp__github__create_pull_request_with_copilot")
PREFILTER = re.compile(r"\b(?:gh|glab)\b")
LOOKS_LIKE_CREATE = re.compile(r"\b(?:gh\s+pr\s+(?:create|new)|glab\s+mr\s+(?:create|new)|gh\s+api\b.*pulls)\b", re.S)
PR_URL = re.compile(r"https?://[^\s/\"'<>]+/([\w.-]+(?:/[\w.-]+)*?)/(?:pull|-/merge_requests)/\d+")
PASTED = re.compile(r"<(system-reminder|pasted_content)\b[^>]*>.*?(?:</\1>|\Z)", re.S)
PULLS_ENDPOINT = re.compile(r"\A/?repos/([^/\s]+)/([^/\s]+)/pulls/?(?:\?.*)?\Z")
GH_API_VALUE_FLAGS = {"-X", "--method", "-H", "--header", "-f", "--raw-field", "-F", "--field",
                      "--input", "-q", "--jq", "-t", "--template", "--hostname", "-p",
                      "--preview", "--cache"}
GH_API_BODY_FLAGS = {"-f", "--raw-field", "-F", "--field", "--input"}
REPO_FLAGS = {"-R", "--repo"}
GH_REMOTE_ORDER = ("upstream", "github", "origin")
WRAPPER_WINDOW = 6


def _key(path):
    """`owner/repo`, lowercased, from a repository path; None when it has fewer than two parts."""
    parts = [p for p in (path or "").strip().strip("/").split("/") if p]
    if len(parts) < 2:
        return None
    repo = parts[-1][:-4] if parts[-1].lower().endswith(".git") else parts[-1]
    return f"{parts[-2]}/{repo}".lower() if repo else None


def url_path(url):
    """The repository path of a remote URL or a `-R` value (`[HOST/]OWNER/REPO` or a URL)."""
    url = (url or "").strip()
    m = re.match(r"\A[\w.+-]+://[^/]*/(.*)\Z", url) or re.match(r"\A[^/@\s]+@[^:/\s]+:(.*)\Z", url)
    return m.group(1) if m else url


def _remotes(directory):
    """{remote name: {"url": ..., "gh-resolved": ...}} for the checkout at `directory`."""
    try:
        out = subprocess.run(["git", "-C", directory, "config", "--get-regexp", r"^remote\..*\.(url|gh-resolved)$"],
                             capture_output=True, encoding="utf-8", timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    remotes = {}
    for line in out.splitlines():
        name, _, value = line.partition(" ")
        m = re.match(r"\Aremote\.(.+)\.(url|gh-resolved)\Z", name)
        if m:
            remotes.setdefault(m.group(1), {})[m.group(2)] = value.strip()
    return remotes


def gh_target(directory):
    """The repository key gh targets from the checkout at `directory`, or None.

    A remote marked `gh-resolved` (`gh repo set-default`) wins; otherwise the
    first of `upstream`, `github`, `origin`, then any other, as gh sorts them.
    """
    if not directory or not os.path.isdir(directory):
        return None
    remotes = _remotes(directory)
    for conf in remotes.values():
        resolved = conf.get("gh-resolved")
        if resolved:
            return _key(url_path(conf.get("url") if resolved == "base" else resolved))
    if not remotes:
        return None
    first = sorted(remotes, key=lambda n: GH_REMOTE_ORDER.index(n) if n in GH_REMOTE_ORDER else 99)[0]
    return _key(url_path(remotes[first].get("url")))


def home_repos(directory):
    """The session's own repositories: gh's target from `directory` and its `origin`."""
    if not directory or not os.path.isdir(directory):
        return set()
    origin = (_remotes(directory).get("origin") or {}).get("url")
    return {k for k in (gh_target(directory), _key(url_path(origin)) if origin else None) if k}


def _flag_value(args, flags):
    """The value of the last of `flags` in `args` (`-R x`, `-Rx`, `--repo=x`), or None."""
    value = None
    for i, tok in enumerate(args):
        for flag in flags:
            if tok == flag and i + 1 < len(args):
                value = args[i + 1]
            elif flag.startswith("--") and tok.startswith(flag + "="):
                value = tok[len(flag) + 1:]
            elif not flag.startswith("--") and tok.startswith(flag) and len(tok) > len(flag):
                value = tok[len(flag):]
    return value


def _gh_api_target(args, cur):
    """(target key or None, True) when `gh api` args POST to a pulls endpoint, else None."""
    endpoint, method, body, i = None, None, False, 0
    while i < len(args):
        tok = args[i]
        flag = tok.split("=", 1)[0] if tok.startswith("--") else tok[:2] if tok.startswith("-") else None
        if flag in GH_API_VALUE_FLAGS:
            attached = tok.startswith("--") and "=" in tok or not tok.startswith("--") and len(tok) > 2
            value = tok.split("=", 1)[1] if tok.startswith("--") and attached else tok[2:] if attached else (
                args[i + 1] if i + 1 < len(args) else "")
            if flag in ("-X", "--method"):
                method = value.upper()
            body = body or flag in GH_API_BODY_FLAGS
            i += 1 if attached else 2
            continue
        if not tok.startswith("-") and endpoint is None:
            endpoint = re.sub(r"\A(?:https?://[^/]+)", "", tok)
        i += 1
    m = PULLS_ENDPOINT.match(endpoint or "")
    if not m or (method or ("POST" if body else "GET")) != "POST":
        return None
    owner, repo = m.group(1), m.group(2)
    if "{" in owner or "{" in repo:
        return gh_target(cur), True
    return _key(f"{owner}/{repo}"), True


def _program(argv):
    """(argv from its gh or glab word on, the words before it), when a command runs one directly or
    under a wrapper (`timeout 60 gh ...`), else (None, [])."""
    for i, tok in enumerate(argv[:1 + WRAPPER_WINDOW]):
        if os.path.basename(tok) in ("gh", "glab"):
            lead = argv[:i]
            if all(ENV_ASSIGNMENT.match(t) for t in lead) or any(t in COMMAND_WRAPPERS for t in lead):
                return [os.path.basename(tok)] + argv[i + 1:], lead
            break
    return None, []


def creations(command, start):
    """[(target key or None, label, overridden)] for each PR creation in a Bash `command`."""
    found = []
    for depth, piece in enumerate(shell_c_expansions(command)):
        if not PREFILTER.search(piece):
            continue
        cmds = simple_commands_with_scope(piece)
        if cmds is None:
            if LOOKS_LIKE_CREATE.search(piece):
                found.append((None, "a command this hook could not parse", False))
            continue
        for argv, _env, _rest, cur in walk_dirs(cmds, start if depth == 0 else None):
            prog, lead = _program(argv)
            if not prog or len(prog) < 2:
                continue
            assigned = [t for t in lead if ENV_ASSIGNMENT.match(t)]
            overridden = env_value(assigned, OVERRIDE_ENV) == "1"
            if prog[0] == "gh" and prog[1] == "api":
                hit = _gh_api_target(prog[2:], cur)
                if hit:
                    found.append((hit[0], "`gh api .../pulls` (POST)", overridden))
                continue
            sub = ("pr", "mr")[prog[0] == "glab"]
            if len(prog) < 3 or prog[1] != sub or prog[2] not in ("create", "new"):
                continue
            label = f"`{prog[0]} {sub} create`"
            repo_env = "GH_REPO" if prog[0] == "gh" else "GITLAB_REPO"
            repo = _flag_value(prog[3:], REPO_FLAGS) or env_value(assigned, repo_env) or os.environ.get(repo_env)
            found.append((_key(url_path(repo)) if repo else gh_target(cur), label, overridden))
    return found


def _content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_content_text(b.get("text") if b.get("type") == "text" else b.get("content"))
                         for b in content if isinstance(b, dict))
    return ""


def read_session(path, prompt_text, user_bodies):
    """(user texts, prior PR repo keys, first record's cwd) from the transcript at `path`."""
    texts, prior, pending, first_cwd = [], set(), {}, None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            if first_cwd is None and isinstance(rec.get("cwd"), str):
                first_cwd = rec["cwd"]
            att = rec.get("attachment") or {}
            if isinstance(att, dict) and att.get("type") == "queued_command" \
                    and att.get("commandMode") != "task-notification" \
                    and (att.get("origin") or {}).get("kind") != "peer":
                texts.append(str(att.get("prompt") or ""))
                continue
            msg = rec.get("message")
            content = msg.get("content") if isinstance(msg, dict) else None
            if rec.get("type") == "assistant" and isinstance(content, list):
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                        continue
                    name, inp = b.get("name") or "", b.get("input") or {}
                    if name in MCP_CREATE:
                        pending[b.get("id")] = [_key(f"{inp.get('owner')}/{inp.get('repo')}")]
                    elif name == "Bash" and LOOKS_LIKE_CREATE.search(str(inp.get("command") or "")):
                        pending[b.get("id")] = []
                continue
            if rec.get("type") != "user":
                continue
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                        keys = pending.pop(b.get("tool_use_id"))
                        if not b.get("is_error"):
                            prior.update(k for k in keys if k)
                            prior.update(k for k in (_key(m) for m in PR_URL.findall(_content_text(b.get("content")))) if k)
            if rec.get("isMeta") or rec.get("isSidechain") or rec.get("isCompactSummary"):
                continue
            text = prompt_text(content)
            if text:
                texts.extend(b for b in user_bodies(text) if b.strip())
    return [PASTED.sub(" ", t) for t in texts if t.strip()], prior, first_cwd


def named(key, texts):
    """True when the bare name of repository `key` is a whole word in one of the user's `texts`."""
    bare = key.split("/")[-1]
    rx = re.compile(r"(?<![\w.-])" + re.escape(bare) + r"(?:\.git)?(?![\w-])(?!\.\w)", re.I)
    return any(rx.search(t) for t in texts)


def _targets(payload):
    """[(target key or None, label, overridden)] for the call, or [] when it creates no PR."""
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    if tool in MCP_CREATE:
        return [(_key(f"{inp.get('owner') or ''}/{inp.get('repo') or ''}"), f"`{tool}`", False)]
    if tool == "Bash":
        command = inp.get("command") or ""
        if isinstance(command, str) and PREFILTER.search(command):
            return creations(command, payload.get("cwd") or None)
    return []


def decide(payload):
    """(decision, text): decision in {"deny", "note", None}."""
    found = [t for t in _targets(payload) if not t[2]]
    if not found or os.environ.get(OVERRIDE_ENV) == "1":
        return None, ""
    tpath = payload.get("transcript_path") or payload.get("transcriptPath")
    sweep = load_sibling(__file__, "no-unrequested-sweep-pr.py")
    why = None
    try:
        if sweep is None:
            why = "its helper `no-unrequested-sweep-pr.py` could not be loaded"
        elif not isinstance(tpath, str) or not os.path.isfile(tpath):
            why = "the session transcript could not be read"
        else:
            user_bodies, _typed = sweep.load_user_bodies()
            texts, prior, first_cwd = read_session(tpath, sweep.prompt_text, user_bodies)
            if not texts:
                why = "the transcript holds no message the user wrote (a subagent's own transcript?)"
    except Exception as exc:  # noqa: BLE001 -- reported in the note, never silent
        why = f"reading the transcript failed ({exc})"
    if why:
        return "note", (f"no-unnamed-repo-pr: this call opens a PR, and {why}, so the hook could not check "
                        "that the user named the target repository. Open it only in a repository the user "
                        "asked for (ai-config#5780).")
    home = home_repos(first_cwd or payload.get("cwd") or "")
    unresolved, denied = [], []
    for key, label, _ in found:
        if key is None:
            unresolved.append(label)
        elif not (key in home or key in prior or named(key, texts)):
            denied.append((key, label))
    if denied:
        repos = ", ".join(f"`{k}` ({label})" for k, label in denied)
        home_txt = ", ".join(f"`{h}`" for h in sorted(home)) or "none found"
        return "deny", (
            "MECHANISTIC PROHIBITION: no PR in a repository the user never named (ai-config#5780). "
            "Ezra, 2026-11-17: \"never broaden your scope like that again without my direct "
            "instructions; this counts as an unauthorized sweep.\"\n\n"
            f"    Target: {repos}.\n\n"
            "No message the user wrote this session names it, it is not the session's own checkout "
            f"({home_txt}), and no PR was opened in it earlier this session. \"We did similar things in X\" "
            "is precedent, not a request.\n\n"
            "Ask the user whether they want a PR in that repository, and wait for the answer. If they "
            "already asked in words this hook cannot see (a relay, an earlier session), quote that message "
            f"in the PR body and re-run the creation as one Bash command prefixed with {OVERRIDE_ENV}=1, "
            f"for example `{OVERRIDE_ENV}=1 gh api repos/<owner>/<repo>/pulls -f title=... -f head=... "
            "-f base=main -F body=@body.md`; an MCP call cannot carry the prefix. Do not export it.")
    if unresolved:
        return "note", ("no-unnamed-repo-pr: could not tell which repository " + ", ".join(unresolved)
                        + " targets, so it was not checked against the repositories the user named "
                        "(ai-config#5780). Pass `-R <owner>/<repo>` so the target is explicit.")
    return None, ""


def _read_payload():
    args = sys.argv[1:]
    dry = "--dry-run" in args or "--simulate" in args
    positional = [a for a in args if not a.startswith("--")]
    if dry and positional:
        try:
            return json.loads(positional[0]), True
        except ValueError:
            return {"tool_name": "Bash", "tool_input": {"command": positional[0]}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), dry
    except Exception as exc:  # noqa: BLE001
        print(f"no-unnamed-repo-pr: unreadable hook input ({exc})", file=sys.stderr)
        return {}, dry


def main():
    payload, dry = _read_payload()
    if not payload:
        return 0
    try:
        decision, text = decide(payload)
    except Exception as exc:  # noqa: BLE001 -- fail open, but say so
        decision, text = "note", f"no-unnamed-repo-pr: the check failed ({exc}); it did not run (ai-config#5780)."
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if decision == "deny":
        out["hookSpecificOutput"]["permissionDecision"] = "deny"
        out["hookSpecificOutput"]["permissionDecisionReason"] = text
    elif decision == "note":
        out["hookSpecificOutput"]["additionalContext"] = text
        out["systemMessage"] = text
    elif not dry:
        return 0
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
