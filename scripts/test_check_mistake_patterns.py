#!/usr/bin/env python3
"""Tests for scripts/check-mistake-patterns.py (Morrison-Lab/ai-config#2946)."""
import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "check-mistake-patterns.py"
spec = importlib.util.spec_from_file_location("check_mistake_patterns", SCRIPT)
cmp_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cmp_mod)

passes = 0
failures = 0


def check(name, cond):
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name}")


def problems(text):
    return cmp_mod.find_problems(cmp_mod.pattern_numbers(text))


def heading(n, title="T"):
    return f"## Pattern {n}: {title}\n- **Do**: x\n"


def test_clean_sequence():
    text = "# Title\n\n" + heading(1) + heading(2) + heading(3)
    check("a 1..3 sequence is clean", problems(text) == [])


def test_lettered_subpatterns():
    text = heading(4) + heading(5) + heading("5b") + heading("5c") + heading(6)
    check("5, 5b, 5c, 6 is clean (the file's existing scheme)",
          problems("# T\n" + heading(1) + heading(2) + heading(3) + text) == [])


def test_duplicate_is_reported_once():
    text = heading(1) + heading(2) + heading(2) + heading(3)
    got = problems(text)
    check("a duplicated number is reported", len(got) == 1 and "duplicates" in got[0])


def test_gap_and_reorder_reported_locally():
    text = heading(1) + heading(2) + heading(4) + heading(5)
    got = problems(text)
    check("a gap is reported once, at the point of divergence, not on every later heading",
          len(got) == 1 and "Pattern 4 follows Pattern 2" in got[0])
    swapped = heading(1) + heading(3) + heading(2) + heading(4)
    got = problems(swapped)
    check("an out-of-order pair is reported at both headings and nowhere else", len(got) == 2)


def test_measured_2026_09_01_defect():
    """The live defect the checker found on its first run: 34, 36, 35, 36, 37."""
    text = heading(34) + heading(36) + heading(35) + heading(36) + heading(37)
    prefix = "".join(heading(i) for i in range(1, 34))
    got = problems(prefix + text)
    check("the 34/36/35/36/37 sequence reports the duplicate 36 and the misordered 36 and 35",
          any("duplicates" in p for p in got) and any("Pattern 36 follows Pattern 34" in p for p in got))


def test_letter_must_follow_its_base():
    text = heading(1) + heading(2) + heading("1b") + heading(3)
    got = problems(text)
    check("a lettered sub-pattern away from its base is reported", len(got) == 1 and "1b" in got[0])
    text = heading(1) + heading("1c") + heading(2)
    got = problems(text)
    check("a lettered sub-pattern must start at b", len(got) == 1 and "Pattern 1b" in got[0])


def test_non_pattern_headings_ignored():
    text = heading(1) + "## Some prose section\n\ntext\n" + heading(2)
    check("an un-numbered ## heading is ignored", problems(text) == [])
    check("only Pattern headings are counted", len(cmp_mod.pattern_numbers(text)) == 2)


def test_live_file_is_clean():
    """Dogfood: the shipped memories/mistake-patterns.md passes (this is the CI gate)."""
    live = Path(__file__).parent.parent / "memories" / "mistake-patterns.md"
    got = problems(live.read_text(encoding="utf-8"))
    for p in got:
        print("   ", p)
    check("memories/mistake-patterns.md has unique, sequential pattern numbers", got == [])
    check("exit code is 0 on the live file", cmp_mod.main([str(live)]) == 0)


def test_unreadable_file_exits_2():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as fh:
        fh.write(b"\xff\xfe\x00\x01")
        bad = fh.name
    check("a non-UTF-8 file exits 2, not 1", cmp_mod.main([bad]) == 2)
    check("a missing file exits 2", cmp_mod.main(["/nonexistent/mistake-patterns.md"]) == 2)


def main():
    test_unreadable_file_exits_2()
    test_clean_sequence()
    test_lettered_subpatterns()
    test_duplicate_is_reported_once()
    test_gap_and_reorder_reported_locally()
    test_measured_2026_09_01_defect()
    test_letter_must_follow_its_base()
    test_non_pattern_headings_ignored()
    test_live_file_is_clean()
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
