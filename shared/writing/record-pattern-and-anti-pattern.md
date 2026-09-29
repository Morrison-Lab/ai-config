# Record both the pattern and the anti-pattern

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#record-both-the-pattern-and-the-anti-pattern) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When I tell you what to do, or what not to do, in a `cai` or `ums` statement, write down **both** sides: the behaviour to adopt and the behaviour to stop.
Record them explicitly, as a labelled pair, not as a paragraph that leaves one side implied.

Both halves carry information the other cannot.
A rule stated only as the anti-pattern says what to stop without saying what replaces it, which invites a second wrong behaviour that merely avoids the named one.
A rule stated only as the pattern is the more common failure and the harder one to notice: it reads as complete, but the specific move that prompted the correction usually *looks* like compliance from the inside, so the next reader has to re-derive which near-miss was actually being ruled out.
The near-miss is the whole content of the correction.
Naming it is what makes the entry falsifiable rather than merely agreeable.

Keep the pair concrete enough to check against.
"Do: run the pass before flagging a stopping point" and "Don't: recommend a fresh session while a pass is owed" both name an observable action, whereas "be diligent about UMS" names nothing and cannot be violated.
Where a correction only ever surfaced as one side, derive the other rather than omitting it, and say which side came from the user and which you inferred.

This applies to how the entry is *written*, so it composes with whatever the entry is about.
It also applies to this entry: below is its own pair.

- **Do:** state the adopted behaviour and the retired one, labelled, in every `cai`/`ums` entry that records a correction.
- **Do:** make each side an action a later reader could observe you taking or not taking.
- **Don't:** write only the corrected behaviour and leave the reader to infer which specific move it displaced.
- **Don't:** state the pair so abstractly that no concrete action would violate it.
