#!/usr/bin/env python3
"""UserPromptSubmit reminder: a verdict read off a LOCAL sim run owes a CI cross-check.

A deterministic simulation is deterministic per (seed, platform, renderer
config) -- not across them. Hundreds of ticks of floating-point soldier-
collision physics compound differently on another platform, so a local run and
CI's transcript agree exactly for a long while and then diverge.

The consumer repo already teaches that, and scopes it to CAPTIONS and to
precise per-tick numbers quoted into comments. What no site said is that the
divergence is large enough to **invert a gating verdict**. Measured 2026-08-22
on `Lacaedemon/sparta`, one clip (`demos/inputs/relief-fighting-withdrawal.json`),
one seed, one commit: `uid0 overlap worst=1.611` locally -- a FAIL against a
2.25 threshold -- and `worst=2.432` on CI, a PASS. A decision was published off
the local number, and the local number was the wrong one.

WHY THIS IS NOT A ONE-OFF, AND SO IS WORTH MECHANIZING
------------------------------------------------------
`shared/principles/deterministic-tools.md` sets a third-occurrence bar. This
class is past it by the consumer repo's own dated case record, which lives in
that repo rather than in this one: `Lacaedemon/sparta`'s
`.claude/skills/sparta-demos/SKILL.md`, section "A precise-tick caption claim
on a LONG battle: verify against CI's own posted transcript, not a local
`dump-state.sh` run". It logs PR #794 (2026-07-12), then a recurrence paragraph
covering #861 and #866 (2026-07-15, both caught by a reviewer rather than by
the author), then #1199 (2026-08-05).

Those citations are deliberately given with their source document rather than
as bare PR numbers: this repo carries no case record for another repo's PRs,
so a reader grepping HERE for them finds nothing and cannot tell a real
citation from an invented one. Every one of them is about PROSE. The
2026-08-22 recurrence moved the same trap into a gating verdict, which is
strictly worse -- prose gets reviewed, a verdict gets acted on.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Modeled on `remind-ums-after-error.py`, not on `no-offer-to-file.py`, and the
distinction is load-bearing.

A `Stop` guard suppresses a message that is WRONG TO SEND. A local verdict is
not wrong to send. Reporting one while diagnosing, or quoting one explicitly
labelled local, is ordinary correct work -- what is wrong is *gating a decision*
on it without corroboration, and "gating a decision" has no lexical signature.
Blocking would also demand a remedy the model cannot supply inside the turn: a
CI answer is minutes away, so a blocked reply would stall on something no edit
can satisfy.

So this fires on the next prompt and only ever adds context. There is no code
path here that can suppress, delay, or alter a message.

MECHANISM
---------
Fires when all three hold:

  1. a Bash call ran one of the LOCAL sim/transcript tools;
  2. a LATER assistant message states a verdict-shaped figure;
  3. no CI-side read sits between the most recent local run BEFORE that
     message and the message itself.

Condition 3 is snapshotted **at the moment the claim is seen**, not read off
the end of the transcript. Comparing function-final values instead lets a
later, unrelated local run drag `local_at` past an already-discharged claim
and re-arm it -- an ordinary sequence (dump, read CI, report the CI figure,
dump again to keep investigating) that would then nag about a properly
grounded number.

Commands are split into simple commands with `shlex` before matching, the same
construction `no-clobbering-push.py` and `flag-reset-hard-uncommitted-work.py`
use. A free `search()` over the raw string reads inside quoted arguments, so
`gh pr comment --body "...via gh run view 123..."` would discharge the guard
without any CI read having happened -- the false-NEGATIVE direction, and the
one this hook exists to prevent. That is the same failure class README names
in its `require-gh-repo-flag.py` cautionary tale.

Fails OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SHELL_OPS = set("();|&")

# Local tools that produce sim state or judge it, none of which involve CI.
# Matched against a token, so a bare `godot` is deliberately absent -- it would
# fire on every unit-test run, and noise is what gets a guard switched off.
LOCAL_TOOL = re.compile(
    r"(^|/)(dump-state\.sh|dump-demo-states\.sh|analyze_transcript\.gd"
    r"|website-demo-defect-sweep\.sh|website-demo-defect-delta\.sh)$"
)
LOCAL_ENV = "SPARTA_DEMO_STATE"

# `gh api` paths that read what CI itself measured. `gh pr checks` is
# deliberately absent: it reports check STATE, never a verdict's numbers, so
# treating it as corroboration would discharge the obligation with nobody
# having looked at a CI-side figure -- the conflation `fully-clean.md` warns
# about when it says a green rollup is about CI state rather than review
# content.
CI_API_PATH = re.compile(
    r"check-runs|actions/(runs|jobs)|issues/comments|issues/\d+/comments"
    r"|pulls/\d+/comments"
)

# Verdict-shaped claims. Each alternative is a SHAPE the analyzer emits, not a
# bare number, so ordinary prose about counts cannot trip it.
VERDICT_CLAIM = re.compile(
    r"""(
      \bworst\s*=
    | \bnnd_(min|med)\b
    | \b\d+\s*/\s*\d+\s+verdicts\b
    | \b(PASS|FAIL|EXEMPT|STALE)\s+uid\d+
    | \b(overlap|blob|shape_residual|misslotted|path_crossing)\s*\(\s*uid\d+
    )""",
    re.X,
)

FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)


def visible_prose(text):
    """Drop code fences and blockquotes.

    A verdict table pasted into a fence is raw tool output being shown, not a
    claim made in the model's own voice, and quoting CI's own posted table is
    the behaviour this hook wants to encourage. Inline code is deliberately
    KEPT, unlike in `remind-ums-after-error.py`: a verdict quoted in prose is
    nearly always written as `worst=1.611`, so stripping backticks would blind
    the hook to its main case.
    """
    text = FENCE.sub(" ", text)
    return QUOTED.sub(" ", text)


def simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error.

    Same construction as `no-clobbering-push.py`'s `_simple_commands`.
    """
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = cmd.replace("\n", ";")
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


# Words that may precede the command itself, matching the sibling hooks'
# `LEAD_WORDS`. Kept alongside ASSIGNMENT so `GH_PAGER=cat gh run view ...` --
# the form `memories/gh-cli.md` mandates -- reaches the `gh` test below.
LEAD_WORDS = {"then", "do", "else", "!", "time", "sudo", "command", "exec",
              "nohup", "env"}


def _is_ci_read(argv):
    """True when this simple command actually READS CI state.

    Structural rather than textual: the markers are looked for among a `gh`
    command's own POSITIONAL arguments, so they cannot be matched inside a
    quoted body that a different `gh` subcommand is merely posting.

    Positional rather than fixed-index, which is the correction to a first
    attempt at this. Reading `argv[1]`/`argv[2]` directly is over-tight in two
    ways that both fire on the commonest spellings: an env prefix shifts the
    command word off index 0 (`GH_PAGER=cat gh run view`), and a flag before
    the path shifts the path off index 2 (`gh api --paginate <path>`). Both are
    real CI reads, so both failing to discharge nags on the happy path -- the
    exact false-positive the previous over-loose regex did not have. Trading
    one failure direction for the other is not a fix; skipping the prefix and
    the flags is.
    """
    if not argv:
        return False
    i = 0
    while i < len(argv) and (ASSIGNMENT.match(argv[i]) or argv[i] in LEAD_WORDS):
        i += 1
    if i >= len(argv):
        return False
    exe = argv[i]
    if exe != "gh" and not exe.endswith("/gh"):
        return False
    rest = argv[i + 1:]
    if len(rest) >= 2 and rest[0] == "run" and rest[1] == "view":
        return True
    # Scanned rather than read at a fixed index: `gh api --paginate <path>` and
    # `gh api <path> --paginate` are the same read, and the path is at a
    # different offset in each. A flag-stripping pass was tried here first and
    # removed -- no test could make it bite, since this scan already finds the
    # path wherever it sits, and a clause no test justifies is one to drop.
    if rest and rest[0] == "api":
        return any(CI_API_PATH.search(t) for t in rest[1:])
    return False


def _is_local_run(argv):
    """True when this simple command runs a local sim/transcript tool.

    Scans every token rather than only the command word, so `bash
    tools/check.sh ...`, `godot ... -s tools/demo/analyze_transcript.gd`, and a
    leading `SPARTA_DEMO_STATE_FULL=1` all match. A tool name appearing inside
    a quoted argument would over-arm the guard, which costs one reminder --
    the safe direction, unlike the CI side where over-matching costs the miss.
    """
    if not argv:
        return False
    if any(LOCAL_TOOL.search(t) for t in argv):
        return True
    if any(t.startswith(LOCAL_ENV) and ASSIGNMENT.match(t) for t in argv):
        return True
    return any(t.endswith("check.sh") for t in argv) and "demo_defects" in argv


def classify(cmd):
    """(ran_local_tool, read_ci) for one Bash command."""
    cmds = simple_commands(cmd)
    if cmds is None:
        # Unparseable (unbalanced quotes). Arm the LOCAL side from the raw
        # text and never discharge from it: an extra reminder is cheap, a
        # missed one is the failure this hook exists to prevent.
        return bool(LOCAL_TOOL.search(cmd) or LOCAL_ENV in cmd), False
    local = any(_is_local_run(a) for a in cmds)
    ci = any(_is_ci_read(a) for a in cmds)
    return local, ci


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(path):
    """Return (claim_text, claim_at, local_at_claim, ci_at_claim).

    The two index values are snapshotted when the claim is seen, so later
    activity cannot re-arm an already-discharged claim. -1 means never seen.
    """
    claim_txt, claim_at = None, -1
    claim_local, claim_ci = -1, -1
    local_at, ci_at = -1, -1

    for i, m in enumerate(records(path)):
        # A subagent's own turns are not my outgoing message.
        if m.get("isSidechain"):
            continue
        if m.get("type") != "assistant":
            continue
        blocks = (m.get("message") or {}).get("content") or []
        if not isinstance(blocks, list):
            continue

        for b in blocks:
            if not isinstance(b, dict):
                continue

            if b.get("type") == "text":
                # Only a claim that FOLLOWS a local run is this hook's business.
                if local_at < 0:
                    continue
                hit = VERDICT_CLAIM.search(visible_prose(b.get("text", "")))
                if hit:
                    claim_txt, claim_at = hit.group(0).strip(), i
                    claim_local, claim_ci = local_at, ci_at

            elif b.get("type") == "tool_use":
                if (b.get("name") or "") != "Bash":
                    continue
                inp = b.get("input") or {}
                if not isinstance(inp, dict):
                    continue
                is_local, is_ci = classify(str(inp.get("command", "")))
                if is_local:
                    local_at = i
                if is_ci:
                    ci_at = i

    return claim_txt, claim_at, claim_local, claim_ci


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        claim_txt, claim_at, claim_local, claim_ci = scan(path)
    except Exception:
        return 0

    if not claim_txt or claim_local < 0:
        return 0
    # A CI read after the most recent local run and before the claim discharges
    # it. Both values were snapshotted at the claim, so both are <= claim_at.
    if claim_ci >= claim_local:
        return 0

    key = hashlib.sha256(f"{path}:{claim_txt}:{claim_at}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-ci-crosscheck-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(
        "[hook: remind-ci-crosscheck-sim-verdict] A verdict-shaped figure "
        f"({claim_txt!r}) was stated after a LOCAL sim/transcript run, with no "
        "CI-side read in between.\n"
        "\n"
        "A deterministic sim is deterministic per (seed, platform, renderer "
        "config), not across them. Measured: the same clip, same seed, same "
        "commit read `uid0 overlap worst=1.611` locally (FAIL) and "
        "`worst=2.432` on CI (PASS) -- the divergence inverts verdicts, it "
        "does not merely shift digits.\n"
        "\n"
        "Before this figure gates anything -- removing an exemption, calling a "
        "clip clean, correcting someone's stated premise -- get CI's own "
        "number. The cheap self-test: find an `expect` assertion your change "
        "cannot have affected. If it fails locally and passes on CI, discard "
        "the local run wholesale.\n"
        "\n"
        "If the figure is only being reported as a local diagnostic, say so in "
        "the text and carry on -- this hook only ever adds context."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
