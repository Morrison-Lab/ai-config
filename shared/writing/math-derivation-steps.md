When writing or reviewing a mathematical derivation --- an algebraic
manipulation, a proof, a statistical argument --- hold it to a stricter
completeness bar than ordinary prose reasoning.

This fragment covers two axes, and the sections below take them in turn.
The first is **between** displayed lines: how much happens from one line to
the next, which the skipped-step rule governs.
The second is **within** a single line: how much structure is packed inside
one expression, which the last section governs.
That last section applies to any displayed equation, a standalone definition
included, not only to a line inside a running derivation.

## Writing: don't skip steps

Write out every intermediate step: every distribution, cancellation,
substitution, application of a named identity or assumption, and change of
notation. Don't combine two or more operations into a single displayed line.
A reader should be able to get from one line to the next by checking a single
mechanical operation, never by re-deriving an omitted one.

This is stricter than ordinary prose, where combining a few closely related
points in one sentence is fine --- a derivation's whole value is that each
line is independently checkable, so skipping a step defeats the purpose even
when the reader could reconstruct it themselves.

## Reviewing: name the gap, don't just flag it

[`fact-check-prose.md`](fact-check-prose.md)'s document-internal-reasoning
check already covers whether each *stated* step is valid (verifying it
follows from the last, checking dimensions/units, checking edge cases). This
fragment is about a different failure mode: a step that isn't stated at
all --- the derivation jumps from one line to a non-adjacent one.

When a derivation skips a step:

1. **Point to the exact gap** --- the last line before the jump and the
   first line after it, not just "this derivation skips steps" in general.
2. **Name the missing operation** --- what specific move closes the gap
   (which distribution, cancellation, substitution, identity, or
   assumption). Don't leave it to the author to guess what you think is
   missing.
3. **Draft the missing line(s)** where feasible, so the author can drop them
   in directly rather than re-deriving the gap themselves --- the same
   spirit as proposing a concrete fix rather than only naming a problem
   (see [`challenge-unnecessary-complexity.md`](../workflow/challenge-unnecessary-complexity.md)'s
   "propose the fix, don't just name the issue" pattern).

A derivation with a plausible-looking but unstated jump is exactly the kind
of gap a reader skims past --- the same reason
[`challenge-ambiguous-terminology.md`](../workflow/challenge-ambiguous-terminology.md)
warns against accepting a plausible reading at face value instead of
verifying it.

## Keep each equation simple: decompose its internal structure

The rules above govern what happens *between* two displayed lines.
This one governs what is packed *inside* one of them.

When an equation's operator takes a compound expression as its operand, a
reader has to parse two structures at once: the outer relation, and whatever
is nested inside it.
Give the inner structure its own name, and state the outer relation in terms
of that name.
Introducing extra notation is the mechanism rather than a cost to work
around, because the goal is a simple equation and not a short one.

### Worked example, in three states

A cluster's score contribution, written as one equation that inlines the
per-observation score:

```latex
$$U_c = \sum_{i \in c} \nabla_\lambda \log \dens(Y_i \mid \lambda)$$
```

Decomposed once, by naming the per-observation score:

```latex
$$
\begin{aligned}
U_i &= \nabla_\lambda \log \dens(Y_i \mid \lambda)
\\
U_c &= \sum_{i \in c} U_i
\end{aligned}
$$
```

Decomposed again, by naming the per-observation log-likelihood that was still
nested inside the gradient:

```latex
$$
\begin{aligned}
\llik_i(\lambda) &= \log \dens(Y_i \mid \lambda)
\\
U_i &= \nabla_\lambda \llik_i(\lambda)
\\
U_c &= \sum_{i \in c} U_i
\end{aligned}
$$
```

Each line of the third state performs exactly one operation: a log, a
gradient, a sum.

### The rule reapplies to its own output

The second state above is the near-miss worth naming, because it is visibly
better than the first and therefore reads as finished.
It is not.
$U_i$'s own definition still nests a log inside a gradient, which is the same
defect the first decomposition was made to remove, one level down.

So decomposition is recursive rather than a single split.
After naming an intermediate, ask the original question again about that
intermediate's own definition, and keep asking until each line carries one
operation.
Stopping at the first split is the failure mode, and it is a comfortable one:
the diff already shows a clear improvement, so nothing about it prompts
another look.

### What the decomposition buys

Three specific gains.
Naming them is what makes the rule checkable rather than a matter of taste,
and they double as the test for when *not* to apply it.

1. **The named intermediate becomes independently referenceable.**
   Surrounding prose can now say something about $U_i$ by name --- that it is
   the quantity the estimating equation sets to zero, that it is what is
   assumed independent across clusters --- without restating the gradient
   each time.
2. **The structure becomes visible at a glance.**
   The line defining $U_c$ says that it is a sum over its cluster, and says
   nothing else.
   In the inlined form that fact is buried inside a summand.
3. **Each line can be checked on its own.**
   A reader verifying the per-observation score never has to hold the cluster
   summation in mind, and a reader verifying the summation never has to
   re-read the gradient.

### When not to decompose

Every named intermediate is another symbol a reader has to carry, so the rule
has a real cost and a real limit.

A name earns itself when it buys at least one of the three gains above.
It does not when the expression is already self-contained and shallow, or
when the name is used exactly once and never referred to again --- there the
decomposition enlarges the reader's working set and returns nothing.
Splitting a simple equation in two to satisfy a rule is the failure this
limit exists to prevent.

The cost also depends on the name, so choose one the document's existing
notation already implies.
A symbol that slots into an established pattern is close to free, because a
reader who knows the pattern can read it without being taught anything.
In the example above, `\llik` already denoted the full-sample log-likelihood
in the document being edited, so `\llik_i` reads immediately as its
per-observation piece, and summing over $i$ recovers the whole.
A symbol invented for one equation and used nowhere else is the expensive
kind, and it is the kind most likely to fail the earns-itself test above ---
so reusability and consistency are what make a name cheap, not brevity.

Note also what this is not.
[`use-math-macros`](../../skills/use-math-macros/SKILL.md) condenses the
*symbols* an expression is written with; this rule reduces the *structure* it
is built from.
Macroizing a dense equation makes it shorter on the page while leaving its
nesting depth untouched, so it is not a substitute for decomposing it.

A name introduced this way is new notation, so it carries notation's usual
obligations: define it where a reader meets it first, per
[`definition-crossrefs.md`](definition-crossrefs.md), and give it a formal
construct rather than only prose when it is doing definitional work, per
[`informal-definitions.md`](informal-definitions.md).

### The same principle, one medium over

This is [`avoid-nesting.md`](../coding/avoid-nesting.md)'s named-intermediate
rule applied to mathematical notation rather than to code.
That fragment prefers a named intermediate variable over `f(g(h(x)))`, on the
grounds that naming each step makes the flow read top-to-bottom and leaves
the intermediate values inspectable --- gains 2 and 3 above, in a different
medium.

The parallel runs to the shape of both fragments, not just their advice.
Each covers a within-one-expression axis and a between-steps axis, and
`avoid-nesting.md`'s "prefer more, simpler steps over fewer, denser ones" is
the counterpart of the skipped-step rule at the top of this file.

### Do and don't

- **Do:** pull a compound sub-expression out into its own named symbol, and
  write the outer equation in terms of that symbol.
- **Do:** reapply the rule to the intermediate you just named, and keep going
  until each line carries one operation.
- **Do:** pick a name the document's existing notation already implies, so a
  reader needs no introduction to it.
- **Do:** check a proposed name against the three gains above, and drop it
  when it buys none of them.
- **Don't:** stop at the first decomposition because it is plainly better
  than what you started with --- that is the state that most reads as
  finished while still nesting.
- **Don't:** inline a structure that the surrounding prose then has to
  describe in words, because it has no name to refer to.
- **Don't:** split a self-contained expression, or introduce a
  used-once-never-referenced name, merely to have decomposed something.

### In review

Flag a displayed equation whose operand is itself a compound expression,
where naming that operand would buy one of the three gains.
Give it the weight of the other prose-review findings, raised as a suggestion
rather than a blocker.
Propose the decomposed form in the finding rather than only observing that
the equation is dense, per the drafting step in "Reviewing: name the gap"
above.
Flag a partial decomposition too: a diff that names one intermediate and
leaves that intermediate's own definition nesting, which is the second state
above.
Read a decomposition's last line as the place to look, since that is where
the remaining structure collects.
Flag the opposite as well: a named intermediate used once and never
referenced has spent a symbol and bought nothing.

(Two directives from the user, 2026-08-09.
First: "try keep each equation simple, by decomposing out complicated
internal structures using extra notation.
for example, in
<https://ucd-serg.github.io/serocalculator/pr-preview/pr-654/vignettes/methodology.html#eq-anchor-22>,
why not define U_i as the score contribution of observation i, and then write
the score contribution of cluster u as a the sum of the U_i's for i \in c?"
Then, on the result: "note that you should apply the same principle to the
definition of U_i; the log-likelihood of observation i should get its own
notation (something like \llik_i) to make U_i's definition simpler."
Both quoted verbatim, typo included; that URL is a PR-preview build and will
stop resolving once the PR closes.
Applied in `UCD-SERG/serocalculator#654`, whose cluster-robust sandwich
variance definition moved through all three states above.
The recursion point is the second directive's, and it is why this fragment
treats the one-split version as a near-miss rather than as the fix.
`\llik` was already the vignette's own notation before this change ---
`vignettes/methodology.qmd` defines
`$\llik(\lambda) \eqdef \logf{\Lik(\lambda)}$` as the full-sample
log-likelihood --- which is what made `\llik_i` a cheap name rather than a
new one to learn.)
