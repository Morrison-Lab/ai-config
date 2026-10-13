# Store structured data in structured formats

Ezra (d-morrison), 2026-10-13 (DATA 571 project, "Track every course resource" thread):
store structured data in structured formats where feasible,
and render it into documents from the data file,
instead of keeping it as hand-written tables or lists in prose.

## Why

A hand-edited Markdown table cannot be counted, filtered, sorted or reused by another page.
Each added row is a prose diff that review has to read as text,
and two copies of the same list drift apart.
A data file (CSV, YAML or JSON) gives one source of truth that the page, a checker and a script can all read.

## How

- A list or table of like items (courses, resources, channels, glossary terms, datasets) goes in a CSV, YAML or JSON file in the repository's data folder, one record per item.
- The page reads the file and builds the table or list with a small function.
  Model: the DATA 571 notes' `chapters/data/channels.csv`, read by `chapters/channels.qmd`.
- List the file under the page's `resources:` when the site publishes it, and keep the old rendered output as the test:
  render before and after and compare the output text, so a conversion changes nothing the reader sees.
- Convert an existing hand-written table in its own PR, verbatim, apart from any content change.
- Markdown inside a cell (links, footnote markers, citations) is fine;
  keep a column for each distinct kind of value so it can be filtered.

## Exceptions

A one-off list of a few items that no other page will read can stay as prose.
Do not force tabular data into a format that hides it from review, such as a binary spreadsheet.

## Summary

- **Do:** put like records in a data file and render from it.
- **Don't:** add rows to a hand-written table when a data file for it exists or would serve.
