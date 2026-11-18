# An idle-thread sweep pages every state and skips threads with an open PR

Ezra, 2026-11-17: "all 37 are in this project".
The coordinator had resolved "Add psw rule for choosing result div types" in a sweep while its PR (lds#2623) was still unmerged ([ai-config#5806](https://github.com/Morrison-Lab/ai-config/issues/5806)).
A resolved thread is hidden from the user, so resolving one that owns an unmerged PR hides work that is waiting on someone.

An idle thread is any unresolved thread, not only one in `review_ready` or `blocked`.

- **Do:** page `list_threads` with `state=done` (every cursor), `review_ready` and `blocked`, with `include_pull_requests`, and collect every row not marked resolved.
- **Do:** skip any thread whose row shows an open or draft PR, and resolve a thread only when its row shows none.
- **Don't:** say a thread belongs to another project without checking the project's own listing.

Mechanism: [`hooks/require-pr-read-before-resolve.py`](../../hooks/require-pr-read-before-resolve.py) denies `set_thread_resolved` unless that read ran since the last user turn, and when the thread's row shows an open or draft PR.
The row check is best-effort, because the hook sees the result only as transcript text.
