# Claude Code transcript records

What is on disk under `~/.claude/projects/*.jsonl`, for anything that reads a transcript --- a hook via `transcript_path`, or a tool given `--root`.
Measured 2026-08-28 against 28 transcripts (8,825 records) on CLI 2.1.250.
Every count here is a reading, not a constant; re-derive rather than cite.

## `message.role == "user"` is a transport role, not an authorship claim

The same role carries harness continuations, stop-hook output, injected skill bodies, task notifications, tool results, compaction summaries, inter-agent coordinator messages, editor selections appended to the user's own prompt, another agent's `teammate-message`, and --- inside a subagent's transcript --- the dispatch brief the *assistant* wrote.

Nothing lexical separates the harness's text from the user's.
It arrives entity-escaped (`&lt;system-reminder&gt;` is what the harness writes when it neutralizes control tags), namespaced, split across blocks, or carrying no angle bracket at all.
Twelve successive attempts to classify authorship each certified harness- or assistant-authored text as the user's own words;
[`shared/writing/citations.md`](../shared/writing/citations.md) carries that argument and `scripts/check-user-quote.py` is the instrument that stopped trying.

## `origin.kind` classifies bridge ingress, and is usually absent

```bash
# the census, re-derivable
python3 - <<'PY'
import json, glob, collections
c = collections.Counter()
for f in glob.glob("/root/.claude/projects/**/*.jsonl", recursive=True):
    for line in open(f, encoding="utf-8", errors="replace"):
        try: r = json.loads(line)
        except Exception: continue
        m = r.get("message") or {}
        if m.get("role") != "user": continue
        o = r.get("origin")
        c[o.get("kind") if isinstance(o, dict) else "<absent>"] += 1
print(c)
PY
```

On the measured root: **2,270 of 2,339** user-role records carried no `origin` key at all, 2 were `human`, 64 `task-notification`, 3 `coordinator`.

So the label is absent from essentially every genuine turn, and treating its absence as a rejection discards the corpus.
Two further traps, both from the shipped binary rather than from a transcript:

- A sanitizer rewrites a user record's origin to `unclassified` when the kind is `human` or `auto-continuation`.
  **That is evidence about an in-memory pass, not about what reaches disk** --- `unclassified` occurred zero times in the census above.
  Citing it as a fact about the transcript is [`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md) in miniature.
- One of the CLI's own human tests reads, de-minified, `O0(o.origin) && o.verifiedSlackHumanTurn !== true` --- so a record can be stamped human and still be somebody else's message relayed from a channel.

## User prose lives in several record shapes, and one of them is the important one

Reading only `message` reports "no record contains it" over text the user typed.

| Shape | Where the prose is |
|---|---|
| `message` | `message.content`, as a string or a list of `text` blocks |
| `queue-operation` | `content` --- written at **enqueue** |
| `last-prompt` | `lastPrompt` --- a rolling pointer, so one prompt repeats across scores of records |
| `attachment` | `attachment.prompt` / `content` / `text`, and `content` is not always a string |
| **`tool_result`** | `content`, **not** `text` --- a block inside a `message` record |

A prompt exists as `queue-operation` before it exists as `message`;
measured across 75 enqueue-to-message pairs, the gap ran from 6 ms to 8m19s, so a session ending between them leaves the sentence only in the first shape.

**The `tool_result` case is the one to remember.**
There were 2,451 such blocks in the measured root, every one inside a `role: "user"` record, and an `AskUserQuestion` answer exists in **no other shape** --- so the records carrying the user's own *decisions* are exactly the ones a `text`-only reader cannot see.

Do not enumerate the shapes in a checker.
The list is the format author's, not yours, and it decays silently;
recurse into nested payloads instead, so a shape nested inside one already read is reached with no code change.

- **Do:** treat `origin.kind == "human"` as the strongest available signal and still only a signal.
- **Do:** walk nested payloads rather than naming the shapes you have seen.
- **Don't:** read `role: "user"` as "the user wrote this".
- **Don't:** cite the CLI's in-memory behaviour as a claim about the on-disk transcript without checking the transcript.
