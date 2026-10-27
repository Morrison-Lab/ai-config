# Argon reads through the Antigravity `agy` CLI

These scripts run a cross-harness adversarial review of a pull request with `agy` and post the verdict as a PR comment in the format `scripts/check-pr-fully-clean.py` reads.

- `argon.sh owner/repo PR [focus]` feeds the PR diff (first 24000 characters) to one model.
  It exits with an error and writes no verdict when `gh pr diff` fails or returns nothing.
  `gh pr diff` fails with HTTP 406 above 300 changed files, and an unchecked failure used to reach the model as an empty diff.
- `bigread.py owner/repo PR [focus]` reads a PR that `argon.sh` cannot, through the paginated files API, in parts of about 22000 characters, and joins the parts into one verdict.
  A part without a real verdict, a file without patch text, or a PR with no files is an error, not a pass.
- `rf.sh owner/repo PR [focus]` runs `argon.sh` on a model chain (Gemini Argon, Claude, GPT-OSS) and posts the first real read.
- `post.sh owner/repo PR` posts `out-<owner>_<repo>-<PR>.txt` as a structured comment: agent report header, `### Findings` when there are any, `VERDICT:`, and `Reviewed-Commit:` pinned to the head that was read.
  It skips merged and closed PRs, and refuses error text, a missing `HEAD:` line, a `gh` failure, a CLEAN verdict that lists notes, and a CLEAN verdict from a diff `argon.sh` had to truncate.
  Plans and a verdict that is not the last line are refused by `rf.sh`, which appends the instruction to end with a `VERDICT:` line;
  run `argon.sh` and `post.sh` by hand only with that instruction in the focus text.
  Run alone, `post.sh` posts what is in the out file.

Notes:
- The scripts write `out-*.txt`, `comment-*.md` and `*.truncated` next to themselves;
  the local `.gitignore` keeps them out of commits.
  One out file exists per PR, so do not run two reads of the same PR at once.
- `argon.sh` calls GNU `timeout`.
  Under Git Bash that is `/usr/bin/timeout`;
  if Windows `timeout.exe` comes first on `PATH`, `agy` never runs and `rf.sh` reports "no real review".
- Subscription models only; none of these scripts calls a pay-as-you-go API.

Run the tests with `python3 -m pytest scripts/agy-review`.
