---
name: draft-in-ezras-voice
description: "Draft communications for Ezra in his own voice: announcements, emails, and comments sent under his name."
user-invocable: true
allowed-tools:
  - Read
  - Edit
  - Write
---

# draft-in-ezras-voice --- imitate Ezra's writing when drafting for him

Ezra's standing rule (2026-11-05, `cai:`): always imitate his writing style
when drafting communications for him.

## When this fires

Any draft that goes out as Ezra, or that he will send or post himself:

- Canvas announcements and course emails.
- Issue, PR, and review comments written in his voice.
- Messages to collaborators, students, or colleagues.

It does not apply to agent-voice text.
That covers status replies, agent-authored PR bodies,
and comments marked as posted by an agent.
Those keep the agent marker and follow [use-preferred-style](../use-preferred-style/SKILL.md).

## Procedure

1. Read [references/ezra-voice.md](references/ezra-voice.md) before drafting.
2. Draft with its traits, and apply [use-preferred-style](../use-preferred-style/SKILL.md)
   underneath (plain words, active voice, few dependent clauses).
3. Show the draft as a draft.
   Never send it for him without his go-ahead.
   A class announcement waits for his review and approval of its exact text (Ezra, 2026-10-27, [ai-config#4780](https://github.com/Morrison-Lab/ai-config/issues/4780)).
   `hooks/no-unapproved-announcement.py` refuses the post until his latest message approves it,
   and [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md#announcements-need-approval) looks for one posted without it.
   - **Do:** show the exact text in chat, wait for "post the announcement", then post that text unchanged.
   - **Don't:** post or edit an announcement on a coordinator's or another agent's say-so.
4. When Ezra edits a draft, record the change as a trait in the reference
   (a short, dated bullet), so the next draft starts closer to his voice.

## Sources the reference may use

- Only text Ezra wrote himself: his typed messages, directives, and commits.
- Never student emails, rosters, survey responses, or other FERPA data.
- Never agent-written text posted under his login (it carries the agent marker).
