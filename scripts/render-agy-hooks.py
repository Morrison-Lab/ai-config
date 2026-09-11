#!/usr/bin/env python3
"""Render the Antigravity hook manifest for the machine installing it.

`bootstrap.sh` calls this in place of the `cp` it used to run. The canonical
`plugins/ai-config/hooks.json` stays portable (`python3 ~/.gemini/...`), which
Antigravity resolves on macOS and Linux and `cmd.exe` resolves on neither
count: `python3` is usually absent from a Windows PATH and `~` is not expanded
there. Copying it verbatim is what left the Windows install needing a hand
repair, and the repair is what wrote the escaped quotes that broke every
`run_command` hook (https://github.com/Morrison-Lab/ai-config/issues/3091).

Rendering rather than repairing keeps the escaping right by construction:
`json.dumps` writes a real quote in the value as one escape, never two.

Usage:
    python3 scripts/render-agy-hooks.py --output <path>
    python3 scripts/render-agy-hooks.py --platform windows   # print to stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import agy_hooks  # noqa: E402

CANONICAL_MANIFEST = agy_hooks.CANONICAL_MANIFEST


def render(source: Path, windows: bool) -> str:
    """Return the rendered manifest text for one platform."""
    manifest = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"is a {type(manifest).__name__} rather than a JSON object")
    return json.dumps(agy_hooks.render_manifest(manifest, windows), indent=2) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", help="write here instead of stdout")
    parser.add_argument(
        "--platform",
        choices=("auto", "windows", "posix"),
        default="auto",
        help="target launcher; 'auto' reads the running machine",
    )
    parser.add_argument(
        "--source",
        default=str(CANONICAL_MANIFEST),
        help="canonical manifest to render",
    )
    args = parser.parse_args(argv)

    windows = agy_hooks.is_windows() if args.platform == "auto" else args.platform == "windows"
    try:
        text = render(Path(args.source), windows)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not args.output:
        sys.stdout.write(text)
        return 0
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"rendered {out} for {'windows' if windows else 'posix'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
