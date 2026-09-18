# A test harness reading embedded script from a YAML block scalar must not re-strip indentation

A GitHub Actions `run: |` step is a YAML block scalar.
`yaml.safe_load` already removes that block's own indentation when it parses
the file --- the returned string is dedented relative to the block's first
content line, not relative to column zero of the raw file.

A harness that extracts an embedded script --- Python inside a
`python3 - <<'PY' ... PY` heredoc, most commonly --- to test it separately
from CI must consume that already-dedented string as-is.
Stripping a second, fixed number of leading spaces on top of it --- to
compensate for the block's nesting depth, typically copied once from how deep
the block happened to sit in the file at the time --- double-dedents.
Every line whose true indentation is shallower than that fixed width loses
real code characters, not whitespace, and the result is either silently wrong
code or a raised `IndentationError`/`SyntaxError` that reads as a bug in the
workflow file itself rather than in the harness reading it.

```python
import yaml

run_block = yaml.safe_load(open("workflow.yml"))["jobs"]["job"]["steps"][0]["run"]
# run_block is ALREADY correctly dedented here. Extract the heredoc body and
# hand it to compile()/exec() unchanged -- do not strip anything further.
```

**Why it can pass review for a long time before it breaks.**
A fixed-width strip only corrupts a line whose real indentation is
*shallower* than the width the harness subtracts.
If every line in the script so far has happened to sit at or below the top
level (few or no nested blocks), the strip either removes nothing consequential
or removes only leading whitespace that was already blank-equivalent, and the
harness looks like it works.
The failure surfaces later, once someone adds a line that legitimately needs
*less* indentation than the harness assumes --- a new top-level statement, or
a block whose body sits shallower than the harness's hardcoded width --- and
the harness reports a syntax error against a file that is, in fact, syntactically
fine.

- **Do:** feed the harness the string `yaml.safe_load` already produced,
  with no further dedent step.
- **Do:** if the embedded script needs isolating further (e.g. slicing out a
  heredoc body), do so with a search anchored on the heredoc delimiter, not
  with an indentation-width assumption.
- **Don't:** hardcode a "strip N leading spaces" step to compensate for a
  block's nesting depth --- `yaml.safe_load` has already done that
  computation correctly, using the block's own first line as the reference,
  and a second, fixed-width guess can only be wrong relative to it.
- **Don't:** read a resulting `IndentationError`/`SyntaxError` as evidence the
  *workflow file* is broken without first checking whether the harness itself
  re-stripped anything.

(Verified 2026-09-18 by direct reproduction against a real GitHub Actions
`run: |` block containing a Python heredoc: `yaml.safe_load`'s own output
compiled cleanly with no further processing, while re-stripping a fixed 4 or
6 leading spaces from every line reliably produced
`IndentationError: expected an indented block after 'for' statement` on a
line that was never touched by hand --- because the loop body's own
indentation had been reduced below what the `for` line required.)
