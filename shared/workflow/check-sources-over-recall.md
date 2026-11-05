# Check sources; do not answer from memory

When a source can be checked, check it before answering.
Sources include books, repositories, documentation, APIs and files.
Cite what you read (file and page or line), not what you remember.

Ezra, 2026-11-04: "never use memory when you can check."
The slip (ai-config#4957): a reply named the datasets ISL uses "from my memory of the book, not checked against the text" and then asked where the book lives.
The project library at `/mnt/project-files` held it.

- Search the library, the attached repos (`add_repo` if needed), the docs or the API first.
- Ask the user where a source lives only after naming the places you searched.
- A hedge such as "from memory" or "not checked against" is a defect, not a disclosure: replace it with the check.
- If no source exists, say what you searched and that the claim rests on inference.

Enforced by `hooks/no-answer-from-recall.py`, which denies a reply that says it answers from memory or recall, says it was not checked against a source, or asks where a source lives without naming a search.
Related: `hooks/flag-book-unavailable-without-library-search.py`, [`dont-take-my-word-for-it`](../principles/dont-take-my-word-for-it.md).
