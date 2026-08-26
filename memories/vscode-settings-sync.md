# VS Code Settings Sync can silently revert a machine's configuration

Settings Sync replaces `settings.json` wholesale from another machine's copy.
Nothing announces it, no prompt appears, and the file simply holds different
values than it did.

Measured 2026-08-26 on macOS: 31 of 37 `oaicopilot.models` entries had
`context_length` flattened, undoing a fix made five days earlier.

## Two reads identify it, and neither is guessable

**The sync record's mtime.**
`~/Library/Application Support/Code/User/sync/settings/lastSyncsettings.json`
shares an mtime **to the second** with `settings.json` when sync performed the
write.
On Linux the path is `~/.config/Code/User/sync/settings/`.

**Line endings.**
A macOS VS Code write is LF.
The reverted file was CRLF on 635 of 639 lines, so it was authored on Windows
and arrived through sync.
This is the stronger signal of the two, because it names the *origin* rather
than only the mechanism.

## Two traps in reading the evidence

**The payload is an escaped JSON string.**
`.syncData.content` parses to `{"settings": "<json text>"}`, so a `grep` for a
setting name over the file returns **zero hits** for a setting that is present
throughout.
A false negative that reads as "the setting is absent".
Decode it in two steps before comparing.

**A correct inventory is not a correct configuration.**
The model *list* was right --- 37 entries, current ids, a recent cleanup
applied --- while every context value was wrong.
Checking the count confirmed the wrong property.

## Attribute the values before assuming corruption

The reverted values were a faithful, model-by-model application of a
**published table** in another repo, including its distinctive outliers.
That fingerprint identified a *document* as the source, and so the machine
that had followed it, rather than leaving the change unexplained.

When a config changes unexpectedly, check whether the new values match some
document verbatim.
A sibling machine following a written procedure is a commoner cause than
corruption, and it is the only one that tells you where to go fix it.

## Repair

Edit in place with a targeted substitution over each entry.
Preserve CRLF (`open(path, newline='')` in Python) and JSONC comments; a
`json.load`/`json.dump` round trip destroys both, and the resulting whole-file
diff is unreviewable.
Verify by diffing against a pre-edit backup and confirming every changed line
is one you intended.

- **Do:** compare the sync record's mtime and the file's line endings before
  diagnosing a config change as local corruption.
- **Do:** check whether reverted values reproduce a published table exactly.
- **Don't:** grep the sync payload for a setting name --- it is escaped JSON
  and the zero is false.
- **Don't:** read a correct item count as a correct configuration.

Companion of [`vscode-copilot-byok.md`](vscode-copilot-byok.md), which
documents the other BYOK route and was itself measured on the Windows machine
that is the likely origin of this sync write.
