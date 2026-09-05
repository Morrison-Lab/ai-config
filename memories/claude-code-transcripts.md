# Claude Code transcript records

What is on disk under `~/.claude/projects/*.jsonl`, for anything that reads a transcript --- a hook via `transcript_path`, or a tool given `--root`.
Every count below comes from **one** reading, 2026-08-28T21:14:06Z, on CLI 2.1.250: 29 transcripts, 9,465 records, 2,770 of them user-role.
They are readings rather than constants --- the corpus grows while the measuring session appends --- so re-derive rather than cite.
Taking them at different moments is the mistake this entry was first written with: three figures from two epochs, all labelled "the measured root".

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

At the reading above: **2,675 of 2,770** user-role records carried no `origin` key at all, 2 were `human`, 90 `task-notification`, 3 `coordinator`.

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

**The `tool_result` case is the one to remember.**
There were **2,613** such blocks at the reading above, every one inside a `role: "user"` record, and an `AskUserQuestion` answer exists in **no other shape** --- so the records carrying the user's own *decisions* are exactly the ones a `text`-only reader cannot see.
This case has nothing to do with timing, and it is the strongest reason to read past `message`.

The `queue-operation` window is real, much narrower than it first looks, and getting it wrong is instructive.
A prompt is written at enqueue and becomes a `message` record at dequeue, so a session ending between the two leaves it only in the first shape.
Of 85 enqueue-to-message pairs at the reading above, **82 carry harness envelopes rather than user prose**;
the 3 that carry prose closed in 0.1, 0.2 and 0.4 seconds.
An earlier version of this entry quoted the range across all 85 --- up to 8m19s --- as the size of that window, which measured the harness's own traffic and presented it as the user's.
That is the transport-role conflation the section above forbids, committed while writing the section that forbids it.

Do not enumerate the shapes in a checker.
The list is the format author's, not yours, and it decays silently;
recurse into nested payloads instead, so a shape nested inside one already read is reached with no code change.

- **Do:** treat `origin.kind == "human"` as the strongest available signal and still only a signal.
- **Do:** walk nested payloads rather than naming the shapes you have seen.
- **Don't:** read `role: "user"` as "the user wrote this".
- **Don't:** cite the CLI's in-memory behaviour as a claim about the on-disk transcript without checking the transcript.

## After a compaction, file order and chronological order can disagree

A transcript is append-only,
so reading it front-to-back reads it in time order ---
which holds until a context compaction replays earlier records.
A replayed copy is appended at the point of the replay,
so an **older** result can sit **below** a newer one, carrying its original timestamp.
Measured 2026-09-03: record 6394 carried record 4306's identical timestamp,
sitting below a reviewer result recorded after both.

Anything keyed on "the last X in the transcript" is unsound for that reason,
and it fails silently ---
the reader parses every record correctly and simply holds the wrong one,
so there is no malformed input to notice.
`hooks/no-push-without-self-review.py` walks the file keeping the last verdict it parses,
and refused a push over a stale verdict for exactly this reason
([#3151](https://github.com/Morrison-Lab/ai-config/issues/3151)).

Two practical consequences.
Sort by each record's own timestamp rather than by position when the question is "most recent".
And when a position-keyed tool has already held the wrong record,
appending a fresher one is a remedy available to you:
a fresh review of the current head makes a newer record land last.
That remedy has a precondition, and it is the whole of what separates it from overwriting a verdict you dislike:
run the reader's own parser against the transcript first and print what it holds,
so the held record is shown to be a replayed one rather than a current refusal.

- **Do:** read a record's own timestamp when the question is which came last.
- **Do:** unblock a position-keyed reader by producing a fresh record,
  once its own parser has been run and shown to hold a replayed one,
  and when fixing the reader is not available in the moment.
- **Don't:** append a fresher record before establishing that the held one is stale --- a current refusal is a finding, not an ordering artifact.
- **Don't:** treat append-only as a guarantee of chronological order --- a compaction replays records carrying their original timestamps.
- **Don't:** key a tool you write on "the last X in the transcript".
