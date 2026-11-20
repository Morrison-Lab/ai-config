Write user-facing prose in a plain, direct style. This applies to everything a
reader sees --- PR/issue/commit text, docs, READMEs, code comments, release
notes, emails, and chat replies. Apply it by default to your own drafts, not
just when asked.

The guide of record is the lab's **Principles of Scientific Writing (PSW)**:
<https://morrison-lab.github.io/psw/>.
The rules below operationalize it.
When PSW and this guidance disagree, PSW wins.

- **Limit dependent (subordinate) clauses.** One per sentence is plenty. When
  two or more stack up, split the sentence.
- **Cut low-content filler and jargon.** Delete words that add no information
  ("it's worth noting", "in order to" -> "to", "due to the fact that" ->
  "because").
- **Prefer plain (Anglish) words over Latin-derived ones** (PSW, "Word choice").
  "before", not "prior to"; "needed", not "necessary"; "use", not "utilize". A
  heuristic, not a purity rule.
- **Never swap a technical term for a plain word to avoid defining it**
  (Ezra, 2026-11-20: "never switch to a plain word to avoid needing to define a technical term").
  When the idea needs a technical term, use the term and define it,
  or link its definition; write the definition first when none exists yet.
  The plain-word preference above is for words that carry no technical meaning, such as "utilize" for "use".
  The jargon to cut is filler, not a defined term.
  A plain stand-in reads easier and says less:
  "a set" drops what "a finite set" required,
  and "a nice curve" says nothing that "a smooth function" does
  ([Morrison-Lab/mds#868](https://github.com/Morrison-Lab/mds/pull/868), open as of 2026-11-20, defines "smooth function" rather than avoid the word).
  A word used in its everyday sense, such as "weight" for heaviness, is not a technical term and needs no definition.
  - **Do:** keep "smooth function" and link it to its definition, writing one if the notes have none.
  - **Don't:** write "a nice curve" because "smooth" has no definition yet,
    or caption a histogram "bars" because "histogram" would need a link.
  [`hooks/no-delete-flagged-term.py`](../../hooks/no-delete-flagged-term.py) denies the case a tool can see:
  an edit that rewords a line where gha's `check-term-links` flags a term and drops that term.
  A term that no lab notes define yet is in no term list,
  so no check can tell it from a plain word, and that case rests on this rule alone.
- **Prefer simple declarative sentences and active voice.** Subject, verb,
  point. Name the actor, then the action.
- **Join independent clauses with coordinating conjunctions** (and, but, so, or)
  over subordinate constructions. Prefer "X is fast, but Y is correct" over
  "While X is fast, Y is correct."
- **Don't build a model only to retract it.**
  Lead with what is actually the case;
  present an idealization or a prior approach afterward,
  as an extension rather than a correction to something just asserted.
  See [`no-rug-pulls`](no-rug-pulls.md).
- **Lead with the subject, name the referent, and state the literal claim.**
  The canonical rules and examples are in PSW:
  [Lead with the subject](https://morrison-lab.github.io/psw/chapters/conciseness.html#lead-with-the-subject),
  [Say which thing](https://morrison-lab.github.io/psw/chapters/word-choice.html#say-which-thing),
  [Demonstrative pronouns](https://morrison-lab.github.io/psw/chapters/grammar.html#demonstrative-pronouns),
  and [Avoid vague and metaphorical language](https://morrison-lab.github.io/psw/chapters/word-choice.html#avoid-vague-and-metaphorical-language)
  (idioms).
  - **Do:** apply those PSW sections when writing or reviewing prose.
  - **Don't:** copy their text here; link the section instead
    (see [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)).
- **Don't use money words as idioms for trade-offs** (Ezra, 2026-10-14).
  Avoid "X costs us Y", "this buys us Z", "at the price of", "pays off",
  "the whole bargain" and "that trade" (Ezra, 2026-10-29, mds#529);
  say what is lost or gained.
  Keep literal uses: computational or monetary cost,
  and a cost function the text defines as a term.
  PSW's rule is in
  [Avoid vague and metaphorical language](https://morrison-lab.github.io/psw/chapters/word-choice.html#avoid-vague-and-metaphorical-language).
  - **Do:** write "continuity gives us the intermediate value theorem".
  - **Don't:** write "continuity buys us the intermediate value theorem".
- **Check every prose edit against PSW before the push that carries it**
  (Ezra and d-morrison, 2026-10-15,
  [`Morrison-Lab/psc#39`](https://github.com/Morrison-Lab/psc/pull/39)).
  A concision edit cut a relative pronoun and a citation duplicated a link,
  both against PSW pages that the editor had not read.
  Before the push, read the PSW pages that cover the edit,
  such as [Conciseness](https://morrison-lab.github.io/psw/chapters/conciseness.html)
  and [Do not omit relative pronouns](https://morrison-lab.github.io/psw/chapters/grammar.html#do-not-omit-relative-pronouns),
  then check the edit against them.
  Give each source one citation.
  - **Do:** write "the add-on packages that R Markdown needed".
  - **Don't:** write "the add-on packages R Markdown needed"
    to save a word.
- **Follow an abstract or general statement with a concrete example.**
  A general claim is fine when an instance follows it;
  a vague one with no instance is not.
  PSW's rule and its before/after are proposed in
  [`Morrison-Lab/psw#76`](https://github.com/Morrison-Lab/psw/pull/76)
  (open as of 2026-10-02) ---
  once merged, they live at
  [Follow an abstract statement with an example](https://morrison-lab.github.io/psw/chapters/word-choice.html#follow-an-abstract-statement-with-an-example).
  - **Do:** give the instance right after the general claim.
  - **Don't:** leave a general claim for the reader to instantiate.
- **Put an inline list of three or more phrases in a bullet list**,
  introduced by a sentence ending in a colon, and number sequential steps.
  A short series of single words may stay inline.
  PSW's rule and examples are proposed in `Morrison-Lab/psw#60` ---
  once merged, they live at `chapters/conciseness.qmd`,
  "Put lists in bullet points".
- **Write for every reader, including readers learning English
  and neurodiverse readers.**
  Use literal words, not idioms or slang,
  and spell out abbreviations and hidden steps.
  This includes postural or residency verbs used for numbers, sets, or distributions
  ("lies in", "lies between", "sits at", "lives in" --- use "is in", "is between", or "has [quantity]"),
  verbs that stand in for equality, zero, or special cases
  ("agree" --- use "are equal" or "give the same result";
  "vanish" --- use "equal $0$", "converge to $0$", or "cancel";
  "recover" --- use "give", "equal", or "reduce to"),
  cognitive or speech verbs applied to models or equations
  ("the model knows nothing about $[0, 1]$", "the boundary decides",
  "the derivative recommends a step", "the recommendation is trustworthy" (Ezra, 2026-10-29, mds#529)
  --- state the constraint or condition under which the claim holds;
  gha's `check-ai-tells` flags the literal phrasings as warn-only once gha#1326 merges),
  and imperative or exercise-prompt idioms
  ("Write $X$ as", "Fix $X$", "Take $X$", "Call $X$", "Say which/why" --- use "Express $X$ as", "Let $X$", "Consider $X$", "Denote $X$ by", "State which", or "Explain why").
  PSW's rules and table of literal alternatives live at
  [Writing for every reader](https://morrison-lab.github.io/psw/chapters/inclusive-writing.html#use-literal-language)
  ([`Morrison-Lab/psw#308`](https://github.com/Morrison-Lab/psw/pull/308),
  [`Morrison-Lab/psw#309`](https://github.com/Morrison-Lab/psw/pull/309)).
  - **Do:** write "the estimates become very large" and "the residual is in $(-1, 1)$".
  - **Don't:** write "the estimates blow up" or "the residual lies in $(-1, 1)$".

This is a default, not an absolute rule. Keep a clause or a technical term when
removing it would lose meaning or precision. Never trade an honest hedge for
false confidence.
A simile or an as-though construction is a hedge too, so swapping one for its
"precise equivalent" can assert a mechanism the original only likened, with no
hedge word deleted
(see [`find-ai-tells`](../../skills/find-ai-tells/SKILL.md)'s anti-patterns).

Writing agents do not need to enforce all style guidelines on first draft.
Work iteratively: write a substantively-correct but stylistically loose first draft,
and then hand off to the prose editor agent ([`prose-editor`](../../.claude/agents/prose-editor.md)) for revisions.
See [`iterative-editing`](../workflow/iterative-editing.md).
