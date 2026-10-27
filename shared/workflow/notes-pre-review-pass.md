A notes PR (psw, rme, mds, lds, pds, sds, win, araomm) reaches the maintainer already checked against the notes rules, so he reviews the ideas and not the wording.
Morrison-Lab/ai-config#4600: sds#268 took nine review threads on one 20-line definition, each an instance of a rule we already had.

## Sweep the class, not the line

A review comment names one instance of a class.
Before you reply, find the class and fix every instance in the PR's diff and in the divs it includes or follows.

1. Name the class in a few words: "term not linked at first use", "input without its symbol", "type of an output unstated".
2. Search the whole diff for it, with a command or a read of each changed div, not from memory.
3. Fix every instance in one commit, and say in the reply how many there were and where.
4. Record the class in this checklist if it is not already an item.

A fix confined to the commented line is the usual cause of the next comment on the same PR.

## Run the checklist before the first review request

Dispatch a separate subagent to read the diff against the items below, per [`adversarial-self-review`](adversarial-self-review.md), and fix every failing item before the PR goes to a person.
The agent returns pass or fail for each item with `path:line` evidence.
State in the PR body that the checklist ran.

1. **Types.**
   Each function or procedure states its domain and codomain, and the type of each input and output, as in psw's [Types of functions and procedures](https://morrison-lab.github.io/psw/chapters/notation.html#types-of-functions-and-procedures).
   A procedure that produces a function says so.
   "Function" replaces "rule" and "map", and links the formal definition.
   The argument of a function is typed by its domain, and is not one of the inputs that specify the function.
2. **Links.**
   Every technical term is hyperlinked at first use in each div, and each target div precedes its first mention in reading order.
   A term with no definition gets its own definition div, filed as an issue if it widens the PR, never left unlinked.
   Fix a forward reference or dependency-graph cycle by reordering the content or defining the prerequisite concept first, never by removing the hyperlink and adding `<!-- check-term-links: allow -->`.
   Run [`Morrison-Lab/gha`](https://github.com/Morrison-Lab/gha)'s [`check-term-links.py`](https://github.com/Morrison-Lab/gha/blob/main/check-term-links/check-term-links.py) with `--diff <pr.diff>` locally before pushing so every `unlinked-first-use` finding in the PR diff is caught pre-push.
3. **Symbols.**
   Every technical term is paired with its semantic macro, and the macro is the existing one: search `Morrison-Lab/macros` for the concept before writing any expression.
4. **Minimal expressions.**
   Each expression is as short as the macros allow, with no manual delimiter around a function's arguments, and any repeated chunk is named.
5. **Definitions.**
   No term appears in its own definition, none is defined as a modification of another, and each preposition states a relation you can name.
   A definition div holds its one term and links to everything else.
   A clause that defines another term or notation ("we write ... for ...", "a function that maps ...") gets its own definition div and example instead.
   Define a general concept from prerequisite terms defined before it (for example, define bounds first, then define an interval from its bounds), then state its special cases after it, rather than defining the general concept by listing later special-case divs or moving the general definition after its special cases.
   Each new or revised subfile holds a single div, per [`lecture-conventions`](../writing/lecture-conventions.md) (with `{{< slidebreak >}}` between includes in the parent chapter spine);
   never bundle a definition and its remarks or additional definitions into the same subfile.
6. **No overexplaining.**
   Delete a clause that restates what the term and its symbol already say.
   Replace a pronoun such as "It" with its referent.
7. **Population or sample.**
   Every "mean", "average" and error shorthand says which.
8. **Estimands.**
   Every "estimate", "smallest" or "best" names its target, as in psw's [estimand rule](https://morrison-lab.github.io/psw/chapters/defining-terms.html).
   A vague verb such as "generalizes" or "captures" gives way to the relation it stands for, stated in the definition.
9. **Relevance.**
   Each remark, source credit and citation supports the claim in the div that contains it, per psw's [What makes a citation relevant](https://morrison-lab.github.io/psw/chapters/citations-evidence.html#what-makes-a-citation-relevant).
   Remove one the div does not need.
10. **Literal wording (no idioms).**
    Replace postural or residency verbs for mathematical objects ("lies in", "lies between", "sits at", "lives in"),
    money-word trade-off idioms ("costs", "buys", "at the price of"),
    idioms for equality, zero, or special cases ("agree", "vanish", "recover"),
    cognitive or speech verbs on models or equations ("knows nothing", "decides", "says"),
    and imperative or exercise-prompt idioms ("Write $X$ as", "Fix $X$", "Take $X$", "Call $X$", "Say which/what/why")
    with literal wording,
    per psw's [Use literal language](https://morrison-lab.github.io/psw/chapters/inclusive-writing.html#use-literal-language)
    ([`Morrison-Lab/psw#308`](https://github.com/Morrison-Lab/psw/pull/308),
    [`Morrison-Lab/psw#309`](https://github.com/Morrison-Lab/psw/pull/309)).

An item that fails on one div is checked on every div of the PR, per the sweep above.
Recurrence: sds#268 (2026-10-17) drew an inline definition at least five times after the first correction, which is why item 5 now names the pattern.
mds#422 (2026-10-19) stripped `@def-` links and added `<!-- check-term-links: allow -->` to silence `build_dependency_graph.py` forward-reference findings and moved `@def-interval` after its special-case interval definitions instead of reordering the content and defining bounds first.
[`Morrison-Lab/lds#1237`](https://github.com/Morrison-Lab/lds/pull/1237) (2026-10-27, recorded in [`Morrison-Lab/ai-config#4769`](https://github.com/Morrison-Lab/ai-config/issues/4769)) bundled `#def-noise-model`, `#rem-noise-draws`, and `#rem-noise-model` into a single `_def-noise-model.qmd` subfile and pushed with `unlinked-first-use` findings in the diff before a local `check-term-links.py --diff` pass ran.
