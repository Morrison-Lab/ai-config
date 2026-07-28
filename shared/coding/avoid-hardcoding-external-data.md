Avoid hard-coding data that already has a reliable external source of truth ---
a version number, a package list, a dependency's release date, a set of
downstream consumers, a schema, an enum's valid values. Read or generate it
from that source instead of copying a snapshot into the codebase:

- **Versions and pins.** Don't retype a dependency's version in prose or a
  second config file when a lockfile, `DESCRIPTION`, or manifest already
  states it --- reference that file, or generate the mention from it.
- **Generated lists.** A list of consumers, plugins, or registered items that
  the source system can enumerate (an API, a directory scan, a registry)
  should be produced by querying that system, not maintained by hand
  alongside it.
- **Cross-file duplication.** When the same fact must appear in two places
  (a usage example and a reference doc, a schema and its example), generate
  the second from the first, or have CI check they agree, rather than
  trusting two hand-edited copies to stay in sync.

## Prose enumerations count, and they are the ones that rot unnoticed

The "generated lists" bullet reads as being about code, and the rule is
easiest to break in a sentence.
An enumeration written into documentation --- "the rules below (A, B, C,
...)" --- is a hand-maintained copy of a directory listing, and it has no
generator, no test, and no linter behind it.
Nothing fails when the directory grows; the sentence simply becomes wrong
and stays wrong, while still reading as authoritative.

When a prose list mirrors something the filesystem or an API already
enumerates, prefer a pointer to the source over the list: "every fragment
under `shared/coding/`" cannot drift, while a parenthetical naming seven of
them silently can.
Keep an explicit list only where the *selection* is the point --- a curated
subset, an ordering that matters --- and then say that it is a selection, so
a reader knows not to trust it as complete.

**Fixing a drifted list by refreshing it only resets the clock.**
The list will drift again on the next addition, by exactly the same
mechanism.
Replace it with the pointer instead, and treat "this needs updating again"
as the signal that it should not have been a list.
(ai-config#774, 2026-07-28: `CLAUDE.md`'s KISS section enumerated the
coding rules beneath it and had reached 7 of the 13 files then in
`shared/coding/`, having silently missed six additions.
The PR was adding four more.
Refreshing the parenthetical to 17 entries would have been wrong again
within weeks, so it became "every fragment under `shared/coding/`, indexed
by the principle it serves in the catalog above".)

This is conditioned on the external source being **reliably available** ---
don't add a network fetch or a fragile dependency where a static value would
do. A constant that has no external owner (a magic number intrinsic to the
algorithm, a default chosen by this project) is not "hard-coded data" in this
sense --- it is just a value. The target is duplicated *ownership* of a fact:
if updating the external source should have updated this value too, and
didn't, that is the bug this guidance prevents.
