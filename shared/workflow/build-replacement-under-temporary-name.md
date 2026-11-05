When a repository's replacement is a history-free snapshot (a public release, a purge of history), build the new version under a *temporary name* and swap names only when it is approved.
Do not rename the live repository first.

## Why the old name stays put

The live repository's name is what its rendered site, its links and its open PRs hang off.
Renaming it first takes the published site's repository path (`org.github.io/<name>/`) away from the old content while the new repository is still unbuilt, and the new site has nothing to serve yet.

Reproduced on `Morrison-Lab/lds` (2026-11-04): the first cutover renamed `lds` to `lds-archive` and created a new `lds`.
The public site `morrison-lab.github.io/lds/` would have gone down until the new build finished, about 48 minutes, so the names were swapped back (`lds` kept the old content, the snapshot became `lds-new`).

## Steps

1. **Build the snapshot** from the current default branch with `git archive`, no `.git`, and a submodule kept as a gitlink at the same commit (`git update-index --add --cacheinfo 160000,<sha>,<path>`) with `.gitmodules` kept.
   Scan it before the first push: gitleaks over the tree (`--no-git`), a file-name scan for student records, and the repo's own forbidden-word grep.
2. **Create the new repository under a temporary name** (for example `<name>-new`), private, and push the snapshot as one commit.
   Confirm the tree hash equals the source commit's (`git rev-parse <sha>^{tree}`): the commit SHA differs by design, the tree must not.
3. **Re-create what a snapshot does not carry** on the new repository: Actions variables and secrets (read the names the workflows use, compare with the old repository's;
   org-level ones come free;
   never copy a secret value), and the repository ruleset (same rules, same bypass actors).
   Verify each required status-check context is emitted by a workflow in the snapshot.
4. **Rewrite references to old numbers.**
   A snapshot restarts issue and PR numbers, so `repo#N` and `/issues/N`, `/pull/N`, `/commit/`, `/actions/runs/` URLs in comments, docs and memory notes name items that stay behind.
   Point them at the archive name in a PR on the new repository;
   GitHub redirects a transferred issue's old URL, so the links keep working after issues move.
5. **Do not publish from the temporary name.**
   A publish run on `<name>-new` deploys a *public* Pages site (private repositories can have public Pages on an enterprise org) at the wrong URL, with absolute links pointing at the old site.
   Cancel a queued publish dispatch; run it after the swap.
6. **Review the new version privately**, then swap the names in one step (old to `<name>-archive`, new to `<name>`), run publish, check the site, then move issues.
   GitHub transfers issues but not PRs: reopen each PR by replaying its patch onto the new default branch.
   Transfer one issue first and check labels, assignees and links.

## Approvals

Each outward-facing step needs the owner's own yes in the chat that does the work: the rename, the repository creation, enabling Pages or publishing, and any visibility change.
A coordinator note that says the owner approved it is a claim, not the approval;
ask the owner to confirm the exact action.
A snapshot repository stays private until the owner gives a separate public go.
