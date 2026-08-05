#!/usr/bin/env python3
"""PreToolUse reminder: an `Agent` brief that asserts corpus state owes a derivation.

`shared/workflow/challenge-the-assignment.md` explains why a brief is the
artifact where a false premise hides best.
A brief asserts nothing in the grammatical sense --- it *instructs* --- so no
claim-checking rule fires on it, and the receiving agent inherits the premise
carrying the orchestrator's authority rather than the orchestrator's evidence.
Every step downstream can then be executed correctly and check green while the
whole task rests on something nobody looked up.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
Sending a brief is right.
Only the unverified premise inside it is wrong, and a guard cannot tell a
premise that was checked from one that was not --- it can only tell that the
sentence has the shape of a claim about a file.
Blocking on that shape would deny half the briefs this corpus writes, on a
signal that is suggestive rather than decisive.

So this only ever ADDS context.
There is no code path here that denies, escalates, or auto-approves; in
particular it never emits `permissionDecision`, whose absence defers to the
normal permission flow, and it never rewrites the prompt.
The model is free to read the note, decide the claim was already verified, and
launch the agent unchanged.

THE TWO INCIDENTS
-----------------
Both 2026-08-04, one session, both verified after the fact.

  1. A brief asserted that `CLAUDE.md` carries a quota carve-out phrased
     "`total_cost` 0 at `num_turns` 1".
     It does not: `grep -n "total_cost\\|num_turns" CLAUDE.md` returns nothing,
     and the sentence lives only at `shared/workflow/fully-clean.md:651`.
     The receiving agent caught it, which is luck rather than a mechanism.
  2. A later brief said `CLAUDE.md` has "five quota mentions".
     `grep -ci quota CLAUDE.md` returns 6 and `grep -oi quota CLAUDE.md | wc -l`
     returns 7.

The second is the worse one, and it is what shapes the discharge rule below.
Its correct line numbers had already been printed by the session's own earlier
`grep -n`, so the miscount came from visible data rather than from
recollection.
A discharge keyed on "this session grepped that file" would therefore have gone
silent on precisely the instance that most needed the reminder --- the
over-broad-discharge failure `shared/workflow/algorithmatize-checks.md` names,
where silence is indistinguishable from compliance.

DISCHARGE IS MATCHED TO THE CLAIM KIND
--------------------------------------
A claim is classified CONTENT ("carries", "does not mention") or CARDINALITY
("five quota mentions", "three sites").

  - A CONTENT claim is discharged by any derivation that inspects the file:
    `grep`, `git grep`, `rg`, `sed -n`, `wc`, `jq ... | length`, or a `Read`.
  - A CARDINALITY claim is discharged only by a derivation that PRODUCES A
    COUNT: `grep -c`, `rg -c`/`--count`, `wc -l`, or `jq ... | length`.

That asymmetry is the whole point.
Listing lines is not counting them, so incident 2 fires under this rule while a
naive path-match discharge would have missed it.

A derivation counts whether it sits in the brief itself, beside the claim ---
which is what the reminder asks for --- or earlier in this session's
transcript with its output actually present.

PRECISION, MEASURED
-------------------
Measured over every `Agent`/`Task` prompt retained in this machine's
transcripts on 2026-08-04, each replayed against its own session transcript
truncated to the records that preceded the launch, so the discharge saw exactly
what that session had derived at the time.

  - 26 prompts examined, 7 fired, 19 silent.
  - Those 7 carry 9 claims, and on inspection all 9 are genuine corpus-state
    assertions rather than incidental mentions. Two were the false ones above.
    The other seven were true, and none of them had been derived: they were
    asserted from recollection and happened to be right.
  - Both incidents fire. Incident 2 fires on its cardinality claim ALONE, its
    two content claims correctly discharged by that session's own earlier
    `grep -n`, which is the claim-kind matching doing its job.

Read 26 as a small denominator rather than a settled rate.
It is every Agent prompt this machine still holds, but transcripts rotate:
`flag-unassigned-worktree.py` measured 121 launches a few days earlier, and
those records are gone.
Two matcher false positives were found and fixed during that measurement, both
recorded at their fix sites -- a citation whose next verb belonged to the
reader, and a count that reached back across a paragraph break.

See `hooks/test-remind-brief-premises.py` for the corpus cases and the
clause-isolation mutation checks.

Fires once per distinct claim per session, because a reminder repeated on every
retry of the same call is noise, and noise is what gets a guard ignored.

Fails OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# ---------------------------------------------------------------- clause A
# A corpus path or a bare corpus filename. Bare `CLAUDE.md` and `MEMORY.md` are
# included because they are the files briefs assert about most, and both
# incidents were about `CLAUDE.md`. A bare kebab basename (`fully-clean.md`) is
# deliberately NOT a path on its own: adding it widened clause A with no new
# true positive in the measured corpus, and clause B is not tight enough to
# carry that much extra surface alone.
PATH = re.compile(
    r"""(?<![\w./-])(
        CLAUDE\.md
      | MEMORY\.md
      | (?:\./)?(?:shared|memories|skills|hooks|scripts|codex-skills)
          /[\w./-]*[\w-]
    )(?![\w/-])""",
    re.X,
)

# ---------------------------------------------------------------- clause B
# Verbs that assert what a file CONTAINS, as opposed to what should be done to
# it. "already covers" and "does not mention" are reached via the 0-2 word gap.
VERB = (
    r"carries|carry|contains|contain|says|say|states|state|asserts|assert"
    r"|documents|document|covers|cover|mentions|mention|lists|list"
    r"|defines|define|describes|describe|has|have|had|includes|include"
    r"|omits|omit|lacks|lack|records|record|notes|note|shows|show"
)

# Words allowed to sit between the path and its verb. Each must START with a
# letter, which is what stops a dash from being counted as a gap word: without
# that, "(see a.md and grep-is-not-coverage.md -- and note that ...)" parses as
# path + gap("--", "and") + verb("note") and a bare citation reads as a content
# assertion. The conjunction stoplist closes the same hole one token over.
GAP = r"(?:(?!and\b|or\b|but\b|nor\b|see\b|then\b|to\b|for\b)[A-Za-z][\w'-]*\s+){0,2}?"

COUNT = (
    r"\d{1,3}"
    r"|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|zero|no"
)

# Words ending in -s that are never the plural noun of a cardinality claim.
NOT_PLURAL = {
    "is", "was", "has", "does", "goes", "this", "its", "us", "thus",
    "less", "plus", "yes", "as", "hers", "theirs", "whose",
}

# An identifier, not a word: `num_turns`, `total_cost_usd`, `foo.bars`, a path.
# Prose plural nouns do not carry underscores, dots, slashes, or digits, so
# this is what stops a code literal from supplying a cardinality claim -- see
# `visible_prose` for why it replaced an inline-code mask.
NOT_A_NOUN = re.compile(r"[_./\d]")

# An imperative opening means the sentence tells the agent to DO something to
# the file rather than telling it what the file holds. "Verify that CLAUDE.md
# carries X" is suppressed on purpose: the brief has already asked for the
# check this hook would ask for.
IMPERATIVE = re.compile(
    r"""^[\s>*+#-]*(?:\d+[.)]\s*)?(?:then\s+|first\s+|also\s+|next\s+)?
        (add|append|write|edit|create|update|put|insert|move|delete|remove
        |rename|run|read|open|grep|check|verify|confirm|re-?run|scan|search
        |look|cite|link|see|follow|use|keep|make|fix|apply|review|load
        |consult|avoid|skip|ignore|prefer|push|commit|stage|file|land|ship
        |do|don't|do\s+not|touch|copy|paste|extend|split|merge|refresh
        |regenerate|rebuild|report|start|stop|leave|hold|drop|pick)\b""",
    re.I | re.X,
)

FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)

# ---------------------------------------------------------------- discharge
# Any command that inspects a file's contents.
#
# Deliberately narrow. An earlier draft also accepted `cat`, `head`, and
# `tail`, which made the discharge fire on ordinary prose -- "head commit",
# "head node", and "head_sha" all appear constantly in this corpus, so a
# sentence merely naming a file next to the word "head" silently discharged a
# real claim. That is the over-broad-discharge failure, and its symptom is
# silence, so nothing would have reported it.
DERIVE_ANY = re.compile(
    r"\b(?:git\s+)?(?:grep|rg|ag|ack)\b|\bsed\s+-n\b|\bwc\s+-|\bjq\b"
    r"|\|\s*length\b",
)
# Commands that produce a NUMBER. Bundled short flags are handled by the
# character class, so `grep -ci` and `grep -rc` both match.
DERIVE_COUNT = re.compile(
    r"\b(?:git\s+)?(?:grep|rg|ag)\s+(?:-[a-z]*c[a-z]*\b|--count\b)"
    r"|\bwc\s+-[a-z]*l\b|\|\s*wc\b|\|\s*length\b|\bcount\s*\(",
)


def visible_prose(text):
    """Drop fenced blocks and blockquotes, and unwrap inline code.

    Backticks are removed rather than deleted with their contents, unlike
    `remind-ums-after-error.py`, because in this corpus the path itself is
    nearly always inside backticks -- deleting inline code would delete clause
    A's own anchor and the guard would never fire at all. They are removed
    rather than replaced by a space so that "`CLAUDE.md`'s" still reads as a
    possessive.

    Nothing here tracks WHICH text came from inside a code span, deliberately.
    Two earlier drafts tried, one toggling on each backtick and one pairing
    them with a regex, and both are defeated the same way: prose in this corpus
    carries odd backticks inside quoted shell strings, such as
    `grep -rn 'total_cost` 0 at'`, and a single stray one shifts the parity of
    everything after it. The job that mask was doing -- keeping a code literal
    from supplying a cardinality claim's plural noun -- is done instead by
    NOT_A_NOUN below, which rejects the identifier by its own shape and cannot
    be knocked out of alignment.
    """
    # Line-count-preserving, so an offset in the returned text sits on the same
    # line as in the raw prompt. The in-prompt discharge below is proximity
    # scoped, so a shifted line number would silently move a derivation out of
    # its claim's window.
    text = FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = QUOTED.sub(" ", text)
    return text.replace("`", "")


def segment_start(text, pos):
    """Index of the start of the sentence or line containing `pos`."""
    best = 0
    for m in re.finditer(r"(?:\n|(?<=[.!?:])\s)", text[:pos]):
        best = m.end()
    return best


def plural_after(text, start, span=90):
    """Return the matched phrase when a small count plus a plural noun follows."""
    window = text[start:start + span]
    for m in re.finditer(
        rf"\b({COUNT})\s+(?:[\w./-]+\s+){{0,2}}?([A-Za-z][\w./-]*s)\b", window, re.I
    ):
        noun = m.group(2)
        if noun.lower() in NOT_PLURAL or NOT_A_NOUN.search(noun):
            continue
        return m.group(0)
    return None


def claims(prompt):
    """Return [(kind, quoted_claim, path, line)] per corpus-state assertion."""
    text = visible_prose(prompt)
    found, seen = [], set()

    for pm in PATH.finditer(text):
        path, end = pm.group(1), pm.end()

        seg = segment_start(text, pm.start())
        if IMPERATIVE.match(text[seg:pm.start() + len(path) + 1]):
            continue

        kind = quote = None

        # PATH's <count> <plural noun>  -- "CLAUDE.md's five quota mentions"
        poss = re.match(r"'s\s+", text[end:end + 4])
        if poss:
            hit = plural_after(text, end + poss.end())
            if hit:
                kind, quote = "cardinality", f"{path}'s {hit}"

        # PATH <verb>  -- "CLAUDE.md carries ...", "CLAUDE.md does not mention"
        if kind is None:
            vm = re.match(
                rf"(?:'s)?\s+{GAP}(?:{VERB})\b", text[end:end + 60], re.I,
            )
            if vm:
                kind = "content"
                quote = (path + vm.group(0)).strip()
                hit = plural_after(text, end + vm.end())
                if hit:
                    kind, quote = "cardinality", f"{quote} {hit}"

        # <count> <plural noun> ... in PATH  -- "three sites in shared/x.md"
        if kind is None:
            # Scoped to the claim's own sentence, not a fixed character
            # window. A 110-character lookback reached back past a blank line
            # and a heading into the previous paragraph, so an unrelated
            # "three lines below it" supplied the count for a path two
            # sentences later.
            before = text[max(seg, pm.start() - 160):pm.start()]
            if re.search(r"\b(?:in|under|across|within|inside|of)\s+$", before):
                hit = plural_after(before, 0, span=len(before))
                if hit:
                    kind, quote = "cardinality", f"{hit} ... in {path}"

        if kind is None:
            continue
        key = (kind, path, quote.lower())
        if key in seen:
            continue
        seen.add(key)
        line = text.count("\n", 0, pm.start())
        found.append((kind, " ".join(quote.split()),
                      path, line))

    return found


# How far from a claim an in-brief derivation may sit and still discharge it.
# The reminder asks for the command pasted BESIDE the claim, so this is scoped
# rather than whole-prompt: a brief that greps a file in one place must not
# thereby vouch for an unrelated assertion about it forty lines away.
NEAR_LINES = 5


def derivations(prompt):
    """Line numbers where the brief itself derives a path.

    Returns (any_lines, count_lines), each a basename -> [line] mapping.
    """
    any_p, count_p = {}, {}
    for n, line in enumerate(prompt.splitlines()):
        for pm in PATH.finditer(line):
            base = os.path.basename(pm.group(1))
            if DERIVE_COUNT.search(line):
                count_p.setdefault(base, []).append(n)
                any_p.setdefault(base, []).append(n)
            elif DERIVE_ANY.search(line):
                any_p.setdefault(base, []).append(n)
    return any_p, count_p


def near(table, base, line):
    return any(abs(n - line) <= NEAR_LINES for n in table.get(base, ()))


def transcript_derivations(path):
    """Basenames derived earlier in this session, with output present."""
    any_p, count_p = set(), set()
    pending = {}
    try:
        fh = open(path, errors="ignore")
    except Exception:
        return any_p, count_p

    with fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            blocks = (m.get("message") or {}).get("content") or []
            if not isinstance(blocks, list):
                continue

            if m.get("type") == "assistant":
                if m.get("isSidechain"):
                    continue
                for b in blocks:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    inp = b.get("input") or {}
                    if not isinstance(inp, dict):
                        continue
                    if b.get("name") == "Bash":
                        pending[b.get("id")] = str(inp.get("command", ""))
                    elif b.get("name") in ("Read", "Grep", "Glob"):
                        # A Read shows the file; it never yields a count.
                        blob = str(inp.get("file_path") or inp.get("path") or "")
                        if blob:
                            any_p.add(os.path.basename(blob))

            elif m.get("type") == "user":
                for b in blocks:
                    if not isinstance(b, dict) or b.get("type") != "tool_result":
                        continue
                    cmd = pending.pop(b.get("tool_use_id"), None)
                    if cmd is None or b.get("is_error"):
                        continue
                    # Output must actually be present: a command whose result
                    # is empty or errored derived nothing.
                    if not str(b.get("content") or "").strip():
                        continue
                    for pm in PATH.finditer(cmd):
                        base = os.path.basename(pm.group(1))
                        if DERIVE_COUNT.search(cmd):
                            count_p.add(base)
                            any_p.add(base)
                        elif DERIVE_ANY.search(cmd):
                            any_p.add(base)

    return any_p, count_p


NOTE = (
    "This brief asserts corpus state, and a brief is where an unverified "
    "premise survives best -- it reads as instruction rather than as a claim, "
    "so nothing downstream checks it and the receiving agent inherits it with "
    "your authority.\n\n"
    "Unverified claim(s):\n{claims}\n\n"
    "Either paste the deriving command beside the claim in the brief, or tell "
    "the agent to verify before acting on it. A count needs a counting command "
    "(`grep -c`, `wc -l`); listing lines is not counting them.\n\n"
    "If you already derived these, say so in the brief and launch unchanged."
)


def evaluate(prompt, tpath=""):
    """Return the undischarged claims as [(kind, quote)].

    Split out of `main` so the test suite can mutation-check one clause at a
    time without going through stdin, per
    `shared/workflow/algorithmatize-checks.md`: an ANDed fire condition hides
    an untested clause, because reverting one clause still passes any case a
    sibling clause keeps correct.
    """
    found = claims(prompt)
    if not found:
        return []

    in_any, in_count = derivations(prompt)
    if tpath and os.path.isfile(tpath):
        t_any, t_count = transcript_derivations(tpath)
    else:
        t_any, t_count = set(), set()

    undischarged = []
    for kind, quote, path, line in found:
        base = os.path.basename(path)
        if kind == "cardinality":
            if base in t_count or near(in_count, base, line):
                continue
        elif base in t_any or near(in_any, base, line):
            continue
        undischarged.append((kind, quote))
    return undischarged


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") not in ("Agent", "Task"):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return 0

    try:
        tpath = payload.get("transcript_path") or ""
        undischarged = evaluate(prompt, tpath)
        if not undischarged:
            return 0

        key = hashlib.sha256(
            (tpath + "|" + "|".join(q for _, q in undischarged)).encode()
        ).hexdigest()[:16]
        sentinel = os.path.join(
            tempfile.gettempdir(), f".claude-brief-premises-{key}"
        )
        if os.path.exists(sentinel):
            return 0
        try:
            open(sentinel, "w").close()
        except Exception:
            pass

        listed = "\n".join(
            f'  - [{k}] "{q}"' for k, q in undischarged[:3]
        )
        if len(undischarged) > 3:
            listed += f"\n  - ... and {len(undischarged) - 3} more"

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": NOTE.format(claims=listed),
            },
            "systemMessage": (
                f"Agent brief asserts corpus state ({len(undischarged)} "
                "underived claim(s)); verify or paste the deriving command."
            ),
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
