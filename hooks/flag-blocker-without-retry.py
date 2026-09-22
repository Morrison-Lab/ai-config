#!/usr/bin/env python3
"""Stop-hook guard: a reply that hands a denied action to the user, with no retry tried.

THE MEASURED CASE (2026-09-22, ai-config, this session's own transcript)
--------------------------------------------------------------------------
The auto-mode permission classifier denied
`ALLOW_MERGE=1 gh pr merge 5 -R Morrison-Lab/mlg --squash --delete-branch`.
The reply that followed posted a `\U0001F6D1` **BLOCKER** box saying the PR
"needs you to merge it" and "the permission classifier denied my merge, and
I'm not routing around it". The next turn re-ran the byte-identical command
and it succeeded: the PR merged. A user turn was spent on a handoff that was
not necessary, and the escalation was written after exactly one denial with
no retry.

`remind-retry-before-declaring-blocked.py` (ai-config#2994) already covers
the general form of this -- a denial is a sample, not a wall -- but it fires
on the NEXT `UserPromptSubmit`, a full turn after the escalating reply has
already gone out and the user has already been handed the blocker. This file
is the missing half: it reads the SAME turn, at the moment the reply is
about to be sent, and warns before the handoff is delivered rather than
after.

WHAT IT CHECKS
--------------
    the final assistant message ESCALATES a permission denial to the user
        (a blocker/handoff marker or phrasing, PAIRED with an explicit
        attribution to a permission denial or classifier refusal)
    AND the transcript contains a classifier denial with NO LATER attempt
        of a command with the same NORMALIZED shape

Both conditions are required. An escalation with no denial in the transcript
at all is not this incident -- it might be a genuine blocker for some other
reason, and this guard has nothing to say about it. A denial that WAS
retried is exactly the case #2994 argues should not stall a session, and
here it did not: nothing to warn about.

WHY "ESCALATES" NEEDS BOTH A MARKER AND AN ATTRIBUTION
-------------------------------------------------------
A marker alone (`\U0001F6D1`, "I cannot", "you'll need to") is far too
common on its own to anchor a warning -- this corpus's own prose uses "I
cannot" routinely for reasons that have nothing to do with a permission
classifier. Requiring it to sit near an explicit attribution ("denied by
the classifier", "permission was denied") is what keeps the guard scoped to
the actual incident shape: a handoff whose STATED REASON is a permission
refusal, not any blocker whatsoever. See `ESCALATION_RX` / `ATTRIBUTION_RX`
and `_find_pair` below.

WHY THIS WARNS RATHER THAN BLOCKS
-----------------------------------
The obvious shape is a `Stop` guard that blocks the escalating message
outright, copying `no-offer-to-file.py`. That shape is wrong here, for the
same reason `flag-cop-out-offer.py` and `remind-deserialize-before-binary-claim.py`
give for their own cases.

A denial the user genuinely must resolve -- a destructive action correctly
gated, a permission rule that is not going to change on a retry, a case
where the classifier's caution is exactly right -- is a REAL case, and a
guard that blocked it would be training the session to say nothing rather
than to ask. Authorization and intent are not lexically decidable: this file
can see that a denial happened and that no retry followed it, but it cannot
see whether retrying is actually a good idea for THIS command. So it warns,
and leaves the call to whoever is composing the reply.

NORMALIZING "THE SAME COMMAND"
-------------------------------
A byte-identical re-run is the strongest evidence of a retry, but requiring
byte-identity would miss the routine case where a retry drops or adds an
env-var prefix, a redirection, or a trailing pipe -- none of which changes
what the command DOES. `ALLOW_MERGE=1 gh pr merge 5 ...` and
`gh pr merge 5 ...` are the same attempt for this guard's purposes, and
`normalize_command()` below strips exactly those three things (a leading run
of `VAR=value` assignments, a trailing pipeline, and redirection operators)
before two commands are compared. This is deliberately its OWN, stronger
normalization rather than a reuse of
`remind-retry-before-declaring-blocked.py`'s `identity()`, which only
collapses whitespace -- that hook's docstring explains why byte-for-byte
matching is the right default THERE (the displayed command must be
copy-paste-safe), which is not a concern here since this guard never echoes
a command back for the user to run.

ANCHORING AGAINST THIS CORPUS'S OWN PROSE
-------------------------------------------
This repo's hooks quote denial text, blocker markers, and phrases like
"I'm not routing around it" constantly -- including in this very docstring.
Two mitigations, matching the conventions `no-unread-issue-claim.py` and
`flag-cop-out-offer.py` already established:

  * Only the FINAL assistant message is read, via the same reply-tool-aware
    extraction `flag-cop-out-offer.py` uses (reused by dynamic import, with a
    plain-text-block fallback) -- not every message that happens to discuss
    this rule.
  * Fenced code, blockquotes, and inline code spans are stripped from that
    message before matching (`scripts/lib/fences.py`'s `strip_code`, with a
    regex fallback), so a reply that quotes the classifier's own denial text
    in backticks while explaining what happened does not self-trigger.

Fires once per distinct final message (sentinel keyed by a content hash),
and fails OPEN and SILENT on any parse trouble: this file's own contract, and
every hook's, per README's "A hook that misfires is worse than a missing
one".
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))


def _sibling(name):
    """Import a hyphenated sibling module by path, or None. Fails open."""
    try:
        path = os.path.join(HERE, name)
        spec = importlib.util.spec_from_file_location(
            "_sib_" + re.sub(r"\W", "_", name), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Final-message extraction. Reused from flag-cop-out-offer.py rather than
# re-derived, because that file's `last_visible_texts` already carries a real
# fix: in a project-thread session the user-visible text is the payload of a
# reply-tool call (`mcp__hearthbot__reply` and similar), never a plain
# assistant text block, and a reader that only walks text blocks is blind to
# the whole reply -- measured on ai-config#(flag-cop-out-offer's own case),
# 2026-09-19. A plain-text-only fallback is kept for a checkout where that
# sibling is missing or has changed shape, on the same fail-open contract
# every hook here carries.
_copout = _sibling("flag-cop-out-offer.py")
_last_visible_texts = getattr(_copout, "last_visible_texts", None)


def _fallback_last_texts(path):
    """Plain-text-block extraction: the final assistant text, or none."""
    text = ""
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("isSidechain"):
                    continue
                role = m.get("type") or m.get("role")
                if role != "assistant":
                    continue
                blocks = (m.get("message") or {}).get("content") or m.get("content") or []
                if isinstance(blocks, list):
                    joined = "".join(
                        b.get("text", "") for b in blocks
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                    if joined.strip():
                        text = joined
                elif isinstance(blocks, str) and blocks.strip():
                    text = blocks
    except Exception:
        return []
    return [text] if text.strip() else []


def last_texts(path):
    if _last_visible_texts is not None:
        try:
            return _last_visible_texts(path)
        except Exception:
            pass
    return _fallback_last_texts(path)


# ---------------------------------------------------------------------------
# Code-region stripping, so a quoted denial in backticks is not an assertion.
try:
    _LIB = os.path.join(os.path.dirname(HERE), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from fences import strip_code  # type: ignore
except Exception:
    _FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
    _CODE_SPAN_RE = re.compile(
        r"(?<!`)(`+)(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
    )
    _QUOTE_RE = re.compile(r"(?m)^[ \t]*>[^\n]*$")

    def strip_code(text, fence_replacement=" ", span_replacement=" "):
        text = _FENCE_RE.sub(fence_replacement, text)
        text = _CODE_SPAN_RE.sub(span_replacement, text)
        return _QUOTE_RE.sub(" ", text)


# ---------------------------------------------------------------------------
# Condition 1: does the message ESCALATE a permission denial?
#
# The boxed marker comes from CLAUDE.md's chat-output tagging convention
# (the stop-sign emoji plus the bold **BLOCKER** label); the phrasing
# alternatives are the ones actually used in the measured case and its
# closest paraphrases. Deliberately narrower than
# `remind-deserialize-before-binary-claim.py`'s own `ESCALATION` regex,
# which also matches QUESTION/RECOMMENDATION markers and generic
# "should I .../do you want me to ..." phrasing -- none of which is a
# blocker/handoff about a DENIED action, which is what this guard is
# scoped to.
ESCALATION_RX = re.compile(
    r"""(
        \U0001F6D1                          # stop-sign emoji (BLOCKER box)
      | \*\*BLOCKER\*\*
      | \bneeds?\s+you\s+to\b
      | \byou(?:'ll|\s+will)\s+need\s+to\b
      | \bnot\s+routing\s+around\b
      | \brouting\s+around\b
      | \bi\s+cannot\b
    )""",
    re.I | re.X,
)

# An explicit attribution of a refusal to the permission layer or the
# auto-mode classifier -- as opposed to a blocker for any OTHER reason
# (a destructive action, a genuine ambiguity, a missing credential).
ATTRIBUTION_RX = re.compile(
    r"""(
        \bpermission\b[^.\n]{0,30}\bclassifier\b[^.\n]{0,20}\bdenied\b
      | \bclassifier\b[^.\n]{0,20}\bdenied\b
      | \bdenied\b[^.\n]{0,40}\bclassifier\b
      | \bdenied\s+by\s+the\s+(?:claude\s+code\s+)?auto[- ]?mode\s+classifier\b
      | \bpermission\b[^.\n]{0,20}\bwas\b\s+\bdenied\b
      | \bpermission\s+denied\b
      | \bclassifier\s+refus(?:ed|al)\b
    )""",
    re.I | re.X,
)

# How far an escalation marker may sit from an attribution mention and still
# count as the SAME handoff. Wide enough to span a boxed marker and its
# following sentence ("needs you to merge it. The permission classifier
# denied my merge, and I'm not routing around it."), narrow enough that an
# unrelated attribution mention elsewhere in a long recap does not pair with
# an unrelated "I cannot" many paragraphs away.
PAIR_WINDOW = 400


def find_denial_escalation(text):
    """Return (escalation_phrase, attribution_phrase) or None.

    Anchored on the ATTRIBUTION side: for each place the message attributes
    a refusal to the permission layer, look at a window around it for a
    blocker/handoff marker. Anchoring on attribution rather than on
    escalation is deliberate -- "I cannot" alone is common enough that
    scanning outward from EVERY occurrence of it would multiply false
    positives, while an explicit "denied by the classifier" is rare and
    specific.
    """
    prose = strip_code(text)
    for am in ATTRIBUTION_RX.finditer(prose):
        lo = max(0, am.start() - PAIR_WINDOW)
        hi = min(len(prose), am.end() + PAIR_WINDOW)
        em = ESCALATION_RX.search(prose[lo:hi])
        if em:
            return em.group(0).strip(), am.group(0).strip()
    return None


# ---------------------------------------------------------------------------
# Condition 2: an unretried classifier denial in the transcript.
#
# `is_classifier_denial` and its marker/kind constants are reused from
# `remind-retry-before-declaring-blocked.py` (ai-config#2994) so the two
# guards agree on what counts as "the classifier denied this", rather than
# each carrying its own copy free to drift. `identity`/normalization is NOT
# reused -- see the module docstring's "Normalizing" section for why this
# guard needs a stronger command-identity than that hook's own
# whitespace-only collapse.
_retry = _sibling("remind-retry-before-declaring-blocked.py")

CLASSIFIER_MARKER = getattr(
    _retry, "CLASSIFIER_MARKER",
    "Permission for this action was denied by the Claude Code auto mode "
    "classifier",
)
CLASSIFIER_KIND = getattr(_retry, "CLASSIFIER_KIND", "automode-blocked")
BASH_TOOLS = getattr(
    _retry, "BASH_TOOLS",
    ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"),
)


def _is_classifier_denial(record, block):
    """True only for the auto-mode classifier's own refusal.

    Delegates to the sibling's own function when available, since that is
    the version measured against real transcripts (ai-config#2994's own
    corpus sweep); falls back to a local copy of the same two-signal check
    (a structured `toolDenialKind`, or the marker text on an error block).
    """
    fn = getattr(_retry, "is_classifier_denial", None)
    if fn is not None:
        try:
            return fn(record, block)
        except Exception:
            pass
    if record.get("toolDenialKind") == CLASSIFIER_KIND:
        return True
    if not block.get("is_error"):
        return False
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(
            c.get("text") or "" for c in content if isinstance(c, dict))
    if not isinstance(content, str):
        return False
    return content.lstrip().startswith(CLASSIFIER_MARKER)


# A leading run of `VAR=value` assignments (`ALLOW_MERGE=1 FOO=bar cmd`).
# Values may be bare, single-quoted, or double-quoted; only a SIMPLE
# assignment is stripped, which is enough for the shapes this guard needs to
# normalize (env-var gates on a `gh`/`git` command) without attempting a
# general shell parse.
_ENV_ASSIGN_RE = re.compile(
    r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*=(?:'[^']*'|\"[^\"]*\"|\S*)\s+)+"
)
# A trailing pipeline. Only the FIRST stage is kept: `cmd | wc -l` and `cmd`
# are treated as the same attempt, because the guard's question is whether
# the underlying action was re-attempted, not whether its output was piped
# somewhere new.
_PIPE_TAIL_RE = re.compile(r"\s*\|.*$", re.S)
# A redirection operator and its target (`2>&1`, `>/dev/null`, `< file`).
_REDIRECT_RE = re.compile(r"\s*\d*(?:>{1,2}&?\d*|<)\s*\S*")


def normalize_command(raw):
    """Strip env-var prefixes, a trailing pipeline, and redirections.

    Deliberately stronger than `remind-retry-before-declaring-blocked.py`'s
    own `identity()`, which only collapses whitespace -- see the module
    docstring. Two commands normalize equal exactly when this guard should
    treat one as a retry of the other.
    """
    if not isinstance(raw, str):
        return ""
    cmd = _ENV_ASSIGN_RE.sub("", raw)
    cmd = _PIPE_TAIL_RE.sub("", cmd)
    cmd = _REDIRECT_RE.sub(" ", cmd)
    return " ".join(cmd.split())


def _bash_identity(name, inp):
    """(normalized_key, raw_command) for a Bash-shaped tool call, or ('', '')."""
    if name not in BASH_TOOLS or not isinstance(inp, dict):
        return "", ""
    raw = str(inp.get("command") or inp.get("cmd") or inp.get("CommandLine") or "")
    norm = normalize_command(raw)
    if not norm:
        return "", ""
    return norm, raw


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def unretried_denials(path):
    """Return [(key, raw_command)] for denials with no later same-shape attempt.

    Only Bash-shaped tool calls are considered: the incident and the design
    constraints this guard is built from are both about shell commands
    (`gh pr merge`, `git push`), and normalizing a non-shell tool's structured
    input the same way would be meaningless.

    A later attempt counts whether the classifier let it through or denied it
    again -- this guard's question is only "was it tried again", the same
    question `remind-retry-before-declaring-blocked.py` asks of its own
    `attempts` list.
    """
    uses = {}       # tool_use id -> (record_index, normalized_key, raw)
    attempts = []   # [(record_index, normalized_key)]
    denied = {}     # normalized_key -> [record_index, ...]
    raws = {}       # normalized_key -> first raw command seen

    for i, rec in enumerate(records(path)):
        if not isinstance(rec, dict) or rec.get("isSidechain"):
            continue
        blocks = (rec.get("message") or {}).get("content") or rec.get("content")
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                key, raw = _bash_identity(b.get("name") or "", b.get("input") or {})
                if not key:
                    continue
                uses[b.get("id")] = (i, key, raw)
                attempts.append((i, key))
                raws.setdefault(key, raw)
            elif b.get("type") == "tool_result":
                seen = uses.get(b.get("tool_use_id"))
                if not seen:
                    continue
                at, key, _raw = seen
                if _is_classifier_denial(rec, b):
                    denied.setdefault(key, []).append(at)

    out = []
    for key, hits in denied.items():
        last = max(hits)
        if any(j > last for j, other in attempts if other == key):
            continue  # a later attempt exists, whatever it did
        out.append((key, raws.get(key, key)))
    return out


# ---------------------------------------------------------------------------
def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        texts = last_texts(path)
    except Exception:
        return 0
    if not texts:
        return 0

    pair = None
    for t in texts:
        try:
            pair = find_denial_escalation(t)
        except Exception:
            pair = None
        if pair:
            break
    if not pair:
        return 0

    try:
        candidates = unretried_denials(path)
    except Exception:
        return 0
    if not candidates:
        return 0

    escalation_phrase, attribution_phrase = pair
    _key, raw_cmd = candidates[0]
    shown = raw_cmd if len(raw_cmd) <= 240 else raw_cmd[:237] + "..."

    key = hashlib.sha256("|".join(texts).encode()).hexdigest()[:16]
    sentinel = os.path.join(
        tempfile.gettempdir(), f".claude-blocker-without-retry-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    message = (
        "This reply hands a denied action to the user "
        f"(\"{escalation_phrase}\" ... \"{attribution_phrase}\"), and the "
        "denied command has not been re-attempted in this session:\n"
        f"    {shown}\n"
        "ai-config#2994 measured a byte-identical command succeeding after "
        "three denials, with no settings change and no permission rule "
        "added -- a denial is a sample, not a wall. This is the same "
        "pattern one denial in: the escalating reply was composed, and sent, "
        "before a retry was tried at all.\n"
        "Before sending this reply, consider re-running the same command "
        "once. If the action is genuinely destructive, irreversible, or "
        "requires a judgment only the user can make, the escalation is "
        "correct as written -- this is a reminder, not a refusal."
    )

    print(json.dumps({"systemMessage": message}))
    sys.stderr.write(f"[hook: flag-blocker-without-retry] {message}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
