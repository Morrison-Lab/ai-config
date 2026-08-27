#!/usr/bin/env python3
"""Validate the copyable OAICopilot model template and its quota policy."""

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "skills/register-oaicopilot-models/models-template.jsonc"


def strip_jsonc(text: str) -> str:
    """Remove line comments and trailing commas without altering strings."""
    out = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            out.append(char)
        elif char == "/" and index + 1 < len(text) and text[index + 1] == "/":
            index += 2
            while index < len(text) and text[index] != "\n":
                index += 1
            if index < len(text):
                out.append("\n")
        else:
            out.append(char)
        index += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def policy_errors(models: list[dict]) -> list[str]:
    """Return every schema or operational-policy violation."""
    errors = []
    ids = [model.get("id") for model in models]
    if len(ids) != len(set(ids)):
        errors.append("model ids must be unique")

    required = {"id", "owned_by", "family", "context_length", "max_tokens",
                "baseUrl", "apiMode"}
    for model in models:
        model_id = model.get("id", "<missing id>")
        missing = sorted(required - model.keys())
        if missing:
            errors.append(f"{model_id}: missing {', '.join(missing)}")
            continue
        if model["max_tokens"] >= model["context_length"]:
            errors.append(f"{model_id}: max_tokens must be below context_length")

    expected = {
        "databricks-claude-opus-5": (64000, 16000, 15000),
        "databricks-claude-sonnet-5": (64000, 16000, 15000),
        "databricks-claude-opus-4-1": (64000, 16000, 15000),
        "databricks-gpt-5-5": (64000, 16000, 15000),
        "databricks-gpt-5-3-codex": (64000, 16000, 15000),
        "databricks-gemini-3-7-flash": (64000, 16000, 15000),
        "databricks-inkling": (64000, 8192, 15000),
        "databricks-gpt-5-6-sol": (400000, 16000, None),
        "databricks-gpt-oss-120b": (131072, 25000, None),
        "databricks-llama-4-maverick": (128000, 8192, None),
    }
    by_id = {model.get("id"): model for model in models}
    if set(by_id) != set(expected):
        errors.append("template model ids differ from the policy test inventory")
    for model_id, (context, output, delay) in expected.items():
        model = by_id.get(model_id)
        if model is None:
            continue
        actual = (model.get("context_length"), model.get("max_tokens"),
                  model.get("delay"))
        if actual != (context, output, delay):
            errors.append(f"{model_id}: expected {(context, output, delay)}, got {actual}")

    for model_id in ("databricks-gpt-5-5", "databricks-gpt-5-3-codex"):
        model = by_id.get(model_id, {})
        if model.get("apiMode") != "openai-responses":
            errors.append(f"{model_id}: current catalog requires openai-responses")
    return errors


models = json.loads(strip_jsonc(TEMPLATE.read_text(encoding="utf-8")))
failures = policy_errors(models)
if failures:
    print("FAIL: OAICopilot model template")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

# Negative control: prove that a provider-maximum context regression is caught.
mutated = [dict(model) for model in models]
mutated[0]["context_length"] = 1_000_000
if not policy_errors(mutated):
    print("FAIL: negative control did not detect quota-policy drift")
    sys.exit(1)

print(f"PASS: OAICopilot template policy ({len(models)} entries)")
