#!/usr/bin/env python3
"""Self-test for scripts/check-memory-index.py (ai-config#4987).

The negative control comes first: an unregistered file must fail, or a pass on
the real corpus shows nothing.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cmi", HERE / "check-memory-index.py")
cmi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cmi)

failures = 0


def check(name: str, ok: bool) -> None:
    global failures
    print(("PASS: " if ok else "FAIL: ") + name)
    failures += not ok


with tempfile.TemporaryDirectory() as tmp:
    mem = Path(tmp)
    (mem / "MEMORY.md").write_text(
        "| [`a.md`](a.md) | A |\n| [b](./b.md#section) | B |\n", encoding="utf-8"
    )
    for name in ["a.md", "b.md", "c.md"]:
        (mem / name).write_text("x\n", encoding="utf-8")
    check("an unregistered file fails", cmi.main(["--memories", tmp]) == 1)
    check("only the unregistered file is named", cmi.unregistered(mem) == ["c.md"])
    (mem / "MEMORY.md").write_text(
        (mem / "MEMORY.md").read_text(encoding="utf-8") + "| [c](c.md) | C |\n",
        encoding="utf-8",
    )
    check("every file registered passes", cmi.main(["--memories", tmp]) == 0)
    (mem / "MEMORY.md").write_text("mentions c.md in prose only\n", encoding="utf-8")
    check("a bare mention is not a link", cmi.unregistered(mem) == ["a.md", "b.md", "c.md"])
    (mem / "MEMORY.md").unlink()
    check("a missing index exits 2", cmi.main(["--memories", tmp]) == 2)

check("this repo's memories are all registered", cmi.main([]) == 0)

print(f"\n{failures} failed")
sys.exit(1 if failures else 0)
