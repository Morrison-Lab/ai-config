"""Tests for bigread.py: chunk packing, per-part cleanup, and the no-patch hard error."""
import importlib.util
import os
import sys

import pytest

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bigread.py")
_SPEC = importlib.util.spec_from_file_location("bigread", _PATH)
bigread = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bigread)


def _file(name, patch):
    return {"filename": name, "status": "modified", "patch": patch}


def test_pack_keeps_every_file_exactly_once():
    items = [_file("f%d.qmd" % i, "@@ -1 +1 @@\n-a\n+b\n" * 40) for i in range(200)]
    chunks = bigread.pack(items)
    seen = [n for names, _ in chunks for n in names]
    assert sorted(set(seen)) == sorted(f["filename"] for f in items)
    assert all(len(text) <= bigread.CHUNK_CHARS + 200 for _, text in chunks)


def test_pack_splits_one_huge_patch_without_dropping_lines():
    patch = "\n".join("+line %d" % i for i in range(5000))
    chunks = bigread.pack([_file("big.qmd", patch)])
    assert len(chunks) > 1
    joined = "\n".join(text for _, text in chunks)
    for i in (0, 2500, 4999):
        assert "+line %d" % i in joined


def test_pack_rejects_a_file_with_no_patch():
    with pytest.raises(SystemExit) as exc:
        bigread.pack([{"filename": "img.png", "status": "added"}])
    assert exc.value.code == 5


def test_clean_part_drops_the_repeated_answer_and_status_lines():
    out = "1. problem\n\nVERDICT: FINDINGS\n1. problem\n\n**Stopping Point**: done\n\nVERDICT: FINDINGS"
    assert bigread.clean_part(out) == "1. problem"
