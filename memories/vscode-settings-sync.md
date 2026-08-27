# VS Code Settings Sync can silently revert a machine's configuration

Settings Sync replaces `settings.json` wholesale from another machine's copy.
Nothing announces it, no prompt appears, and the file simply holds different
values than it did.
(Behaviour as measured in the 2026-08-26 incident below; re-verify against
the running VS Code before relying on it, per
`shared/writing/timestamp-volatile-claims.md`.)

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
`.syncData.content` parses to `{"settings": "<json text>"}`, so inside the
sync record every quote in the settings text is escaped (`\"`).
A grep for the *quoted* key --- `"oaicopilot.models"`, the form copied from a
JSON file --- returns **zero hits** for a setting that is present throughout,
a false negative that reads as "the setting is absent".
(A grep for the bare identifier `oaicopilot.models` does match, since JSON
string escaping leaves the identifier text intact; it is the quote characters
that differ.)
Decode the payload in two steps before comparing:
first parse the sync record and read `.syncData.content` (a JSON string),
then parse that string to get the `{"settings": ...}` object whose
`settings` value is the actual settings text.

**A correct inventory is not a correct configuration.**
The model *list* was right --- 37 entries, current ids, a recent cleanup
applied --- while 31 of the 37 context values were wrong.
Checking the count confirmed the wrong property.

## Attribute the values before assuming corruption

The reverted values were a faithful, model-by-model application of a
published table --- `models-template.jsonc` in ai-config's
`register-oaicopilot-models` skill --- including its distinctive outliers.
That fingerprint identified a *document* as the source, and so the machine
that had followed it, rather than leaving the change unexplained.

When a config changes unexpectedly, check whether the new values match some
document verbatim.
In this incident (one measured case, so a working heuristic rather than a
measured base rate), a sibling machine following a written procedure was the
cause rather than corruption --- and it is the only cause that tells you
where to go fix it.

## Repair

Pause Settings Sync (or close VS Code) on this machine first, so the repair
is not itself reverted or pushed over a sibling machine's copy mid-edit.
Copy the file aside as a pre-edit backup before touching it.
Then edit in place with a targeted substitution over each entry.
Preserve CRLF (`open(path, newline='')` in Python) and JSONC comments:
`json.load` refuses a comment-bearing JSONC file outright
(`JSONDecodeError`), and even on a comment-free file a `json.dump` rewrite
normalizes line endings and formatting, so the resulting whole-file diff is
unreviewable either way.
Verify by diffing against the pre-edit backup and confirming every changed
line is one you intended.

- **Do:** compare the sync record's mtime and the file's line endings before
  diagnosing a config change as local corruption.
- **Do:** check whether reverted values reproduce a published table exactly.
- **Don't:** grep the sync payload for a quoted setting key --- the payload
  is escaped JSON, so the quoted form's zero is false; decode first, or grep
  the bare identifier.
- **Don't:** read a correct item count as a correct configuration.

Companion of [`vscode-copilot-byok.md`](vscode-copilot-byok.md), which
documents the route split this incident rode: the OAICopilot extension (and
so an `oaicopilot.models` array) belongs to the work Windows machine, making
that machine the likely origin of this sync write.
(The personal Windows machine that `vscode-copilot-byok.md`'s own
measurements ran on does not have the extension installed, per that file.)
