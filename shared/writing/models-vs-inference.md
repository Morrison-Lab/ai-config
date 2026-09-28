Keep a model's structure and its estimation or inference method separate,
in wording as well as in the exposition itself.

## The distinction

A **model** is the structural assumption about how the data relate to the
parameters:

- distributional family
- link function
- mean structure
- random effects
- hierarchy

An **estimation or inference method** is how the parameters are learned from
data given that structure:

- maximum likelihood
- Bayesian inference
- GEE
- method of moments
- least squares

The two are orthogonal.
Any structure that is compatible with a method can be paired with it, so a
model never belongs to one paradigm.
A random-effects model can be fitted by maximum likelihood or by Bayesian
MCMC; a linear mean structure can be fitted by least squares or by Bayesian
inference with a normal likelihood.
Naming the method a chapter happens to use does not make that method part of
the model it is applied to.
This is the same distinction `Morrison-Lab/rme`'s `CLAUDE.md` draws in its
["Content Writing"
section](https://github.com/Morrison-Lab/rme/blob/main/CLAUDE.md#content-writing),
whose random-effects example this fragment reuses.

### The hierarchical case

A hierarchy --- group-level parameters with their own distribution, at one
or more levels --- is model structure, not a method, and it follows the
same rule as any other structure: it can be fitted by maximum likelihood or
by Bayesian inference.
A prior or a hyperprior on the top-level parameters is part of Bayesian
inference for that structure, not part of the model.
So write "a hierarchical model fitted by Bayesian inference", never "a
Bayesian hierarchical model".
[`Morrison-Lab/sds#6`](https://github.com/Morrison-Lab/sds/pull/6) fixed its
`def-hierarchical-model` on exactly this point, in commit `2e5d442`: the
definition used to build the prior into the hierarchy's own stages, making
the structure Bayesian by definition; it now defines the structure alone
and adds, separately, that Bayesian inference fits it with a hyperprior.

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
adjective modifying the model noun, each of these attaching a paradigm to
the model noun:

- "Bayesian regression model"
- "Bayesian model"
- "frequentist model"
- "likelihood model"
- "MLE model"

Name the model and the method as two separate phrases instead: "a linear
regression model fitted by Bayesian inference", "Bayesian inference for a
logistic regression model".

A phrase that names only the method, with no model noun attached, is fine,
because each says how parameters are learned and claims nothing about the
model's structure:

- "Bayesian inference"
- "Bayesian analysis"
- "the MLE of $\beta$"

**A carve-out**: a few phrases contain the words "Bayesian model" while
naming a method or a procedure, not a model --- "Bayesian model averaging"
(averaging predictions over models, weighted by posterior model
probability), "Bayesian model comparison" (comparing candidate models by a
Bayesian criterion).
These name what is done *to or across* models, not a model's own structure,
so they are fine as written.

The prior is part of the Bayesian inference setup, not a change to the
model's structure.
Placing a prior on a parameter does not turn the regression model the
parameter belongs to into a different model, and the same holds for a
hyperprior on a hierarchical model's top-level parameters --- see "The
hierarchical case" above, which is the one place this applies often enough
to need its own section.
Keep the point brief wherever else it comes up: name the model's structure
once and move on, rather than relitigating the model/method line for every
mention of a prior.

## Do / Don't

- **Do:** name the model and the method separately --- "a logistic
  regression model fitted by Bayesian inference" --- keeping the repo
  owner's example (2026-09-28): there's no such thing as a "Bayesian
  regression model", only a regression model fitted using Bayesian
  inference.
- **Don't:** give a paradigm-prefixed model name, such as "Bayesian
  regression", as an example of a kind of model (inferred from the incident
  below).

## Incident

The repo owner gave the directive on 2026-09-28, and it took two rounds to
land on a `Morrison-Lab/pds` PR ([Morrison-Lab/pds#12](https://github.com/Morrison-Lab/pds/pull/12)),
`_subfiles/_sec-stochastic-probabilistic-random.qmd`'s `exm-probabilistic`.

The first round (`cec756c`) changed "A Bayesian regression model is
probabilistic" to "A linear regression model whose parameters are estimated
by Bayesian inference is probabilistic: Bayesian inference assigns a
probability distribution to the parameters and predictions."
That reworded away the banned phrase and still attributed the model's
probabilistic character to the fitting method rather than to the model
itself --- exactly the near-miss this fragment's "why a phrase list is not
the rule" section warns about: a rewording can satisfy a banned-phrase list
while keeping the underlying conflation intact.

The second round (`61d5538`) is the more instructive one, because it fixes
what the first round missed.
It grounds the example in the model's own error distribution instead: a
linear regression model with Gaussian errors is probabilistic because it
assigns a probability distribution to the outcome for each covariate value,
independent of how it is fitted.
A notes aside then states the fitting-method point separately: the same
model is probabilistic whether fitted by maximum likelihood or by Bayesian
inference, and Bayesian inference additionally makes the *inference method*
probabilistic by assigning a distribution to the parameters themselves.

## Related terms

- [`math-derivation-steps`](math-derivation-steps.md) governs how a
  derivation's steps are written once a model and method are chosen; this
  rule governs how the model and the method are named in the first place.
- [`informal-definitions`](informal-definitions.md) covers a concept that is
  never formalized into its own div; a model/method conflation is a
  different failure, since both halves may be formally defined and still be
  named as one thing.
