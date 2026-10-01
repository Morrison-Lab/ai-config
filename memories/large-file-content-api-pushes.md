# Large-file content-API pushes without a local checkout

**When no local git push path exists at all (a cloud/remote session with no checkout, and a permission classifier has already denied git-based credential workarounds for the branch), a large multi-chunk `create_or_update_file` restore is the wrong tool, not a harder version of the right one.**
Reconstructing a large file (~180KB+) across several `Read`/chat-context chunks and then retyping it into a single `content` parameter compounds two independent failure modes: a context-compaction summary between turns can silently replace the real content with a plausible-sounding placeholder or a truncated "continuation omitted" note, and the tool call's own output-size limit can cut the `content` parameter off mid-generation --- both land as a successful-looking push that actually ships broken content, repeatable across several segments before anyone notices.
The fix is not a bigger or more careful single-shot push: route the edit to a session with a real local checkout instead (a Remote Control session on a machine with git access), where `git diff`/`git hash-object` give byte-for-byte verification with no retyping step for drift to hide in.

**Guard every whole-file content-API write by comparing against the CURRENT live remote size, not just the intended source's size.**
The existing `content.size`-after-push check (see [`github-mcp-tools.md`](github-mcp-tools.md)) catches content that shipped wrong relative to what you meant to send;
it does not catch a write that is internally consistent but still far smaller than what is already on the branch --- which is exactly what a partial restore or a stale/truncated reconstruction produces.
Before any `create_or_update_file`/`push_files` call that replaces an existing file's entire content, fetch (or recall from the same turn) the file's current live size and refuse the write --- or flag it loudly for confirmation --- if the new content is substantially smaller, then re-fetch and compare after the push completes.
This is mechanizable (a pre-write size-shrink check);
file a hook/tooling issue for it rather than hand-checking every time.

**Report self-inflicted breakage the moment it's noticed, in one line, even mid-repair** --- don't let a multi-segment repair attempt run silently for hours before the first status update.
A compaction summary written mid-incident is a claim about what you did, not a verified fact (see the context-summary-premise rule elsewhere in this corpus);
re-verify the actual live artifact before trusting or acting on that summary's account of the damage, rather than compounding a wrong premise across further pushes.

(Morrison-Lab/ai-config#4134, 2026-09-30/10-01: a session truncated `memories/preferences.md` while attempting a "restore" of content it had itself already damaged, then carried a false "still corrupted" premise across several compaction cycles --- each segment re-attempting a full-file reconstruction from increasingly unreliable context rather than fetching the live file.
The file was eventually fixed by a separate session with real git tooling before the affected session ever re-checked the live branch;
once it did, the "corruption" had already been resolved for some time.)
