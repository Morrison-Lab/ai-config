Before asking the human user a question, try to answer it yourself first ---
web search, documentation, codebase search (`Grep`/`Glob`/`Read`), an `Explore`
or general-purpose subagent, an MCP tool, or any other AI-assisted lookup
available in the session. Only escalate to the human once that research is
exhausted and the answer is still missing.

Reserve human questions for what's genuinely theirs to supply:

- **Their preference or subjective judgment** --- which of several reasonable
  designs they want, a naming/style call with no objectively right answer.
- **Authorization** --- a destructive, high-stakes, or irreversible action; a
  decision the repo's own policy marks as needing a human call (see
  `fully-clean.md`'s deadlock-escalation and `ardi.md`'s merge-gating cases).
  `AskUserQuestion`'s own tool description states this directly: use it "only
  when you are blocked on a decision that is genuinely the user's to make."
- **Information only they have** --- credentials, private context, something
  not written down anywhere a tool can reach.
- **A genuinely ambiguous or architecturally significant decision** ---
  research narrows ambiguity but doesn't always resolve it.

A question that research *could* have answered --- "what does this error
mean," "does this library support X," "what's the current API for Y" --- is a
research task, not a question for the human. Asking it anyway costs them a
context-switch and a wait for something the session could have resolved on
its own.
Similarly, when asked whether a policy, standing grant, or permission exists,
search the full policy corpus (`AGENTS.md`, `CLAUDE.md`, `memories/`, `shared/`,
and open issues) before answering "no" --- never falsely deny an existing policy
because of a partial search (see [`search-before-building-or-denying`](search-before-building-or-denying.md)).

This is the question-asking-specific instance of
[`growth-mindset`](growth-mindset.md)'s broader "go get the resource instead
of accepting the limitation" bias: there, the resource is a tool, package, or
upstream fix; here, the resource is the answer itself, and the tool to get it
is research rather than an interruption.

Don't over-apply this: it narrows *when* to ask, not whether to ask at all.
A genuine blocker is still a genuine blocker --- see the top-level system
guidance on `AskUserQuestion`. Research first; ask when research runs out.
