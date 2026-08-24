# Verify a lever actually controls the observed behaviour before building the change

- **When asked to turn something off, confirm the mechanism you are about to
  disable is the one producing what the user actually saw --- before
  implementing, not after merging.**
  The check is usually seconds: grep the workflows for the vendor name, and look
  for that bot's own comments or check runs on recent pull requests.
  Running it afterwards is worth a fraction of running it first, and the
  difference is in how the finding can be delivered.
  The work is already merged, so it lands as a caveat on a change the user now
  has to re-evaluate, rather than as a question they could have settled in one
  reply before any code was written.
  When the check comes back empty, say so and ask which surface they meant
  instead of shipping against the only lever you happened to find.
  This is `shared/workflow/challenge-the-assignment.md` applied to a disable
  request: the load-bearing premise is that the lever you found is the one that
  was running, and it is cheap to falsify.
  - **Do:** run the vendor grep and the recent-PR bot scan before writing the
    config, and report what each one returned.
  - **Do:** treat an empty result as a question about which surface was meant.
  - **Don't:** implement against the first plausible lever and verify afterwards,
    since a post-merge finding is a caveat rather than a decision the user still
    gets to make.
  - **Don't:** read an absence of bot activity as evidence about *why* it is
    absent; that is a second claim, and it needs its own evidence.
  (Learned on `Lacaedemon/sparta`#1214, 2026-08-06: asked to disable Antigravity
  pull-request reviews, I configured `.gemini/config.yaml` --- the Gemini Code
  Assist **GitHub App** lever --- and merged it.
  Only afterwards did I establish that no workflow in that repo mentions Gemini or
  Antigravity, and that no such bot had posted a comment or a check run on any
  recent pull request.
  That absence does not say why it is absent.
  An app whose quota is exhausted and one that was never active on the repo leave
  exactly the same trace, so the lever I configured may govern nothing that was
  running, while reviews driven from the Antigravity dashboard or IDE are toggled
  there rather than in-repo.
  The change stands as a documented statement of intent; the point is that one
  grep and two API reads would have established all of this before any of it was
  written.
  Note that the answer is per-repo: `Morrison-Lab/ai-config` does have an
  Actions-based reviewer in `.github/workflows/antigravity-review.yml`, so the
  same request there would have had a different lever.)

