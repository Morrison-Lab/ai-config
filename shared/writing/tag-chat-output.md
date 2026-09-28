# Tag chat output by category so long recaps stay scannable

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#tag-chat-output-by-category-so-long-recaps-stay-scannable) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

Recaps get long across many parallel tracks, so tag categories of output with a stable marker and let the eye jump straight to what needs the user's attention.
Terminal markdown can't force text color, so the emoji plus the `===` frame plus the bold label *is* the signal.
Readers skim past a question or a flag buried mid-paragraph; a marked, set-apart block is harder to miss.

Reserve a **`===` box** for the output a user is waiting on --- something they must respond to (a question, an offer, a blocker) or the headline answer they asked for --- and use a lighter **emoji-prefix** (bold label, no box) for informational categories they can skim.
Boxing everything defeats the purpose, so keep the box meaningful.

Boxed (a `===` line above and below the labeled block):

- ❓ **QUESTION** --- need the user's input.
  For a real either/or, prefer the AskUserQuestion picker over a boxed question.
  When a question is posed inline in chat prose rather than through a box, still set it apart --- its own paragraph (blank line before and after, since a bare newline collapses back into the surrounding paragraph), in bold.
- 💡 **OFFER** --- optional work I can do if they want it.
- 🛑 **BLOCKER** --- stopped; need their call.
- ✅ **ANSWER** --- the headline answer to a question they asked (put nuance below the box).
- 🧭 **RECOMMENDATION** --- the course of action I think they should take,
  when the decision is theirs.
  Distinct from the two categories it is most easily confused with:
  an ✅ **ANSWER** reports what is true,
  and a 💡 **OFFER** proposes work I would do.
  A recommendation is a judgment about what *they* should do,
  including about things I will not be doing ---
  which PR to merge first, which option to decline, whether to stop.
  Lead the box with the action and put the reasoning below it,
  so the box holds the call rather than the argument for it.
  It boxes because it feeds a decision they are waiting to make;
  an opinion nobody was waiting on is a 📊 **UPDATE** with a view in it,
  and stays unboxed.
  - **Do:** box the recommendation, lead with the action,
    keep the reasoning under the box.
  - **Don't:** bury it in a closing paragraph,
    or fold it into an ✅ **ANSWER** box
    so a factual claim and a judgment read as one thing.
- 🔀 **MERGE ORDER** --- several PRs are ready,
  and merging them in the wrong order would produce a wrong result.
  The one category labeled with a markdown **heading** (`### 🔀 MERGE ORDER`) rather than bold text,
  since a heading is the only "large font" lever a terminal has.
  List the PRs in the order to merge, each linked per [`link-forge-artifacts`](link-forge-artifacts.md),
  naming what each one's position depends on.
  The PR-side and draft-gating surfaces live in [`surface-merge-order`](../workflow/surface-merge-order.md).

Prefixed, no box (informational, frequent):

- 📊 **UPDATE** --- status or progress.
- ⚠️ **FLAG** --- non-blocking heads-up or risk.
- ✔️ **DONE** --- a completed action.
- 🟢 **ALL CLEAR** --- nothing needs the user right now;
  work continues in the background.
  The recap's standing sign-off.

Keep the markers stable so they become muscle memory.
The set-apart ❓ **QUESTION** format also gives the `prompt-me` / `prompt-me-all` skills a reliable signal to key off when they sweep the transcript for unanswered questions later.
The user may tune the emoji set; the full taxonomy and rationale live in `memories/preferences.md`.
