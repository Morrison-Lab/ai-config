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
- **Put an inline list of three or more phrases in a bullet list**,
  introduced by a sentence ending in a colon, and number sequential steps.
  A short series of single words may stay inline.
  PSW's rule and examples are proposed in `Morrison-Lab/psw#60` ---
  once merged, they live at `chapters/conciseness.qmd`,
  "Put lists in bullet points".

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
