#!/usr/bin/env python3
"""Tests for scripts/lib/fences.py (CommonMark fence/code stripper, ai-config#1567)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import (  # noqa: E402
    count_unbalanced_fences,
    find_fence_spans,
    find_indented_code_block_lines,
    strip_code,
    strip_code_spans,
    strip_fences,
    strip_indented_code_blocks,
)

passed = 0
failed = 0


def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {name}")
    else:
        failed += 1
        print(f"FAIL: {name}")


# 1. Discriminating case from issue #1567: runs of 4, 3, 4, 3, 3 backticks
doc_43433 = """````
inside 4
```
still inside 4
````
outside 1
```
inside 3
```
outside 2"""

stripped_43433 = strip_fences(doc_43433)
check("discriminating 4,3,4,3,3: outside 1 is preserved", "outside 1" in stripped_43433)
check("discriminating 4,3,4,3,3: outside 2 is preserved", "outside 2" in stripped_43433)
check("discriminating 4,3,4,3,3: inside 4 is stripped", "inside 4" not in stripped_43433)
check("discriminating 4,3,4,3,3: still inside 4 is stripped", "still inside 4" not in stripped_43433)
check("discriminating 4,3,4,3,3: inside 3 is stripped", "inside 3" not in stripped_43433)

# 2. Tildes and Backticks don't cross-close
doc_tilde_cross = """```
@inside_backtick
~~~
@still_inside_backtick
```
@outside
~~~
@inside_tilde
~~~"""
stripped_tilde = strip_fences(doc_tilde_cross)
check("tilde does not close backtick fence", "@inside_backtick" not in stripped_tilde)
check("content between tilde and backtick closer stays stripped", "@still_inside_backtick" not in stripped_tilde)
check("prose between blocks is preserved", "@outside" in stripped_tilde)
check("tilde block is stripped", "@inside_tilde" not in stripped_tilde)

# 3. Indented fences up to 3 spaces
doc_indented = """   ```python
   def foo():
       pass
   ```
real prose"""
stripped_indent = strip_fences(doc_indented)
check("indented fence is stripped", "def foo():" not in stripped_indent)
check("prose after indented fence is preserved", "real prose" in stripped_indent)

# 4. Info string containing backticks is not a valid backtick opener
doc_invalid_opener = """``` `invalid`
this is ordinary text
```
real code
```"""
fenced_lines, _, _ = find_fence_spans(doc_invalid_opener)
check("backtick in info string is rejected as fence opener", 0 not in fenced_lines)
check("text after invalid opener is preserved outside code block", 1 not in fenced_lines)

# 5. CRLF line endings
doc_crlf = "```\r\ncode line\r\n```\r\nprose line\r\n"
stripped_crlf = strip_fences(doc_crlf)
check("CRLF fence is stripped", "code line" not in stripped_crlf)
check("CRLF prose is preserved", "prose line" in stripped_crlf)

# 6. swallow_unclosed behavior
doc_unclosed = """prose 1
```
code 1
code 2"""

stripped_default = strip_fences(doc_unclosed)
check("strip_fences defaults to swallow_unclosed=False (safe default)", "code 1" in stripped_default and "code 2" in stripped_default)

stripped_swallow = strip_fences(doc_unclosed, swallow_unclosed=True)
check("swallow_unclosed=True strips to EOF", "code 1" not in stripped_swallow and "code 2" not in stripped_swallow)
check("swallow_unclosed=True preserves leading prose", "prose 1" in stripped_swallow)

stripped_no_swallow = strip_fences(doc_unclosed, swallow_unclosed=False)
check("swallow_unclosed=False preserves unclosed block content", "code 1" in stripped_no_swallow and "code 2" in stripped_no_swallow)
check("swallow_unclosed=False drops orphan opener marker line", "```" not in stripped_no_swallow)
check("count_unbalanced_fences counts unclosed fence", count_unbalanced_fences(doc_unclosed) == 1)

# 7. Code spans
doc_spans = "here is `inline code` and ``double ` span`` but not ```triple`` broken"
stripped_spans = strip_code_spans(doc_spans)
check("single backtick span stripped", "inline code" not in stripped_spans)
check("double backtick span with inner backtick stripped", "double ` span" not in stripped_spans)
check("triple opener does not pair with double closer", "```triple``" in stripped_spans)

# 8. Code span does not cross blank lines
doc_span_blank = "stray ` backtick\n\nreal prose\n\nclosing ` backtick"
stripped_span_blank = strip_code_spans(doc_span_blank)
check("code span stopped by blank line", "real prose" in stripped_span_blank)

# 9. Indented code blocks vs 4-space lists
doc_indented_code = """Prose before

    def foo():
        return 42

Prose between

    - list item 1
    - list item 2
    * bullet item
    + plus item
    1. numbered item
    - [ ] task item unchecked
    - [x] task item checked

Prose after"""

stripped_indented = strip_indented_code_blocks(doc_indented_code)
check("indented code block is stripped", "def foo():" not in stripped_indented and "return 42" not in stripped_indented)
check("prose before is preserved", "Prose before" in stripped_indented)
check("prose between is preserved", "Prose between" in stripped_indented)
check("4-space list item 1 is preserved", "    - list item 1" in stripped_indented)
check("4-space list item 2 is preserved", "    - list item 2" in stripped_indented)
check("4-space bullet item is preserved", "    * bullet item" in stripped_indented)
check("4-space plus item is preserved", "    + plus item" in stripped_indented)
check("4-space numbered item is preserved", "    1. numbered item" in stripped_indented)
check("4-space task item unchecked is preserved", "    - [ ] task item unchecked" in stripped_indented)
check("4-space task item checked is preserved", "    - [x] task item checked" in stripped_indented)
check("prose after is preserved", "Prose after" in stripped_indented)

# 10. Indented code block with blank line inside
doc_indented_blank = """Intro

    first line of code

    second line of code after blank

Outro"""
stripped_indented_blank = strip_indented_code_blocks(doc_indented_blank)
check("code before blank in block is stripped", "first line of code" not in stripped_indented_blank)
check("code after blank in block is stripped", "second line of code" not in stripped_indented_blank)
check("outro after code block is preserved", "Outro" in stripped_indented_blank)

# 11. Lazy paragraph continuation is not a code block
doc_lazy = """Paragraph text
    indented continuation line
still paragraph"""
stripped_lazy = strip_indented_code_blocks(doc_lazy)
check("lazy paragraph continuation without blank line is preserved", "indented continuation line" in stripped_lazy)

print(f"\n{passed} passed, {failed} failed")
if failed:
    sys.exit(1)

