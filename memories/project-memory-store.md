# The project session memory store

A Claude Code **project** gives every session in it one shared, file-backed memory directory, surfaced through a memory-service index.
In the hosted harness it lives under `/tmp/claude/memory/team/<project>/`, one fact per Markdown file, with a `MEMORY.md` index beside them.

It is not this repository's `memories/` directory, and nothing in it is version-controlled --- which is why `CLAUDE.md`'s "Encoding reusable feedback into ai-config" section requires a reusable learning to land in a repo as well.
This file records how that store fails, because every one of its failure modes is silent.

## A write can report success and then not persist

Measured 2026-09-18 between 11:30 and 11:33 PDT on `merge-race-between-thread-sessions.md`.
Two sessions in one project edited that file minutes apart.
The second appended a section, the shell reported the write complete, and a re-read three minutes later showed the file with no trace of it.
The mirror case was measured the same day on `merging-from-a-thread-session.md`, losing the other session's write instead.

The directory is shared with no locking and no merge on write, so last writer wins and "last" is decided by the store rather than by the order the shells ran.
Nothing errors and no conflict is raised, so two sessions can each believe they recorded a lesson while only one of them did --- which is worse than an outright failure, because both then stop thinking about it.

It composes badly with a proactive-UMS habit, since several sessions bank learnings at the same checkpoints, into the same few files.

## A delete is lost the same way

Measured 2026-09-18 at 11:47 PDT, checking a peer session's report rather than accepting it.
The peer had reported deleting a duplicate memory and adding an index entry.
The index entry had landed and the delete had not, so the duplicate was still on disk fifteen minutes later.

A removal that silently fails leaves two entries for one lesson, which is exactly the outcome the removal existed to prevent.

## The index is a third surface, and it fails with no write failing at all

The same check found 15 of 22 files carrying no `MEMORY.md` link.
Nothing had failed --- the entries were simply never added --- so a write-race check cannot find this class, and neither can re-reading a file you just wrote.

The consequence is a coverage claim that is false without being a lie: a sweep that walks the index was covering under a third of the directory while reporting that it had swept.
Derive the population from a directory listing, per [`derive-dont-enumerate`](../shared/workflow/derive-dont-enumerate.md), and report the count rather than trusting it.

## Grep for the lesson, not the filename

A duplicate banked under a second name is invisible to both a filename check and a link check, and survives as two files saying one thing.
The measured pair was `widening-a-matcher-needs-a-negative-control` and `widening-an-evidence-recognizer-is-the-unsafe-direction`: one incident, two files, no string in common in their names.

## A peer's report of an action is not the action

Every case above was found by re-reading rather than by any tool reporting a problem, and two of them were found in a peer's work rather than in this session's own.
So read the file before repeating that a peer wrote, deleted, or indexed something, and say when you checked.

Reading first also protects the peer: before deleting a file they said was a duplicate, confirm the survivor actually carries what the deleted one said, including any clause they folded across.

- **Do:** re-read after writing and grep for a distinctive string from what you added, treating the tool's success as no evidence at all.
- **Do:** prefer a new file with a distinct name over appending to a file a peer is actively editing, since a new path cannot lose a race.
- **Do:** derive the file set from a listing rather than from the index.
- **Don't:** re-apply a lost write blindly --- read the surviving version first, since it often already carries the substance under different wording.
- **Don't:** delete a peer's file on their say-so, or repeat their report of an action as if it were the action.
