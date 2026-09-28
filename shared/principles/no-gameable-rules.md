No gameable rules.
A rule, instruction, metric, hook condition, or checklist item has to
target the outcome it actually cares about, so that no behaviour can
satisfy its letter while defeating its purpose.
This is one principle with three named aspects, not three separate
rules: they name the same failure from three angles, and a single
instance of the failure is usually all three at once.

## The three aspects

**Loophole.**
The rule can be satisfied by an unwanted behaviour, including by doing
nothing.
A rule that says "don't recommend a fresh session while a pass is
owed" is satisfied by never recommending anything, which is not the
behaviour it wants either.

**Perverse incentive.**
The rule rewards the unwanted behaviour, because the unwanted
behaviour is the cheapest way to comply.
A penalty for *mentioning* a defect in another repo without filing it
makes silence about the defect the cheapest way to avoid the penalty
--- which is the opposite of what the rule exists to produce.

**Monkey-paw phrasing.**
The literal wording grants the request in a way that defeats it, the
way a wish is granted in the story the name comes from.
Writing "don't mention a defect without filing it" when the goal is
"file every defect you notice" is monkey-paw phrasing: read literally,
it grants "never mention defects" as a compliant reading.

## The shared check

Before shipping a rule, a Do/Don't pair, a hook condition, or a
checklist item, ask: how could this be complied with while defeating
its purpose, and is the cheapest way to comply the behaviour actually
wanted?

Key the rule to the state it cares about --- noticed, true, done ---
not to a visible proxy for that state --- mentioned, stated, reported.
A rule keyed to the proxy is satisfied by managing the proxy instead of
the state: staying quiet, not writing the sentence, not producing the
artifact the instrument would see.
When an instrument (a hook, a grep, a reviewer) can only ever see the
proxy and not the underlying state directly, say so explicitly in the
rule, and state plainly that silence, or any other way of keeping the
proxy clean, does not count as compliance.

## Related terms

These name adjacent ideas, not this principle by another name; each is
distinct from it.

- **Malicious compliance** is the behaviour this principle exists to
  foreclose: deliberately following a rule's letter to defeat its
  purpose.
  This principle is broader, because a loophole gets exploited without
  malice too --- the path of least resistance does it on its own.
  A model that stays quiet about a defect it would rather not deal
  with is not being malicious; the rule simply made silence the
  cheapest way to comply.
- **Specification gaming / reward hacking** name the same failure shape
  in optimization and RL systems: an agent maximizes the literal
  objective instead of the intended one.
- **Goodhart's law** --- "when a measure becomes a target, it ceases to
  be a good measure" --- is the proxy aspect above, stated for metrics
  rather than for rules in general.
- **Letter vs. spirit of a rule** is the everyday phrase for the same
  gap between what a rule says and what it is for.

The principle covers all of these: write rules so that neither
malicious compliance nor merely lazy, incentive-following compliance
can satisfy them while defeating their purpose.

## How this relates to other entries

[`CLAUDE.md`](../../CLAUDE.md)'s "Record both the pattern and the
anti-pattern" section already asks that a Do/Don't pair be
**falsifiable**: naming the near-miss the correction actually ruled
out, not a paraphrase agreeable enough to cover the near-miss too.
This principle adds the check that makes a pair falsifiable in the
right direction --- against the state the rule cares about, not
against whatever a reader chooses to say about it.

[`algorithmatize-checks`](../workflow/algorithmatize-checks.md) records
several instruments a rule's own gameable proxy defeated: a bare-scheme
URL check satisfied by a line that only *mentions* a URL, a transcript
scan for a derived string satisfied by typing that string in an
unrelated comment, and a mutation-insensitive assertion satisfied by
the wrong failure.
Each is this principle applied to a specific check rather than to
prose.
[`fail-fast`](fail-fast.rationale.md)'s "The narration can be the
unfalsifiable part, while the check is fine" section is the same shape
one level up: the code's check is sound, but the surrounding claim
about what happened is not pinned to anything the check verifies.

- **Do:** key a rule to the state it cares about (noticed, true, done),
  and say explicitly when an instrument can only see a proxy for that
  state.
- **Do:** write down the cheapest behaviour that would satisfy a rule
  as drafted, before shipping it, and confirm that behaviour is the
  one actually wanted.
- **Don't:** phrase a rule around a visible proxy --- anything
  observable that can stand in for the state the rule cares about ---
  when it is that state, not the proxy, that the rule needs to change.
- **Don't:** let a rule's Don't side reward the unwanted behaviour by
  making it the easiest way to avoid the rule's penalty.

## Incident

While drafting a Don't for the "file ideas and issues proactively"
rule ([ai-config#4042](https://github.com/Morrison-Lab/ai-config/pull/4042)),
the wording was "Don't: mentioning a defect in another repo ...
without filing it."
That is satisfied by never mentioning the defect at all, which rewards
exactly the silence the rule exists to prevent.
The repo owner caught it, 2026-09-28: "shouldn't the Don't be noticing
a defect without filing, rather than naming the defect without filing?
we don't want to create loopholes or perverse incentives to avoid
naming things that the model noticed but doesn't want to deal with, so
it doesn't mention them."
The fix keys the rule to *noticing* the defect --- a state the rule can
still only check indirectly, but one that does not make silence the
compliant path.

- **Do** (the repo owner's words, 2026-09-28): key the Don't to
  *noticing* a defect without filing it, not to *mentioning* one
  without filing it.
- **Don't** (inferred from the incident): write a Don't whose
  condition is something the model says or writes, when the behaviour
  it is meant to rule out is something the model does or fails to do.
