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
- **Setup-then-payoff clichés:** a straw objection raised only to be answered
  ("It can read like a definition that says nothing.
  Its use is in ..."), which is the antithesis above spread over two sentences;
  a personified abstraction that "forces", "invites", or "demands" something of
  the reader; a colon reveal that withholds the point until after the colon;
  a second-person "you" in expository prose; and a closing aphorism that
  restates the point as a verdict ("... has not yet stated a problem").
  Replace them with the literal claim.
  (Directive from the user, 2026-09-25, flagging those in a lecture slide.)
- **More clichéd sentence shapes** (user directive, 2026-09-25: add every
  known one).
  A rhetorical question answered at once ("The result? ...",
  "Why does this matter? Because ...").
  A throat-clearing lead-in ("Here's the thing:", "Here's why:",
  "The key is", "The short answer:", "Put simply,").
  An "X isn't about Y; it's about Z" or "The question isn't X, it's Y" reframe.
  "Not because X, but because Y".
  Fragment emphasis ("Simple. Fast. Reliable.").
  A trailing participial clause that editorializes
  (", highlighting the importance of ...", ", ensuring that ...",
  ", making it ideal for ...").
  "Serves as", "stands as", or "acts as" in place of "is".
  "When it comes to", "In the world of", "In the realm of".
  "From X to Y" range framing that lists extremes instead of the scope.
  "Whether you're X or Y" audience framing.
  An "In other words" restatement of what was just said.
  A one-line verdict closing a paragraph ("And that's the point.",
  "That's the whole trick.", "Simple as that.").
  Intensifiers used as sincerity markers ("genuinely", "truly", "actually",
  "really", "crucially").
  Conversational or assistant chatter ("Let's dive in", "Let's unpack this",
  "Great question", "I hope this helps").
  Metaphor clusters: "journey", "landscape", "navigate", "unlock", "harness",
  "pave the way", "shed light on", "at the heart of", "sits at the
  intersection of", "beacon", "cornerstone", "deep dive".
  More overused words: underscore, highlight, foster, bolster, intricate,
  meticulous, comprehensive, groundbreaking, game-changer, empower, elevate,
  streamline, paradigm, synergy, ever-evolving, dynamic, myriad, plethora,
  noteworthy, "at its core", "in essence", "boils down to", "key takeaway".
  Chained additive connectors ("Furthermore", "Moreover", "Additionally")
  opening consecutive sentences.
  Fix: state the literal claim; name the actor, the object, and the number.
- **Formulaic openers:** a declarative sentence fronted by one of four shapes.
  An underspecified reference: a bare demonstrative ("This is", "That is",
  "These are", "Those are") or "The one that".
  A fronted wh-clause: "Who", "What", "Where", "When", "Why", "How", "Which",
  "Whose" ("What makes it work is the lease", "Why that matters is the cost").
  A partitive quantifier ("Some of the", "Many of the", "All of the",
  "None of the").
  A fronted subordinate clause or preposition ("While", "Although", "Despite",
  "Because", "Since"), which creates a fronted nested clause before the reader
  knows the subject or main claim.
  The underspecified reference narrows two rules that already exist.
  [`use-preferred-style`](../../skills/use-preferred-style/SKILL.md) rule 8 and
  [`ambiguous-reference`](ambiguous-reference.md) both govern a demonstrative
  anywhere in a sentence, and ask whether its referent is named.
  What this adds is **position and count** --- sentence-initial, tallied per
  page --- plus the wh-word, partitive, and fronted subordinator shapes neither
  covers.
  Fronted concessive and conditional clauses bury the core claim;
  see [`plain-prose`](plain-prose.md)'s subordinate-clause rule and conciseness
  principles.
  Cue: split on sentence-final punctuation before matching.
  A line-start grep sees only the sentences that happen to begin a line, and
  this repo wraps prose at clause boundaries:
  `tr '.!?' '\n' < FILE | grep -icE "^ *(this|that|these|those|the one that|who|what|where|when|why|how|which|whose|while|although|despite) "`.
  Fix: name the noun the demonstrative stands for (-> "The clean verdict is
  the trigger").
  Front the subject and drop the copula (-> "The lease makes it work").
  Cut "of the", or give the count (-> "Many checks fail", "Four of the nine
  checks fail").
  State the main assertion first, then qualify it, or split into two sentences.
- **Cliches and jargon:** idioms, sports metaphors, unnecessary copulas, and
  contrastive closes used as reflexes.
  A contrastive close used as the default end of a claim ("rather than",
  "not the same as") --- the quiet sibling of the antithesis above.
  Unnecessary copula and cleft structures: "is what", "is where", "is when",
  "is how" ("the lease is what stops" -> "the lease stops"; "this is where
  the check runs" -> "the check runs here").
  Metaphor cliches and sports jargon: "the whole of it" (-> "all of it",
  "the entirety"), "own-goal" (sports jargon for self-inflicted error),
  "load-bearing" (architectural metaphor for "essential").
  Overused verbs: "carries"/"carry" standing in for a specific verb, and
  "tells"/"doesn't tell"/"does not tell" standing in for a plain verb of report.
  Mid-phrase conjunctive ticks: inserting ", however, " or ", therefore, "
  mid-clause where a direct sentence or cleaner connector works better.
  Indirect questions as noun phrases: "about what" where a concrete noun fits
  (-> "disagreed on the requirements", not "disagreed about what was needed").
  Gratuitous explanations and disclaimers: unsolicited throat-clearing
  ("Note that...", "It is important to remember that...").
  Cue: count them per page, since each is ordinary English at one or two hits
  and a verbal tic at ten ---
  `grep -ioE "rather than|not the same as|load-bearing|carr(y|ies)|\btells\b|does(n't| not) tell|the whole of it|own-goal|is (what|where|when|how)|\babout what\b|, however," FILE | wc -l`.
  Fix: state the claim positively, and keep one contrast per paragraph at most.
  Say what a thing **is**, not what it is not (-> "the lease compares against
  your remote-tracking ref", not "a lease is not the same as a force").
  Use the plain verb (-> has, includes, states, sets, shows, omits).
  Say what a part does directly without a copula cleft (-> "the lease stops
  a background fetch clobbering a peer's commit").
  Drop mid-phrase conjunctives or start with "Yet" or "Still".
  Replace "about what" with the concrete noun or subject.
- **Thin punctuation:** long sentences glued together with "and", while commas,
  semicolons, colons, and parentheses stay rarer than a human writer's.
  The Economist measured this in August 2026 ("How to spot AI writing").
  Its corpus ran to 55,940 sentences and 1.2 million words:
  the Economist's own copy, ChatGPT, Claude, Gemini, and Grok versions of
  those articles, journalism from CNN, the New York Times, and the Washington
  Post, and excerpts from novels published between 1950 and 2022.
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
  Fix: split the sentence, per
  [`plain-prose`](plain-prose.md)'s subordinate-clause rule.
  Repeat the shared subject in the second half.
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
  Deterministic candidate scanning: `scripts/check-sentence-complexity.py`
  computes sentence word count, clause/subordinator nesting, Automated
  Readability Index (ARI), Coleman-Liau, and paragraph burstiness.
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
