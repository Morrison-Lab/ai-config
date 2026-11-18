#!/usr/bin/env python3
"""PreToolUse deny: no PR in a repository the user never named (ai-config#5780).

- Denies the MCP create_pull_request tools, `gh pr create|new` and `glab mr create|new` when the target
  (`-R`/`--repo`, a `GH_REPO`/`GITLAB_REPO` prefix or environment value, else gh's pick in the command's
  directory) is neither home (gh's pick in the first transcript `cwd`) nor named: a whole word in a
  message the user wrote (`no-unrequested-sweep-pr.py`'s helpers; reminders and pastes dropped,
  slash-command args and queued messages kept). Override: `ALLOW_UNNAMED_REPO_PR=1` in the hook's
  own environment only. Fails open with a note: unreadable transcript, no user message, unresolved target.
- Also denies `gh api repos/<o>/<r>/pulls` and `glab api projects/<o>%2F<r>/merge_requests` sent as POST
  (explicit method, or implied by a body flag), and notes `gh api graphql` with `createPullRequest`, whose
  target is a node id (ai-config#5784 part A).
- Known limits: a repo named only as precedent passes; new-branch pushes are not guarded (a push opens
  no PR); `git push` and the MCP branch-write tools are ai-config#5784 part B.
"""
import json
import os
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

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


# Flag tables derived from the tools, not recalled (ai-config#5784, 2026-11-18).
# gh 2.89.0 (2026-03-26), `gh api --help`. Value flags: --cache, -F/--field, -H/--header, --hostname, --input,
#   -q/--jq, -X/--method, -p/--preview, -f/--raw-field, -t/--template. Boolean: -i/--include, --paginate,
#   --silent, --slurp, --verbose, --help. gh api has NO -R/--repo (it exits "unknown shorthand flag" before
#   any request); placeholders `{owner}`, `{repo}`, `{branch}` come from GH_REPO, else the current directory.
# glab (not installed here): gitlab-org/cli docs/source/api/_index.md, fetched 2026-11-18 through a summarising
#   fetcher. Value flags: -F/--field, --form, -H/--header, --hostname, --input, -X/--method, --output,
#   --placeholder, -f/--raw-field. Boolean: -i/--include, --paginate, --silent, -h/--help. Placeholders:
#   :branch :fullpath :group :id :namespace :repo :user :username. glab's global -R/--repo is not in that page;
#   it is read as a value flag so its value is never mistaken for the endpoint.
# A flag in neither table is unknown: it is never the endpoint, and a creation endpoint gets a note.
API_VALUE_FLAGS = {"-X": "method", "--method": "method", "-f": "body", "-F": "body", "--field": "body",
                   "--raw-field": "body", "--input": "body", "--form": "body", "-R": "repo", "--repo": "repo",
                   "--output": "", "--placeholder": "", "-H": "", "--header": "", "-q": "", "--jq": "", "-t": "",
                   "--template": "", "--hostname": "", "--cache": "", "-p": "", "--preview": ""}
API_BOOL_FLAGS = {"-i", "--include", "--paginate", "--silent", "--slurp", "--verbose", "-h", "--help"}


def api_request(args):
    """(endpoint, is_post, body flags [(flag, value)], -R/--repo value, unknown flags) of a `gh|glab api`."""
    endpoint, method, bodies, repo, unknown, i = None, None, [], None, [], 0
    while i < len(args):
        arg = args[i]
        flag, val = (arg.split("=", 1) if arg.startswith("--") and "=" in arg else
                     (arg[:2], arg[2:].removeprefix("=")) if arg[:2] in API_VALUE_FLAGS and not arg.startswith("--")
                     and len(arg) > 2 else (arg, None))
        i += 1
        if flag in API_VALUE_FLAGS and val is None:
            val, i = (args[i] if i < len(args) else ""), i + 1
        kind = API_VALUE_FLAGS.get(flag)
        method = val.upper() if kind == "method" else method
        repo = val if kind == "repo" else repo
        bodies += [(flag, val)] if kind == "body" else []
        unknown += [flag] if arg.startswith("-") and flag not in API_VALUE_FLAGS and flag not in API_BOOL_FLAGS else []
        endpoint = endpoint or (arg if not arg.startswith("-") else None)
    return endpoint, (method == "POST" if method else bool(bodies)), bodies, repo, unknown


def api_parts(endpoint):
    """Path segments of an API endpoint, without query string, host, empty segments or an `api/v3|v4` prefix."""
    url = "://" in (endpoint or "")
    parts = [x for x in (urlsplit(endpoint).path if url else re.split(r"[?#]", endpoint or "", 1)[0]).split("/") if x]
    cut = [i for i in range(len(parts) - 1) if parts[i] == "api" and parts[i + 1] in ("v3", "v4")]
    # Strip the prefix only at the path's start, or after one host path prefix of an absolute URL, so a repo
    # literally named api/v3 survives.
    lead_ok = cut and (cut[0] == 0 or (url and cut[0] == 1 and parts[0] not in ("repos", "projects")))
    return parts[cut[0] + 2:] if lead_ok else parts


def unreadable_body(bodies):
    """True when a GraphQL body comes from a file, an `@file` field or a shell substitution."""
    return any(flag == "--input" or "$(" in val or "`" in val
               or (flag in ("-F", "--field") and val.partition("=")[2].startswith("@")) for flag, val in bodies)


def api_creation(prog, cur, lead, elsewhere):
    """[(target key or None, label)] when `gh api`/`glab api` args in `prog` create a PR or MR.

    Error direction (ai-config#5784, algorithmatize-checks): fail open, as the rest of this hook does.
    Deny only when the target resolves offline and is unnamed. A target we cannot read (a numeric
    GitLab project, a GraphQL node id, a GraphQL body from `--input`, `-F key=@file` or a `$(...)`
    substitution, a repo variable set elsewhere in the line) is a note, never a deny, and a request
    that is not provably a POST (GET reads) passes silently.
    """
    endpoint, post, bodies, flag_repo, unknown = api_request(prog[2:])
    parts = api_parts(endpoint)
    label = f"`{prog[0]} api {endpoint}`"
    odd = [(None, f"{label} (unrecognised flag `{f}`)") for f in unknown[:1]]
    if parts == ["graphql"]:
        mutation = "createPullRequest" if prog[0] == "gh" else "mergeRequestCreate"
        if any(mutation in val for _, val in bodies):
            return [(None, f"`{prog[0]} api graphql` {mutation} (the target is a node id or path we cannot read)")]
        return [(None, f"`{prog[0]} api graphql` (could not read the GraphQL body; it may create a PR)")] * unreadable_body(bodies) or odd
    gh_rest = prog[0] == "gh" and len(parts) == 4 and parts[0] == "repos" and parts[3] == "pulls"
    glab_rest = prog[0] == "glab" and len(parts) == 3 and parts[0] == "projects" and parts[2] == "merge_requests"
    if not (gh_rest or glab_rest):
        return []
    if not post:
        return odd
    elems = parts[1:3] if gh_rest else unquote(parts[1]).split("/")
    fills = {"{owner}": 0, "{repo}": 1, ":namespace": 0, ":group": 0, ":repo": 1,
             ":id": 2, ":fullpath": 2}
    fills.update({":owner": 0} if prog[0] == "gh" else {})
    if any(x.startswith(":") and x not in fills for x in elems):
        return [(None, f"{label} (an unknown placeholder)")]
    if not any(x in fills for x in elems):
        return [(_key("/".join(elems)) if len(elems) > 1 else None, label)]
    # -R/--repo wins. Else the repo variable: GH_REPO is documented for gh placeholders; glab's docs do not say
    # whether GITLAB_REPO fills them, so any GITLAB_REPO gets a note rather than a trusted value.
    var = REPO_ENV[prog[0]]
    repo = flag_repo or env_value(lead, var)
    if not repo and elsewhere:
        return [(None, f"{label} ({var} set elsewhere in the line)")]
    repo = repo or os.environ.get(var)
    if prog[0] == "glab" and not flag_repo and repo:
        return [(None, f"{label} ({var} is set and may fill the placeholders)")]
    key = _key(repo) if repo else gh_target(cur)
    if not key:
        return [(None, label)]
    own, name = key.split("/")
    values = (own, name, key)
    return [("/".join(values[fills[x]] if x in fills else x for x in elems).lower(), label)]


def creations(command, start):
    """[(target key or None, label)] for each PR creation in a Bash `command`."""
    found = []
    for depth, piece in enumerate(shell_c_expansions(command)):
        cmds = simple_commands_with_scope(piece)
        found += [(None, "an unparsed command")] if cmds is None and LOOKS_LIKE_CREATE.search(piece) else []
        assigns = [t for _, argv in cmds or [] for t in argv if re.match(r"\A(?:GH_REPO|GITLAB_REPO)=", t)]
        for argv, _env, _rest, cur in walk_dirs(cmds or [], start if depth == 0 else None):
            prog, lead = _program(argv)
            if prog and prog[1:2] == ["api"]:
                found += api_creation(prog, cur, lead, any(t not in lead for t in assigns))
                continue
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
