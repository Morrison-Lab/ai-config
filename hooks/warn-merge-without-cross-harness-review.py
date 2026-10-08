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
             non-sidechain call that invoked a cross-harness reviewer and
             whose result is not an error:
               * a Bash command whose command word is one of the CLIs in
                 CROSS_HARNESS_CLIS, minus this session's own harness; or
               * a Skill call naming one of CROSS_HARNESS_SKILLS.

Merge recognition (command position via `scripts/lib/shellcmd.py`, so an
echoed or heredoc'd merge is inert) and push detection are imported from
`warn-merge-without-fully-clean.py` rather than re-derived, so the two merge
warnings cannot disagree about what a merge or a push is.

## What it cannot see, and why it warns rather than denies

* The INVOCATION is decidable; the VERDICT is not. A run that returned
  "needs more work" discharges this hook. It answers "was the gate even
  attempted", which is the question both recorded misses failed;
  `check-pr-fully-clean.py` and `warn-merge-without-fully-clean.py` own
  the verdict.
* A multi-backend harness (`opencode`, `cursor-agent`) qualifies only when
  its configured model also differs. The model is a config file away, not on
  the command line, so the hook takes the harness as the signal.
* A review run in another session or by a human is invisible here.

Each is a false-silence or a false-warning a deny would turn into an escape-
variable reflex, so this warns, like its sibling. It never blocks, and fails
open on any internal error.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))

# Reviewer CLIs by harness. Every entry here is a harness other than Claude
# Code's; `claude` is listed so a non-Claude session reviewing through it
# still counts.
CROSS_HARNESS_CLIS = frozenset({
    "codex", "opencode", "agy", "gemini", "cursor-agent", "claude",
})
# Skills that dispatch to a cross-harness reviewer CLI.
CROSS_HARNESS_SKILLS = frozenset({
    "adv", "agy-review-workflow", "delegate-to-codex", "dtc",
    "delegate-to-opencode", "dto", "delegate-to-databricks",
})
AUTO_MERGE_TOOL = "mcp__github__enable_pr_auto_merge"
SKILL_TOOLS = frozenset({"Skill", "skill"})
GATE = "shared/workflow/adversarial-self-review.md"

NOTE = (
    "[warn-merge-without-cross-harness-review] {target}: this session's "
    "transcript shows no cross-harness reviewer run since the last push. "
    "The merge gate in " + GATE + " ('Cross-model and cross-harness reviews "
    "are required for merging') needs a verdict from a reviewer whose model "
    "AND harness both differ from this session's. An Agent subagent and the "
    "CI claude-review workflow are both Claude and do not qualify. Run one "
    "of {clis} (or the dtc/dto/adv skills) on the shipping head first. If no "
    "qualifying reviewer is reachable here, the gate's own answer is that "
    "the merge waits for a human or a differently-provisioned session "
    "(ai-config#3099)."
)


def _sibling():
    path = os.path.join(HERE, "warn-merge-without-fully-clean.py")
    spec = importlib.util.spec_from_file_location("_sib_wmwfc", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def own_harness():
    """The CLI name of the harness running this hook."""
    if os.environ.get("ANTIGRAVITY_AGENT"):
        return "agy"
    return "claude"


def _reviewer_call(sib, block, clis):
    """True when a tool_use block invokes a cross-harness reviewer."""
    name = block.get("name")
    inp = block.get("input") or {}
    if name in SKILL_TOOLS:
        skill = str(inp.get("skill") or inp.get("name") or "").lstrip("/")
        return skill.split(":")[-1] in CROSS_HARNESS_SKILLS
    if name not in sib.SHELL_TOOLS:
        return False
    cmd = inp.get("command")
    if not isinstance(cmd, str):
        return False
    for line in sib.shell_c_expansions(cmd):
        for argv in sib.simple_commands(line) or []:
            _env, rest = sib.strip_env(argv)
            if rest and os.path.basename(rest[0]) in clis:
                return True
    return False


def scan(sib, path, clis):
    """Return (last_push_seq, [seq of successful reviewer calls])."""
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
                if name in sib.SHELL_TOOLS and isinstance(cmd, str):
                    try:
                        if any(e is None for e in sib._events(cmd)):
                            last_push = max(last_push, seq)
                    except Exception:
                        pass
                if rec.get("isSidechain"):
                    continue
                try:
                    if _reviewer_call(sib, b, clis):
                        pending[b.get("id")] = seq
                except Exception:
                    continue
            elif kind == "tool_result" and b.get("tool_use_id") in pending:
                seq_used = pending.pop(b["tool_use_id"])
                if not b.get("is_error"):
                    reviews.append(seq_used)
    return last_push, reviews


def _targets(sib, tool, tool_input):
    if tool == AUTO_MERGE_TOOL:
        return sib._merge_targets(sib.MCP_MERGE_TOOL, tool_input)
    return sib._merge_targets(tool, tool_input)


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
    if tool not in sib.SHELL_TOOLS and tool not in (sib.MCP_MERGE_TOOL,
                                                    AUTO_MERGE_TOOL):
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
