[hook: remind-encode-user-correction] The user's message reads as a correction,
or says they have had to repeat themselves ("{quote}").
The user should never have to say this twice,
in this session or any other project.
Fix the instance they pointed at, then, in this same turn:
1. Name the general rule behind the correction, read broadly:
   an example stands for its category, and "etc." is open-ended.
2. Check for a similar rule first and strengthen it rather than duplicating.
   Commit that rule to the repo that owns it and open the PR:
   Morrison-Lab/ai-config for anything that applies beyond one repo
   (AGENTS.md for a cross-agent rule,
   CLAUDE.md or a shared/ fragment for detail,
   a skill for a procedure),
   the current repo's own agent docs for a rule about that repo only.
   If ai-config is not in this session, attach or clone it first.
   Do this even when the rule is "obvious":
   that it had to be said is the evidence it was not encoded.
3. If the miss is mechanically detectable, add a hook for it in the same PR.
4. Project or host memory may get a copy too, but never instead:
   no other project reads it.
A "why didn't you ...?" question gets a forensic analysis, not a guess:
trace from the transcript, tool results, files and standing rules
what you did and which rule, reading or missing check led there,
and answer with that cause.
If it was your mistake, fix the instance and prevent recurrence
(rule plus hook or check) in the same turn, without asking whether to start.
The same holds in a project thread and in a PR review comment (Ezra, 2026-11-24).
If the matched words are not a correction of you
(quoted text, a remark about someone else), ignore this reminder.
See AGENTS.md "Treat user profanity and frustration as urgent defect signals"
and CLAUDE.md "Encoding reusable feedback into ai-config".
