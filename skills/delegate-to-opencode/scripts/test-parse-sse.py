#!/usr/bin/env python3
"""Unit tests for parse-sse.py."""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add script directory to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("parse_sse", SCRIPTS_DIR / "parse-sse.py")
parse_sse = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(parse_sse)  # type: ignore[union-attr]


class TestParseSSE(unittest.TestCase):
    def test_clean_stream(self) -> None:
        input_data = [
            ': keep-alive\n',
            'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
            '\n',
            'data: {"choices":[{"delta":{"content":" world!"}}]}\n',
            'data: [DONE]\n',
        ]
        out = io.StringIO()
        code = parse_sse.parse_sse_stream(input_data, out=out)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "Hello world!")

    def test_upstream_failure(self) -> None:
        input_data = [
            'upstream request failed\n',
        ]
        out = io.StringIO()
        code = parse_sse.parse_sse_stream(input_data, out=out)
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")

    def test_error_json_payload(self) -> None:
        input_data = [
            'data: {"error": {"message": "Rate limit reached"}}\n',
        ]
        out = io.StringIO()
        code = parse_sse.parse_sse_stream(input_data, out=out)
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")

    def test_empty_stream(self) -> None:
        input_data: list[str] = []
        out = io.StringIO()
        code = parse_sse.parse_sse_stream(input_data, out=out)
        self.assertEqual(code, 1)

    def test_cli_stdin(self) -> None:
        script_path = SCRIPTS_DIR / "parse-sse.py"
        raw_input = 'data: {"choices":[{"delta":{"content":"From STDIN"}}]}\ndata: [DONE]\n'
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            input=raw_input,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(proc.stdout, "From STDIN")

    def test_cli_file(self) -> None:
        script_path = SCRIPTS_DIR / "parse-sse.py"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write('data: {"choices":[{"delta":{"content":"From FILE"}}]}\ndata: [DONE]\n')
            temp_path = Path(f.name)
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path), str(temp_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(proc.stdout, "From FILE")
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
