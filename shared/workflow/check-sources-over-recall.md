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

## Hyperlink the evidence for every factual claim

Ezra, 2026-11-12, after a coordinator post hedged a claim with "I may be out of date on that":
"all your factual claims need citations linking to current information",
then "correction: need *evidence* hyperlinked to current information",
then "(in other words, don't rely on your neural memory)" ([#5588](https://github.com/Morrison-Lab/ai-config/issues/5588)).

- **Do:** link each factual claim in a message to a person to the live evidence it rests on,
  such as the PR, issue, commit, workflow run, file at a sha or doc page you read this turn.
  This covers status, PR, CI and review state, settings, file contents, tool behaviour and dates.
- **Don't:** state a fact from model recall, or hedge it ("I may be out of date") instead of checking it.
  A source named without a link, or a link to an earlier report, is not evidence of current state.
- If no live source exists, say the claim is unverified.

No hook: whether a sentence is a factual claim is not lexically decidable,
so this rests on the rule, as [#5215](https://github.com/Morrison-Lab/ai-config/issues/5215) concluded for its sibling.

Enforced by `hooks/no-answer-from-recall.py`, which denies a reply that says it answers from memory or recall in the first person.
"Not checked against" and asking where a source lives are not matched, because every pattern for them over-matched ordinary prose or missed real cases.
Those two rest on this rule alone (#4959).
Related: [`live-state-over-notes`](live-state-over-notes.md) (a note's claim about a changing condition), `hooks/flag-book-unavailable-without-library-search.py`, [`dont-take-my-word-for-it`](../principles/dont-take-my-word-for-it.md).
