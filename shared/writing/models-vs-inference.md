Keep a model's structure and its estimation or inference method separate,
in wording as well as in the exposition itself.

## The distinction

A **model** is the structural assumption about how the data relate to the
parameters: distributional family, link function, mean structure, random
effects, hierarchy.
An **estimation or inference method** is how the parameters are learned from
data given that structure: maximum likelihood, Bayesian inference, GEE,
method of moments, least squares.

The two are orthogonal.
Any structure that is compatible with a method can be paired with it, so a
model never belongs to one paradigm.
A random-effects model can be fitted by maximum likelihood or by Bayesian
MCMC; a linear mean structure can be fitted by least squares or by Bayesian
inference with a normal likelihood.
Naming the method a chapter happens to use does not make that method part of
the model it is applied to.

## What this rules out, and why a phrase list is not the rule

The state this rule cares about is whether a passage conflates a model's
structure with a method applied to it.
A list of banned phrases is illustrative of that conflation, not the
definition of it --- rewording around a listed phrase while still describing
the paradigm as a property of the model is still the conflation, so read the
examples as instances, not as the check itself.
Applying the corpus's no-gameable-rules principle here (`shared/principles/no-gameable-rules.md`,
[PR #4047](https://github.com/Morrison-Lab/ai-config/pull/4047), not yet
merged as of this writing): key the rule to *whether structure and method
are conflated*, so that no rewording of a banned phrase can satisfy the
letter of a phrase list while still attaching a paradigm to the model.

With that said, the commonest surface form of the conflation is a paradigm
adjective modifying the model noun.
"Bayesian regression model", "Bayesian model", "frequentist model",
"likelihood model", "MLE model": each attaches a paradigm to the model noun.
Name the model and the method as two separate phrases instead: "a linear
regression model fitted by Bayesian inference", "Bayesian inference for a
logistic regression model".

A phrase that names only the method, with no model noun attached, is fine.
"Bayesian inference", "Bayesian analysis", "the MLE of $\beta$": these say how
parameters are learned and claim nothing about the model's structure.

The prior is part of the Bayesian inference setup, not a change to the
model's structure.
Placing a prior on a parameter does not turn the regression model the
parameter belongs to into a different model.
Where a prior does act like model structure, most notably a hierarchical
prior that introduces its own distributional layer, say so, but keep the
point brief: name the added structure once and move on, rather than
relitigating the model/method line for every mention of the prior.

## Do / Don't

- **Do** (the repo owner's words, 2026-09-28): always clearly distinguish
  between models vs. estimation and inference methods; there's no such thing
  as a "Bayesian regression model", only a regression model fitted using
  Bayesian inference.
- **Don't** (inferred from the incident below): give a paradigm-prefixed
  model name, such as "Bayesian regression", as an example of a kind of
  model.

## Incident

On 2026-09-28, a `Morrison-Lab/pds` PR
([Morrison-Lab/pds#12](https://github.com/Morrison-Lab/pds/pull/12)) gave
"Bayesian regression" as an example of a probabilistic model.
Bayesian inference is a method for fitting a regression model, not a kind of
regression model in its own right, and the repo owner corrected it.

## Related terms

- [`math-derivation-steps`](math-derivation-steps.md) governs how a
  derivation's steps are written once a model and method are chosen; this
  rule governs how the model and the method are named in the first place.
- [`informal-definitions`](informal-definitions.md) covers a concept that is
  never formalized into its own div; a model/method conflation is a
  different failure, since both halves may be formally defined and still be
  named as one thing.
