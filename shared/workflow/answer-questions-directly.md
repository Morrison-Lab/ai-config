# Answer a question in the first sentence of the reply

Ezra, 2026-11-25 00:46 PST ([#6129](https://github.com/Morrison-Lab/ai-config/issues/6129)): "cai: always answer my questions directly and immediately".

He had asked "why haven't you merged 2196?"
([gha#2196](https://github.com/Morrison-Lab/gha/pull/2196)).
The first reply was "Running the clean check on gha#2196 now, then merging it under gha's standing grant."
That reply says what happens next and never says why.
The answer needed no tool call at all: the thread had never looked at the PR, because another thread opened it.

- **Do:** open the reply to a question with the answer, in its first sentence.
  When the answer needs a lookup, still say first what you already know ("I hadn't looked at it"), then name the step.
- **Don't:** reply to a "why", "did you" or "have you" question with only a plan or status line ("Running X now, then Y").

A harness instruction to send a short first reply naming your first step does not override this.
Its own note says to just answer when one quick read gets you the answer, and an answer you already hold needs no read at all.

A polite request worded as a question ("can you push that?") is an instruction, so a reply that does it ("Pushing now.") answers it.

`hooks/no-status-line-answer-to-question.py` denies the first `post_message` after a user's question when the reply's first sentence is only a status or plan line.
`ALLOW_STATUS_FIRST_REPLY=1` overrides when a sentence that opens with a gerund really is the answer.
