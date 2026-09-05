# A nested worktree inflates a whole-tree instrument, because the worktree lives INSIDE the repo

Split out of [`git-worktrees.md`](git-worktrees.md) (ai-config#694 pattern) at
the 1250-line gate.

[`git-worktrees.md`](git-worktrees.md)'s "A repo script run from a worktree
can measure the MAIN checkout" is the case where an instrument reads a
**different** tree than the one you stand in.
This is the mirror: the instrument reads **your** tree, correctly, plus a
second copy of the corpus nested inside it.
`isolation: "worktree"` on an `Agent` call places that worktree at
`<repo>/.claude/worktrees/agent-<id>`, so while the agent is live the
repository physically contains another branch's checkout of every file.

Whether an instrument notices depends on how it enumerates files.
Measured on `main` at `41d82611`, with and without one worktree present:

| instrument | no worktree | one worktree present |
| --- | --- | --- |
| `npx markdownlint-cli2` | `Linting: 512 files` | `Linting: 1207 files` |
| `scripts/check-links.py` | 503 files | 503 files |
| `scripts/check-context-closure.py` | 80 fragments | 80 fragments |
| `scripts/check-hook-catalog.py` | 18 / 20 | 18 / 20 |

Removing the worktree returned markdownlint to 512.

What decides exposure is **how an instrument enumerates**, and the shapes are
worth knowing because they predict which of your own tools is affected
without re-measuring each one.

Exactly one shape is exposed, which is why only one row moved:

- **An unrestricted recursive glob from the repo root.**
  `.markdownlint-cli2.jsonc` globs `**/*.md`, and its `ignores` list named
  generated output and dependencies rather than a nested checkout.

The other three rows are immune, and each for a different reason:

- **A named-directory glob** never reaches it.
  `check-links.py`'s `SCAN_GLOBS` lists `skills/**/*.md`, `memories/**/*.md`,
  and their siblings, so `.claude/` sits outside its search space.
- **A closure walk from named entry points** never reaches it either.
  `check-context-closure.py`'s `walk_closure` follows references outward
  from its roots, so a nested checkout is reachable only if something in the
  closure cites it, and nothing does.
- **A fixed-file read** has nothing to enumerate at all.
  `check-hook-catalog.py` opens `hooks/hooks.json` and `README.md` by path;
  it globs nothing.

One further immune shape is worth naming even though no row above uses it,
since much of `scripts/` is built on it: **a `git ls-files` enumeration**
cannot see a nested worktree, because its files are untracked in the parent
index.
`scripts/check-memory-file-size.py` is the example.

The config fix is tracked as
[#1511](https://github.com/Morrison-Lab/ai-config/issues/1511) and proposed
in [#1513](https://github.com/Morrison-Lab/ai-config/pull/1513), and is not
what this entry is about.
That PR's own `ignores` comment carries the breakdown of the 1207, the
worktree's markdown, the files its `.claude/skills` symlink pulls in, and
its `codex-skills/` escaping the root-anchored ignore, so read the count's
composition there rather than here.
The enumeration question outlives that fix, since any tool added later that
globs the repo root inherits the same exposure.

**Nothing in the output flags the change.**
`Summary: 0 issues in 0 files` is identical either way, so the inflation
lives entirely in the `Linting:` line, and a reader who pipes to `tail` to
shorten the output keeps the summary and drops exactly that line.
That is the same self-inflicted blind spot recorded in
[`git-worktrees.md`](git-worktrees.md)'s "A repo script run from a worktree
can measure the MAIN checkout", arriving through a different fault.

Note the failure direction is the opposite of
[`fail-fast`](../shared/principles/fail-fast.md)'s "A zero-shaped
summary can be sound, and the scope line is what decides it".
There a sound figure is wrongly retracted; here an inflated one is published
unremarked, and the same line separates the two cases.

So **run `git worktree list` before publishing a whole-tree figure**.
More than one row means the scan may have covered another branch's copy of
the corpus, so the figure describes a tree nobody asked about.
`git archive HEAD | tar -x` into a scratch directory settles it outright,
[`fail-fast`](../shared/principles/fail-fast.md) already prescribes that for
a drifted working tree, and an archive of `HEAD` carries no untracked nested
checkout either.

A second consequence is a hook rather than a figure.
A pre-commit hook running such a tool with `always_run: true` scans the
nested checkout too, so it can fail on a file from a branch you are not on,
in a commit that does not touch it.

- **Do:** run `git worktree list` before quoting a whole-tree count.
- **Do:** ask how an instrument enumerates, `git ls-files`, named
  directories, or a root glob, before assuming it is immune.
- **Don't:** read a stable `Summary:` line as evidence the scope was
  stable; the scope sits on the line above it.
- **Don't:** trust a whole-tree figure measured while a subagent was live,
  including one you published earlier in the same session.
