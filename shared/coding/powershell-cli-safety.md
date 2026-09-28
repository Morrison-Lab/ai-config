# PowerShell CLI Command Safety

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#powershell-cli-command-safety) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

- **Never pass backtick-containing content in PowerShell double-quoted strings**: PowerShell treats `` ` `` as its escape character --- `` `b `` (Backspace, 0x08), `` `n ``, `` `t ``, `` `r ``, etc. --- so Markdown code spans and other backtick-containing text will be silently corrupted. Use single-quoted strings (`'...'` / `@'...'@`) for inline content, or write to a file and pass `--body-file` for multi-line PR descriptions.
- **Use body files for GitHub PR descriptions**: Write multi-line PR descriptions to a temp file and pass `--body-file <file>` to `gh pr create`/`gh pr edit`, or `gh api -F body=@<file>` for raw API calls. This avoids terminal string-escaping corruption for any content with backticks or other shell-special characters.
- **The hazard is not PowerShell-specific, and not limited to PR descriptions**: bash and zsh double-quoted strings run backtick spans as command substitution, so `gh pr comment`, `gh issue comment`, `gh api .../comments -f body="..."` / `.../replies -f body="..."`, and `git commit -m "..."` corrupt a backtick-carrying body exactly as `gh pr create --body "..."` does (a `` `ms.` `` code span runs `ms.` as a command and vanishes). Use `--body-file` / `-F body=@<file>` for comment and review-reply bodies too, in any shell, and `git commit -F <file>` for a commit message. See `memories/git.md`'s "`gh pr comment` / `gh api ... -f body=` run backtick spans too" and "`git commit -m "..."` runs backtick spans as shell commands" sections.
- **`git commit -m` is the surface that enumeration hides**, because every other entry posts to GitHub, so a commit message reads as a different kind of thing while the shell treats it identically.
  Measured 2026-08-17: an unescaped span inside a bash double-quoted string runs, so `` `echo SUBSTITUTED` `` became `SUBSTITUTED` in the resulting message.
  The same day a `-m` message quoting a merge command in backticks was refused by `hooks/no-unauthorized-merge.py`; those backticks were backslash-escaped, so what actually matched is unverified, and blocking is the safe direction rather than a defect.
  `git commit -F <file>` succeeded immediately either way, which is why the remedy needs no diagnosis first.
  - **Do:** `git commit -F` a backtick-carrying message from the session scratchpad, outside the worktree.
  - **Don't:** pass a backtick-carrying message through `git commit -m "..."`, or spend a round diagnosing a guard refusal when the file route costs one command.
