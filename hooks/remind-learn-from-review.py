#!/usr/bin/env python3
"""UserPromptSubmit reminder: an ACCEPTED reviewer finding owes a learning.

Standing goal (Morrison-Lab/ai-config#1065): "every PR gets a clean review on
the first push -- learn from your mistakes so you don't repeat them, and
algorithmatize whenever possible". A reviewer's valid finding is a first-push
miss, so accepting one is a learn-from-mistakes trigger in its own right. This
file is that goal applied at the boundary where it is decidable.

WHY THE EXISTING HOOKS DO NOT COVER THIS
----------------------------------------
`remind-ums-after-error.py` and `no-mistake-without-a-hook.py` both key on a
FIRST-PERSON admission ("I was wrong", "my mistake"), and the former's
docstring is explicit that correcting SOMEONE ELSE must never fire it. Agreeing
with a reviewer is the commoner case and the one they miss by construction: you
admit nothing, you accept a finding. So the whole learn-from-mistakes
machinery -- record the learning, consider a mechanism -- never engages for the
mistakes a reviewer catches, which is exactly the class #1065 is about.

The condition is decidable from the transcript, which is why this is a hook
rather than a rule to remember:

    an acceptance of a reviewer's finding  AND  review context nearby
    AND  no learning, mechanism, or one-off judgment recorded after it

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Identical to `remind-ums-after-error.py`, and for the same reason. Accepting a
reviewer's finding and fixing it is RIGHT to do; blocking that would suppress a
correct action. Only the FOLLOW-UP is owed. So this fires on the next prompt
and can only ever ADD context -- there is no code path here that suppresses,
delays, or alters a message.

WHAT DISCHARGES IT, AND WHY THE FIX ITSELF DOES NOT
---------------------------------------------------
The trap this hook is built around (ai-config#1075 review): in THIS repo the
fix for a review finding usually edits `shared/`, `skills/`, `CLAUDE.md`, or
`memories/` -- ~49% of tracked files. So a plain write to one of those paths
cannot tell a recorded *lesson* from the ordinary *fix* the reviewer asked
for, and treating it as a discharge makes the reminder silent in exactly its
home repo. Fixing what the reviewer flagged is definitionally not learning from
it. So a bare corpus write does NOT discharge; the signal has to be explicit:

  * LEARNING -- an explicit `ums` / record-learnings / memorize / "update
    memories" action, or a subagent dispatched to run one (UMS_WORD in a
    Bash/Task/Agent/Skill call). Reused from the sibling so the two cannot
    drift on what counts as a learning pass.
  * MECHANISM -- a WRITE (not a read) to a hook or CI file: `hooks/*.py`,
    `hooks.json`, `install-hooks.py`, or `.github/workflows/`. Gated to
    write-type tools, because Reading or grepping such a path builds nothing.
  * ONE-OFF -- an explicit statement that the finding has no rule or hook
    behind it. Forcing a mechanism onto a genuine one-off produces a guard
    that misfires and gets switched off (see `algorithmatize-checks`'s
    "Limits"), so saying so is a valid discharge. The pattern is deliberately
    narrow: it must read as declining to encode ("one-off", "no rule would
    have caught this"), not as routine PR-status prose ("no check is failing",
    "already tracked in #N").

Erring toward OVER-firing (a spurious advisory reminder) is deliberate: a
missed reminder is silent and loses the lesson, while a spurious one costs one
line the reader can dismiss by naming what they recorded.

REVIEW CONTEXT MUST BE NEARBY, NOT MERELY EARLIER
-------------------------------------------------
"You're right" is also said to the USER. A session-sticky "some review happened
once" flag misclassifies any later agreement as accepting a finding
(ai-config#1075 review). So an acceptance counts only when a review signal --
a review-surface tool call, or the word review/reviewer/finding/nit/copilot/
jules/claude-review -- appears in the acceptance message itself or within a few
records of it.

Fires once per distinct acceptance (sentinel keyed by content hash), and fails
OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# How near (in transcript records) a review signal must sit to an acceptance
# for that acceptance to count as accepting a *reviewer's* finding rather than
# agreeing with the user about something else. Small on purpose: in the ARD
# flow you reply to or resolve the thread in the same stride as accepting it.
REVIEW_WINDOW = 6


def _sibling(name):
    """Import a hyphenated sibling module, or None if unavailable."""
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location("_sib", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_ums = _sibling("remind-ums-after-error.py")

# Reuse the sibling's prose cleaner and its learning-word detection so the two
# hooks cannot drift on what counts as a recorded learning. Fallbacks exist
# only so this degrades to silence rather than crashing if the sibling is
# missing -- they must never become a second, divergent copy. NOTE: the
# sibling's UMS_PATH (a plain corpus-file write) is deliberately NOT reused as
# a discharge here -- see the docstring, "the fix itself does not discharge".
visible_prose = getattr(_ums, "visible_prose", lambda t: t)
# The fallback must stay byte-identical in behaviour to the sibling's own
# UMS_WORD, including its path guard: `\b` matched inside
# `cat shared/workflow/run-ums-proactively.md`, so a READ discharged this
# reminder too (ai-config#1965). See that sibling for why `.` is excluded only
# when a word character follows it.
# A leading `/` needs splitting apart, because it plays two roles. In a
# PATH (`skills/ums`, `./ums-helper`) it is a separator and must block
# the match; as a slash-COMMAND (`/ums`, `/memorize`) it is how this
# corpus spells the invocation, and blocking that loses a real
# discharge. What separates them is the character BEFORE the slash: a
# path has a word character or a dot there, an invocation has
# whitespace or nothing. So reject `/` only in that context.
# (Review finding on ai-config#1968: the first spelling, `(?<![\\w/-])`,
# rejected both, silently dropping `/ums` as a discharge.)
_NOT_PATH = r"(?<![\w-])(?<![\w.]/)"
_NOT_PATH_END = r"(?![\w/-]|\.\w)"

# `update\s+memories` is the one alternative left unguarded, and deliberately.
# It cannot match a path, because the hyphen form (`update-memories-and-skills`,
# the skill alias) has no whitespace in it. What it CAN match is
# `update memories/git.md` in a dispatch prompt -- which is a genuine UMS
# instruction, so a `_NOT_PATH_END` here would cost a true positive rather
# than removing a false one. The guard is applied where the word alone is
# ambiguous, not everywhere it would parse.
UMS_WORD = getattr(
    _ums, "UMS_WORD",
    re.compile(
        _NOT_PATH + r"ums" + _NOT_PATH_END +
        r"|update\s+memories"
        r"|" + _NOT_PATH + r"record[- ]learnings" + _NOT_PATH_END +
        r"|" + _NOT_PATH + r"memorize" + _NOT_PATH_END,
        re.I))

# Accepting a reviewer's finding. Deliberately the AGREEMENT vocabulary only: a
# Rebut ("the review is wrong") is the opposite disposition and must never fire
# this. Every alternative anchors a trailing word boundary so "good pointer",
# "valid pointer", etc. do not match (ai-config#1075 review).
ACCEPT = re.compile(
    r"""(
      good\s+catch\b
    | nice\s+catch\b
    | great\s+catch\b
    | you(?:'re|\s+are)\s+right\b
    | (?:the\s+)?review(?:er)?(?:'s|\s+is)\s+right\b
    | (?:that|this)(?:'s|\s+is)\s+(?:a\s+)?(?:correct|valid|fair|good)\s+
        (?:catch|point|finding|call|concern)\b
    | (?:valid|fair)\s+(?:point|concern|finding|catch)\b
    | (?:good|fair)\s+point\b
    | the\s+finding\s+is\s+(?:correct|right|valid)\b
    | (?:agreed|correct),?\s+(?:the\s+)?review(?:er)?\b
    )""",
    re.I | re.X,
)

# Review context. A review-surface tool call, or the review vocabulary in prose
# (including an incoming <github-webhook-activity> review record).
REVIEW_TOOL = re.compile(
    r"resolve_review_thread|add_reply_to_pull_request_comment|"
    r"add_comment_to_pending_review|pull_request_review_write|"
    r"get_review_comments|get_reviews|request_copilot_review|"
    r"gh\s+pr\s+review|/pulls/\d+/(comments|reviews)",
    re.I,
)
REVIEW_WORD = re.compile(
    r"\breview(?:er)?\b|\bfinding\b|\bnit\b|\bcopilot\b|\bjules\b|claude-review",
    re.I,
)

# A hook or CI file, matched ONLY against a write-type tool's file_path -- a
# mechanism built from the finding. A Read/Grep touching such a path builds
# nothing and must not discharge (ai-config#1075 review).
MECH_PATH = re.compile(
    r"hooks/[\w.-]+\.py|hooks\.json|install-hooks\.py|\.github/workflows/", re.I)

# An explicit judgment that the finding is not a learnable pattern. Narrow on
# purpose: it must read as declining to encode, not as routine PR-status prose.
# "no check is failing", "already tracked in #N", and "no rule about this, so I
# added one" must NOT match (ai-config#1075 review).
NOT_ENCODABLE = re.compile(
    r"\bone[- ]off\b|"
    r"not\s+worth\s+(?:a\s+)?(?:rule|hook|check|encoding|recording|mechaniz\w*)|"
    r"not\s+(?:a\s+)?(?:generaliz\w*|mechaniz\w*|hookab\w*)|"
    r"not\s+a\s+recurring\s+(?:pattern|mistake)|"
    r"no\s+(?:rule|hook|check|mechanism|guard)\s+(?:would|could)\s+"
        r"(?:have\s+)?(?:caught|prevented|helped|fired)|"
    r"could\s?n(?:o|')t\s+have\s+(?:known|caught|been\s+caught)|"
    r"already\s+(?:covered|encoded)\s+by\b",
    re.I,
)


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(path):
    """Return (accept_text, accept_at, discharge_at).

    accept_at is the index of the last acceptance sitting within REVIEW_WINDOW
    records of a review signal; -1 if none. discharge_at is the last index
    carrying an explicit learning, a mechanism write, or a one-off judgment.
    """
    accept_txt, accept_at, discharge_at = None, -1, -1
    last_review_at = -10 ** 9  # far in the past, so nothing is "near" it yet

    for i, m in enumerate(records(path)):
        # A subagent's own turns are not my outgoing message; skip them the way
        # the sibling does.
        if m.get("isSidechain"):
            continue

        # A review signal anywhere in this record -- a review-surface tool call
        # or the review vocabulary (covers an incoming webhook review record as
        # well as my own prose). json.dumps gives a cheap whole-record view.
        raw = json.dumps(m)
        if REVIEW_TOOL.search(raw) or REVIEW_WORD.search(raw):
            last_review_at = i

        tool_calls = []
        text_blocks = []

        is_assistant = m.get("type") == "assistant" or m.get("role") == "assistant"
        blocks = (m.get("message") or {}).get("content") or m.get("content") or []
        if isinstance(blocks, list):
            for b in blocks:
                if isinstance(b, dict):
                    if b.get("type") == "tool_use":
                        tool_calls.append((b.get("name") or "", b.get("input") or {}))
                    elif b.get("type") == "text" and is_assistant:
                        text_blocks.append(b.get("text") or "")
        elif isinstance(blocks, str) and is_assistant:
            text_blocks.append(blocks)

        if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
            content = m.get("content")
            if isinstance(content, str):
                text_blocks.append(content)
            elif isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        text_blocks.append(b.get("text") or "")
                    elif isinstance(b, str):
                        text_blocks.append(b)
            for tc in m.get("tool_calls") or []:
                if isinstance(tc, dict):
                    tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                    targs = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                    if isinstance(targs, str):
                        try:
                            targs = json.loads(targs)
                        except Exception:
                            targs = {"command": targs}
                    tool_calls.append((tname, targs if isinstance(targs, dict) else {}))

        for name, inp in tool_calls:
            if not isinstance(inp, dict):
                inp = {}
            if name in ("Write", "Edit", "NotebookEdit", "write", "edit", "write_to_file", "replace_file_content"):
                target = str(inp.get("file_path") or inp.get("path") or inp.get("TargetFile") or inp.get("target_file") or "")
                if MECH_PATH.search(target):
                    discharge_at = i
                continue
            if name in ("Task", "Agent", "invoke_subagent"):
                blob = str(inp.get("prompt") or inp.get("Prompt") or "") + str(inp.get("description") or "")
            elif name in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
                blob = str(inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or "")
            elif name == "Skill":
                blob = str(inp.get("skill", "")) + str(inp.get("args", ""))
            else:
                blob = ""
            if blob and UMS_WORD.search(blob):
                discharge_at = i

        for raw_text in text_blocks:
            prose = visible_prose(raw_text)
            if not prose.strip():
                continue
            if NOT_ENCODABLE.search(prose):  # ONE-OFF judgment
                discharge_at = i
            hit = ACCEPT.search(prose)
            if hit and (i - last_review_at) <= REVIEW_WINDOW:
                accept_txt, accept_at = hit.group(0).strip(), i

    return accept_txt, accept_at, discharge_at


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    # A non-dict payload is valid JSON but has no .get -- guard it so the hook
    # keeps its "fails open and silent" promise (ai-config#1075 review).
    if not isinstance(payload, dict):
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        accept_txt, accept_at, discharge_at = scan(path)
    except Exception:
        return 0  # fail open

    if accept_at < 0:
        return 0
    # `>=` rather than `>`: a single message can both accept the finding and
    # record the learning (or judge it a one-off), and that is the ideal case.
    # Recording strictly BEFORE the acceptance does not discharge it.
    if discharge_at >= accept_at:
        return 0

    key = hashlib.sha256(f"{path}:{accept_txt}:{accept_at}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-learn-from-review-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(
        "[hook: remind-learn-from-review] You accepted a reviewer's finding "
        f"earlier in this session (\"{accept_txt}\") and recorded no learning "
        "or mechanism after it.\n\n"
        "Standing goal (Morrison-Lab/ai-config#1065): every PR gets a clean "
        "review on the first push -- so a reviewer's valid finding is a "
        "first-push miss to learn from, not just an item to fix and close. "
        "Fixing it discharges the PR; it does not discharge the lesson, and the "
        "two feel identical from the inside. Note that the fix itself does not "
        "count: editing the shared/skills/CLAUDE.md file the reviewer flagged "
        "is the fix, not the lesson.\n\n"
        "This is the external-correction case hooks/remind-ums-after-error.py "
        "misses by construction: it keys on a first-person admission (\"I was "
        "wrong\"), and here you agreed with someone else instead.\n\n"
        "Do two things beyond the fix (see "
        "shared/workflow/learn-from-review-findings.md):\n"
        "  1. Record the class of mistake -- what you overlooked and what the "
        "reviewer saw. Run an explicit UMS pass, or delegate it to a subagent "
        "as pre-authorized sidecar work.\n"
        "  2. Ask whether it is algorithmatizable "
        "(shared/workflow/algorithmatize-checks.md): a finding with a decidable "
        "condition -- a banned token, a stale cross-reference, a missing test "
        "-- is one a pre-push check or a hook can catch every time thereafter, "
        "so the next reviewer never has to.\n\n"
        "If the finding is a genuine one-off (a typo, a fact you could not have "
        "known, a judgment call), say so explicitly and why -- that discharges "
        "this as completely as recording it. What this catches is the silent "
        "third option: fix it, resolve the thread, and record nothing.\n\n"
        "This only ever adds context; it never blocks. Accepting a finding is "
        "right -- only the follow-up is owed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
