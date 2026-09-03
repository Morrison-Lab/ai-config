# AI writing patterns, detection metrics, and anti-slop architectures

Empirical synthesis of AI writing patterns,
statistical detection metrics,
and multi-tier enforcement architecture,
reviewed 2026-08-31 from `r/claudeskills` community research
(`Abdulkader-Safi/AI-Writing-Rules`,
derived from Wikipedia's "Signs of AI writing" catalog
and SlopDetector empirical benchmarks).

## Multi-tier anti-slop architecture

Enforcing human writing quality without context bloat
relies on separating concerns across four operational layers:

1. **Session-start hard rules (always-loaded, minimal context):**
   Inject a compact (~250---300 word) ruleset at session start
   covering non-negotiable negative constraints:
   no em-dashes, straight quotes, sentence-case headings,
   no negative parallelism ("not just X, it's Y"),
   breaking the rule of three,
   and direct vocabulary bans.
   Keeping this compact prevents context exhaustion.

2. **On-demand pattern reference (skill layer):**
   Expose detailed pattern catalogs,
   explanations of why models produce each reflex,
   bad examples, and plain human revisions in on-demand skill documentation.
   The agent consults specific pattern files when diagnosing or rewriting,
   avoiding full catalog injection into working context.

3. **Deterministic post-tool verification (hook layer):**
   Run a fast, local script on `PostToolUse`
   after writing or editing narrative text files (`.md`, `.txt`, `.rst`).
   The checker performs deterministic regex scans for mechanical tells
   (AI vocabulary, negative parallelism, em-dashes, curly quotes)
   and statistical metric calculations (sentence burstiness, triplet density).
   If violations occur, the hook returns line numbers and specific instructions
   to fix the text immediately before proceeding.

4. **Audit and rewrite tools (command layer):**
   Provide dedicated audit/rewrite routines (e.g. `/deslop`)
   that scan a target file,
   execute targeted de-slopping,
   and verify clean status through the deterministic checker.

## Core pattern taxonomy

No single tell proves machine generation in isolation;
the diagnostic signal lies in clustering and mechanical repetition.

### 1. Lexical & vocabulary reflexes

- **Corporate verb inflation:**
  Substituting inflated Latinate verbs where plain Anglo-Saxon verbs suffice
  (e.g., *utilize* -> *use*, *facilitate* -> *help*, *commence* -> *start*, *terminate* -> *end*).
- **Reflex AI vocabulary:**
  Persistent over-representation of specific tokens:
  *delve*, *tapestry*, *testament*, *realm*, *landscape*, *beacon*, *nuanced*,
  *multifaceted*, *intricate*, *pivotal*, *crucial*, *holistic*, *foster*, *harness*,
  *embark*, *unlock*, *elevate*, *showcase*, *meticulous*, *streamline*, *empower*,
  *groundbreaking*, *transformative*.
- **Narrow vocabulary range (Type-Token Ratio):**
  LLM text exhibits lower lexical diversity (lower TTR = unique words / total words)
  compared to human writing of matched length.

### 2. Sentence-level syntactic habits

- **Copula avoidance (dodging "is" and "are"):**
  Refusing plain statements of identity or existence in favor of dressed-up constructions:
  "serves as a", "stands as a", "acts as a", "marks a".
  *Fix:* Replace with "is" or "are".
- **Negative parallelism (antithesis reflex):**
  The most recognizable syntactic formula:
  "It's not just X, it's Y";
  "This is not about X; it's about Y";
  "Not only X, but also Y".
  *Fix:* Delete the negation and state the positive half directly.
- **Rule-of-three autopilot (tricolon clustering):**
  Defaulting to triplets of adjectives, nouns, or parallel clauses
  ("fast, reliable, and scalable")
  to mimic comprehensive coverage without committing to actual enumeration.
  *Fix:* Use one, two, or four items;
  vary list lengths;
  keep three only when accurate.
- **Trailing "-ing" participle commentary:**
  Tacking a participial phrase onto the end of a factual clause
  to simulate profound analysis without verifiable substance
  (e.g., "...thereby highlighting the importance of X", "...ensuring seamless alignment", "...paving the way for future growth").
  *Fix:* Cut the participle clause or split into a concrete second sentence.
- **Formulaic sentence openers:**
  Fronting a declarative with a bare demonstrative
  ("This is", "That is", "These are", "Those are"),
  a wh-word ("What makes it work is..."),
  or a partitive quantifier ("Some of the", "Many of the", "None of the").
  *Fix:* Name the noun the demonstrative stands for,
  or front the subject and drop the copula.
- **Contrastive closes and stock metaphors:**
  Ending a claim by default with "rather than" or "not the same as";
  "carries"/"carry" and "tells"/"doesn't tell" standing in for a plain verb;
  "load-bearing" standing in for "essential".
  *Fix:* State the claim positively, and use the plain verb.
  Judge these by density, since each is ordinary English at one or two hits.
- **Sentence-complexity metrics (measuring convoluted nesting):**
  Readability formulas score word and sentence length only
  (Flesch-Kincaid grade level, Kincaid et al. 1975; Gunning fog, Gunning 1952),
  so they proxy clause nesting instead of measuring it.
  Parse-tree depth measures the nesting itself
  (Yngve depth, Yngve 1960, or a plain count of embedded clauses).
  Mean dependency distance (Liu 2008) measures head-to-dependent span:
  a working-memory proxy that correlates with nesting
  without being the same quantity,
  and one a flat coordinated list inflates at zero nesting depth.
- **Hedging stacks:**
  Layering epistemic modals ("may potentially help to", "can arguably to some extent").
  *Fix:* Make the direct claim or drop it.

### 3. Substance & rhetorical structure

- **Puffed-up significance:**
  Inflating mundane factual topics with grand, unearned framing
  ("stands as a testament to the enduring power of", "plays a pivotal role in the evolving landscape of").
- **Vague attribution:**
  Citing unnamed, unverifiable authorities
  ("experts agree", "studies have shown", "industry observers note")
  or using "such as" before an exhaustive list to imply false breadth.
- **Empty openers & pseudo-wisdom:**
  Setting scenes with meaningless boilerplate
  ("In today's fast-paced digital world", "Now more than ever", "The key is finding the right balance").
- **The deletion test:**
  A diagnostic test for vacuous prose:
  remove the rhetorical framing and check if any concrete fact remains
  (a specific name, date, measurement, trade-off, or actionable decision).
  If nothing remains, the sentence or paragraph has zero information content.
- **Lead construction (title as an object):**
  Opening a document by defining its own title as a noun in the world
  ("X is a comprehensive guide that outlines...").

### 4. Rhythm, punctuation & typography

- **Uniform sentence length (low burstiness):**
  Human prose alternates short, punchy sentences with longer complex structures
  (burstiness = standard deviation / mean of sentence lengths;
  human baseline is 0.6---1.2).
  LLM text often hovers around a flat 18---24 word average with low burstiness (~0.3).
- **Thin punctuation:**
  Over-reliance on commas and additive conjunctions ("and")
  while avoiding semicolons, colons, parentheses, or mid-thought periods.
  The Economist ("How to spot AI writing", August 2026)
  compared 55,940 sentences and 1.2 million words of its own copy
  against ChatGPT, Claude, Gemini, and Grok rewrites of the same articles,
  and found sparse punctuation a better marker than the em-dash.
  Only Claude used em-dashes more often than the human writers did,
  so read the em-dash baselines below per model
  and re-check them as models change.
- **Em-dash density:**
  Overusing em-dashes as an all-purpose glue for clause attachment
  (human baseline is ~3.2 per 1,000 words;
  GPT-4.1 measured at ~10.6 per 1,000 words,
  with concern thresholds at 20+ per 1,000 words).
- **Smart punctuation leakage:**
  Curly quotes (typographic double and single quotes), ellipsis glyphs,
  and model artifacts (`attributableIndex`, `turn0search0`, `oaicite`, `oai_citation`, `[cite: 1]`).

### 5. Formatting tells

- **Excessive mechanical bolding:**
  Applying bolding reflexively to keywords or every bullet label (`**Label:** text`)
  without editorial discretion.
- **Forced tables and forced bulleting:**
  Tabulating content that is not multidimensional data,
  or bulleting a narrative paragraph to create a cosmetic appearance of structure.
- **Outline-shaped endings:**
  Generic "Conclusion", "Looking ahead", or "Challenges and future prospects" sections
  that merely summarize preceding points without contributing new analysis.

- **Do:** use deterministic regex and metric hooks for mechanical writing checks.
- **Do:** apply the deletion test to catch substance-free paragraphs that pass lexical filters.
- **Don't:** ban valid vocabulary words in isolation;
  evaluate clustering and mechanical repetition.
- **Don't:** load extensive research catalogs into every session's baseline context.
