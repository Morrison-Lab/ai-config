#!/usr/bin/env python3
"""Guard: a claim about what a LaTeX macro prints needs a read of its definition.

ai-config#6109. On 2026-11-24 (lds#3144) an agent told Ezra that `\\vx` "prints a
bold x", and that swapping `\\Sigma` for `\\covmat` would change a chapter's
notation. `\\vx` prints x with an underset tilde, and `\\covmat` is defined as
`\\Sigma`. Both claims came from recall, and the definitions sit in one file
(macros.qmd) that one Read or Grep returns.

What a macro prints is a fact about its definition, and the definition is
decidable from the transcript:

    a sentence of the reply names a backslash macro
    AND the same sentence says what it prints, renders as, displays,
        typesets, looks like, is defined as or expands to
    AND no Read, Grep or Bash result (or GitHub file read) in the session
        shows that macro's definition (`\\def\\NAME`, `\\newcommand{\\NAME}`,
        `\\renewcommand{\\NAME}`, `\\providecommand{\\NAME}` and the like)

Runs on PreToolUse of a hearthbot reply tool (reply, post_message,
update_message, edit_message), the same tools the other reply guards cover,
and denies the call so the claim never reaches the user.

Backticks do not exempt a claim: both incident claims sat in backticks, and a
macro name in code formatting is still a claim about that macro. Fenced code
blocks are skipped, since a code example is not a statement of this reply.

Standard LaTeX and MathJax commands (`\\alpha`, `\\frac`, `\\Sigma`) are not
macros of the lab's library, so a claim about one needs no definition read.

Scope is the whole session, not the turn since the last user turn. The
sibling guards on PR state scope to the turn because a forge reading goes
stale between turns. A macro definition does not change within a session, so
one read stays true, and a per-turn scope would make an agent reread
macros.qmd every turn. Fails OPEN on any parse trouble.
"""
import json
import os
import re
import sys

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from sibling import load_sibling

    _offer = load_sibling(__file__, "no-offer-to-file.py", "no_offer_to_file", required=True)
    sentence_around = _offer.sentence_around
except Exception:
    sys.exit(0)

REPLY_TOOL_RX = re.compile(
    r"^mcp__hearthbot__(reply|post_message|update_message|edit_message)$"
)
# Tools whose results can show a definition. An Edit or Write input is the
# agent's own text, and a memory note is a recollection, so neither counts.
READ_TOOL_RX = re.compile(
    r"^(Read|Grep|Bash|mcp__github__(get_file_contents|search_code))$"
)

# A backslash command name. Not after a word character, a backslash or a
# colon, so `C:\Users` and `\\vx` in a doubled escape do not match.
MACRO_RX = re.compile(r"(?<![\w\\:])\\([A-Za-z]+)(?![A-Za-z])")

CLAIM_RX = re.compile(
    r"\b(prints?|printed|printing|renders?|rendered|rendering|displays?|displayed"
    r"|typesets?|typeset|looks? like|(?:is|are) defined as|defined as"
    r"|expands? to|expanded to)\b",
    re.I,
)

# Escape sequences and commands every LaTeX or MathJax install defines. A
# claim about one of these is not a claim about a library macro.
BUILTINS = frozenset(" ".join((
    "n r t b f s d w u x v",
    "alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa",
    "lambda mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi",
    "psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega",
    "frac dfrac tfrac sqrt sum prod int oint iint lim sup inf max min log ln exp",
    "sin cos tan det dim ker arg hat bar tilde vec dot ddot widehat widetilde",
    "overline underline overbrace underbrace mathbf mathrm mathit mathsf mathtt",
    "mathbb mathcal mathfrak boldsymbol bm text textbf textit textrm emph",
    "left right big Big bigg Bigg begin end cdot cdots ldots dots vdots ddots",
    "times div pm mp circ star ast bullet oplus otimes infty partial nabla",
    "le leq ge geq ne neq approx sim simeq equiv propto subset subseteq supset",
    "in notin ni cup cap setminus emptyset varnothing forall exists neg land lor",
    "to rightarrow leftarrow Rightarrow Leftarrow leftrightarrow Leftrightarrow",
    "mapsto implies iff top bot perp mid parallel",
    "langle rangle lceil rceil lfloor rfloor lbrace rbrace",
    "quad qquad hspace vspace newline item label ref cite",
    "def let newcommand renewcommand providecommand",
)).split())

DEF_NAME_RX = re.compile(
    r"\\{1,2}(?:def|gdef|edef|xdef|let|(?:new|renew|provide)command\*?"
    r"|DeclareRobustCommand\*?|DeclareMathOperator\*?|newcommandx"
    r"|DeclareMathSymbol)\s*\{?\s*\\{1,2}([A-Za-z]+)"
)

FENCE_RX = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$", re.M | re.S)


def _blocks(m):
    blocks = (m.get("message") or {}).get("content") or m.get("content")
    return blocks if isinstance(blocks, list) else []


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and isinstance(b.get("text"), str)
        )
    return ""


def defined_names(path):
    """Names whose definition appears in a Read/Grep/Bash result of the session."""
    reads, names = set(), set()
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if not isinstance(m, dict):
                    continue
                for b in _blocks(m):
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        if READ_TOOL_RX.match(str(b.get("name") or "")):
                            reads.add(b.get("id"))
                    elif (b.get("type") == "tool_result" and not b.get("is_error")
                          and b.get("tool_use_id") in reads):
                        names.update(DEF_NAME_RX.findall(_result_text(b)))
    except Exception:
        pass
    return names


def find_claim(text):
    """[(macro, sentence)] for each macro named in a sentence that says what it prints."""
    prose = FENCE_RX.sub(" ", text)
    out, seen = [], set()
    for m in MACRO_RX.finditer(prose):
        name = m.group(1)
        if name in BUILTINS or name in seen:
            continue
        sentence = sentence_around(prose, m.start(), m.end())
        if CLAIM_RX.search(sentence):
            seen.add(name)
            out.append((name, sentence.strip()))
    return out


# realpath, not abspath: the plugin registers hooks through a symlinked path
# (scripts/check-hook-file-resolution.py).
MESSAGE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                       "messages", "no-macro-claim-without-definition.md")
FALLBACK = ("[hook: no-macro-claim-without-definition] This message says what a LaTeX "
            "macro prints ({macros}), and nothing in this session shows its definition: "
            "read it in macros.qmd first. ai-config#6109.")


def reason_for(missing):
    names = ", ".join("\\" + n for n, _ in missing)
    sentence = missing[0][1]
    if len(sentence) > 160:
        sentence = sentence[:157] + "..."
    try:
        with open(MESSAGE, encoding="utf-8") as fh:
            template = fh.read()
    except OSError:
        template = FALLBACK
    return template.replace("{macros}", names).replace("{sentence}", sentence)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPLY_TOOL_RX.match(str(payload.get("tool_name") or "")):
        return 0
    inp = payload.get("tool_input")
    text = inp.get("text") if isinstance(inp, dict) else None
    if not isinstance(text, str) or not text.strip():
        return 0
    claims = find_claim(text)
    if not claims:
        return 0
    known = defined_names(payload.get("transcript_path") or "")
    missing = [(n, s) for n, s in claims if n not in known]
    if not missing:
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason_for(missing),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
