# Output-highlighting taxonomy

Split out of [`preferences.md`](preferences.md) at the 1250-line gate (ai-config#694 pattern).

Tag categories of chat output with a stable marker so long recaps stay scannable.
Recaps get long across many parallel tracks; the eye should find questions, offers, and flags instantly.
Terminal markdown can't force text color, so the emoji plus the `===` frame plus the bold label *is* the signal --- there's no other channel for it.

The core distinction: **box the output a user is waiting on --- a response they must give, or the headline answer they asked for --- and leave ongoing informational categories unboxed.** Every boxed category demands the user's attention: some ask for a response (a question, an offer, a blocker), one delivers the answer they were waiting on, one proposes the course of action to take, and one constrains an action they are about to take.
Stated without a count on purpose --- the previous wording said "the five boxed categories" and went stale the first time one was added.
If everything is boxed, the box stops meaning "look here," so keep it reserved.

- **Boxed** --- a `===` line directly above and below the labeled block:
  - ❓ **QUESTION** --- need the user's input.
    For a genuine either/or, prefer the AskUserQuestion picker over a boxed question.
  - 💡 **OFFER** --- optional work I can do if they want it.
  - 🛑 **BLOCKER** --- stopped; need their call.
  - ✅ **ANSWER** --- the headline answer to a question they asked; put nuance below the box.
  - 🧭 **RECOMMENDATION** --- the course of action I think they should take,
    when the decision is theirs.
    The boundary against the two categories it most resembles
    is what makes it a separate category rather than a flavour of either:
    an ✅ **ANSWER** reports what is true,
    a 💡 **OFFER** proposes work I would do,
    and a recommendation is a judgment about what *they* should do ---
    including about things I will not be doing,
    such as which PR to merge first, which option to decline, or whether to stop.
    Lead with the action and keep the reasoning below the box.
    A recommendation earns the box
    because it feeds a decision the user is waiting to make;
    an opinion nobody was waiting on is a 📊 **UPDATE** with a view in it,
    and stays unboxed.
  - 🔀 **MERGE ORDER** --- several PRs are ready,
    and merging them in the wrong order would produce a wrong result.
    Labeled with a markdown heading rather than bold text;
    see the "Why 🔀 MERGE ORDER works the way it does" section.
- **Prefixed, no box** --- informational and frequent, so a bold label with the emoji is enough:
  - 📊 **UPDATE** --- status or progress.
  - ⚠️ **FLAG** --- a non-blocking heads-up or risk.
  - ✔️ **DONE** --- a completed action.
  - 🟢 **ALL CLEAR** --- nothing needs the user right now; work continues in the background.
    The recap's standing sign-off --- the frequent "nothing needs you" message.

Keep the markers stable so they become muscle memory.
The user may tune the emoji set over time; the categories and the box-versus-prefix split are the durable part.
This is the fuller companion to the CLAUDE.md section on tagging chat output by category --- keep the two in sync if either changes.

## Why 🔀 MERGE ORDER works the way it does

CLAUDE.md's "Surface merge-order constraints" section carries the procedure ---
the three surfaces, the draft-gating caveats, and when the convention fires.
This is the reasoning behind those choices.

**Why a heading, when every other category uses a bold label.**
The taxonomy above notes terminal markdown can't force color,
so the emoji and the `===` frame are the whole signal.
A heading adds the one axis a terminal does still render: size.
Reserve it for this category alone;
a second heading-labeled category would spend the distinctness this one buys.

**Why a GitHub alert on the PR, not just a sentence in the body.**
The decision to merge happens on the PR page, not in chat,
often days after whatever chat message explained the ordering.
`> [!IMPORTANT]` renders with a colored bar and icon,
which is the native "look here" affordance GitHub gives and plain body prose does not.
This is the corpus's only sanctioned use of GitHub alert syntax,
and that scarcity is what keeps it legible --- don't spread it to ordinary PR bodies.

**Why draft-gating exists at all, given its costs.**
The first two surfaces are decorations: they work only if the human reads them.
Draft-gating instead makes the wrong action unavailable,
which is [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
applied to a human decision rather than to a verification step.
That is strictly stronger, which is exactly why it's reserved:
it suppresses a mistake at the cost of suppressing the PR's own review and auto-merge machinery.
