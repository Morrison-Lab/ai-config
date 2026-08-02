# use-preferred-style — write the way the user prefers

Apply the user’s prose style to anything user-facing. The style is plain and direct. Say the point in a short sentence. Stack fewer clauses. Drop filler.

The authority is the user’s own guide, **Principles of Scientific Writing (PSW)**: https://d-morrison.github.io/psw/. PSW covers word choice, conciseness, and active voice. This skill operationalizes PSW and adds the user’s own rules on clause structure (limit subordinate clauses; join with coordinating conjunctions), which PSW does not cover. When in doubt, defer to PSW.

## When this fires

- The user asks to “use my style”, “apply my preferred style”, “rewrite in my voice”, “tighten this”, “plain-language this”, or invokes `/style`.
- You are drafting or revising any prose the user will read: PR/issue/commit bodies, docs, READMEs, code comments, release notes, emails, chat replies.
- Apply it by default to your own drafts, even when not asked. This is a standing preference, not just an on-demand command.

## The rules

The user’s clause-structure rules (1–4) sit on top of PSW’s word-choice and conciseness rules (5–6).

1.  **Limit dependent clauses.** A dependent (subordinate) clause cannot stand alone. It starts with a word like *because*, *although*, *which*, *while*, *since*, *when*, or *if*. One per sentence is plenty. Two or more stacked together is a rewrite signal. Break the sentence apart instead.

2.  **Cut low-content filler and jargon.** Delete words that add no information. Replace jargon with the plain word. See the swap table below.

3.  **Prefer simple declarative sentences.** State the fact. Put the subject first, then the verb, then the rest. Short beats clever.

4.  **Join independent clauses with coordinating conjunctions.** Two complete thoughts read better side by side than nested. Use *and*, *but*, *so*, *or*, *yet*, *nor*, *for*. Prefer “X is fast, but Y is correct” over “While X is fast, Y is correct.”

5.  **Prefer plain (Anglish) words over Latin-derived ones** (PSW, “Word choice”). Old-English-derived words decompose into parts a reader already knows. Latin roots must be memorized. So write *before*, not *prior to*; *needed*, not *necessary*; *use*, not *utilize*. This is a heuristic, not a purity rule — pick whatever word the reader grasps fastest.

6.  **Prefer active voice** (PSW, “Conciseness”). Name the actor, then the action. Prefer “The researchers ran the experiment” over “The experiment was run by the researchers.” Passive is fine when the actor is unknown or beside the point.

## Filler and jargon to cut or swap

| Cut / avoid                      | Use instead          |
|----------------------------------|----------------------|
| in order to                      | to                   |
| due to the fact that             | because              |
| at this point in time            | now                  |
| prior to                         | before               |
| in the event that                | if                   |
| necessary                        | needed               |
| has the ability to, is able to   | can                  |
| utilize, leverage                | use                  |
| facilitate                       | help, let            |
| make a decision                  | decide               |
| give consideration to            | consider             |
| a large number of, a number of   | many, some, N        |
| it is worth noting that          | (delete)             |
| it should be noted that          | (delete)             |
| needless to say                  | (delete)             |
| as a matter of fact              | (delete)             |
| basically, essentially, actually | (delete)             |
| very, really, quite, simply      | (delete)             |
| in terms of                      | (rephrase or delete) |
| with regard to                   | about                |

Treat the table as a starting set, not a closed list. Any word that carries no information is filler. Cut it. Most of these swaps come from PSW’s “Conciseness” and “Word choice” chapters.

## Procedure

1.  **Read the target prose.** A file, a diff, a draft, or text the user pasted.
2.  **Find the long sentences first.** A sentence over ~25 words usually hides a dependent clause you can split out. Split it.
3.  **Strip filler and swap for plain words.** Run the swap table over the text. Delete dead words. Prefer the Anglish word over the Latin one.
4.  **Flatten subordination.** Turn “Although A, B” into “A. But B.” or “A, but B.” Turn “which” relative clauses into a second sentence.
5.  **Switch passive to active** where the actor matters. Name the actor first.
6.  **Keep the meaning exact.** Style edits must not change facts, scope, hedges the user meant, or technical precision. When a hedge is load-bearing, keep it. Plainness is the goal, not false confidence.
7.  **Read it back.** Each sentence should make one point. The data should flow top to bottom.

## Before / after

> **Before:** It is worth noting that, due to the fact that the cache was not being invalidated when the user updated their profile, which caused stale data to be served, we decided to utilize a new eviction strategy in order to resolve the issue.

> **After:** The cache was not invalidated on profile update. So it served stale data. We switched to a new eviction strategy to fix it.

The “after” is three sentences. Each makes one point. No filler, no `utilize`, no stacked `which`/`due to the fact that` clauses.

## When to keep the nesting

This is a default, not an absolute rule. Keep a dependent clause when splitting it would read worse or lose a real logical link. Keep a technical term when it is the precise word and the plain swap would be wrong. Readability wins, not minimalism for its own sake. (Mirrors the “avoid nesting, but not blindly” stance in the coding-style rule.)

## Further reading — PSW

The user’s guide, **Principles of Scientific Writing**, is the source of record. Pull the latest rules from it, not from this summary:

- Guide home: https://d-morrison.github.io/psw/
- [Word choice](https://d-morrison.github.io/psw/chapters/word-choice.html) — Anglish over Latin.
- [Conciseness](https://d-morrison.github.io/psw/chapters/conciseness.html) — cut redundancy; active voice; the swap list.
- [Defining terms clearly](https://d-morrison.github.io/psw/chapters/defining-terms.html)
- [Paper organization](https://d-morrison.github.io/psw/chapters/paper-organization.html)

PSW is a work in progress. When it and this skill disagree, PSW wins — and flag the drift so this skill gets updated.

## Relationship to other skills

- **`find-ai-tells`** (issue \#49, in progress) — the detector counterpart. It *scans* finished text for AI-authorship tells. This skill *prescribes* how to write up front. Run `find-ai-tells` after; run `use-preferred-style` during.
- **`simplify` / `tidy`** — the same “cut what adds no value” instinct, applied to code instead of prose.
- **`memorize` / `remember`** — for a one-off wording preference, write a memory instead of editing this skill.

## Anti-patterns

- ❌ Changing the meaning, scope, or technical precision while “tightening.”
- ❌ Dropping a hedge the user meant to keep (turning honest uncertainty into false confidence).
- ❌ Chopping every sentence to staccato fragments — vary length; aim for clear, not robotic.
- ❌ Applying it to code identifiers or quoted material that must stay verbatim.

Back to top
