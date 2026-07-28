Use the least-flexible construct that does the job.
When two constructs both work, prefer the one that can do less, because a
narrower construct announces its own purpose and a general one does not.

*Advanced R* states this directly and builds a ladder from it.
On loops, in
[Related tools](https://adv-r.hadley.nz/control-flow.html#for-family):

> You can rewrite any `for` loop to use `while` instead, and you can rewrite
> any `while` loop to use `repeat`, but the converses are not true.
> That means `while` is more flexible than `for`, and `repeat` is more
> flexible than `while`.
> It's good practice, however, to use the least-flexible solution to a
> problem, so you should use `for` wherever possible.

And one rung further up, in
[Functionals](https://adv-r.hadley.nz/functionals.html):

> the real downside of for loops is that they're very flexible: a loop
> conveys that you're iterating, but not what should be done with the
> results.
> Each functional is tailored for a specific task, so when you recognise the
> functional you immediately know why it's being used.

## The ladder

From most flexible to least, prefer the last one that fits:

`repeat` -> `while` -> `for` -> a functional (`map()`, `reduce()`,
`some()`, ...) -> a vectorised call over the whole object.

Reading `repeat` tells you nothing but that something recurs.
Reading `map_dbl(x, f)` tells you the length of the result, its type, and
that each element is handled independently.
That information is carried by the choice of construct, so it costs the
reader nothing and it cannot go stale.

## Beyond loops

The same argument decides several rules already in this corpus, which is
the sign it is the general form rather than a loop-specific tip:

- [`per-operation-grouping`](per-operation-grouping.md) prefers `.by=` over
  `group_by()`/`ungroup()`, because `.by=` cannot outlive the verb it is
  attached to.
- [`type-stable-outputs`](type-stable-outputs.md) prefers `map_dbl()` over
  `map()` plus `unlist()`, because `map_dbl()` cannot return anything but a
  double vector.
- A constant belongs in `const`-equivalent form, a helper stays local rather
  than exported, and a script's scope stays as small as it can be.

## The escape hatch

Do not reach past the ladder for a construct that does not actually fit.
The book is explicit that forcing the fit is worse than the loop:

> If one doesn't exist, don't try and torture an existing functional to fit
> the form you need.
> Instead, just leave it as a for loop!

A `map()` call carrying a lambda that mutates shared state, threads an
index, and returns `NULL` is a `for` loop wearing a functional's name.
It has given up the readability that motivated the ladder while keeping the
cost.
Write the loop, and apply [`loop-hygiene`](loop-hygiene.md) to it.

The book adds the useful trigger for revisiting that decision: once the same
loop has been written two or more times, that is the moment to consider
writing your own functional for it.

## In review

Flag these with the same weight as the other coding rules:

- A `while` or `repeat` where the set of values to iterate over is known up
  front, and `for` would do.
- A `for` loop whose body is a single independent transformation per
  element, where a `map_*()`/`vapply()` call would say the same thing.
- A functional twisted to fit a shape it does not have --- a lambda mutating
  enclosing state, or one whose return value is discarded --- where the loop
  it replaced was clearer.

The last one is a finding in the opposite direction from the first two, and
that is deliberate: this rule is not "use functionals", it is "let the
construct match the job".
