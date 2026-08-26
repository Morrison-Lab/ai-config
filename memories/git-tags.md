# Git tags

## Git tags (force-move / slide)
- To move a tag to a new commit: `git tag -d <tag> && git tag <tag> <target> && git push origin :refs/tags/<tag> && git push origin <tag>`
- Can't use `git push --force origin <tag>` on some GitLab instances (protected tags). The delete+recreate pattern always works.
- `git fetch --tags` silently refuses to update a local tag that already exists if the remote moved it. Use `git fetch --tags --force` to get the latest remote tag positions. Without `--force`, you'll see stale local tags and draw wrong conclusions about what the tag includes.

## Resolving a tag to a COMMIT sha (e.g. to SHA-pin a GitHub Action)

- **`git ls-remote --refs` is the wrong tool for this, and fails silently.**
  The `--refs` flag filters out *peeled* (`^{}`) entries.
  For a **lightweight** tag that is harmless --- the one line printed is the
  commit.
  For an **annotated** tag, the only line left is the **tag object's** sha,
  and nothing in the output says so.
  Pin that and GitHub Actions rejects it (`uses:` needs a commit), or worse,
  a tool silently resolves something you did not intend.
- Ask for **both exact refspecs**, and take the `^{}` line when there is one:
  ```bash
  git ls-remote https://github.com/<owner>/<repo> 'refs/tags/<tag>' 'refs/tags/<tag>^{}'
  # lightweight -> one line:  <commit-sha>  refs/tags/<tag>
  # annotated   -> two lines: <tag-obj-sha> refs/tags/<tag>
  #                           <commit-sha>  refs/tags/<tag>^{}   <- the one you want
  ```
  Don't reach for a `'refs/tags/<tag>*'` glob instead: `*` matches any suffix,
  so looking up `v0.0.1` in a repo that also has `v0.0.10`--`v0.0.18` returns
  nine unrelated tags and the two-line rule above stops meaning anything.
  The exact pair has no such failure mode --- a tag name and its own peeled
  form are the only two refs it can ever match.
- Real demonstration of the gap, on `git/git`'s annotated `v2.9.5`:
  ```
  $ git ls-remote https://github.com/git/git 'refs/tags/v2.9.5' 'refs/tags/v2.9.5^{}'
  dcba104ffdcf2f27bc5058d8321e7a6c2fe8f27e  refs/tags/v2.9.5
  4d4165b80d6b91a255e2847583bd4df98b5d54e1  refs/tags/v2.9.5^{}

  $ git ls-remote --refs https://github.com/git/git 'refs/tags/v2.9.5'
  dcba104ffdcf2f27bc5058d8321e7a6c2fe8f27e  refs/tags/v2.9.5
  ```
  `--refs` returns `dcba104` --- the **tag object** --- as its only line, with
  nothing marking it as such.
  The commit is `4d4165b`.
- **Don't infer the object type from the ref listing --- ask git.** Fetch the
  object into a throwaway repo and check it directly, which works even when
  `gh` is absent and `api.github.com` is blocked by a sandbox proxy:
  ```bash
  cd "$(mktemp -d)" && git init -q .
  git remote add o https://github.com/<owner>/<repo>
  git fetch -q --depth 1 o <sha>
  git cat-file -t <sha>          # want: commit   (a `tag` here means you peeled wrong)
  ```
- **The commit sha is only half of a pin --- the trailing version comment is a
  claim too, and the tag you looked up does not tell you what to write.**
  Pinning `actions/checkout@v4` and commenting `# v4` restates the input and
  tells a reader nothing.
  The comment earns its place by naming the release the pin actually sits on,
  which means finding every tag that points at the same commit:
  ```bash
  git ls-remote --tags https://github.com/<owner>/<repo> |
    awk -v s="<commit-sha>" '$1==s {sub(/\^[{][}]$/,"",$2); print $2}'
  ```
  The major tag, any minor alias, and the exact release all come back together,
  so the most specific one is visible rather than guessed at.
  Two details in that one-liner, both load-bearing.
  The `sub()` is needed because an **annotated** tag's line matching the commit
  is the peeled one, so `$2` arrives as `refs/tags/v2.9.5^{}` and reading the
  version straight off it writes a comment with a `^{}` glued to the end.
  And the suffix has to be matched as `\^[{][}]` rather than `\^{}`: mawk,
  which is `awk` on Debian and Ubuntu, parses a bare `{}` as an interval
  expression and dies with `regular expression compile failed (bad interval
  expression)` --- bracketing each brace makes it a literal in every awk.
  Guessing is the failure worth naming: a version comment is a factual claim
  sitting next to an opaque sha, so a wrong one is both undetectable at a
  glance and exactly what a later reader will trust.
  (d-morrison/altdoc#65, 2026-07-26: `quarto-dev/quarto-actions@v2` resolved to
  a commit carrying `v2`, `v2.2`, and `v2.2.0` --- only `# v2.2.0` was worth
  writing, and no amount of reasoning about the `@v2` in the workflow would
  have produced it.)
- This is an [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
  case: two commands decide it exactly, so never write a pin from recollection
  or from a ref listing you did not check the peel state of.
  (d-morrison/altdoc#57, 2026-07-25: SHA-pinning `etiennebacher/setup-jarl`.
  The tag was lightweight so `--refs` happened to give the right answer --- the
  trap only bites on annotated tags, which is exactly why it is worth checking
  every time rather than when something looks off.)
