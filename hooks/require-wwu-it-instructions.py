#!/usr/bin/env python3
"""PreToolUse DENY: cluster-job work before the WWU CS IT instructions have been read.

Ezra, 2026-11-04 02:42 UTC (lds project thread, cai): "you must always follow
WWU CS IT's instructions exactly unless I say otherwise". The instructions on
record are in `memories/wwu-cs-it-instructions.md`. On 2026-11-03 and 04 a
session built and repaired `condor-batch` (the CI route to the WWU clusters)
that copies the whole checkout to the NFS home and runs the job there,
against IT's advice to avoid heavy home-directory I/O and use HTCondor file
transfer. The advice sat in project memory; nothing made the session read it
before touching the job machinery, and it cleaned up around the home quota for
hours instead of asking why the jobs lived on the home at all.

A reminder was the first draft of this hook and Ezra refused it ("reminder is
not enough"): a warning is context a session reads past
(`block-merge-without-clean-checker.py`). So this DENIES.

WHAT IS DENIED
--------------
A tool call that touches cluster-job machinery, while the transcript holds no
read of `wwu-cs-it-instructions.md`:

  * Bash: a command naming an HTCondor tool (`condor_submit`, `condor_q`,
    `condor_rm`, `condor_wait`, `condor_history`, `condor_status`), a cluster
    head (`cse-head`, `csci-lab-head`, `csci-head`), `CLUSTER_CI_ROOT`, or
    `condor-batch`;
  * Write, Edit, MultiEdit: a file whose name has `condor` in it, a
    `cluster-*.yml` workflow, a `.sub` submit file, or whose new text names
    one of the Bash triggers above.

Files under `hooks/`, `memories/` and `shared/` are exempt, because they
quote these names to explain the rule (this file included).

DISCHARGE
---------
The session has READ `wwu-cs-it-instructions.md`: a Read tool call on a path
ending in that name, or a Bash command that names it (cat, sed, head and the
like). The deny reason prints the instructions in full, so the next call can
proceed on knowing them; reading the file is what records that the session
did.

WHAT THIS DOES NOT DO
---------------------
It cannot judge whether a design follows the instructions; that takes reading
them, which is the point of the gate. Ezra's own words lift the rule for the
one case he names, and the hook has no override variable: a gate with a
reflex escape stops being a gate.

Fails OPEN and SILENT when the payload, transcript path or transcript cannot
be read: a wedged session is worse than a missed gate, and the Stop-time
guards still apply.
"""
import json
import os
import re
import sys

INSTRUCTIONS = "wwu-cs-it-instructions.md"
EDIT_TOOLS = {"Write", "Edit", "MultiEdit"}

CLUSTER_RE = re.compile(
    r"(?<![\w-])(?:condor_(?:submit(?:_dag)?|q|qedit|rm|wait|history|status|hold|release|run|tail|ssh_to_job|transfer_data|reschedule|prio|userprio|dagman|fetchlog)|cse-head|csci-lab-head|csci-head|CLUSTER_CI_ROOT|condor-batch)(?![\w-])"
)
FILE_RE = re.compile(
    r"(?:(?:^|/)condor-batch(?:[^/]*$|/)|(?:^|/)cluster-[^/]*\.ya?ml$|\.sub$)", re.I)
READ_CMD_RE = re.compile(r"(?:^|[;&|(\s])(?:cat|bat|head|tail|less|more|sed|awk|grep|rg|nl|view)\s")
EXEMPT_RE = re.compile(r"(?:^|/)(?:hooks|memories|shared)/")

REASON = (
    "[hook: require-wwu-it-instructions] This call touches cluster-job "
    "machinery ({what}), and this session has not read "
    "`memories/wwu-cs-it-instructions.md`.\n\n"
    "Ezra, 2026-11-04 (cai): \"you must always follow WWU CS IT's instructions "
    "exactly unless I say otherwise\". Only his own words, naming the case, lift "
    "that. Convenience, speed and an existing design do not.\n\n"
    "The instructions on record:\n\n{body}\n\n"
    "Read `{path}` (it records that you did) and retry. If your change departs "
    "from any numbered item, stop and ask Ezra first, quoting the item."
)


def tool_uses(transcript_path):
    with open(transcript_path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else rec
            blocks = msg.get("content")
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield block


def has_read_instructions(transcript_path):
    for block in tool_uses(transcript_path):
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        name = block.get("name") or ""
        cmd = str(inp.get("command") or "")
        if name == "Read" and os.path.basename(str(inp.get("file_path") or "")) == INSTRUCTIONS:
            return True
        if name == "Bash" and INSTRUCTIONS in cmd and READ_CMD_RE.search(cmd):
            return True
    return False


def trigger(payload):
    """Return a short description of the cluster-job machinery touched, or None."""
    name = payload.get("tool_name")
    inp = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    if name == "Bash":
        hit = CLUSTER_RE.search(str(inp.get("command") or ""))
        return f"the command names `{hit.group(0)}`" if hit else None
    if name in EDIT_TOOLS:
        path = str(inp.get("file_path") or inp.get("path") or "")
        if FILE_RE.search(path):
            return f"the file `{os.path.basename(path)}`"
        if EXEMPT_RE.search(path):
            return None
        texts = [str(inp.get(k) or "") for k in ("content", "new_string")]
        for edit in inp.get("edits") or []:
            if isinstance(edit, dict):
                texts.append(str(edit.get("new_string") or ""))
        for text in texts:
            hit = CLUSTER_RE.search(text)
            if hit:
                return f"the new text names `{hit.group(0)}`"
    return None


def instructions_text():
    here = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(here, "..", "memories", INSTRUCTIONS)
    try:
        with open(path, encoding="utf-8") as fh:
            return os.path.normpath(path), fh.read().strip()
    except Exception:
        return f"memories/{INSTRUCTIONS}", "(the file could not be loaded here; read it from ai-config)"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        what = trigger(payload) if isinstance(payload, dict) else None
        if not what:
            return 0
        transcript = payload.get("transcript_path")
        if not isinstance(transcript, str) or not os.path.isfile(transcript):
            return 0
        if has_read_instructions(transcript):
            return 0
    except Exception:
        return 0
    path, body = instructions_text()
    reason = REASON.format(what=what, body=body, path=path)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": reason,
        },
        "systemMessage": "Blocked: read the WWU CS IT instructions before touching cluster-job machinery.",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
