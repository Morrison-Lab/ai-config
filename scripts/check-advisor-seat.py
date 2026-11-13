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
Exit 2 prints the reason for the refusal on stderr.
See ai-config#884.
"""

import argparse
import sys

# Engines the lab never seats as an advisor. Codex is allowed only in UCDH
# projects, which this skill does not serve (skills/advisor/SKILL.md).
REFUSED_ENGINES = {"codex"}

# Model-name prefixes, matched after any `provider/` path, mapped to the
# family that trained the model. No prefix is a prefix of another, so order
# does not matter.
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
    "codestral": "mistral",
}


class Refusal(Exception):
    """The seat fails a rule; the message says which."""


def family(model: str) -> str:
    """Return the family of a model name, or raise Refusal if it is unknown.

    An unknown name fails closed: guessing its family could seat a
    same-family model as independent.
    """
    name = model.strip().lower().rsplit("/", 1)[-1]
    for prefix, fam in FAMILY_PREFIXES.items():
        if name.startswith(prefix):
            return fam
    raise Refusal(
        f"unknown model family for {model!r}; add its prefix to "
        "FAMILY_PREFIXES in scripts/check-advisor-seat.py"
    )


def check_seat(caller_model, engine, model, effort, reported_model=None,
               allow_same_family=False):
    """Return the seat's label, or raise Refusal."""
    if engine.strip().lower() in REFUSED_ENGINES:
        raise Refusal(f"engine {engine!r} is never an advisor seat")
    if not model.strip():
        raise Refusal("model must be passed explicitly")
    if not effort.strip():
        raise Refusal("effort must be passed explicitly, not inherited")
    if reported_model is not None and (
        reported_model.strip().lower() != model.strip().lower()
    ):
        raise Refusal(
            f"the reply came from {reported_model!r}, not the requested "
            f"{model!r}; treat it as a fallback, not the consult"
        )
    caller = family(caller_model)
    seat = family(model)
    if seat != caller:
        return "independent"
    if not allow_same_family:
        raise Refusal(
            f"{model!r} is in the caller's family ({caller}); a same-family "
            "seat is not independent. Pick another engine, or pass "
            "--allow-same-family and report the answer as weaker"
        )
    return f"weaker: same family ({caller})"


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
    args = ap.parse_args(argv)
    try:
        label = check_seat(
            args.caller_model, args.engine, args.model, args.effort,
            args.reported_model, args.allow_same_family,
        )
    except Refusal as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
