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
   Every technical term is hyperlinked at first use in each div.
   A term with no definition gets its own definition div, filed as an issue if it widens the PR, never left unlinked.
3. **Symbols.**
   Every technical term is paired with its semantic macro, and the macro is the existing one: search `Morrison-Lab/macros` for the concept before writing any expression.
4. **Minimal expressions.**
   Each expression is as short as the macros allow, with no manual delimiter around a function's arguments, and any repeated chunk is named.
5. **Definitions.**
   No term appears in its own definition, none is defined as a modification of another, and each preposition states a relation you can name.
   A definition div holds its one term and links to everything else.
   A clause that defines another term or notation ("we write ... for ...", "a function that maps ...") gets its own definition div and example instead.
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
    Replace postural verbs for mathematical objects ("lies in", "lies between", "sits at"), money-word trade-off idioms ("costs", "buys", "at the price of"), and imperative mathematical idioms ("Write $X$ as", "Fix $X$", "Take $X$", "Call $X$") with literal wording, per psw's [Use literal language](https://morrison-lab.github.io/psw/chapters/inclusive-writing.html#use-literal-language) and [`Morrison-Lab/psw#308`](https://github.com/Morrison-Lab/psw/pull/308) (open as of 2026-10-20).

An item that fails on one div is checked on every div of the PR, per the sweep above.
Recurrence: sds#268 (2026-10-17) drew an inline definition at least five times after the first correction, which is why item 5 now names the pattern.
