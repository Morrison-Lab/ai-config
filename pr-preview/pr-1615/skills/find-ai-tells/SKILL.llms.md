# find-ai-tells — spot the telltale signs of AI-written prose

Scan prose for the patterns that make text read as machine-generated, report each one with its location and a plain-English revision, and (on request) apply the fixes. The same catalog doubles as a **self-check on my own writing**.

A “tell” is a heuristic, never proof. Any single one is innocent — `delve` is a real word, an em-dash is correct punctuation, three items is sometimes just three items. The signal is **clustering and mechanical repetition**: the same rhetorical move every paragraph, every bullet built `**Term:** gloss`, a triad in every sentence. The goal is to *de-slop* — cut the filler and the reflexes — **not** to ban words or flatten a real human voice.

## When this fires

- “find AI tells”, “find-ai-tells”, “ai-tells”, “de-slop this”, “remove the AI tells”, “make this not sound AI-generated”
- “does this sound like AI / ChatGPT?”, “was this written by AI?”, “check this draft for tells”
- **As part of any PR/MR review where the diff touches narrative prose** — docs, READMEs, lecture notes, textbook chapters, commit/PR descriptions making a substantive claim. Run alongside (not instead of) accuracy review (`fact-check-prose`) and style review (`use-preferred-style`).
- **Standing self-check (no invocation needed):** before I present any non-trivial prose I authored — a PR/issue description, a commit body, README or doc text, a vignette paragraph, a long chat answer meant as deliverable prose — I first run my draft against the catalog below and cut what I find. Code, terse status lines, and short conversational replies are exempt.

## Procedure

1.  **Identify the target.** A path, a PR/MR (`gh pr diff N` / `glab mr diff N`), pasted text, or — for the self-check — my own draft before I send it.
2.  **First pass, grep the cheap lexical/typographic tells** (catalog below has a ready-to-run command). This finds the mechanical ones fast and cheaply.
3.  **Second pass, read for the rhetorical and structural tells** that grep can’t see — antithesis, triads, both-sidesing, hollow conclusions, uniform rhythm.
4.  **Report** *(external targets only — skip for the self-check)*. A table — *tell · location (`file:line` or quoted snippet) · why it reads as AI · suggested revision* — followed by a one-line **density verdict**: is this an isolated word or a pervasive pattern? Don’t cry wolf on a single innocent em-dash.
5.  **Offer to apply** *(external targets)* / **just fix it silently** *(self-check)*. For an external target, on request rewrite in place with `Edit`, preserving the author’s meaning and voice. When scanning my own draft, skip the report (step 4) and simply cut the tells before presenting.

## The catalog

### A. Lexical tells (overused words & phrases)

Reflex vocabulary that LLMs reach for far more than human writers:

- **Verbs:** delve, leverage, harness, utilize, foster, facilitate, navigate, underscore, embark, unlock, elevate, spotlight, “shed light on”, “dive into”.
- **Nouns/imagery:** tapestry, testament, realm, landscape, beacon, journey, treasure trove, plethora, myriad, game-changer, deep dive.
- **Adjectives:** robust, seamless, holistic, nuanced, multifaceted, intricate, comprehensive, pivotal, crucial, vital, paramount, vibrant, bustling, cutting-edge, state-of-the-art, ever-evolving, rich (as in “rich history”).
- **Stock frames:** “in today’s fast-paced world”, “in the realm of”, “at the heart of”, “when it comes to”, “more than just”, “stands as a testament to”, “plays a crucial/pivotal role”.

Quick first-pass grep (case-insensitive, prints `file:line`). Define the pattern once, then run it through whichever tool is on hand:

``` bash
tells='delve|leverage|utilize|seamless(ly)?|robust|holistic|nuanced|multifaceted|intricate|tapestry|testament|realm|landscape|beacon|plethora|myriad|pivotal|crucial|paramount|underscore|foster|harness|embark|unlock|elevate|game-?changer|cutting-edge|state-of-the-art|ever-evolving|treasure trove|fast-paced|in the realm of|at the heart of|more than just|shed light|dive in(to)?|deep dive'
rg -niE "\b($tells)\b" <target>          # ripgrep
grep -rniE "\b($tells)\b" <target>       # no ripgrep — same pattern, via grep
```

### B. Rhetorical tells (sentence-level reflexes)

- **The negation-reversal antithesis** — the single biggest tell: “It’s not just X, it’s Y” / “It isn’t about X; it’s about Y” / “This isn’t merely X — it’s Z”. Grep: `rg -niE "(it'?s|this is) not (just|only|merely|about)"`.
- **Rule of three, mechanically** — triadic lists everywhere (“fast, reliable, and scalable”; “discover, explore, and master”). One triad is rhetoric; a triad in every sentence is a tell.
- **Sweeping range frames** — “from X to Y”, “whether you’re X or Y”.
- **Signposting filler** — “It’s worth noting that”, “It’s important to note”, “Importantly,”, “Notably,”, “That said,”, “At the end of the day,”, “It’s essential to understand that”.
- **Hedging stacks** — piled modals: “may potentially”, “can sometimes help to”.
- **Conversational scaffolding** (chat-style) — “Certainly!”, “Absolutely!”, “Great question!”, “Let’s dive in”, “Let’s explore”, “I hope this helps!”, “Feel free to…”.
- **Transition-adverb pileup** — “Moreover,”, “Furthermore,”, “Additionally,”, “Consequently,” opening consecutive sentences.
- **Hollow conclusion** — an “In conclusion,” / “In summary,” paragraph that only restates, adding nothing.

### C. Structural & typographic tells

- **Em-dash overuse** — multiple `—` per paragraph used as a default connector. (Em-dashes are correct; the tell is *frequency*, not presence.) Grep: `rg -n '—' <target>` and judge density.
- **Bold-leading bullets** — every list item shaped `**Term:** explanation`, applied mechanically rather than where emphasis helps.
- **Emoji section headers / bullets** — ✅ 🚀 🎯 🔑 decorating headings or list items in otherwise plain prose.
- **Uniform rhythm** — every section the same length, every paragraph 3–4 sentences; conspicuously even, sanded-down structure.
- **Over-signposting** — “Let’s take a closer look”, “Now, let’s…”, a heading before every two sentences.

### D. Tonal / content tells

- **Promotional register** — marketing gloss on neutral material (“a powerful, intuitive solution that empowers you to…”).
- **Reflexive both-sidesing** — “on one hand… on the other hand…” balance where the writer should just take a position.
- **Vague universals with no specifics** — claims with no names, numbers, or concrete detail; the absence of specifics is itself a tell.
- **Restating the prompt** before answering; over-explaining the obvious.
- **False precision** — confident, invented-looking statistics.

## Reporting format

    | Tell | Location | Why it reads as AI | Suggested revision |
    |------|----------|--------------------|--------------------|
    | "it's not just a library, it's a platform" | README.md:12 | negation-reversal antithesis | "It's a platform, not just a library." (or cut) |
    | em-dash ×5 in one paragraph | intro.md:4–9 | em-dash used as default connector | split into sentences; keep one |

Then a density verdict, e.g.: *“Pervasive — antithesis + triads in most paragraphs; reads strongly AI. Recommend a rewrite pass,”* vs. *“One stray ‘delve’; otherwise clean.”*

## Relationship to other skills

- **`simplify` / `tidy`** — the code-side analogues (cut dead code / cruft); this skill is the prose-side analogue (cut filler / reflexes).
- **`grade-work`** — when reviewing a deliverable, fold an AI-tells pass into the quality check.
- **`memorize` / `ums`** — if a new recurring tell surfaces, add it here and note it; keep the catalog living.
- **`find-overlap`** — the sibling read-only scanner: this skill scans prose for AI tells; `find-overlap` scans a corpus for duplicated/redundant content. Same detect-and-report posture, different signal.
- **`check-info-quality` / `ciq`** — another sibling scanner: this skill checks *how* text is written; `ciq` checks *what* it claims (stale, irrelevant, or misleading/out-of-context content). Run both over the same target.
- **`fact-check-prose`** — the accuracy-side sibling: this skill flags prose that *reads* as machine-generated; `fact-check-prose` checks whether prose claims and reasoning are actually *true*. Run both on a review pass.

## Anti-patterns

- **Don’t** treat any single tell as proof of AI authorship — it’s a heuristic; weigh clustering, not isolated hits.
- **Don’t** robotically purge correct words (`delve`, `robust`) or correct em-dashes when they’re well-used in context.
- **Don’t** rewrite until the text is flat and voiceless — de-slopping removes filler, it doesn’t sand off a real human style.
- **Don’t** flag code, identifiers, or quoted source material as prose tells.
- **Don’t** skip the self-check on my own draft, then ship prose full of the very tells this skill exists to catch.

Back to top
