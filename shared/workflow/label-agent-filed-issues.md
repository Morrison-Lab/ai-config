# Labelling an agent-filed issue: mechanics

The rule lives in [`issue-first`](issue-first.md)'s "Label an agent-filed issue with its authorship and its model" section.
This fragment carries the mechanics.
It is linked rather than `@`-imported, because `issue-first.md` is imported into `CLAUDE.md` wholesale and the always-loaded pool is budgeted --- run `python3 scripts/check-context-closure.py` before moving anything back.

## Scope

The rule covers an issue an **agent wrote** and filed into a repo **we administrate**.
Two adjacent cases sit outside it.

A repo we do not administrate is governed by [`upstream-issues`](upstream-issues.md), which decides whether to file at all before any of this, and whose label taxonomy is not ours to extend --- so [`sup`](../../skills/sup/SKILL.md) files upstream without these labels.

An issue whose body is quoted human content, such as the migration [`migrate-discussion`](../../skills/migrate-discussion/SKILL.md) performs, already states its provenance in the body, so the disclosure gap these labels close is not open there.

An agent-created **discussion** body is neither covered nor exempt: `CREATE_DISCUSSION` in [`tool-mappings`](../../tool-mappings.md) carries no disclosure note where its `COMMENT_DISCUSSION` neighbour does, and [`choose-issue-or-discussion`](choose-issue-or-discussion.md) routes real work to that surface.
It is out of scope here only because the rule was written for issues, not because the gap is closed.

## Which model identifier

Use the exact model identifier the harness reports, normalized --- not a display or marketing name, and not the display name a `Co-Authored-By` trailer carries, which is a separate convention.
Claude Code states the exact id in the session's own system prompt;
a remote session can also read it from `get_session`'s `session_context.model`.

Normalize before forming the label, because the reported id is not stable per model.
Strip a bracketed context-window suffix, and resolve an alias to the id it aliases: a session reporting `<model-id>[1m]` labels as `model:<model-id>`.
`get_session`'s own documentation says `configured_model` "may be an alias or carry a context-window suffix, so normalize before comparing", which is the same normalization.
Skipping it splits one model across two or three labels, and `gh issue list --state all --label "model:<model-id>"` then silently misses the issues filed under the other spellings --- which is the sweep this label exists for.

## The `gh` path

```sh
gh issue create --title "..." --body-file <file> \
  --label ai-authored --label "model:<model-id>"   # CREATE_ISSUE
```

`gh issue create --label` rejects a label that does not exist, which is the useful failure: it says to create the label rather than filing an unlabelled issue.
[`defer-issue`](../../skills/defer-issue/SKILL.md) already says not to fabricate labels for that reason.

## The `glab` path

`glab` takes one comma-separated `--label`, not a repeated flag:

```sh
glab issue create --title "..." --description "..." \
  --label "ai-authored,model:<model-id>"
```

Whether `glab` rejects an unknown label or creates it is not established here, so create the pair on GitLab first rather than relying on either behaviour.

## The MCP path

Filing is `CREATE_ISSUE` in [`tool-mappings`](../../tool-mappings.md): `mcp__github__issue_write` with `method: create` and `labels: ["ai-authored", "model:<model-id>"]`.
That is the only filing path in a remote session, where `gh` is not on `PATH`.

It **silently creates** an unknown label name instead of rejecting it, so a mistyped model id there produces a second near-identical label that no query will ever match.
Read the label back off the created issue rather than trusting the call's success.

The replacement hazard `LABEL_ISSUE` records belongs to a **later** edit rather than to filing.
`method: update` replaces the whole label set, so an already-filed issue relabelled that way needs the union of its current labels and the new ones.
A freshly created issue has no prior set, so nothing can be dropped at filing time.

## Creating the labels

Neither label is guaranteed to exist.
Checked against `Morrison-Lab/ai-config` on 2026-09-03, `ai-authored` returned `label 'ai-authored' not found`, so create the pair once per repo rather than assuming they are there:

```sh
gh label create ai-authored --description "Filed by an AI agent" --color EDEDED
gh label create "model:<model-id>" --description "Filed by that model" --color EDEDED
```

`GET_LABEL` in [`tool-mappings`](../../tool-mappings.md) records that **no MCP tool creates or updates a label**, so a remote session cannot run the block above at all.
Two paths remain there: `gh api repos/<owner>/<repo>/labels` from a workflow, or the MCP silent-create described above --- the one place that behaviour is useful rather than hazardous, at the cost that the label's spelling is then whatever you typed.
On GitLab the equivalent is `glab label create --name "..." --description "..." --color "..."`.

## A repo where you cannot create the labels still gets the issue

The issue is the durable record and the label is metadata on it, so a missing label is never a reason to skip filing.
File it, then say in the same reply which label is missing and why, rather than dropping the label silently --- which is indistinguishable from an issue a human wrote.

## Sweeping

Both sweeps take `--state all`, for the reason [`issue-first`](issue-first.md)'s opening paragraph gives: a closed issue is exactly what an open-only listing cannot see, and a sweep that silently omits closed issues is worse than no sweep, because it returns results.

```sh
gh issue list --state all --label ai-authored
gh issue list --state all --label "model:<model-id>"
```

- **Do:** normalize the model id --- strip a context-window suffix, resolve an alias --- before forming the label.
- **Do:** create the pair once per repo, and read the label back when the MCP path created it silently.
- **Do:** pass `--state all` on both sweeps.
- **Don't:** use a display or marketing name, or the `Co-Authored-By` trailer's spelling, as the label value.
- **Don't:** carry the `LABEL_ISSUE` union warning onto a filing call --- a new issue has no prior label set to preserve.
- **Don't:** add these labels to an issue filed into a repo we do not administrate.
