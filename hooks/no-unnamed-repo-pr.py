#!/usr/bin/env python3
"""PreToolUse deny: no PR in a repository the user never named (ai-config#5780).

- Denies the MCP create_pull_request tools, `gh pr create|new` and `glab mr create|new` when the target
  (`-R`/`--repo`, a `GH_REPO`/`GITLAB_REPO` prefix or environment value, else gh's pick in the command's
  directory) is neither home (gh's pick in the first transcript `cwd`) nor named: a whole word in a
  message the user wrote (`no-unrequested-sweep-pr.py`'s helpers; reminders and pastes dropped,
  slash-command args and queued messages kept). Override: `ALLOW_UNNAMED_REPO_PR=1` in the hook's
  own environment only. Fails open with a note: unreadable transcript, no user message, unresolved target.
- Allowed with no user message naming it: a repo the project configures ("Repositories configured for this
  project:" in the first prompt) or one the coordinator's relay `<note>` in the first prompt names (Ezra,
  2026-11-18, decision card "Allow project and named repos"). Only the first prompt counts.
- A verified decision-card tap counts as the user's words: the card's question, the chosen option and its
  consequence (scripts/lib/card_answer.py, ai-config#5839); a declining option counts for nothing.
- Also denies `gh api repos/<o>/<r>/pulls` and `glab api projects/<o>%2F<r>/merge_requests` sent as POST
  (explicit method or a body flag), and notes `gh api graphql` `createPullRequest` (node id; ai-config#5784 part A).
- Known limits: a repo named only as precedent passes; new-branch pushes are not guarded (a push opens
  no PR); `git push` and the MCP branch-write tools are ai-config#5784 part B.
"""
import functools
import html
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
import card_answer  # noqa: E402

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


def _glab_globals(prog):
    """`prog` with glab's root flags (root.go) handled: -R/--repo move to just after the subcommand words,
    --help/-h and --version/-v are dropped. A moved -R stays before any later flag or `--`, so pflag's
    last-value-wins still holds.
    """
    rest, moved = prog[1:], []
    while prog[0] == "glab" and rest[:1] and re.match(r"\A(?:-R.*|--repo(?:=.*)?|--help|--version|-h|-v)\Z", rest[0]):
        flag, n = rest[0], 2 if rest[0] in ("-R", "--repo") else 1
        moved += rest[:2] if n == 2 else ["-R", flag[2:].removeprefix("=")] if flag.startswith("-R") else (
            [flag] if flag.startswith("--repo=") else [])
        rest = rest[n:]
    k = 2 if rest[:1] == ["mr"] else 1
    return prog[:1] + rest[:k] + moved + rest[k:] if prog[0] == "glab" and rest != prog[1:] else prog


def _program(argv):
    """(argv from its gh or glab word on, the assignments before it), or (None, [])."""
    while argv and argv[0] in SHELL_KEYWORDS:
        argv = argv[1:]
    for i, tok in enumerate(argv[:7]):
        if os.path.basename(tok) in REPO_ENV:
            lead = argv[:i]
            if all(ENV_ASSIGNMENT.match(t) for t in lead) or any(t in COMMAND_WRAPPERS for t in lead):
                return _glab_globals([os.path.basename(tok)] + argv[i + 1:]), [t for t in lead if ENV_ASSIGNMENT.match(t)]
            break
    return None, []


# Flag tables derived from the tools, not recalled (ai-config#5784, 2026-11-18).
# gh 2.89.0 (2026-03-26), `gh api --help`. Value flags: --cache, -F/--field, -H/--header, --hostname, --input, -q/--jq,
#   -X/--method, -p/--preview, -f/--raw-field, -t/--template. Boolean: -i/--include, --paginate, --silent, --slurp,
#   --verbose, --help. gh api has NO -R/--repo (it exits "unknown shorthand flag" before any request); placeholders
#   `{owner}`, `{repo}`, `{branch}` come from GH_REPO, else the current directory.
# glab (not installed here): gitlab-org/cli docs/source/api/_index.md (fetched 2026-11-18 through a summarising
#   fetcher) and internal/commands/api/api.go (read by the round-5 reviewer, 2026-11-18). Value flags:
#   -F/--field, --form, -H/--header, --hostname, --input, -X/--method, --output, --placeholder,
#   -f/--raw-field. Boolean: -i/--include, --paginate, --silent, -h/--help. api.go's `Placeholders` list starts
#   with the compound tokens `:group/:namespace/:repo` and `:namespace/:repo`, each ONE url-escaped segment.
#   Global -R/--repo falls back to GITLAB_REPO: internal/cmdutils/repo_override.go `ApplyRepoOverride`, applied
#   by `AddGlobalRepoOverride`. The hook keys a repo by its last two path segments, as `_key` does everywhere.
# A flag in neither table is unknown: the tokenizer stops its cluster there and every positional is tested.
API_VALUE_FLAGS = {"-X": "method", "--method": "method", "-f": "body", "-F": "body", "--field": "body",
                   "--raw-field": "body", "--input": "body", "--form": "body", "-R": "repo", "--repo": "repo",
                   "--output": "", "--placeholder": "", "-H": "", "--header": "", "-q": "", "--jq": "", "-t": "",
                   "--template": "", "--hostname": "", "--cache": "", "-p": "", "--preview": ""}
API_BOOL_FLAGS = {"-i", "--include", "--paginate", "--silent", "--slurp", "--verbose", "-h", "--help"}
COMPOUND_PLACEHOLDERS = (":group/:namespace/:repo", ":namespace/:repo")  # longest first


def api_tokens(args):
    """(positionals, [(flag, value)] of value flags, unknown flags): pflag's argv rules for `gh|glab api`.

    A short cluster is read one character at a time: a boolean continues it, a value flag takes the rest of
    the cluster (minus one leading `=`) or the next argument, an unknown one ends it. `--` ends the flags.
    """
    positionals, flags, unknown, i = [], [], [], 0
    while i < len(args):
        arg, i = args[i], i + 1
        if arg == "--":
            positionals, i = positionals + args[i:], len(args)
        elif not arg.startswith("-") or arg == "-":
            positionals.append(arg)
        elif arg.startswith("--"):
            flag, eq, val = arg.partition("=")
            if flag in API_VALUE_FLAGS and not eq:
                val, i = (args[i] if i < len(args) else ""), i + 1
            flags += [(flag, val)] if flag in API_VALUE_FLAGS else []
            unknown += [flag] if flag not in API_VALUE_FLAGS and flag not in API_BOOL_FLAGS else []
        else:
            for k, ch in enumerate(arg[1:], 1):
                flag = "-" + ch
                if flag in API_VALUE_FLAGS:
                    val = arg[k + 1:].removeprefix("=") if arg[k + 1:] else (args[i] if i < len(args) else "")
                    i += not arg[k + 1:]
                    flags.append((flag, val))
                    break
                if flag not in API_BOOL_FLAGS:
                    unknown.append(flag)
                    break
    return positionals, flags, unknown


def api_request(args):
    """(positionals, is_post, body flags, -R/--repo value, unknown flags) of a `gh|glab api` command."""
    positionals, flags, unknown = api_tokens(args)
    kinds = [(API_VALUE_FLAGS[f], f, v) for f, v in flags]
    methods = [v.upper() for k, _, v in kinds if k == "method"]
    bodies = [(f, v) for k, f, v in kinds if k == "body"]
    repos = [v for k, _, v in kinds if k == "repo"]
    post = bool(bodies) if not methods else None if re.search(r"[$`]", methods[-1]) else methods[-1] == "POST"  # None: unreadable
    return positionals, post, bodies, (repos or [None])[-1], unknown


def api_parts(endpoint):
    """Path segments of an API endpoint: no query, fragment, host, empty segment or leading `api/vN` prefix."""
    url = "://" in (endpoint or "")
    path = urlsplit(endpoint).path if url else re.split(r"[?#]", endpoint or "", 1)[0]
    for compound in COMPOUND_PLACEHOLDERS:
        path = path.replace(compound, ":fullpath")
    parts = [x for x in path.split("/") if x]
    # A prefix counts at the start, or anywhere in an absolute URL if a real API root follows (repo `api/v3` survives).
    for i in range(len(parts) - 1):
        versioned = parts[i] == "api" and parts[i + 1] in ("v3", "v4") and parts[i + 2:i + 3] in (["repos"], ["projects"], ["graphql"])
        if (url or i == 0) and (versioned or parts[i:i + 2] == ["api", "graphql"]):
            return parts[i + 2:] if versioned else parts[i + 1:]
    return parts


def unreadable_body(bodies):
    """True when a GraphQL body comes from a file, an `@file` field or a shell substitution."""
    return any(flag == "--input" or "$(" in val or "`" in val
               or (flag in ("-F", "--field") and val.partition("=")[2].startswith("@")) for flag, val in bodies)


def api_kind(prog, endpoint):
    """("graphql" | "rest" | None, path segments) for an endpoint of `gh api` or `glab api`."""
    parts = api_parts(endpoint)
    rest = ((prog == "gh" and len(parts) == 4 and parts[0] == "repos" and parts[3] == "pulls")
            or (prog == "glab" and len(parts) == 3 and parts[0] == "projects" and parts[2] == "merge_requests"))
    return ("graphql" if parts == ["graphql"] else "rest" if rest else None), parts


CREATION_SHAPES = (("repos", None, None, "pulls"), ("projects", None, "merge_requests"), ("graphql",))  # None: any segment


MAX_EXPANSION_PARTS = 64  # far above any real API path; bounds fits()'s recursion, which grows with the input


def expands(parts):
    """True when a shell expansion in `parts` could stand for any number of segments (`R=owner/name`, or none)
    so that the path becomes a creation endpoint; a literal segment no shape allows (`issues`) rules it out."""
    hole = [bool(re.search(r"[$`]", x)) for x in parts]
    if hole.count(False) > max(map(len, CREATION_SHAPES)):  # each literal segment needs its own shape segment
        return False
    if len(parts) > MAX_EXPANSION_PARTS:
        return any(hole)  # too long to match exactly: note, the fail-open direction

    @functools.lru_cache(maxsize=None)
    def fits(shape, i, j):
        if i == len(shape):
            return all(hole[j:])
        if j == len(parts):
            return False
        if hole[j]:
            return fits(shape, i, j + 1) or fits(shape, i + 1, j)
        return shape[i] in (None, parts[j]) and fits(shape, i + 1, j + 1)
    return any(hole) and any(fits(shape, 0, 0) for shape in CREATION_SHAPES)


def api_creation(prog, cur, lead, elsewhere):
    """[(target key or None, label)] when `gh api`/`glab api` args in `prog` create a PR or MR.

    Error direction (ai-config#5784, algorithmatize-checks): fail open, as the rest of this hook does.
    Deny only when the target resolves offline and is unnamed. A target we cannot read (a numeric
    GitLab project, a GraphQL node id, a GraphQL body from `--input`, `-F key=@file` or a `$(...)`
    substitution, a repo variable set elsewhere in the line, an unrecognised flag that may hide the
    endpoint) is a note, never a deny, and a request that is not provably a POST passes silently.
    """
    positionals, post, bodies, flag_repo, unknown = api_request(prog[2:])
    endpoint = (positionals or [None])[0]
    kind, parts = api_kind(prog[0], endpoint)
    label = f"`{prog[0]} api {endpoint}`"
    if post is None and kind == "rest":
        return [(None, f"{label} (could not read the method)")]
    if post is not False and expands(parts):
        return [(None, f"{label} (could not read the endpoint)")]
    odd = [(None, f"{label} (unrecognised flag `{f}`)") for f in unknown[:1]]
    hidden = [(None, f"`{prog[0]} api {p}` (an unrecognised flag may hide the method or endpoint)")
              for p in positionals[1:] if unknown and api_kind(prog[0], p)[0]][:1]
    if kind == "graphql":
        mutation = "createPullRequest" if prog[0] == "gh" else "mergeRequestCreate"
        if any(mutation in val for _, val in bodies):
            return [(None, f"`{prog[0]} api graphql` {mutation} (the target is a node id or path we cannot read)")]
        return [(None, f"`{prog[0]} api graphql` (could not read the GraphQL body; it may create a PR)")] * unreadable_body(bodies) or odd
    if kind != "rest":
        return hidden
    if not post:
        return odd + hidden
    elems = parts[1:3] if prog[0] == "gh" else unquote(parts[1]).split("/")
    fills = {"{owner}": 0, "{repo}": 1, ":namespace": 0, ":group": 0, ":repo": 1, ":id": 2, ":fullpath": 2}
    fills.update({":owner": 0} if prog[0] == "gh" else {})
    if any(x.startswith(":") and x not in fills for x in elems):
        return [(None, f"{label} (an unknown placeholder)")]
    if not any(x in fills for x in elems):
        return [(_key("/".join(elems)) if len(elems) > 1 else None, label)]
    # -R/--repo wins, then a prefix assignment, then the environment; both CLIs read their variable the same
    # way (GH_REPO documented by gh, GITLAB_REPO via repo_override.go). A variable set elsewhere is a note.
    var = REPO_ENV[prog[0]]
    repo = flag_repo or env_value(lead, var)
    if not repo and elsewhere:
        return [(None, f"{label} ({var} set elsewhere in the line)")]
    key = _key(repo or os.environ.get(var)) if (repo or os.environ.get(var)) else gh_target(cur)
    if not key:
        return [(None, label)]
    values = (*key.rsplit("/", 1), key)  # namespace, project, full path
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
    """(texts the user wrote, first record's cwd, first prompt) from the transcript at `path`."""
    texts, prompts, first_cwd, cards_pending, cards, card_texts, first = [], [], None, {}, {}, [], None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = dict(json.loads(line))
            except (ValueError, TypeError):
                continue
            first_cwd = first_cwd or (rec.get("cwd") if isinstance(rec.get("cwd"), str) else None)
            # The cloud spawn prompt (project context + coordinator brief) is recorded with isMeta set, so the
            # brief is read from the first user record of any kind (ai-config#5839; #5830 read only non-meta ones).
            if first is None and rec.get("type") == "user" and not rec.get("isSidechain") \
                    and isinstance(rec.get("message"), dict):
                first = prompt_text(rec["message"].get("content")) or ""
            att = rec.get("attachment") if isinstance(rec.get("attachment"), dict) else {}
            if att.get("type") == "queued_command" and att.get("commandMode") != "task-notification" \
                    and (att.get("origin") or {}).get("kind") != "peer":
                prompts.append(str(att.get("prompt") or ""))
                card_texts += card_answer.answers_in_record(rec, cards)  # a tap that arrived mid-turn
            msg = rec.get("message")
            if not rec.get("isSidechain"):
                card_answer.track_cards(rec, cards_pending, cards)
            if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain") \
                    or rec.get("isCompactSummary") or not isinstance(msg, dict):
                continue
            prompts.append(prompt_text(msg.get("content")) or "")
            card_texts += card_answer.answers_in_record(rec, cards)
    for text in (PASTED.sub(" ", p) for p in prompts):  # a typed slash command's args, else the user's bodies
        texts += (re.findall(r"<command-args>(.*?)</command-args>", text, re.S)
                  if re.match(r"\s*<command-(?:message|name)>", text) else user_bodies(text) if text.strip() else [])
    # A card answer counts through card_answer (verified, declines dropped, consequence added), not as raw text.
    texts = [t for t in texts if t.strip() and not card_answer.CHOSE.match(html.unescape(t))] + card_texts
    return texts, first_cwd, first if first is not None else (prompts[:1] or [""])[0]


PROJECT_REPOS = re.compile(r"Repositories configured for this project:[ \t]*\n((?:[ \t]*-[ \t]*\S+[ \t]*(?:\n|\Z))+)", re.I)
RELAY_NOTE = re.compile(r"<relay\b[^>]*\bfrom=\"coordinator\"[^>]*>.*?<note>(.*?)</note>", re.S)


def brief_scope(first_prompt):
    """(repo keys the project configures, texts of the coordinator's brief) from the session's FIRST prompt.

    Ezra, 2026-11-18 (decision card, ai-config#5780 follow-up): a thread may open PRs in the project's
    configured repos and in any repo the ask or the coordinator's brief names. Only the first prompt counts:
    a later message carrying the same markup is not the harness's spawn message.
    """
    text = html.unescape(first_prompt or "")
    listed = PROJECT_REPOS.search(text)
    lines = listed.group(1).splitlines() if listed else []
    keys = {k for k in (_key(line.strip().lstrip("-").strip()) for line in lines) if k}
    return keys, [m.group(1) for m in RELAY_NOTE.finditer(text)]


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
        texts, first_cwd, first, err = *read_session(tpath, sweep.prompt_text, sweep.load_user_bodies()[0]), ""
    except Exception as exc:  # noqa: BLE001 -- reported in the note
        texts, first_cwd, first, err = [], None, "", f" ({exc})"
    project, brief = brief_scope(first)
    texts = texts + brief
    if not texts:
        return "note", ("no-unnamed-repo-pr: this opens a PR, and no message the user wrote could be read from the "
                        f"transcript{err}; open it only in a repo the user named (ai-config#5780).")
    home = gh_target(first_cwd or payload.get("cwd"))
    denied = [f"`{k}` ({label})" for k, label in found if k and k != home and k not in project and not named(k, texts)]
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
