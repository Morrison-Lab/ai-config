#!/usr/bin/env python3
"""Tests for scripts/check-sentence-complexity.py.

Morrison-Lab/ai-config, Refs #3108.

Delegates to the checker script's own --self-test suite, which tests:
- Convoluted sentence detection (word count >= threshold, commas + subordinators)
- Negative control (clean short sentence stays quiet)
- Mutation test (raising threshold_words silences length flag)
- Formulaic sentence openers (bare demonstratives, 'the one that', wh-clauses, partitives, fronted subordinators)
- Copula clefts and cliche markers ('is what/where/when/how', 'the whole of it', 'own-goal', 'rather than')
- Markup stripping (fenced code blocks do not trigger false positives)
- Readability metrics (ARI, Coleman-Liau, burstiness)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_sentence_complexity",
    Path(__file__).parent / "check-sentence-complexity.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

if __name__ == "__main__":
    raise SystemExit(mod.run_self_test())
