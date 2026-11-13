# Ask what an instruction that contradicts a rule is meant to be

When the maintainer gives an instruction that seems to contradict a recorded rule or guideline, ask which of these it is, quoting the rule and linking where it is recorded:

- **An exception:** the instruction holds for this case only, and the rule stands.
- **A revision:** the rule itself changes.
- **A clarification:** the rule was ambiguous, and the instruction settles its scope without changing it.
- **A mistake:** the instruction was not meant to cross the rule.
- **No real conflict:** you may have misread the rule or the instruction.
  Quote both, so the maintainer can confirm that they do not conflict.

When the answer is a revision, also ask whether it applies going forward only, or should also sweep existing material that follows the old rule.
A sweep is still new work, so file it as its own issue ([No sweeps for new rules by default](../../AGENTS.md#no-sweeps-for-new-rules-by-default)).

(Ezra, 2026-11-13, [ai-config#5625](https://github.com/Morrison-Lab/ai-config/issues/5625): "when I give an instruction that seems to contradict our general rules and/or guidelines, ask if it is meant as an exception to the rule or a revision of the rule, or if it's a mistake?";
he approved adding the clarification, no-real-conflict and sweep questions the same day.)

## Why ask

An instruction that crosses a rule leaves two records that disagree.
Followed silently, the rule stays written down and the next session enforces it against the maintainer's own wish.
Refused, the agent overrides the maintainer with a default.
Only the maintainer knows which record should win, and the answer changes what gets edited: nothing for an exception or a mistake, the rule's home for a revision or a clarification.

The trigger was a request on 2026-11-13 for table numbers on the lds note-sheet PDFs, which reversed an earlier deliberate choice ([Morrison-Lab/lds#2442](https://github.com/Morrison-Lab/lds/pull/2442)).

## How to ask

- Ask once, as a single question with the readings as options, and recommend one ([Always give recommendations with questions](../../AGENTS.md#act-on-the-whole-request-and-decide-rather-than-ask)).
- Keep working on the instruction while you wait when the step is reversible, since a direct instruction outranks a general default ([`specific-beats-general`](../principles/specific-beats-general.md)).
  Wait for the answer first when the step cannot be undone, or when it would cross a hard safety gate.
- Asking which reading is meant is not asking the maintainer to justify the instruction.
  Do not argue for the rule.
- Once answered, record it: edit the rule's home for a revision or a clarification (with the maintainer's words and date), and note an exception in the PR or commit that carries it.

## Why this is prose and not a hook

No deny hook can detect the case.
Telling that an instruction conflicts with a rule needs knowing which recorded rules it touches, which is a judgment about meaning that no lexical match on the prompt can make.
The mechanism is the rule's bullet in `AGENTS.md`, which `hooks/inject-core-rules.py` puts in the SessionStart index of every session.

- **Do:** quote the rule, link its home, and ask which reading the instruction is, with a recommendation.
- **Do:** for a revision, ask whether to sweep existing material, and file the sweep as its own issue.
- **Don't:** follow an instruction that crosses a rule and leave the rule unchanged and unasked about.
- **Don't:** refuse or argue against the instruction by quoting the rule.
