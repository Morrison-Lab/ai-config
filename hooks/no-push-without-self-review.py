#!/usr/bin/env python3
"""PreToolUse guard: require an adversarial self-review before `git push`.

Every self-review this corpus calls for is dispatched to a separate
`adversarial-reviewer` subagent rather than performed inline by the session
that wrote the diff (`shared/workflow/adversarial-self-review.md`). This guard
enforces the pre-push case.

WHAT COUNTS AS A VERDICT, AND WHY IT IS SO NARROW
-------------------------------------------------
Two independent questions have to be answered before a push is authorized, and
an earlier revision answered neither.

**WHO said it.** A transcript-wide search for the verdict phrase cannot work,
for the reason `no-handrolled-verdict-parse.py` documents (ai-config#1297):
this corpus quotes verdict vocabulary constantly, so a phrase search cannot
separate a verdict from a citation of one. Here it was self-defeating rather
than merely unsound -- a `PreToolUse` deny reason is surfaced back into the
transcript as the blocked call's result, so one blocked push authorized every
retry after it, and `Read`ing any of this repo's prose did the same. So a
verdict is admitted only from the `tool_result` of an `Agent` call whose
`subagent_type` IS the reviewer, and only when that result is not an error.

**WHAT it was about.** Provenance alone still lets one clean verdict authorize
unlimited later pushes of unrelated work. So the reviewer states the commit it
read, as a `Reviewed-Commit: <sha>` line, and this guard compares that against
the pushing repo's current `HEAD`. That comparison is what ties the permission
to the thing being pushed, and it subsumes every "the verdict went stale"
case without enumerating tool names: a push ships COMMITS, so anything that
changes what would be pushed -- an edit committed afterwards, a `main` merge, a
rebase, a commit made by a subagent in a transcript this guard cannot even see
-- moves `HEAD` and fails the comparison. Uncommitted working-tree changes are
not pushed and so do not matter.

It also closes the truncation hole: the reviewer emits the fingerprint AFTER
its verdict, so a report cut short carries no fingerprint and is refused rather
than read as clean.

CONSEQUENCES FOR HOW THE REVIEWER IS DISPATCHED
------------------------------------------------
Dispatch it in the FOREGROUND (`run_in_background: false`): a background
dispatch returns an agent id rather than a report, so no verdict ever becomes
that call's result. This is also the Agent tool's own criterion -- the push is
waiting on the answer.

Review AFTER committing, which is where `shared/workflow/ardi.md` already puts
the pause point. A review of uncommitted work is a review of a commit that does
not exist yet, so it can name no fingerprint this guard can check.

WHERE IT DELIBERATELY DOES NOT FIRE
------------------------------------
- `git push --dry-run` and `git push --delete` re-head nothing, so there is no
  diff to review (this is `no-unreviewed-pr.py`'s `_argv_push` rule, reused
  rather than re-derived).
- A command this guard cannot parse is treated as not-a-push. That is the same
  fail-open posture as `main()`'s bare `except`, stated rather than silent: a
  guard that crashed closed would block every push in the session.
- Pushing something other than `HEAD` (`git push origin other-branch`, a
  `HEAD~2:main` refspec) still requires a verdict naming `HEAD`, since this
  guard does not resolve refspecs. Those take the override.

Authorized overrides:
- `ALLOW_UNREVIEWED_PUSH=1` (env assignment prefix)
- `--allow-unreviewed-push` (flag outside quotes)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys

# --- verdict and reviewer identification ------------------------------------

# ONE pattern for BOTH verdicts, so a body carrying more than one is read
# left-to-right and the last match wins. Two separate searches cannot order
# their matches against each other, which is how a review that opens by quoting
# the blocking verdict it supersedes gets read as blocking.
VERDICT = re.compile(
    r"(?:###\s*Verdict|Verdict):\s*(?:\*\*)?(Ready for merge|Needs (?:more )?work)\b",
    re.I,
)

# The reviewer's statement of what it read. Emitted after the verdict, so a
# truncated report loses it first.
REVIEWED_COMMIT = re.compile(r"Reviewed-Commit:\s*`?([0-9a-f]{7,40})`?", re.I)

# Matched against an Agent/Task call's `subagent_type` ONLY. An earlier revision
# also matched the call's free-text `prompt`, which any prompt containing the
# word "adversarial" satisfied. A plugin-namespaced name (`ai-config:adversarial-
# reviewer`) is accepted, since the same persona is the same reviewer whichever
# surface registered it.
ADVERSARIAL_AGENT_NAME = re.compile(
    r"\A\s*(?:[\w.-]+[:/])?adversarial[-_ ]?reviewer\s*\Z", re.I
)

AGENT_TOOLS = {"agent", "task", "invoke_subagent"}

ALLOW_ENV_FLAG = re.compile(
    r"^\s*(?:(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)\s+)*"
    r"ALLOW_UNREVIEWED_PUSH=(?:\"1\"|'1'|1\b)"
)


# --- push detection ---------------------------------------------------------
#
# Reused from `no-unreviewed-pr.py` rather than re-derived. That module's
# `push_ident` is shell-parsed rather than regex-matched, so it already handles
# `git -C <dir> push` and `git -c k=v push`, and already excludes the two push
# forms that re-head nothing. A second hand-rolled detector would be a DRW
# finding and, worse, would diverge silently from this one
# (ai-config#1920).

def _load_sibling(name: str, filename: str):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    _SIBLING = _load_sibling("no_unreviewed_pr", "no-unreviewed-pr.py")
    push_ident = _SIBLING.push_ident
    _simple_commands = _SIBLING._simple_commands
except Exception:  # pragma: no cover -- sibling missing or unimportable
    _SIBLING = None
    push_ident = None
    _simple_commands = None


def _fallback_simple_commands(cmd: str):
    """Minimal stand-in used only if the sibling module cannot be loaded."""
    try:
        lex = shlex.shlex(cmd.replace("\n", ";"), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= set("|&;()<>"):
            if cur:
                cmds.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def simple_commands(cmd: str):
    fn = _simple_commands or _fallback_simple_commands
    return fn(cmd)


def _fallback_push_ident(cmd: str) -> bool:
    cmds = simple_commands(cmd)
    if cmds is None:
        return False
    for argv in cmds:
        if argv and argv[0] == "git" and "push" in argv[1:]:
            return True
    return False


def has_allow_override(command: str) -> bool:
    """True if the command carries an authorized override.

    Checked against the whole command rather than per-segment, because the
    override is a statement about the push the author is making, not about one
    link in a chain.
    """
    for seg in re.split(r"&&|\|\||;|\n", command):
        if ALLOW_ENV_FLAG.search(seg):
            return True
    cmds = simple_commands(command)
    if cmds:
        for argv in cmds:
            if "--allow-unreviewed-push" in argv:
                return True
    return False


def has_git_push(command: str) -> bool:
    detector = push_ident or _fallback_push_ident
    try:
        return bool(detector(command))
    except Exception:
        return False


def push_directory(command: str) -> str | None:
    """The `-C <dir>` of the pushing command, if it names one."""
    cmds = simple_commands(command)
    if not cmds:
        return None
    for argv in cmds:
        if not argv or argv[0] != "git":
            continue
        for i, tok in enumerate(argv[1:-1], start=1):
            if tok == "-C":
                return argv[i + 1]
    return None


# --- transcript reading -----------------------------------------------------

def _result_text(block: dict) -> str:
    """Flatten a tool_result block's payload into one searchable string.

    A subagent's report arrives as `content`, which is a plain string in some
    transports and a list of content blocks in others. Reading only one shape
    returns "" for the other, and an empty string is indistinguishable from a
    report that stated no verdict.
    """
    parts: list[str] = []
    content = block.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for sub in content:
            if isinstance(sub, str):
                parts.append(sub)
            elif isinstance(sub, dict):
                parts.append(str(sub.get("text") or sub.get("content") or ""))
    for key in ("output", "text"):
        val = block.get(key)
        if isinstance(val, str):
            parts.append(val)
    return "\n".join(p for p in parts if p)


def _iter_blocks(record: dict):
    message = record.get("message")
    blocks = message.get("content") if isinstance(message, dict) else record.get("content")
    if isinstance(blocks, str):
        blocks = [{"type": "text", "text": blocks}]
    elif not isinstance(blocks, list):
        blocks = []
    for b in blocks:
        if isinstance(b, dict):
            yield b


def read_latest_review(transcript_path: str) -> tuple[str | None, str | None, bool]:
    """(verdict, reviewed_commit, saw_reviewer_call) from the transcript.

    `verdict` is "clean", "needs_work", or None. Only the reviewer's own call
    results are consulted, and an errored result is skipped -- a failed or
    interrupted reviewer states no verdict, and `fail-fast` forbids letting that
    look identical to a clean one.
    """
    reviewer_call_ids: set[str] = set()
    saw_reviewer_call = False
    verdict: str | None = None
    reviewed_commit: str | None = None

    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue

            for b in _iter_blocks(record):
                b_type = b.get("type")

                if b_type == "tool_use":
                    if (b.get("name") or "").lower() not in AGENT_TOOLS:
                        continue
                    inp = b.get("input") or {}
                    sub_type = str(
                        inp.get("subagent_type")
                        or inp.get("subagentType")
                        or inp.get("agent_type")
                        or ""
                    )
                    if ADVERSARIAL_AGENT_NAME.match(sub_type):
                        saw_reviewer_call = True
                        call_id = b.get("id")
                        if isinstance(call_id, str) and call_id:
                            reviewer_call_ids.add(call_id)

                elif b_type == "tool_result":
                    if b.get("tool_use_id") not in reviewer_call_ids:
                        continue
                    if b.get("is_error"):
                        continue
                    text = _result_text(b)
                    found = VERDICT.findall(text)
                    if not found:
                        continue
                    verdict = (
                        "clean" if found[-1].lower().startswith("ready") else "needs_work"
                    )
                    sha = REVIEWED_COMMIT.search(text)
                    reviewed_commit = sha.group(1) if sha else None

    return verdict, reviewed_commit, saw_reviewer_call


def current_head(directory: str | None) -> str | None:
    args = ["git"]
    if directory:
        args += ["-C", directory]
    args += ["rev-parse", "HEAD"]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=8)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    sha = out.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None


def verify_review(transcript_path: str, directory: str | None) -> tuple[bool, str]:
    """(is_clean, reason) -- is there a current clean verdict for this HEAD?"""
    if not transcript_path or not os.path.exists(transcript_path):
        return False, "No transcript available to verify the adversarial self-review."

    try:
        verdict, reviewed_commit, saw_reviewer_call = read_latest_review(transcript_path)
    except Exception as e:
        return False, f"Failed reading transcript: {e}"

    if not saw_reviewer_call:
        return False, (
            "No `adversarial-reviewer` subagent was dispatched in this session.\n"
            "Dispatch it against your committed diff and address its findings before pushing."
        )

    if verdict is None:
        return False, (
            "An `adversarial-reviewer` subagent was dispatched, but no verdict came back "
            "as that call's own result.\n"
            "Dispatch it in the foreground (`run_in_background: false`) so its report "
            "returns as the tool result -- a background dispatch returns an agent id, "
            "which carries no verdict, and an errored result carries none either."
        )

    if verdict == "needs_work":
        return False, (
            "The latest adversarial self-review returned a blocking verdict.\n"
            "Address, rebut, or defer every finding, commit, and re-dispatch the reviewer."
        )

    head = current_head(directory)
    if head is None:
        return False, (
            "Could not resolve HEAD for the repository being pushed, so the clean "
            "verdict cannot be tied to the commits this push would ship."
        )

    if not reviewed_commit:
        return False, (
            "The clean verdict does not say which commit it read.\n"
            "The reviewer must end its report with `Reviewed-Commit: <sha>`; without it "
            "there is nothing tying the verdict to what this push would ship, and a "
            "report cut short before its fingerprint is not a verdict."
        )

    if not head.startswith(reviewed_commit.lower()):
        return False, (
            f"The clean verdict is for commit {reviewed_commit}, but HEAD is now "
            f"{head[:12]}.\n"
            "A push ships commits, so whatever moved HEAD -- a new commit, a `main` merge, "
            "a rebase -- is unreviewed. Re-dispatch the reviewer against the current HEAD."
        )

    return True, f"Clean adversarial self-review verified at {head[:12]}."


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if (payload.get("tool_name") or "") != "Bash":
            return 0

        cmd = (payload.get("tool_input") or {}).get("command") or ""
        if not cmd:
            return 0

        if not has_git_push(cmd) or has_allow_override(cmd):
            return 0

        is_clean, reason = verify_review(
            payload.get("transcript_path") or "", push_directory(cmd)
        )
        if is_clean:
            return 0

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"git push blocked by the pre-push self-review policy:\n{reason}\n\n"
                    "Standing rule: every self-review is an adversarial review by a "
                    "separate subagent. Dispatch `adversarial-reviewer` in the foreground "
                    "against your committed diff, address or rebut every finding, and let "
                    "its report state the commit it read.\n\n"
                    "Only that subagent's own result counts -- this message does not, and "
                    "neither does reading a file that quotes a verdict.\n\n"
                    "Override with `ALLOW_UNREVIEWED_PUSH=1` when no verdict can exist to "
                    "check: an initial empty PR branch (per pr-on-claim), a review "
                    "delivered by a separate CLI rather than a subagent, a session where "
                    "the reviewer agent is not registered, or an emergency. Say in your "
                    "reply that you used it and why."
                ),
            }
        }))
        return 0
    except Exception:
        # Fail open, deliberately and in the same direction as the parse-failure
        # rule above: a guard that crashed closed would block every push in the
        # session, which is a worse failure than missing one review.
        return 0


if __name__ == "__main__":
    sys.exit(main())
