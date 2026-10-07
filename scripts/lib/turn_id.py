#!/usr/bin/env python3
"""Extract turn or prompt identifier from tool payload or transcript.

Extracts turn or prompt identifier from direct payload keys or walks a
transcript file to resolve the stable identity of the current turn,
handling multi-turn histories, ID-less prompts, tool boundaries, and
harness metadata (ai-config#4308).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

_LIB = os.path.dirname(os.path.realpath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from transcript_meta import is_harness_meta, is_skill_load_meta
except Exception:
    def is_skill_load_meta(entry):  # noqa: D103 -- fail-open fallback
        return bool(isinstance(entry, dict) and entry.get("isMeta") and entry.get("sourceToolUseID"))

    def is_harness_meta(entry):  # noqa: D103 -- fail-open fallback
        return bool(
            isinstance(entry, dict)
            and entry.get("isMeta")
            and not entry.get("sourceToolUseID")
            and entry.get("promptSource") != "sdk"
        )


def extract_turn_id(payload: dict) -> str:
    """Extract turn or prompt identifier from payload or transcript."""
    for key in (
        "prompt_id",
        "promptId",
        "turn_id",
        "turnId",
        "step_index",
        "stepIndex",
    ):
        val = payload.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    tpath = (
        payload.get("transcript_path")
        or payload.get("transcriptPath")
        or payload.get("transcript")
        or payload.get("history_file")
        or ""
    )
    if tpath and os.path.exists(tpath):
        try:
            with open(tpath, "r", encoding="utf-8") as f:
                content = f.read()
            current_turn_id = ""
            prompt_lines_so_far = []
            last_prompt_unhashed = False
            for line in content.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    event = json.loads(line_str)
                except Exception:
                    continue
                if not isinstance(event, dict):
                    continue

                if is_skill_load_meta(event) or is_harness_meta(event):
                    continue
                if event.get("isSidechain"):
                    continue

                etype = event.get("type") or event.get("role") or ""
                source = event.get("source") or ""
                if etype in {"user", "USER_INPUT"} or source == "USER_EXPLICIT":
                    blocks = (
                        (event.get("message") or {}).get("content")
                        or event.get("content")
                        or []
                    )
                    is_tool_result = (
                        event.get("type") == "tool_result"
                        or (
                            isinstance(blocks, list)
                            and any(
                                isinstance(b, dict) and b.get("type") == "tool_result"
                                for b in blocks
                            )
                        )
                    )
                    if not is_tool_result:
                        prompt_lines_so_far.append(line_str)
                        ev_id = None
                        for k in (
                            "prompt_id",
                            "promptId",
                            "turn_id",
                            "turnId",
                            "step_index",
                            "stepIndex",
                        ):
                            val = event.get(k)
                            if val is not None and str(val).strip():
                                ev_id = str(val).strip()
                                break
                        if ev_id is None:
                            val = (event.get("message") or {}).get("id") or event.get("id")
                            if val is not None and str(val).strip():
                                ev_id = str(val).strip()
                        if ev_id is not None:
                            current_turn_id = ev_id
                            last_prompt_unhashed = False
                        else:
                            # Prompt lacks an ID: defer hashing until after the scan
                            # so each final prefix is hashed only once, avoiding quadratic
                            # hashing across growing prompt histories.
                            current_turn_id = None
                            last_prompt_unhashed = True

            if current_turn_id:
                return current_turn_id
            if last_prompt_unhashed and prompt_lines_so_far:
                prefix = "\n".join(prompt_lines_so_far)
                return hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:16]

            # Fallback for transcripts with no genuine prompt boundary
            last_id = ""
            for line in content.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    event = json.loads(line_str)
                except Exception:
                    continue
                if not isinstance(event, dict):
                    continue
                ev_id = None
                for k in (
                    "prompt_id",
                    "promptId",
                    "turn_id",
                    "turnId",
                    "step_index",
                    "stepIndex",
                ):
                    val = event.get(k)
                    if val is not None and str(val).strip():
                        ev_id = str(val).strip()
                        break
                if ev_id is None:
                    val = (event.get("message") or {}).get("id") or event.get("id")
                    if val is not None and str(val).strip():
                        ev_id = str(val).strip()
                if ev_id is not None:
                    last_id = ev_id

            if last_id:
                return last_id
            if content.strip():
                return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        except Exception:
            pass
    return ""
