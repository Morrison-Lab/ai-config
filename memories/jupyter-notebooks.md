# Jupyter notebooks (`.ipynb`): stored outputs outlive the source that produced them

## Emptying a notebook's source cells does not empty its stored outputs

A `.ipynb` file is JSON, and each code cell carries `source` and `outputs` as
**sibling** keys.
Clearing `source` leaves `outputs` exactly as it was, still holding whatever
the cell printed the last time it ran.

For a graded exercise notebook that means the answers survive the blanking.
The solution is gone from the code the student reads and still sits in the JSON
one key over, recoverable by anyone who opens the file with anything but a
rendering view.

**Two review rounds of exactly this check missed it**, because both read what
the cells *said* rather than what they had already *printed*.
That is the shape of the miss rather than an accident of care: a rendered
notebook view, a `git diff` skim, and a direct read of `source` all agree the
answer is gone, and each of the three is a real check.
The file has two representations of its content and only one of them is the one
anybody looks at.

`execution_count` is the cheap tell that a cell ever ran;
a non-null value on a cell whose `source` is now blank means outputs were
produced against code that is no longer there to explain them.

### Derive the count rather than reading the cells

```bash
jq '[.cells[] | (.outputs // [])[]] | length' notebook.ipynb
```

`// []` matters: a markdown cell has no `outputs` key at all, and indexing a
missing key without the alternative aborts the whole expression rather than
skipping that cell.

To read what those outputs actually contain --- a stream write and an
`execute_result` store their text under different keys:

```bash
jq -r '.cells[] | (.outputs // [])[]
       | (.text // .data["text/plain"] // empty)
       | if type == "array" then join("") else . end' notebook.ipynb
```

And to find cells that ran:

```bash
jq '[.cells[] | select(.execution_count != null)] | length' notebook.ipynb
```

Measured 2026-09-18 against a notebook with two blanked-source cells: the
`source` read printed only a heading and a `# your work here` comment, while
the count returned `2` and the text query printed `THE ANSWER IS 42` and
`secret_key = 'hunter2'`.

**Run the negative control**, since a zero here is otherwise
indistinguishable from a query that matched nothing for a structural reason.
The same count over a cleared copy of that notebook returned `0`, so the
detector discriminates rather than always reporting clean.

### Clearing them

```bash
jupyter nbconvert --ClearOutputPreprocessor.enabled=True \
  --to notebook --inplace notebook.ipynb
```

Verified 2026-09-18 with nbconvert 7.17.1: it zeroes `outputs` **and** resets
`execution_count` to null, so both tells above go quiet together.
`nbstripout` is the dedicated tool for the same job and was not installed on
the machine where this was measured, so its behaviour here is unverified.

- **Do:** derive the stored-output count before calling a notebook cleared,
  redacted, or safe to publish.
- **Do:** run the count over a known-clean copy first, so a zero is evidence
  rather than a query that matched nothing.
- **Do:** treat a non-null `execution_count` beside blank `source` as a
  standing flag, whatever the source says.
- **Don't:** read a notebook's rendered view, its `git diff`, or its `source`
  keys as evidence about what the file carries.
- **Don't:** clear `outputs` by hand and leave `execution_count` set --- the
  two are separate fields and only one of them is the one you remember.

## The wider family, and what does not cover it

A file whose visible content and its stored byproducts are different things is
a recurring shape rather than a notebook quirk.
The `.pptx` case --- a hash reconciliation that cannot see inside a zip
container, plus a slide hidden with `show="0"` --- is recorded separately in
[ai-config#3783](https://github.com/Morrison-Lab/ai-config/pull/3783).

Notebooks are **not** an instance of the opaque-container problem, though, and
the distinction decides which instrument applies.
A `.pptx` payload is deflated, so a plain `grep` over the file finds nothing
and the bytes have to be unzipped first.
A `.ipynb` is uncompressed JSON, so `grep` finds the answer string perfectly
well --- the reason nobody found it is that nobody looked at that key, not that
the bytes were unreadable.

That is also why
[`hooks/remind-deserialize-before-binary-claim.py`](../hooks/remind-deserialize-before-binary-claim.py)
does not apply and should not be extended to cover `.ipynb`.
That hook fires when a claim rests on a byte-level diff of a serialized
artifact whose deserialized values may be unchanged;
its `SERIAL_EXT` list is deliberately all binary formats, and its
`DESERIALIZE` signals are readers like `readRDS` and `pd.read_`.
A notebook's `git diff` is legible, so the premise the hook exists to doubt
does not hold here.

- **Do:** ask which key holds the content, when a format stores the same
  material twice.
- **Don't:** reach for a container-opacity or deserialization remedy on a
  plain-text format --- the content was always readable, and the gap was in
  the predicate.
