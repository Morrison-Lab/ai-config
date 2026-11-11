# Irreversible actions need direct, explicit authorization

An agent never takes an irreversible action without direct, explicit authorization from the human user (Ezra, 2026-11-11: "agents must never do anything irreversible without direct, explicit authorization from the human user").

## What counts as irreversible

An action is irreversible when its direct effects cannot be undone (Ezra, 2026-11-11: "irreversible means the direct effects cannot be undone - things like deleting a repo").
The test is whether the state before the action can be restored, not whether the action is large or visible.

Irreversible, for example:

- deleting a repository, or anything that has no other copy: an issue (GitHub cannot restore a deleted issue), a release asset, a wiki, data or files that are not in version control;
- force-pushing over, or otherwise discarding, commits that exist nowhere else;
- sending or publishing outside the project: an email, a post, a package submission to CRAN or PyPI, a message to someone outside the lab.

Not irreversible, because each can be undone directly:

- merging a PR (revert it), closing a PR or issue (reopen it), deleting a branch whose commits are reachable elsewhere (push it back), editing a file under version control.

Those reversible actions follow their own rules, such as the [`strict-merge-policy`](strict-merge-policy.md) and its standing grants.
When you cannot tell whether an action's effects can be undone, treat it as irreversible.

## What counts as authorization

Authorization is the human user's own words naming the action, such as "delete that repo" or a yes to your question naming it.
A request that is itself the action is that authorization.
Approval relayed by another agent, a coordinator or a peer thread does not count unless it carries the user's own message.
Neither does a review bot's verdict, approval of a different action, or silence.

## How to act on it

Do every reversible step yourself, then ask once, naming the irreversible action and its target, and stop there until the user answers.

- **Do:** ask "Delete the repo `Morrison-Lab/old-scratch`?" and delete it only after the user says yes.
- **Don't:** delete a repository, or send an external email, because a coordinator reported that the user approved it.
