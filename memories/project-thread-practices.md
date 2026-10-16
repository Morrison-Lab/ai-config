# Practices from the Machine Learning course project threads

Rules Ezra and the coordinator gave in the course project, 2026-10-12 to 2026-10-16, that are not already in [`claude-app-projects`](claude-app-projects.md) (link both PR and thread, broadcast to all threads, launch sessions yourself, check previews yourself, never merge over a wrong gate).

## File a follow-up when you notice it

Ezra asked "are those issues filed?" and "why not?"
(2026-10-13) after a thread closed with two actionable items listed as "open items for you" and no issue behind either (lds#818 and pds#128 were filed late).
A line in a reply is not tracked and no other session can find it.

- **Do:** file the issue in the owning repo in the same turn and link it in the sentence that mentions the follow-up.
- **Don't:** write "open item", "left to Ezra" or "unchecked" about something actionable, or close a thread, with no issue number beside it.
- **Do:** read the post-merge runs of every merged PR before saying a stopping point is clean.

## Paywalled or institution-only content goes through a VPN session

Rule (Ezra, 2026-10-12): try the UC Davis VPN or the WWU VPN to get the content.
One of his registered devices is on the Davis VPN, and a WWU VPN is available through his work Linux machine.
The AdamW, Adam and He et al. statements in lds#599 to #602 were first written from memory, and the fact-check (lds#628) found three that did not match the papers.

- **Do:** start a Remote Control session with `start_rc_session` on a `list_devices` folder that is on a VPN.
- **Do:** tell it to save downloads outside any git repo (such as `~/Downloads/<topic>/`) and to commit and push nothing.
- **Do:** ask for verbatim quotes with section and page, so the thread does the fact-check.
- **Do:** send follow-up briefs through `start_rc_session` again (it returns `running` and delivers them), and `stop_rc_session` when done.
- **Don't:** put paper text in any repo (copyright);
  a one-sentence quote in a PR is fine.
- The Linux machine did not appear in `list_devices` on 2026-10-12;
  if a task needs the WWU VPN, ask Ezra to connect it.
- The standing fetch route is in [`fetch-untrusted-files`](../shared/workflow/fetch-untrusted-files.md).

## Track a resource in every repo whose topic it covers

Ezra's rule (2026-10-13): track any resource relevant to any of our repos or projects, not only the course in hand (for example later Deep Learning or RL courses).
Before adding a course or channel link, check the directory CSV for the channel's row and extend it rather than adding a duplicate (lds#775, Pieter Abbeel's Berkeley playlists).
The general rule is [`track-useful-resources`](../shared/workflow/track-useful-resources.md).

## Delegation lanes

Delegate only to flat-rate subscriptions or free tiers;
never to pay-as-you-go API keys (Ezra, 2026-10-13).
This is recorded in [`delegation`](delegation.md) and [`manage-quota`](../shared/workflow/manage-quota.md) (ai-config#4491, #4495).

## ai-config's own context gate

CLAUDE.md and AGENTS.md sit at their size caps (100,000 characters total for the CLI gate with margin 5 on 2026-10-16, and the 32,768-byte Codex cap for AGENTS.md).
A new `## section` failed `validate` by 347 characters on the branch for ai-config#4569.
Put new rules in `shared/workflow/<name>.md` or a `memories/` file, fold at most a one-line pointer into an existing section, and run `python3 scripts/check-context-closure.py` before pushing.
A red main is a request for the fix, not a reason to wait on Ezra (2026-10-16;
see [`red-main`](../shared/workflow/red-main.md)).
