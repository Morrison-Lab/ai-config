"""Tests for bigread.py: chunk packing, per-part cleanup, and the hard-error paths."""
import importlib.util
import json
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
    assert sorted(seen) == sorted(f["filename"] for f in items)
    headers = [t.count("FILE: ") for _, t in chunks]
    assert sum(headers) == len(items)
    assert all(len(text) <= bigread.CHUNK_CHARS for _, text in chunks)


def test_pack_splits_one_huge_patch_without_dropping_lines():
    patch = "\n".join("+line %d" % i for i in range(5000))
    chunks = bigread.pack([_file("big.qmd", patch)])
    assert len(chunks) > 1
    joined = "\n".join(text for _, text in chunks)
    for i in range(5000):
        assert "+line %d\n" % i in joined + "\n"


def test_pack_terminates_on_a_patch_that_is_one_very_long_line():
    patch = "a" * (3 * bigread.CHUNK_CHARS)
    chunks = bigread.pack([_file("min.js", patch)])
    assert 3 <= len(chunks) <= 6
    assert sum(t.count("a") for _, t in chunks) == len(patch)


def test_pack_rejects_a_file_with_no_patch():
    with pytest.raises(SystemExit) as exc:
        bigread.pack([{"filename": "img.png", "status": "added"}])
    assert exc.value.code == 5


def test_list_files_rejects_an_empty_file_list(monkeypatch):
    monkeypatch.setattr(bigread, "run", lambda cmd: "[]")
    with pytest.raises(SystemExit) as exc:
        bigread.list_files("o/r", "1")
    assert exc.value.code == 5


def test_list_files_joins_several_pages(monkeypatch):
    page = json.dumps([_file("a.qmd", "+x")])
    monkeypatch.setattr(bigread, "run", lambda cmd: page + page)
    assert len(bigread.list_files("o/r", "1")) == 2


def test_clean_part_drops_the_repeated_answer_and_status_lines():
    out = "1. problem\n\nVERDICT: FINDINGS\n1. problem\n\n**Stopping Point**: done\n\nVERDICT: FINDINGS"
    assert bigread.clean_part(out) == "1. problem"
