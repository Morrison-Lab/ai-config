#!/usr/bin/env python3
"""Stop-hook guard: a quoted phrase attributed to a corpus file that does not
contain it, where the phrase actually lives in a sibling fragment.

The incident (2026-08-16): an agent wrote that
`shared/workflow/pr-on-claim.md` says a vanished reviewer request
"establishes nothing either way".  That file contains zero occurrences of
"either way".  The phrase is in `shared/workflow/pr-on-claim.rationale.md`,
and in past tense -- "has established nothing either way".  Wrong file and
wrong tense, quoted from a stale in-context copy rather than derived by
reading the file.

Why a guard rather than a prose rule.  PR #1468 (merged 2026-08-15,
"Relocate rationale prose out of the 7 heaviest auto-loaded fragments")
split the heaviest fragments into `<name>.md` + `<name>.rationale.md` +
`<name>.cases.md`.  Any session whose context predates that split holds a
stale map of which file carries which passage, so misattribution is now
systematically likely rather than a one-off slip.

And the misread it causes is worse than a wrong citation.  Grepping the
named file returns zero hits, which reads as an *invented* quote -- so the
natural next step is to file a hallucination issue or delete a true claim,
when the passage exists and merely moved.  Naming the sibling is therefore
most of this hook's value; a bare "not found" would be worse than nothing,
which is why the fire condition REQUIRES a sibling (or elsewhere-in-corpus)
hit rather than merely an absence.

Fire condition (all of):
  1. a quoted phrase of >= MIN_TOKENS words, outside fenced code,
  2. attributed -- by proximity plus an attribution cue -- to a path or bare
     filename that resolves to a real file in this corpus,
  3. whose longest contiguous normalized n-gram in that file falls below the
     fire floor (i.e. the phrase is not there, allowing for light paraphrase),
  4. and which IS found, at the looser find floor, in a sibling fragment or
     elsewhere in the corpus.

Discharge / silence (any of): no repo file named beside the quote; the
phrase is present in the named file (or in any other root's resolution of
that name); the phrase is found nowhere else either; an absence-claim marker
sits in the window (a message REPORTING a misquote must not be blocked for
containing one); the time budget is exceeded; anything raises.

Fails OPEN and toward silence throughout.  Per `shared/principles/fail-fast.md`
a guard that misfires gets switched off and takes the real cases with it, so a
missed detection is preferred to a false one.  Fires at most once per distinct
message (sentinel keyed by content hash), so a block cannot loop.
"""
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path

# --- tuning -----------------------------------------------------------------

MIN_TOKENS = 4        # a shorter "quote" is a word, not a phrase
MAX_QUOTE_CHARS = 400
MAX_BRIDGE = 250      # chars allowed between the citation and the quote
WINDOW_PAD = 160      # chars either side scanned for an absence-claim marker
FIRE_RATIO = 0.7      # present-enough in the named file -> stay silent
# Deliberately STRICTER than FIRE_RATIO: more confidence is needed to fire
# than to stay silent.  Swept against this repo's own prose (387 files) --
# 0.5 and 0.6 each admit one coincidental 3-gram, 0.7 and 0.75 admit none,
# and 0.8 loses the incident this guard is named for (a 4-token quote whose
# sibling carries 3 of the 4).  0.75 is the far edge of the clean band.
FIND_RATIO = 0.75
TIME_BUDGET = 4.0     # seconds; over budget -> stay silent
MAX_PAIRS = 12        # bound the work on a long message
MAX_CORPUS_FILES = 400

# Directories searched when the named file is not in the named place.
CORPUS_GLOBS = (
    "CLAUDE*.md",
    "README.md",
    "shared/**/*.md",
    "memories/*.md",
    "skills/*/SKILL.md",
    "hooks/*.py",
)

# --- text handling ----------------------------------------------------------

# One normalizer, applied to BOTH sides.  `shared/workflow/address-every-comment.md`
# ("Apply whatever normalization you choose to the search term as well as to
# the text"): testing a raw needle against normalized text is a third false
# negative of its own, and collapsing `_` is safe only because snake_case
# identifiers are collapsed identically on both sides.
_NORM_RX = re.compile(r"[`*_~\s]+")


def norm(s: str) -> str:
    return _NORM_RX.sub(" ", s).strip().lower()


_FENCE_RX = re.compile(r"```.*?(?:```|\Z)", re.S)
_INDENTED_RX = re.compile(r"^(?: {4}|\t).*$", re.M)


def strip_code(text: str) -> str:
    """Blank out fenced and indented code, preserving offsets.

    A message routinely carries commands, diffs and log lines that pair a
    path with a quoted string for reasons that have nothing to do with
    citing the corpus.  Offsets are preserved so the spans found in the
    remaining prose still index into the original text.
    """
    out = list(text)
    for rx in (_FENCE_RX, _INDENTED_RX):
        for m in rx.finditer(text):
            for i in range(m.start(), m.end()):
                if out[i] != "\n":
                    out[i] = " "
    return "".join(out)


# Straight and curly double quotes.  Single quotes are deliberately excluded:
# apostrophes make them far too noisy.
#
# The curly glyphs are built with `chr()` rather than written literally, so
# this source file stays ASCII per `shared/coding/ascii-punctuation-in-source.md`
# while the compiled pattern still matches the real characters.
_LDQ, _RDQ, _RSQ, _EMD = chr(0x201C), chr(0x201D), chr(0x2019), chr(0x2014)

_QUOTE_RX = re.compile(
    '["%s]([^"%s%s\n]{12,%d})["%s]' % (_LDQ, _LDQ, _RDQ, MAX_QUOTE_CHARS, _RDQ)
)

# A repo-relative path or a bare corpus filename.
_PATH_RX = re.compile(
    r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.(?:md|py|json|ya?ml|sh|qmd|R))(?![\w/])"
)

# Deliberately permissive: precision comes from the fire gate (absent here,
# present there), not from parsing English.  A pairing that survives this and
# then finds the phrase in the named file simply stays silent.
_ATTRIB_RX = re.compile(
    r"\b(say|says|said|read|reads|state|states|stated|note|notes|noted|"
    r"warn|warns|warned|record|records|recorded|document|documents|documented|"
    r"describe|describes|described|call|calls|called|put|puts|phrase|phrases|"
    r"word|words|worded|per|in|from|according|citing|cite|cites|cited|"
    r"quote|quotes|quoting|quoted|insist|insists|require|requires|"
    r"prescribe|prescribes|own|owns|its|it)\b"
)

# A message REPORTING a misquote, PROPOSING new wording, or quoting something
# it says is absent must not be blocked for containing the very shape it is
# about.  This hook's own PR description is such a message.
_ABSENCE_RX = re.compile(
    r"(does not|doesn't|do not|don't|did not|didn't|never|"
    r"\bno (occurrence|hit|match|instance)|\bzero\b|absent|"
    r"not (in|present|there|found|its|the)|nowhere|lacks?\b|missing|"
    r"would (say|read|be)|should (say|read|be)|used to (say|read|be)|"
    r"instead of|rather than|replace|rewrite|new wording|reword|"
    r"misattribut|misquot|mis-?cit|hallucinat|invented|fabricat|"
    r"stale|moved to|relocated|propose|proposed|adding|i'll add|"
    r"wrongly|incorrectly|falsely)",
    re.I,
)


# A quote used as a NAME rather than as a citation -- `the "X" rule`, `the "X"
# triggers in CLAUDE.md's "Run UMS proactively" section`.  A naming use is
# paraphrase by intent, so it must not be held to verbatim fidelity; every
# residual false positive in the corpus measurement was one of these or a
# heading.  Losing a genuine misquote worded this way is the safe direction.
_NAMING_RX = re.compile(
    "^['%s]?s?" % _RSQ +
    r"\s*(section|sections|rule|rules|bullet|bullets|entry|entries|"
    r"trigger|triggers|block|blocks|clause|clauses|heading|headings|paragraph|"
    r"paragraphs|note|notes|line|lines|check|checks|step|steps|item|items|"
    r"case|cases|test|tests|guard|guards|hook|hooks|skill|skills|convention|"
    r"conventions|principle|principles|marker|markers|label|labels|phrase|"
    r"phrases|wording|term|terms|pattern|patterns|disposition|dispositions|"
    r"verdict|verdicts|column|columns|field|fields|flag|flags|mode|modes|"
    r"state|states|form|forms|shape|shapes|family|families|question|questions|"
    r"answer|answers|reading|readings|framing|argument|arguments|half|halves)\b",
    re.I,
)


# A paragraph break between the citation and the quote.
_PARA_RX = re.compile(r"\n[ \t]*\n")


def longest_ngram(tokens, hay_norm: str) -> int:
    """Longest contiguous run of `tokens` present in the normalized haystack."""
    n = len(tokens)
    for size in range(n, 0, -1):
        for i in range(n - size + 1):
            if " ".join(tokens[i:i + size]) in hay_norm:
                return size
    return 0


# --- corpus access ----------------------------------------------------------

class Corpus:
    def __init__(self):
        self.roots = []
        seen = set()
        cands = []
        env = os.environ.get("CLAUDE_PLUGIN_ROOT")
        if env:
            cands.append(Path(env))
        cands.append(Path(__file__).resolve().parent.parent)
        try:
            cands.append(Path.cwd())
        except Exception:
            pass
        for c in cands:
            try:
                r = c.resolve()
            except Exception:
                continue
            if r.is_dir() and str(r) not in seen:
                seen.add(str(r))
                self.roots.append(r)
        self._text = {}
        self._by_name = None

    def text(self, path: Path):
        key = str(path)
        if key not in self._text:
            try:
                self._text[key] = norm(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                self._text[key] = None
        return self._text[key]

    def resolve(self, cited: str):
        """Every real file the citation could name, across all roots."""
        hits = []
        if "/" in cited:
            for root in self.roots:
                p = root / cited
                if p.is_file():
                    hits.append(p)
            return hits
        # Bare filename: accept only an unambiguous match within a root.
        for root in self.roots:
            local = [p for p in self._index(root).get(cited, [])]
            if len(local) == 1:
                hits.append(local[0])
        return hits

    def _index(self, root: Path):
        if self._by_name is None:
            self._by_name = {}
        key = str(root)
        if key in self._by_name:
            return self._by_name[key]
        idx = {}
        count = 0
        for pat in CORPUS_GLOBS:
            for p in root.glob(pat):
                if not p.is_file():
                    continue
                idx.setdefault(p.name, []).append(p)
                count += 1
                if count >= MAX_CORPUS_FILES:
                    break
            if count >= MAX_CORPUS_FILES:
                break
        self._by_name[key] = idx
        return idx

    def siblings(self, path: Path):
        """`<n>.md` <-> `<n>.rationale.md` <-> `<n>.cases.md`, both directions."""
        name = path.name
        variants = (".rationale.md", ".cases.md")
        out = []
        for suf in variants:
            if name.endswith(suf):
                stem = name[: -len(suf)]
                out.append(stem + ".md")
                out.extend(stem + v for v in variants if v != suf)
                break
        else:
            if name.endswith(".md"):
                stem = name[:-3]
                out.extend(stem + v for v in variants)
        return [path.with_name(o) for o in out if path.with_name(o).is_file()]

    def rel(self, path: Path) -> str:
        for root in self.roots:
            try:
                return path.relative_to(root).as_posix()
            except ValueError:
                continue
        return path.name


# --- detection --------------------------------------------------------------

def find_pairs(text: str):
    """(cited-path, quote, window-text) triples worth checking, in order."""
    prose = strip_code(text)
    quotes = [(m.start(1), m.end(1), m.group(1)) for m in _QUOTE_RX.finditer(prose)]
    if not quotes:
        return []
    paths = [(m.start(1), m.end(1), m.group(1)) for m in _PATH_RX.finditer(prose)]
    if not paths:
        return []

    pairs = []
    for qs, qe, qtext in quotes:
        if len(norm(qtext).split()) < MIN_TOKENS:
            continue
        # A heading names a thing; it never cites one.
        line_start = prose.rfind("\n", 0, qs) + 1
        if prose[line_start:qs].lstrip().startswith("#"):
            continue
        # `the "X" rule` / `CLAUDE.md's "X" section` -- a name, not a citation.
        if _NAMING_RX.match(prose[qe + 1:qe + 40]):
            continue
        for ps, pe, ptext in paths:
            if pe <= qs:
                bridge = prose[pe:qs]
            elif qe <= ps:
                bridge = prose[qe:ps]
            else:
                continue  # a path inside the quote is quoted text, not a citation
            if len(bridge) > MAX_BRIDGE:
                continue
            # A citation in one paragraph does not attribute a quote in the
            # next.  Both residual corpus false positives were this: a `See
            # [x.cases.md](...)` cross-reference bound to an unrelated quote
            # opening the paragraph below it.
            if _PARA_RX.search(bridge):
                continue
            bare = bridge.strip(" \t\n:,.;()[]-" + _EMD + ">*`\"'")
            if bare and not _ATTRIB_RX.search(bridge.lower()):
                continue
            lo = max(0, min(qs, ps) - WINDOW_PAD)
            hi = min(len(prose), max(qe, pe) + WINDOW_PAD)
            # Blank the quote out of the window before scanning it for an
            # absence claim: the claim is made by the surrounding prose, and a
            # quoted passage that merely CONTAINS "absent" or "does not" must
            # not suppress its own check.
            window = prose[lo:qs] + " " * (qe - qs) + prose[qe:hi]
            pairs.append((ptext, qtext, window))
            if len(pairs) >= MAX_PAIRS:
                return pairs
    return pairs


def check(text: str, corpus: Corpus, deadline: float):
    """Return the first (cited, quote, found_rel) misattribution, else None."""
    for cited, quote, window in find_pairs(text):
        if time.monotonic() > deadline:
            return None
        if _ABSENCE_RX.search(window):
            continue  # reporting or proposing, not citing

        targets = corpus.resolve(cited)
        if not targets:
            continue  # constraint 1: nothing real was named

        tokens = norm(quote).split()
        n = len(tokens)
        fire_floor = max(3, math.ceil(FIRE_RATIO * n))
        find_floor = max(3, math.ceil(FIND_RATIO * n))

        # Present in ANY resolution of the cited name -> silent.
        present = False
        for t in targets:
            hay = corpus.text(t)
            if hay is None:
                present = True  # unreadable: assume innocent
                break
            if longest_ngram(tokens, hay) >= fire_floor:
                present = True
                break
        if present:
            continue

        # Absent here.  Only fire if it is findable in a SIBLING -- a bare
        # "not found" is the invented-quote misread this hook exists to
        # prevent, so silence is the right answer when nothing is found.
        #
        # A corpus-wide fallback was built, measured, and dropped: it took the
        # false-positive count on this repo's own prose from 4 to 44 while
        # finding nothing the sibling search did not, because a corpus idiom
        # quoted near any filename matches somewhere in 400 files.
        primary = targets[0]
        for cand in corpus.siblings(primary):
            if time.monotonic() > deadline:
                return None
            hay = corpus.text(cand)
            if hay is None:
                continue
            if longest_ngram(tokens, hay) >= find_floor:
                return cited, quote, corpus.rel(cand)
    return None


# --- harness ----------------------------------------------------------------

def last_assistant_text(path):
    last = ""
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") == "assistant" or m.get("role") == "assistant":
                    blocks = (m.get("message") or {}).get("content") or m.get("content") or []
                    if isinstance(blocks, list):
                        txt = "".join(
                            b.get("text", "") for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if txt.strip():
                            last = txt
                    elif isinstance(blocks, str) and blocks.strip():
                        last = blocks
                elif m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
                    content = m.get("content")
                    if isinstance(content, str) and content.strip():
                        last = content
                    elif isinstance(content, list):
                        txt = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                        if txt.strip():
                            last = txt
    except Exception:
        return ""
    return last


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        text = last_assistant_text(payload.get("transcript_path") or "")
        if not text:
            return 0
        hit = check(text, Corpus(), time.monotonic() + TIME_BUDGET)
    except Exception:
        return 0  # fail open
    if not hit:
        return 0
    cited, quote, found = hit

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-misquote-guard-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    short = quote if len(quote) <= 120 else quote[:117] + "..."
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Misattributed quote: you attribute \"{short}\" to `{cited}`, "
            f"which does not contain it.\n\n"
            f"It is in `{found}`.\n\n"
            "PR #1468 split the heaviest fragments into `<name>.md` + "
            "`<name>.rationale.md` + `<name>.cases.md`, so a context that "
            "predates that split holds a stale map of which file carries "
            "which passage. Repoint the citation, and re-read the passage at "
            "its real home rather than quoting the in-context copy -- the "
            "wording may also have shifted (the incident this guard is named "
            "for got the tense wrong as well as the file).\n\n"
            "Do NOT read the zero hits in the file you named as evidence the "
            "quote was invented: the passage exists and merely moved, so "
            "filing a hallucination issue or deleting the claim would be the "
            "wrong correction.\n\n"
            f"If you are deliberately reporting that the phrase is ABSENT from "
            f"`{cited}`, say so in the sentence around the quote (\"does not "
            f"contain\", \"zero occurrences\") and resend."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
