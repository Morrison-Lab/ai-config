#!/usr/bin/env python3
"""Tests for scripts/lib/fences.py (CommonMark fence/code stripper, ai-config#1567)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import (  # noqa: E402
    count_unbalanced_fences,
    find_fence_spans,
    strip_code,
    strip_code_spans,
    strip_display_math,
    strip_fences,
    strip_inline_math,
    strip_math,
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

# 8b. Multi-line multi-backtick spans cross non-blank lines (#2525)
doc_multiline_span = "prose before\n``\ncode line 1\ncode line 2\n``\nprose after"
stripped_multiline_span = strip_code_spans(doc_multiline_span)
check("multiline double-backtick span stripped", "code line 1" not in stripped_multiline_span and "code line 2" not in stripped_multiline_span)
check("multiline double-backtick span preserves surrounding prose", "prose before" in stripped_multiline_span and "prose after" in stripped_multiline_span)


# 9. Display math stripping ($$...$$)
doc_display_math = """prose before
$$
\\int_0^1 f(x) dx = [a, b](not_a_link.md)
$$
prose after"""
stripped_display = strip_display_math(doc_display_math)
check("display math stripped: math content removed", "[a, b](not_a_link.md)" not in stripped_display)
check("display math stripped: prose before preserved", "prose before" in stripped_display)
check("display math stripped: prose after preserved", "prose after" in stripped_display)

# 10. Inline math stripping ($...$)
doc_inline_math = "Let $x \\in [0, 1](t.1)$ be given. Cost is $50 and fee is $20. See [doc](doc.md)."
stripped_inline = strip_inline_math(doc_inline_math)
check("inline math stripped: math formula removed", "[0, 1](t.1)" not in stripped_inline)
check("inline math stripped: currency dollar amounts not treated as math", "$50" in stripped_inline and "$20" in stripped_inline)
check("inline math stripped: prose and markdown links preserved", "[doc](doc.md)" in stripped_inline)

# 11. Escaped dollar signs in math and prose
doc_escaped_dollar = "Formula $\\text{Cost: } \\$50$ is valid math. Price is \\$100 total."
stripped_escaped = strip_math(doc_escaped_dollar)
check("escaped dollar in math parsed as part of math span", "\\text{Cost: }" not in stripped_escaped)
check("escaped dollar in prose preserved", "\\$100" in stripped_escaped)

# 12. Combined strip_math
doc_combined_math = """$$
\\mathbf{A} = [a_{ij}]
$$
Here $f(x) = y$ and price is $50-$100."""
stripped_comb = strip_math(doc_combined_math)
check("combined math strips display math", "\\mathbf{A}" not in stripped_comb)
check("combined math strips inline math", "$f(x) = y$" not in stripped_comb)
check("combined math preserves prose", "Here" in stripped_comb)

print(f"\n{passed} passed, {failed} failed")
if failed:
    sys.exit(1)
