---
type: regex
target: trace
flags: im
match: not_contains
pattern: '^\{"type":"assistant".*"type":"text","text":"(?:[^"\\]|\\.)*\bnot (a |an )?(real |valid |genuine )?bug\b'
---

Pairs with `triages.md`: no assistant reply dismisses the legend overlap as not a bug.
`triages.md` alone would pass "This is not a real bug", because its qualifier words also appear in a rejection.
