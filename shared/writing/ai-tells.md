Write plainly up front, then **scan the draft for AI tells before sending**.
Before presenting non-trivial prose --- PR/issue descriptions, commit bodies,
README/doc/vignette text, or a long answer meant as deliverable prose ---
self-check it and cut the tells. Apply the same catalog **when reviewing
someone else's prose** too --- a PR/MR diff, a doc change, any non-code
narrative content --- not just your own drafts; flag each tell found rather
than waving a plausible-sounding paragraph through unchecked. Watch for:

- **Overused vocabulary:** actionable (→ "to act on"), delve, leverage, utilize,
  tapestry, testament, realm, robust, seamless, holistic, nuanced, multifaceted,
  pivotal, crucial, "in today's fast-paced world", "stands as a testament to".
- **Rhetorical reflexes:** the "it's not just X, it's Y" antithesis (the biggest
  tell), mechanical rule-of-three lists, signposting filler ("it's worth noting
  that", "importantly"), hedging stacks, hollow "in conclusion" restatements.
- **Formulaic openers:** a declarative sentence fronted by a bare demonstrative
  ("This is", "That is", "These are", "Those are"), by a wh-word ("What makes
  it work is the lease", "Why that matters is the cost"), or by a partitive
  quantifier ("Some of the", "Many of the", "All of the", "None of the").
  Cue: read the first two words of every sentence, which a line-start grep
  collects in bulk.
  Fix: name the noun the demonstrative stands for (→ "The clean verdict is
  the trigger"), front the subject and drop the copula (→ "The lease makes
  it work"), and cut "of the" or give the count (→ "Many checks fail",
  "Four of the nine checks fail").
- **Cliche metaphors:** "rather than" as the default close of a claim (the
  quiet sibling of the antithesis above), "carries"/"carry" standing in for a
  plain verb, "load-bearing" standing in for "essential".
  Cue: count them per page, since each is ordinary English at one or two hits
  and a verbal tic at ten.
  Fix: state the claim positively and keep one contrast per paragraph at most,
  use the plain verb (→ has, includes, states, sets), and say what the
  part does and what breaks without it (→ "the lease is what stops a
  background fetch clobbering a peer's commit").
- **Convoluted sentences:** clause nesting deep enough that the reader holds
  the subject open across two or more embedded clauses.
  Cue: a sentence past about 35 words, or one with three or more commas
  plus a subordinator ("which", "whose", "because", "while", "so that").
  Readability formulas (Flesch-Kincaid grade level, Gunning fog) score word and
  sentence length only, so they proxy nesting instead of measuring it.
  A dependency parser's mean dependency distance or parse-tree depth measures
  the nesting itself.
  Fix: split at the outermost clause boundary and repeat the shared subject in
  the second sentence.
- **Structural/typographic:** em-dash overuse as a default connector,
  bold-leading `**Term:**` bullets applied mechanically, emoji section headers,
  conspicuously uniform paragraph rhythm.
- **Tonal:** promotional register, reflexive both-sidesing, vague universals
  with no concrete names or numbers.

De-slop --- cut the filler and the reflexes --- but **don't** ban words outright
or sand the text into a flat, voiceless register. Any single tell is innocent;
clustering and mechanical repetition are the signal. Code, terse status lines,
and short conversational replies are exempt.

- **Do:** count an opener or a cliche across the whole page, and cut it where
  the repetition is what a reader notices.
- **Don't:** reword one instance into a worse sentence to clear a grep.
