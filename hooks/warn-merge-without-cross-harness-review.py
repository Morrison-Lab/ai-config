#!/usr/bin/env python3
"""PreToolUse warning: a merge with no cross-harness reviewer run since the last push.

## The failure this exists for

`shared/workflow/adversarial-self-review.md` ("Cross-model and cross-harness
reviews are required for merging") requires a merge verdict from a reviewer
whose model AND harness both differ from the authoring session's. An
`Agent`-dispatched subagent and the CI `claude-review` workflow are both
Claude, so neither qualifies.

Nothing enforced it. `no-unauthorized-merge.py` checks authorization and
`warn-merge-without-fully-clean.py` checks the fully-clean instrument; both
pass a merge whose every reviewer was Claude. ai-config#3099 records two such
merges on 2026-09-02 (PDT), and the same miss recurred on 2026-10-08, when nine
ai-config PRs were merged from a remote container with Claude reviewers only
before the gap was noticed.

## The condition

    the call merges a PR or arms auto-merge
        (`gh pr merge`, `gh api -X PUT .../pulls/N/merge`,
         `mcp__github__merge_pull_request`, `mcp__github__enable_pr_auto_merge`)
    AND NOT  this session's transcript holds, after the last push, a
             non-sidechain Bash call whose result is not an error and in
             which a simple command's command word is one of the CLIs in
             CROSS_HARNESS_CLIS, minus this session's own harness, with a
             first argument that is not a housekeeping one (NON_REVIEW_ARGS:
             `--version`, `--help`, `login`, `auth`, ...).

A skill (`dtc`, `dto`, `adv`) is not credited by being loaded: loading one
runs nothing. Its reviewer CLI call, which is a Bash call, is what counts.

Merge recognition reuses `_gh_merge` and push recognition reuses `_events`,
`_push_before_merge` and `MCP_PUSH_TOOLS` from
`warn-merge-without-fully-clean.py`, so the two merge warnings cannot disagree
about what a merge or a push is. The sibling's strict `check && merge` chain
discharge is deliberately NOT reused: passing the fully-clean instrument says
nothing about who reviewed.

## What it cannot see, and why it warns rather than denies

* The INVOCATION is decidable; the VERDICT is not. A run that returned
  "needs more work" discharges this hook. It answers "was the gate even
  attempted", which is the question both recorded misses failed;
  `check-pr-fully-clean.py` and `warn-merge-without-fully-clean.py` own
  the verdict.
* A multi-backend harness (`opencode`, `cursor-agent`) qualifies only when
  its configured model also differs. The model is a config file away, not on
  the command line, so the hook takes the harness as the signal.
* The session's own harness is read from the environment: Antigravity when
  `ANTIGRAVITY_AGENT` is set, Claude Code otherwise. Under another harness
  (Codex, OpenCode, Gemini CLI) that default is wrong: its own CLI would be
  credited and `claude` excluded.
* A review run in another session or by a human is invisible here.
* `nohup` and `timeout` are looked through, but a reviewer launched from a
  script (`dtc`'s background `nohup bash "$WORK/run.sh" &`) is not: the
  command word is `bash`, and the script's contents are not in the
  transcript. The foreground `codex exec ...` form is credited.
* `gemini` and `cursor-agent` are credited although the gate fragment's
  ladder does not list them as active yet: a successful run of either in
  the transcript is itself the probe that ladder is waiting on.

Each is a false-silence or a false-warning a deny would turn into an escape-
variable reflex, so this warns, like its sibling. It never blocks, and fails
open on any internal error.
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))

# Reviewer CLIs, one per harness. The session's own harness is removed at run
# time, so `claude` counts only from a non-Claude session.
CROSS_HARNESS_CLIS = frozenset({
    "codex", "opencode", "agy", "gemini", "cursor-agent", "claude",
})
# A first argument that makes the invocation housekeeping, not a review.
NON_REVIEW_ARGS = frozenset({
    "-v", "-V", "--version", "version", "-h", "--help", "help",
    "login", "logout", "auth", "config", "mcp", "update", "upgrade",
    "install", "models",
})
# `timeout` options that take a separate argument (`-s KILL`, `-k 5`).
TIMEOUT_ARG_OPTS = frozenset({"-s", "--signal", "-k", "--kill-after"})
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Both spellings of the MCP auto-merge tool are in use: this server exposes
# `enable_pr_auto_merge`, while enforce-mwc-review-gate.py expects
# `enable_pull_request_auto_merge`. Match both, as no-unauthorized-merge.py does.
RX_AUTO_MERGE_TOOL = re.compile(
    r"^mcp__github__enable_?(?:pull_?request_?|pr_)?auto_?merge$", re.I)
GATE = "shared/workflow/adversarial-self-review.md"

NOTE = (
    "[warn-merge-without-cross-harness-review] {target}: this session's "
    "transcript shows no cross-harness reviewer run since the last push. "
    "The merge gate in " + GATE + " ('Cross-model and cross-harness reviews "
    "are required for merging') needs a verdict from a reviewer whose model "
    "AND harness both differ from this session's. An Agent subagent and the "
    "CI claude-review workflow are both Claude and do not qualify. Run one "
    "of {clis} (for example through the dtc or dto skill) on the shipping "
    "head first. If no qualifying reviewer is reachable here, the gate's own "
    "answer is that the merge waits for a human or a differently-provisioned "
    "session (ai-config#3099)."
)


def _sibling():
    path = os.path.join(HERE, "warn-merge-without-fully-clean.py")
    spec = importlib.util.spec_from_file_location("_sib_wmwfc", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def own_harness():
    """The CLI name of the harness running this hook (see the docstring)."""
    if os.environ.get("ANTIGRAVITY_AGENT"):
        return "agy"
    return "claude"


def _argvs(sib, command):
    for line in sib.shell_c_expansions(command):
        for argv in sib.simple_commands(line) or []:
            yield sib.strip_env(argv)[1]


def _peel_wrappers(rest):
    """Drop leading `nohup` and `timeout [opts] DURATION` from an argv."""
    while rest:
        word = os.path.basename(rest[0])
        if word == "nohup":
            rest = rest[1:]
        elif word == "timeout":
            rest = rest[1:]
            while rest and rest[0].startswith("-"):
                takes_arg = rest[0] in TIMEOUT_ARG_OPTS
                rest = rest[2:] if takes_arg else rest[1:]
            rest = rest[1:]  # the duration
        else:
            return rest
    return rest


def _is_reviewer(rest, clis):
    rest = _peel_wrappers(rest)
    return (len(rest) > 1 and os.path.basename(rest[0]) in clis
            and rest[1] not in NON_REVIEW_ARGS)


def _shell_events(sib, command, clis):
    """Ordered events in *command*: 'push' or 'review', by text position."""
    events = []
    for line in sib.shell_c_expansions(command):
        for argv in sib.simple_commands(line) or []:
            parsed = sib.git_subcommand(argv)
            if parsed and parsed[0] == "push":
                events.append("push")
            # strip_env peels `timeout` but not its options and duration, so
            # also test the raw argv with leading assignments dropped.
            raw = list(argv)
            while raw and ENV_ASSIGNMENT.match(raw[0]):
                raw = raw[1:]
            if (_is_reviewer(sib.strip_env(argv)[1], clis)
                    or _is_reviewer(raw, clis)):
                events.append("review")
    return events


def scan(sib, path, clis):
    """Return (last_push_seq, [seq of successful reviewer calls]).

    A push and a review in ONE command are ordered by their position in the
    text, as the sibling orders a push and an instrument run: the push counts
    at seq - 0.5, a review after it at seq, a review before it at seq - 1.
    """
    last_push = -1
    pending = {}
    reviews = []
    for seq, rec in enumerate(sib.records(path)):
        for b in sib._blocks(rec):
            kind = b.get("type")
            if kind == "tool_use":
                name = b.get("name")
                if name in sib.MCP_PUSH_TOOLS:
                    last_push = max(last_push, seq)
                    continue
                cmd = (b.get("input") or {}).get("command")
                if name not in sib.SHELL_TOOLS or not isinstance(cmd, str):
                    continue
                try:
                    events = _shell_events(sib, cmd, clis)
                    pushes = [i for i, e in enumerate(events) if e == "push"]
                    if pushes:
                        last_push = max(last_push, seq - 0.5)
                    runs = [i for i, e in enumerate(events) if e == "review"]
                    if runs and not rec.get("isSidechain"):
                        fresh = not pushes or max(runs) > max(pushes)
                        pending[b.get("id")] = seq if fresh else seq - 1
                except Exception:
                    continue
            elif kind == "tool_result" and b.get("tool_use_id") in pending:
                seq_used = pending.pop(b["tool_use_id"])
                if not b.get("is_error"):
                    reviews.append(seq_used)
    return last_push, reviews


def _targets(sib, tool, tool_input):
    """[(number|None, repo|None)] for every merge this call performs."""
    if tool == sib.MCP_MERGE_TOOL or RX_AUTO_MERGE_TOOL.match(tool):
        return sib._merge_targets(sib.MCP_MERGE_TOOL, tool_input)
    command = (tool_input.get("command") or tool_input.get("CommandLine")
               or tool_input.get("cmd") or tool_input.get("script"))
    if not isinstance(command, str):
        return []
    return [hit for hit in map(sib._gh_merge, _argvs(sib, command)) if hit]


def main() -> int:
    try:
        sib = _sibling()
        if sib.simple_commands is None:
            return 0
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    if (tool not in sib.SHELL_TOOLS and tool != sib.MCP_MERGE_TOOL
            and not RX_AUTO_MERGE_TOOL.match(tool)):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload.get("toolInput")
    if not isinstance(tool_input, dict):
        return 0
    path = payload.get("transcript_path") or ""
    try:
        targets = _targets(sib, tool, tool_input)
        if not targets or not path or not os.path.isfile(path):
            return 0
        clis = CROSS_HARNESS_CLIS - {own_harness()}
        last_push, reviews = scan(sib, path, clis)
        if tool in sib.SHELL_TOOLS and sib._push_before_merge(
                tool_input.get("command") or ""):
            reviews = []
    except Exception:
        return 0
    if any(seq > last_push for seq in reviews):
        return 0

    num, _repo = targets[0]
    target = f"PR #{num}" if num is not None else "This merge"
    note = NOTE.format(target=target, clis=", ".join(sorted(clis)))
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "additionalContext": note}}
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Merging {target} with no cross-model, cross-harness review "
            f"since the last push ({GATE}).")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
