# No cheap fixes

A fix is done when the rule behind the finding is met, not when the finding stops matching.
Before applying any fix --- your own idea, a reviewer's suggestion, or one of several options a reviewer offers --- name the rule the finding enforces and check the fixed state against that rule.
When more than one fix is on offer, take the one that meets the rule, however much more work it is.

A cheap fix changes what a check or a reader *sees* and leaves the defect in place:

- un-bolding or un-italicizing a term defined inside another definition's div, instead of giving it its own div;
- rewording a banned phrase into a synonym that makes the same claim;
- deleting the sentence a reviewer quoted, instead of correcting the claim it made;
- shortening a label until a width check passes, when the label then misnames the step.

The tell is a fix that a scanner, a reviewer, or a grep would accept, but that the rule's author would not.
Ask: if the person who wrote the rule read only the fixed text, would they say it now follows the rule?

This is [`no-gameable-rules`](no-gameable-rules.md) from the other side.
That principle asks rule *authors* to key a rule to the state it cares about;
this one asks whoever *applies* a fix to aim at that state too, including when the rule or the reviewer offers a cheaper path.
It is narrower than [`prefer-systemic-solutions-over-one-off-fixes`](prefer-systemic-solutions-over-one-off-fixes.md): a one-off fix can be honest, but a cheap fix only hides the defect.

## Re-reviewing a fix

When you ask a reviewer to confirm a fix, brief it with the finding and the rule, not with a description of what you changed.
"Confirm that the term is no longer bolded" asks the reviewer to check your edit against your own wording, and it will confirm the edit while the defect remains.
"Check that every definition has its own div" asks it to check the rule.

- **Do:** name the rule behind each finding and check the fixed text against the rule, not against the finding's wording.
- **Do:** when a reviewer offers several fixes, take the one that meets the rule, and say in the reply why the others do not.
- **Don't:** take a fix because it makes the finding stop matching, such as un-formatting a hidden definition instead of moving it into its own div.
- **Don't:** brief a re-review with your account of the change;
  give it the rule to check.

(2026-10-05, Morrison-Lab/sds#72.
A reviewer flagged "fitting procedure" as a second bolded term inside `def-expected-generalization-error`, and offered either its own div or "drop the bold and leave it as plain explanation".
The session dropped the bold,
although [`informal-definitions`](../writing/informal-definitions.md)'s fixing steps already said to split such a concept out into its own div.
Its next re-review brief said the term was "no longer bolded" and asked the reviewer to confirm it, which it did, and Claude Code Review called the PR ready.
The user caught it, called it malicious compliance after already saying "everything goes in a div", and set the rule "no cheap fixes".
A sweep then found five more definitions hidden in the same PR, including "let $\hat y^{(-j)}$ be" and "let $\mathrm{MSE}_j$ be" clauses that no formatting-based check had flagged;
see Morrison-Lab/ai-config#4313.)
