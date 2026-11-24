# Keep long prose out of string literals

A message of more than a few lines that a program prints,
such as a hook's reminder or deny text,
lives in a Markdown or text file that the program reads,
not in a string literal.
For a hook, that file is `hooks/messages/<hook>.md`,
found through `os.path.realpath(__file__)`
(see `scripts/check-hook-file-resolution.py` for why not `abspath`).
Fill a placeholder such as `{quote}` with `str.replace`,
so a brace in the prose needs no escaping.
Keep a one-line fallback in the code,
so a missing file degrades the message instead of the hook.

Write the file with semantic line breaks:
one clause or sentence per line, as in every other prose file
([`semantic-line-breaks`](../writing/semantic-line-breaks.md)).
Prose that stays in code, such as a docstring or a comment,
breaks at clause boundaries too,
rather than wrapping at a fixed column or with backslash continuations.

**Why:** Ezra, 2026-11-24, on ai-config#6095:
"why aren't we using semantic line breaks in python files?"
and "why are we constructing large prose blocks inline instead of reading them
from text files or markdown files?".
The reminder he flagged copied its hook's existing style,
a backslash-continued string wrapped at a fixed column.
No rule covered prose inside a `.py` file,
and `check-new-line-breaks` reads only Markdown-family files,
so nothing caught it.
In a separate file the prose diffs by sentence,
gets the same line-break and prose checks as any Markdown,
and reads as prose to the person editing it.

**How to apply:** `scripts/check-hook-prose-literals.py` fails a hook
that gains a non-docstring string literal or f-string
of 8 or more source lines.
The hooks that already carry them are listed in
`scripts/hook-prose-literals-known.txt`,
a ratchet whose counts may only fall.
They are not swept;
move a hook's prose out when you next edit that hook,
and lower its count in the same commit.
