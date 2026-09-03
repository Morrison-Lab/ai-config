Write plainly up front, then **scan the draft for AI tells before sending**.
Before presenting non-trivial prose --- PR/issue descriptions, commit bodies,
README/doc/vignette text, or a long answer meant as deliverable prose ---
self-check it and cut the tells. Apply the same catalog **when reviewing
someone else's prose** too --- a PR/MR diff, a doc change, any non-code
narrative content --- not just your own drafts.
Flag each tell found, and do not wave a plausible-sounding paragraph through
unchecked.
Watch for:

- **Overused vocabulary:** actionable (→ "to act on"), delve, leverage, utilize,
  tapestry, testament, realm, robust, seamless, holistic, nuanced, multifaceted,
  pivotal, crucial, "in today's fast-paced world", "stands as a testament to".
- **Rhetorical reflexes:** the "it's not just X, it's Y" antithesis (the biggest
  tell), mechanical rule-of-three lists, signposting filler ("it's worth noting
  that", "importantly"), hedging stacks, hollow "in conclusion" restatements.
- **Formulaic openers:** a declarative sentence fronted by one of three shapes.
  A bare demonstrative ("This is", "That is", "These are", "Those are").
  A wh-word ("What makes it work is the lease", "Why that matters is the cost").
  A partitive quantifier ("Some of the", "Many of the", "All of the",
  "None of the").
  The demonstrative shape narrows two rules that already exist.
  [`use-preferred-style`](../../skills/use-preferred-style/SKILL.md) rule 8 and
  [`ambiguous-reference`](ambiguous-reference.md) both govern a demonstrative
  anywhere in a sentence, and ask whether its referent is named.
  What this adds is **position and count** --- sentence-initial, tallied per
  page --- plus the wh-word and partitive shapes neither of those covers.
  Cue: split on sentence-final punctuation before matching.
  A line-start grep sees only the sentences that happen to begin a line, and
  this repo wraps prose at clause boundaries:
  `tr '.!?' '\n' < FILE | grep -icE "^ *(this|that|these|those) (is|are)\b"`.
  Fix: name the noun the demonstrative stands for (-> "The clean verdict is
  the trigger").
  Front the subject and drop the copula (-> "The lease makes it work").
  Cut "of the", or give the count (-> "Many checks fail", "Four of the nine
  checks fail").
- **Cliches and jargon:** a contrastive close used as the default end of a
  claim ("rather than", "not the same as").
  It is the quiet sibling of the antithesis above.
  Also "carries"/"carry" standing in for a plain verb, "load-bearing" standing
  in for "essential", and "tells"/"doesn't tell"/"does not tell" standing in
  for a plain verb of report.
  Cue: count them per page, since each is ordinary English at one or two hits
  and a verbal tic at ten ---
  `grep -icoE "rather than|not the same as|load-bearing|carr(y|ies)|does(n't| not) tell" FILE`.
  Fix: state the claim positively, and keep one contrast per paragraph at most.
  Say what a thing **is**, not what it is not (-> "the lease compares against
  your remote-tracking ref", not "a lease is not the same as a force").
  Use the plain verb (-> has, includes, states, sets, shows, omits).
  Say what a part does and what breaks without it (-> "the lease is what stops
  a background fetch clobbering a peer's commit").
- **Thin punctuation:** long sentences glued together with "and", while commas,
  semicolons, colons, and parentheses stay rarer than a human writer's.
  The Economist measured this in August 2026 ("How to spot AI writing").
  The study compared 55,940 sentences and 1.2 million words of its own copy
  against ChatGPT, Claude, Gemini, and Grok rewrites of the same articles.
  Sparse punctuation beat the em-dash as a marker, and only Claude used
  em-dashes more often than the human writers did.
  So read the em-dash bullet below as model-specific, not universal.
  Re-check that finding before relying on it: a model release can overturn
  which model over-punctuates
  (see [`timestamp-volatile-claims`](timestamp-volatile-claims.md)).
  Cue: count semicolons, colons, and parentheses per 1,000 words, and count
  "and" against them.
  Fix: break the run-on at the "and", and punctuate the parts.
- **Convoluted sentences:** clause nesting deep enough that the reader holds
  the subject open across two or more embedded clauses.
  Cue: the ~25-word bar
  [`use-preferred-style`](../../skills/use-preferred-style/SKILL.md) step 2
  already sets, or three or more commas plus a subordinator ("which", "whose",
  "because", "while", "so that").
  Fix: [`plain-prose`](plain-prose.md)'s subordinate-clause rule --- split the
  sentence, and repeat the shared subject in the second half.
  On measuring it algorithmically: readability formulas score word and sentence
  length only.
  Flesch-Kincaid grade level (Kincaid et al. 1975) and Gunning fog
  (Gunning 1952) therefore proxy nesting instead of measuring it.
  Parse-tree depth measures the nesting itself --- Yngve depth (Yngve 1960), or
  a plain count of embedded clauses.
  A dependency parser's mean dependency distance (Liu 2008) measures
  head-to-dependent span instead, which is a working-memory proxy that
  correlates with nesting without being the same quantity.
  A flat coordinated list inflates it at zero nesting depth.
- **Structural/typographic:** em-dash overuse as a default connector,
  bold-leading `**Term:**` bullets applied mechanically, emoji section headers,
  conspicuously uniform paragraph rhythm.
- **Tonal:** promotional register, reflexive both-sidesing, vague universals
  with no concrete names or numbers.

De-slop --- cut the filler and the reflexes --- but **don't** ban words outright
or sand the text into a flat, voiceless register. Any single tell is innocent;
clustering and mechanical repetition are the signal. Code, terse status lines,
and short conversational replies are exempt.

- **Do:** judge a lexical tell over the whole page before cutting any single
  instance of it, since one hit is ordinary English.
- **Do:** split an over-nested sentence even when it is the only one on the
  page --- nesting is a defect per sentence, not a density signal.
- **Don't:** reword one instance into a worse sentence to clear a grep.
- **Don't:** read ~25 words as a limit --- it is a cue to reread, and one clear
  40-word sentence beats two awkward 20-word ones.
