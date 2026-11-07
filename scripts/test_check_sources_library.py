#!/usr/bin/env python3
"""Regression tests for check-sources-library.py."""
import importlib.util
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "csl", Path(__file__).parent / "check-sources-library.py"
)
csl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csl)

failures = 0


def check(name, condition):
    global failures
    print(("PASS: " if condition else "FAIL: ") + name)
    failures += 0 if condition else 1


def build(tmp: Path, bib: str, md=(), og=()):
    (tmp / "sources" / "md").mkdir(parents=True)
    (tmp / "sources" / "references.bib").write_text(bib, encoding="utf-8")
    for s in md:
        (tmp / "sources" / "md" / f"{s}.md").write_text("x", encoding="utf-8")
    if og:
        (tmp / "sources" / "og").mkdir()
    for s in og:
        (tmp / "sources" / "og" / f"{s}.pdf").write_text("x", encoding="utf-8")


GOOD = "smith-2020-boosting"
with tempfile.TemporaryDirectory() as d:
    build(Path(d), "@article{%s,\n title={T}\n}\n" % GOOD, md=[GOOD], og=[GOOD])
    check("clean library has no findings", csl.audit(Path(d)) == [])
    check("clean library exits 0", csl.main([d]) == 0)

with tempfile.TemporaryDirectory() as d:
    bib = "@book{a-2001-x,\n}\n@article{Bad Key,\n}\n"
    build(Path(d), bib, md=["orphan-2010-thing", "BadName"], og=["only-2012-pdf"])
    kinds = {f for f in csl.audit(Path(d))}
    check("unfiled key", ("unfiled-key", "a-2001-x") in kinds)
    check("orphan md", ("orphan-md", "orphan-2010-thing") in kinds)
    check("unconverted pdf", ("unconverted", "only-2012-pdf") in kinds)
    check("naming violation", ("naming", "BadName") in kinds)
    check("findings exit 1", csl.main([d]) == 1)

with tempfile.TemporaryDirectory() as d:
    check("no bibliography exits 2", csl.main([d]) == 2)

check("name regex accepts etal and letter suffix", bool(csl.NAME_RE.match("smith-etal-2020a-causal-inference")))
check("name regex rejects missing year", not csl.NAME_RE.match("smith-causal-inference"))

raise SystemExit(1 if failures else 0)
