#!/usr/bin/env python3
"""Check sentence complexity, formulaic openers, and syntactic AI tells in markdown prose.

Morrison-Lab/ai-config, Refs #3108.

Implements algorithmic metrics and deterministic candidate detection for
convoluted sentences and syntactic AI tells, supporting:
- Clause nesting and sentence length thresholds (per shared/writing/ai-tells.md)
- Formulaic sentence openers (bare demonstratives, wh-clefts, partitives, fronted subordinators)
- Copula clefts and cliche markers ("is what/where/when/how", "the whole of it", "own-goal")
- Structural readability proxies (Automated Readability Index, Coleman-Liau, burstiness)

Advisory by default: prints flagged candidates and exits 0.
With --self-test: runs unit tests and exits 0 on pass, 1 on failure.

Usage:
  python3 scripts/check-sentence-complexity.py <file> [<file> ...]
  python3 scripts/check-sentence-complexity.py --threshold-words 30 <file>
  python3 scripts/check-sentence-complexity.py --all --summary <file>
  python3 scripts/check-sentence-complexity.py --self-test
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

# Stripping markdown markup
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")

# Abbreviations that end with a period but do not end a sentence
_ABBREVIATIONS = (
    r"\b(?:e\.g|i\.e|et al|vs|etc|fig|dr|mr|mrs|ms|prof|inc|ltd|co|u\.s|no)\."
)
_ABBR_RE = re.compile(_ABBREVIATIONS, re.IGNORECASE)

# Sentence boundary regex
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")

# Subordinating conjunctions that introduce dependent clauses
_SUBORDINATORS = (
    r"\b(which|whose|because|while|although|despite|since|unless|if|whereas|"
    r"so that|in order that|provided that)\b"
)
_SUBORDINATOR_RE = re.compile(_SUBORDINATORS, re.IGNORECASE)

# Formulaic openers
_OPENER_DEMONSTRATIVE_RE = re.compile(
    r"^(this|that|these|those)\s+(is|are)\b", re.IGNORECASE
)
_OPENER_THE_ONE_THAT_RE = re.compile(r"^the\s+one\s+that\b", re.IGNORECASE)
_OPENER_WH_RE = re.compile(
    r"^(who|what|where|when|why|how|which|whose)\b", re.IGNORECASE
)
_OPENER_PARTITIVE_RE = re.compile(
    r"^(some|many|all|none)\s+of\s+the\b", re.IGNORECASE
)
_OPENER_SUBORDINATOR_RE = re.compile(
    r"^(while|although|despite|because|since|unless)\b", re.IGNORECASE
)

# Copula clefts and cliche markers
_COPULA_CLEFT_RE = re.compile(
    r"\b(is|are|was|were)\s+(what|where|when|how)\b", re.IGNORECASE
)
_CLICHE_RE = re.compile(
    r"\b(the whole of it|own-goal|rather than|not the same as|load-bearing|"
    r"carr(y|ies)|\btells\b|does(n't| not) tell|about what)\b|,\s*however,",
    re.IGNORECASE,
)


def strip_markup(text: str) -> str:
    """Remove code blocks, inline code, comments, images, and unwrap links."""
    text = _FENCE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    text = _HTML_COMMENT_RE.sub("", text)
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    return text


_BLOCK_START_RE = re.compile(r"^\s*(?:[-*+]|\d+\.|#{1,6}|>)\s+")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences while protecting common abbreviations and markdown blocks."""
    # Mask periods in abbreviations temporarily
    def _mask_abbr(match: re.Match[str]) -> str:
        return match.group(0).replace(".", "@@DOT@@")

    # Separate tight markdown list items, headings, and blockquotes so adjacent
    # bullets don't concatenate into single compound sentences.
    lines = text.splitlines()
    normalized_lines: list[str] = []
    for line in lines:
        if _BLOCK_START_RE.match(line):
            normalized_lines.append("\n" + _BLOCK_START_RE.sub("", line))
        else:
            normalized_lines.append(line)
    block_text = "\n".join(normalized_lines)

    masked = _ABBR_RE.sub(_mask_abbr, block_text)
    sentences: list[str] = []
    for paragraph in masked.split("\n\n"):
        para = " ".join(paragraph.split())
        if not para:
            continue
        # Split on sentence terminals
        parts = _SENTENCE_SPLIT_RE.split(para)
        for part in parts:
            clean = part.replace("@@DOT@@", ".").strip()
            # Strip any residual block or bullet marker from sentence start
            clean = re.sub(r"^(?:[-*+>]|\d+\.)\s+", "", clean).strip()
            if clean:
                sentences.append(clean)
    return sentences


def count_words(sentence: str) -> int:
    return len(re.findall(r"\b[a-zA-Z0-9'-]+\b", sentence))


def count_letters_and_digits(sentence: str) -> int:
    return len(re.findall(r"[a-zA-Z0-9]", sentence))


def count_commas(sentence: str) -> int:
    return sentence.count(",")


def count_subordinators(sentence: str) -> int:
    return len(_SUBORDINATOR_RE.findall(sentence))


def find_openers(sentence: str) -> list[str]:
    hits: list[str] = []
    cleaned = re.sub(r"^[*_#\"'([ ]+", "", sentence).strip()
    if _OPENER_DEMONSTRATIVE_RE.match(cleaned):
        hits.append("bare demonstrative ('This/That is')")
    if _OPENER_THE_ONE_THAT_RE.match(cleaned):
        hits.append("'The one that'")
    if _OPENER_WH_RE.match(cleaned):
        hits.append("fronted wh-clause ('What/Why/How...')")
    if _OPENER_PARTITIVE_RE.match(cleaned):
        hits.append("partitive quantifier ('Some/Many/All/None of the')")
    if _OPENER_SUBORDINATOR_RE.match(cleaned):
        hits.append("fronted subordinator ('While/Although/Despite...')")
    return hits


def find_copula_clefts(sentence: str) -> list[str]:
    return [m.group(0) for m in _COPULA_CLEFT_RE.finditer(sentence)]


def find_cliches(sentence: str) -> list[str]:
    return [m.group(0) for m in _CLICHE_RE.finditer(sentence)]


def compute_readability(
    sentences: list[str],
) -> dict[str, float]:
    """Compute ARI, Coleman-Liau, and burstiness for a list of sentences."""
    if not sentences:
        return {
            "sentence_count": 0,
            "word_count": 0,
            "mean_words_per_sentence": 0.0,
            "ari": 0.0,
            "coleman_liau": 0.0,
            "burstiness": 0.0,
        }

    sentence_lengths = [count_words(s) for s in sentences]
    total_words = sum(sentence_lengths)
    total_chars = sum(count_letters_and_digits(s) for s in sentences)
    num_sentences = len(sentences)

    if total_words == 0:
        return {
            "sentence_count": num_sentences,
            "word_count": 0,
            "mean_words_per_sentence": 0.0,
            "ari": 0.0,
            "coleman_liau": 0.0,
            "burstiness": 0.0,
        }

    mean_words = total_words / num_sentences
    variance = sum((l - mean_words) ** 2 for l in sentence_lengths) / num_sentences
    std_dev = math.sqrt(variance)
    burstiness = (std_dev / mean_words) if mean_words > 0 else 0.0

    # Automated Readability Index (Smith & Senter, 1967)
    ari = 4.71 * (total_chars / total_words) + 0.5 * mean_words - 21.43

    # Coleman-Liau Index (Coleman & Liau, 1975)
    l_per_100 = (total_chars / total_words) * 100
    s_per_100 = (num_sentences / total_words) * 100
    coleman_liau = 0.0588 * l_per_100 - 0.296 * s_per_100 - 15.8

    return {
        "sentence_count": num_sentences,
        "word_count": total_words,
        "mean_words_per_sentence": round(mean_words, 2),
        "ari": round(ari, 2),
        "coleman_liau": round(coleman_liau, 2),
        "burstiness": round(burstiness, 3),
    }


def analyze_sentence(
    sentence: str,
    threshold_words: int = 25,
    threshold_commas: int = 3,
    threshold_subordinators: int = 2,
    check_openers: bool = True,
    check_cliches: bool = True,
) -> list[str]:
    """Return reasons why this sentence was flagged, if any."""
    flags: list[str] = []
    words = count_words(sentence)
    commas = count_commas(sentence)
    subordinators = count_subordinators(sentence)

    # Convoluted structure cues
    if words >= threshold_words:
        flags.append(f"length ({words} words >= {threshold_words})")
    if commas >= threshold_commas and subordinators >= 1:
        flags.append(
            f"convoluted nesting ({commas} commas + {subordinators} subordinator(s))"
        )
    elif subordinators >= threshold_subordinators:
        flags.append(f"multiple subordinators ({subordinators} subordinator(s))")

    # Opener cues
    if check_openers:
        openers = find_openers(sentence)
        for opener in openers:
            flags.append(f"formulaic opener: {opener}")

    # Cliche / cleft cues
    if check_cliches:
        clefts = find_copula_clefts(sentence)
        for cleft in clefts:
            flags.append(f"unnecessary copula cleft: '{cleft}'")
        cliches = find_cliches(sentence)
        for cliche in cliches:
            flags.append(f"cliche/jargon: '{cliche}'")

    return flags


def scan_text(
    text: str,
    threshold_words: int = 25,
    threshold_commas: int = 3,
    threshold_subordinators: int = 2,
    check_openers: bool = True,
    check_cliches: bool = True,
) -> tuple[list[tuple[str, list[str]]], dict[str, float]]:
    clean = strip_markup(text)
    sents = split_sentences(clean)
    flagged: list[tuple[str, list[str]]] = []
    for s in sents:
        reasons = analyze_sentence(
            s,
            threshold_words=threshold_words,
            threshold_commas=threshold_commas,
            threshold_subordinators=threshold_subordinators,
            check_openers=check_openers,
            check_cliches=check_cliches,
        )
        if reasons:
            flagged.append((s, reasons))
    metrics = compute_readability(sents)
    return flagged, metrics


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        except OSError:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
        except OSError:
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument(
        "--threshold-words",
        type=int,
        default=25,
        help="minimum words in a sentence to flag (default 25)",
    )
    parser.add_argument(
        "--threshold-commas",
        type=int,
        default=3,
        help="minimum commas accompanied by a subordinator to flag (default 3)",
    )
    parser.add_argument(
        "--threshold-subordinators",
        type=int,
        default=2,
        help="minimum subordinators in a sentence to flag (default 2)",
    )
    parser.add_argument(
        "--check-openers",
        action="store_true",
        default=True,
        help="flag formulaic sentence openers (default True)",
    )
    parser.add_argument(
        "--no-check-openers",
        dest="check_openers",
        action="store_false",
        help="disable checking formulaic sentence openers",
    )
    parser.add_argument(
        "--check-cliches",
        action="store_true",
        default=True,
        help="flag cliches and copula clefts (default True)",
    )
    parser.add_argument(
        "--no-check-cliches",
        dest="check_cliches",
        action="store_false",
        help="disable checking cliches and copula clefts",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print readability metrics summary per file",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run self-tests and exit",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.files:
        parser.print_usage()
        return 2

    total_flagged = 0
    total_sentences = 0
    for path in args.files:
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as err:
            print(f"Error reading {path}: {err}", file=sys.stderr)
            continue

        flagged, metrics = scan_text(
            content,
            threshold_words=args.threshold_words,
            threshold_commas=args.threshold_commas,
            threshold_subordinators=args.threshold_subordinators,
            check_openers=args.check_openers,
            check_cliches=args.check_cliches,
        )
        total_sentences += int(metrics["sentence_count"])
        if flagged:
            print(f"\n{path} ({len(flagged)} flagged candidate(s)):")
            for sent, reasons in flagged:
                total_flagged += 1
                reason_str = "; ".join(reasons)
                print(f"  [{reason_str}]")
                print(f"    {sent}")

        if args.summary:
            print(
                f"  Summary for {path}: {metrics['sentence_count']} sentences, "
                f"{metrics['word_count']} words, mean {metrics['mean_words_per_sentence']} w/s, "
                f"ARI={metrics['ari']}, Coleman-Liau={metrics['coleman_liau']}, "
                f"burstiness={metrics['burstiness']}"
            )

    print(
        f"\nExamined {len(args.files)} file(s), {total_sentences} sentence(s); "
        f"{total_flagged} candidate(s) flagged."
    )
    print("Advisory only: evaluate candidates in context before revising.")
    return 0


# --- self-test -------------------------------------------------------------

_TEST_LONG_CONVOLUTED = (
    "Although the initial simulation appeared promising, the subsequent "
    "iterations revealed unexpected boundary conditions, which caused the "
    "gradient to diverge uncontrollably, and therefore forced a complete restart "
    "of the optimization pipeline."
)

_TEST_CLEAN_SHORT = (
    "The estimator converges to the true parameter as the sample grows."
)

_TEST_OPENER_DEMONSTRATIVE = "This is the primary constraint."
_TEST_OPENER_THE_ONE_THAT = "The one that failed was the lease checker."
_TEST_OPENER_WH = "What makes it work is the lease."
_TEST_OPENER_PARTITIVE = "Some of the checks failed on the remote."
_TEST_OPENER_SUBORDINATOR = (
    "While the test suite passed, the manual verification failed."
)

_TEST_COPULA_CLEFT = "The lease is what stops background fetch collisions."
_TEST_CLICHE = "The whole of it was an own-goal rather than a success."


def run_self_test() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        status = "PASS" if cond else "FAIL"
        print(f"{status}: {name}")
        if not cond:
            failures += 1

    # Convoluted sentence detection
    reasons = analyze_sentence(_TEST_LONG_CONVOLUTED, threshold_words=25)
    check(
        "convoluted sentence is flagged for length and nesting",
        any("length" in r for r in reasons)
        and any("nesting" in r or "subordinator" in r for r in reasons),
    )

    # Clean short sentence is not flagged
    reasons_clean = analyze_sentence(_TEST_CLEAN_SHORT, threshold_words=25)
    check("clean short sentence is not flagged", len(reasons_clean) == 0)

    # Mutation test: raising threshold above word count disables length flag
    words_count = count_words(_TEST_LONG_CONVOLUTED)
    reasons_mutated = analyze_sentence(
        _TEST_LONG_CONVOLUTED, threshold_words=words_count + 5
    )
    check(
        "raising threshold_words silences length flag",
        not any("length" in r for r in reasons_mutated),
    )

    # Formulaic openers
    check(
        "opener 'This is' flagged",
        any("bare demonstrative" in r for r in find_openers(_TEST_OPENER_DEMONSTRATIVE)),
    )
    check(
        "opener 'The one that' flagged",
        any("The one that" in r for r in find_openers(_TEST_OPENER_THE_ONE_THAT)),
    )
    check(
        "opener 'What makes...' flagged",
        any("fronted wh-clause" in r for r in find_openers(_TEST_OPENER_WH)),
    )
    check(
        "opener 'Some of the...' flagged",
        any("partitive quantifier" in r for r in find_openers(_TEST_OPENER_PARTITIVE)),
    )
    check(
        "opener 'While...' flagged",
        any(
            "fronted subordinator" in r for r in find_openers(_TEST_OPENER_SUBORDINATOR)
        ),
    )

    # Copula clefts and cliches
    clefts = find_copula_clefts(_TEST_COPULA_CLEFT)
    check(
        "copula cleft 'is what' flagged",
        len(clefts) == 1 and clefts[0].lower() == "is what",
    )

    cliches = find_cliches(_TEST_CLICHE)
    check(
        "cliches 'the whole of it', 'own-goal', 'rather than' flagged",
        len(cliches) >= 3,
    )

    # Fenced code block stripping
    fenced_doc = (
        "Here is some text.\n\n"
        "```python\n"
        "this is what happens when code runs\n"
        "```\n\n"
        "And clean trailing text."
    )
    flagged, _ = scan_text(
        fenced_doc,
        threshold_words=25,
        check_openers=True,
        check_cliches=True,
    )
    check(
        "fenced code does not trigger opener or copula cleft flags",
        len(flagged) == 0,
    )

    # Tight markdown list items must not be merged into one sentence
    tight_list = (
        "- First point ends here.\n"
        "- Second point starts here and continues for a while.\n"
        "- Third bullet item.\n"
    )
    tight_sents = split_sentences(strip_markup(tight_list))
    check(
        "tight markdown list splits into 3 separate sentences",
        len(tight_sents) == 3
        and tight_sents[0] == "First point ends here."
        and tight_sents[1] == "Second point starts here and continues for a while."
        and tight_sents[2] == "Third bullet item.",
    )

    # Readability computation
    metrics = compute_readability([_TEST_LONG_CONVOLUTED, _TEST_CLEAN_SHORT])
    check("sentence count is 2", metrics["sentence_count"] == 2)
    check("word count is positive", metrics["word_count"] > 30)
    check("burstiness is positive", metrics["burstiness"] > 0.0)

    print(f"\n{failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
