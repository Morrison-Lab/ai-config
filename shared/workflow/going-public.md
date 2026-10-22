# Going public

Making a repository public is hard to undo: the contents can be cached and indexed even if the repository is later made private.
Follow this order, and change visibility last.

1. **Never flip the old repository.**
   Its history keeps every old value.
   Export a history-free copy into a new repository, and rename the old one if the names collide.
2. **Export with a script, then diff it.**
   Run `python3 scripts/check_public_export.py SOURCE EXPORT` (`scripts/check_public_export.py`).
   It fails if any tracked file was dropped from the export, such as a folder the source `.gitignore` excluded, or if the export holds a file the source does not.
3. **Scan for internal names, not only hosts and tokens.**
   The same script searches for `ucdavis/`, UCDH, VPN, BAA, project IDs, runbooks, private mirrors and private repository names, as well as tokens and SSN-like strings.
   Add the project's own names with `--deny-file`.
   Read every hit: a hit is removed or justified in the review, never ignored.
4. **Read the whole export.**
   Open each `CLAUDE.md`, `AGENTS.md`, README and `docs/` file in full.
   A pattern scan does not catch a section that is internal as a whole, such as a mirror or runbook section.
5. **Pass a separate-agent review of the exported tree before visibility changes.**
   The reviewer gets the export, not the source, and not your conclusion.
   Create the new repository **private**, push the single commit, review it there, and make it public only after the review is clean.
6. **Get the owner's typed go on the exact tree.**
   Show the file list and the commit SHA.
   Copyright holder, contributor credits and the upstream's owner are decided before the go.

Incident, 2026-10-22 (`gla` and `glr`): the scan covered hosts and tokens only, the export dropped 16 tracked files unnoticed, and the repositories were created public in one step.
A review after the flip found the project IDs, a runbook pointer, a mirror section and BAA wording;
the repositories were public for a few minutes and were set back to private.
