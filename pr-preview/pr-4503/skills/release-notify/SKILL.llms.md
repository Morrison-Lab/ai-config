# Release-Notify — Tag + Notify Revdeps of Breaking Changes

After merging a breaking change to a shared template/library repo, tag the release and file migration issues on every affected consumer repo.

## Procedure

1.  **Determine the version bump.** Breaking changes get a major version bump (v1 → v2, v2 → v3). If the repo uses semver with minor/patch, bump the major. Check existing tags with `git tag -l | sort -V`.

2.  **Create an annotated tag** on the merged main:

    ``` bash
    git checkout main && git pull origin main
    git tag -a vN -m "vN: <short description> (breaking change)

    <migration instructions>"
    git push origin vN   # PUSH
    ```

3.  **Identify affected consumer repos.** Use multiple strategies (don’t rely on any single one):

    - Check `REVDEPS.md` if the repo has one (advisory — not authoritative).

    - Search the group/org for repos referencing the old behavior:

      ``` bash
      # GitLab: check each project's CI config for the old pattern
      for pid in <project_ids>; do
        result=$(glab api "projects/$pid/repository/files/.gitlab-ci.yml/raw?ref=main" 2>&1)
        if echo "$result" | grep -q "<old_pattern>"; then
          echo "MATCH: $pid"
        fi
      done
      ```

    - For GitHub: use `gh search code` or the code search API.

4.  **File a migration issue on each affected repo.** Include:

    - What changed and why
    - The exact migration steps (ideally a diff)
    - What breaks if they don’t update
    - A link to the MR/PR and the new tag
    - Assign to the maintainer and label appropriately

5.  **Update REVDEPS.md** if any new consumers were discovered during the search (that weren’t already listed).

6.  **Report a summary** with clickable links:

    | Consumer      | Issue filed |
    |---------------|-------------|
    | [repo-a](url) | [\#N](url)  |
    | [repo-b](url) | [\#M](url)  |

## Key principles

- **REVDEPS.md is advisory.** It speeds up discovery but is never the sole source of truth. Always verify with a search.
- **Don’t skip notification** even for repos you think are inactive — let the maintainer decide.
- **One issue per consumer** — don’t batch notifications into a single issue on the template repo.
- **Include migration steps in the issue body** — don’t make the consumer go hunting for what to change.

## When to use

- After merging any breaking change to a shared template/library repo
- When bumping a major version
- When asked to “release”, “tag”, “notify consumers”, or “notify revdeps”

Back to top
