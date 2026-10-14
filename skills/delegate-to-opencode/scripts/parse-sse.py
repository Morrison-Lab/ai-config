#!/usr/bin/env python3
"""Extract text content from an OpenCode Go or OpenAI-compatible SSE stream.

Reads Server-Sent Events (SSE) from standard input (or files specified as
arguments), parses JSON event objects from `data: ` lines, and streams
assembled `delta.content` chunks to standard output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, TextIO


def parse_sse_stream(stream: Iterable[str], out: TextIO = sys.stdout) -> int:
    """Parse SSE lines from stream and write delta content to out.

    Returns:
        0 on success or clean [DONE].
        1 if an upstream error was encountered or no content was produced.
    """
    received_any_content = False
    saw_done = False

    for raw_line in stream:
        line = raw_line.strip()
        if not line:
            continue

        if line == "upstream request failed":
            sys.stderr.write("error: upstream request failed\n")
            return 1

        if line.startswith(":"):
            # SSE comment or keep-alive ping
            continue

        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload == "[DONE]":
                saw_done = True
                break

            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue

            if isinstance(data, dict):
                if "error" in data:
                    err_msg = data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"])
                    sys.stderr.write(f"error: {err_msg}\n")
                    return 1

                choices = data.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    if isinstance(first, dict):
                        delta = first.get("delta")
                        if isinstance(delta, dict):
                            content = delta.get("content")
                            if content:
                                out.write(content)
                                out.flush()
                                received_any_content = True

    return 0 if (received_any_content or saw_done) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Optional input files containing SSE lines (default: stdin)",
    )
    args = parser.parse_args(argv)

    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not args.files:
        return parse_sse_stream(sys.stdin, sys.stdout)

    exit_code = 0
    for path in args.files:
        try:
            with path.open("r", encoding="utf-8") as f:
                code = parse_sse_stream(f, sys.stdout)
                if code != 0:
                    exit_code = code
        except OSError as exc:
            sys.stderr.write(f"error: could not read {path}: {exc}\n")
            return 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
