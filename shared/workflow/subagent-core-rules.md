# Core rules every subagent receives

`hooks/inject-subagent-rules.py` prints this file into every subagent's context at SubagentStart.
A dispatched agent otherwise starts with only its brief, so a rule the brief does not repeat is a rule it never saw ([ai-config#4698](https://github.com/Morrison-Lab/ai-config/issues/4698)).
Keep it under 4,000 characters: it is injected on every dispatch.

- Work from the brief and the files it names.
  The rules below apply even where the brief is silent.
- **Notes content (lds, mds, pds, sds, rme, psw):** one div per subfile, one defined term per `#def-` div, an example after each abstract definition, no forward references.
  Link every technical term at first use, and link prerequisites to mds, pds or sds instead of restating them.
  Use the semantic macros from `Morrison-Lab/macros`: no literal letters, no raw `\hat`, no bare `e^`.
  Split every multi-part exercise.
- **Never** push to `main`, force-push, merge a PR, or ask the user for hand work.
  Merges need the user's own typed word in the owning thread.
- **Small PRs:** every PR is as small and focused as it can be while completely solving its task: at most 10 files and 300 changed lines.
  Split a sweep into minimal batches, one PR per batch; `hooks/no-oversized-pr-push.py` denies a bigger push.
- **No hand work for the user:** no "type go" in a Remote Control session, no merge buttons, no PR numbers in a merge ask.
  A bare `mwc` covers every ready PR.
  Ask one question at a time.
  Retry a denied step once, and never route it through another session.
- **Record what you learn in a repo** (hook, check or `shared/` fragment), not only in project memory.
  Facts the user pastes go into a repo file in the same turn.
  See `shared/workflow/lab-operating-rules.md`.
- **Issue first:** search the tracker, file the issue, then open the PR.
  Keep content and infrastructure in separate PRs.
- **No scope creep:** ship the asked fix, and file anything adjacent as an issue.
- **FERPA:** never open or send student records (rosters, grades, submissions, Canvas exports) to any model.
- **Report faithfully:** say what you did, what you skipped, and what failed.
  A completion report must address every item in the brief.
- **Link** every PR, issue, file, session and thread you mention.
- **No empty promises:** do not write "from now on I will";
  make the change that enforces it.
