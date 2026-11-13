#!/usr/bin/env python3
"""Refuse an advisor consult whose seat is not independent of the caller.

The advisor skill (skills/advisor/SKILL.md) asks a model from a different
family for one opinion. Two of its rules are mechanical, so this script checks
them instead of leaving them to the caller's judgment:

- Step 3: `model` and `effort` are passed explicitly, never inherited.
- Step 4: never fall back to the caller's family. A same-family seat is
  refused unless --allow-same-family is given, and then it is labelled weaker.

Run it twice: once before the call (`--caller-model`, `--engine`, `--model`,
`--effort`), and again after it with `--reported-model` set to the model the
reply names, so a silent substitution by the engine is caught too.

Exit 0 prints `independent` or `weaker: same family (<family>)`.
Exit 2 prints the reason for the refusal on stderr (argparse also exits 2 on
a missing or malformed argument).
See ai-config#884.
"""

import argparse
import re
import sys

# An engine whose name contains this word is never an advisor seat. Codex is
# allowed only in UCDH projects, which this skill does not serve
# (skills/advisor/SKILL.md).
REFUSED_ENGINE_WORD = "codex"

# Effort values that name no level, so passing one is inheriting.
INHERITED_EFFORTS = {"default", "inherit", "inherited", "auto", "unset", "-"}

# Model-name prefixes mapped to the family that trained the model. A prefix
# matches the start of a name segment (split on `/`, `:` and `.`) and must be
# followed by the end of the segment or a non-letter, so `o1` matches `o1-pro`
# but not `o1x`. Extend it per call with --family PREFIX=FAMILY.
FAMILY_PREFIXES = {
    "claude": "anthropic",
    "opus": "anthropic",
    "sonnet": "anthropic",
    "haiku": "anthropic",
    "fable": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "codex": "openai",
    "gemini": "google",
    "gemma": "google",
    "glm": "zhipu",
    "kimi": "moonshot",
    "deepseek": "deepseek",
    "qwen": "alibaba",
    "minimax": "minimax",
    "grok": "xai",
    "llama": "meta",
    "mistral": "mistral",
    "mixtral": "mistral",
    "codestral": "mistral",
}


class Refusal(Exception):
    """The seat fails a rule; the message says which."""


def _matches(segment: str, prefix: str) -> bool:
    if not segment.startswith(prefix):
        return False
    rest = segment[len(prefix):]
    return not rest or not rest[0].isalpha()


def family(model: str, prefixes=None) -> str:
    """Return the family of a model name, or raise Refusal if it is unknown.

    Every segment is classified, so `bedrock/us.anthropic.claude-opus`
    resolves on `claude-opus`. Segments naming two families make the name
    ambiguous, and an unknown name fails closed: guessing either could seat a
    same-family model as independent.
    """
    table = FAMILY_PREFIXES if prefixes is None else prefixes
    segments = re.split(r"[/:.]", model.strip().lower())
    found = {
        fam
        for segment in segments
        for prefix, fam in table.items()
        if _matches(segment, prefix)
    }
    if len(found) > 1:
        raise Refusal(
            f"{model!r} names more than one family ({', '.join(sorted(found))})"
        )
    if found:
        return found.pop()
    raise Refusal(
        f"unknown model family for {model!r}; pass --family PREFIX=FAMILY "
        "or add the prefix to FAMILY_PREFIXES in scripts/check-advisor-seat.py"
    )


def _bare(model: str) -> str:
    """Drop a `provider/` path and a `:tag` suffix such as `:free`."""
    return model.strip().lower().rsplit("/", 1)[-1].split(":", 1)[0]


def same_model(requested: str, reported: str) -> bool:
    """True when the reply's model is the requested one, or a dated snapshot.

    `gpt-5-2025-08-07` answers a request for `gpt-5`; `gpt-5-mini` does not.
    """
    req, rep = _bare(requested), _bare(reported)
    if rep == req:
        return True
    return bool(re.fullmatch(re.escape(req) + r"-\d{4}-?\d{2}-?\d{2}", rep))


def check_seat(caller_model, engine, model, effort, reported_model=None,
               allow_same_family=False, prefixes=None):
    """Return the seat's label, or raise Refusal."""
    if REFUSED_ENGINE_WORD in engine.strip().lower():
        raise Refusal(f"engine {engine!r} is never an advisor seat")
    if not model.strip():
        raise Refusal("model must be passed explicitly")
    if effort.strip().lower() in INHERITED_EFFORTS | {""}:
        raise Refusal(
            f"effort {effort!r} names no level; pin one, do not inherit it"
        )
    if reported_model is not None and not same_model(model, reported_model):
        raise Refusal(
            f"the reply came from {reported_model!r}, not the requested "
            f"{model!r}; treat it as a fallback, not the consult"
        )
    caller = family(caller_model, prefixes)
    seat = family(model, prefixes)
    if seat != caller:
        return "independent"
    if not allow_same_family:
        raise Refusal(
            f"{model!r} is in the caller's family ({caller}); a same-family "
            "seat is not independent. Pick another engine, or pass "
            "--allow-same-family and report the answer as weaker"
        )
    return f"weaker: same family ({caller})"


def _family_pair(text):
    prefix, sep, fam = text.partition("=")
    if not sep or not prefix.strip() or not fam.strip():
        raise argparse.ArgumentTypeError("expected PREFIX=FAMILY")
    return prefix.strip().lower(), fam.strip().lower()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--caller-model", required=True,
                    help="the model running the calling session")
    ap.add_argument("--engine", required=True,
                    help="the CLI or endpoint reaching the advisor")
    ap.add_argument("--model", required=True, help="the advisor model")
    ap.add_argument("--effort", required=True, help="the pinned effort")
    ap.add_argument("--reported-model",
                    help="the model the reply says answered (post-call check)")
    ap.add_argument("--allow-same-family", action="store_true",
                    help="accept a same-family seat, labelled weaker")
    ap.add_argument("--family", type=_family_pair, action="append",
                    default=[], metavar="PREFIX=FAMILY",
                    help="add or override a model-name prefix (repeatable)")
    args = ap.parse_args(argv)
    prefixes = {**FAMILY_PREFIXES, **dict(args.family)}
    try:
        label = check_seat(
            args.caller_model, args.engine, args.model, args.effort,
            args.reported_model, args.allow_same_family, prefixes,
        )
    except Refusal as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
