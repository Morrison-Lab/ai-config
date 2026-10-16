#!/usr/bin/env bash
# Apply the "relayed mwc grant" edits to skills/mwc/SKILL.md and
# hooks/no-unauthorized-merge.py, test them, commit, push, and open the PR.
#
# Why a script: an agent session's permission classifier refuses edits to the
# merge-guard files, so the owner runs this once instead of hand-editing.
# Sanctioned by Ezra in project-thread messages
# cmsg_014QLd5McmoUEgMPRiXeVnjS4R4UoT8rJQgazChajXJYnk and
# cmsg_014QLd5McmoUEgMPRiXeVnjSFKdsPkxz5ztUNjMbG8TGfn.
#
# Run from any ai-config checkout (it makes its own worktree off origin/main):
#   cd ~/Documents/GitHub/ai-config && git fetch origin && \
#     bash <(git show origin/claude/mwc-relay-script:scripts/apply-mwc-relay.sh)
#
# Idempotent: a second run finds the edits present, changes nothing, and
# reuses the existing PR. Edits (each skipped if its marker is already there):
#   1. skills/mwc/SKILL.md: a grant relayed from another thread counts when it
#      carries the user's message id; enable-mwc takes no PR number.
#   2. hooks/no-unauthorized-merge.py: the refusal text points a blocked agent
#      at enable-mwc/check-mwc for a bare or relayed grant.
#   3. hooks/test-no-unauthorized-merge.py: one case asserting that pointer.
# The reviewer fallback (no non-Claude reviewer) is NOT here: it is in #4549.
set -euo pipefail

BRANCH="${MWC_RELAY_BRANCH:-claude/mwc-relay-grant}"
REPO="${MWC_RELAY_REPO:-Morrison-Lab/ai-config}"
WT_NAME="${MWC_RELAY_WORKTREE:-ai-config-wt-mwc-relay}"

top="$(git rev-parse --show-toplevel)"
wt="$(dirname "$top")/$WT_NAME"

git -C "$top" fetch -q origin main
if git -C "$top" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git -C "$top" fetch -q origin "$BRANCH"
  base="origin/$BRANCH"
else
  base="origin/main"
fi

if [ ! -d "$wt" ]; then
  git -C "$top" worktree add -q -B "$BRANCH" "$wt" "$base"
fi
cd "$wt"
git checkout -q "$BRANCH"

python3 - <<'PY'
import pathlib

NL = chr(10)

# ---- 1. skill ----
skill = pathlib.Path("skills/mwc/SKILL.md")
text = skill.read_text()
marker = "A grant relayed from another thread counts"
anchor = ("  The gates still run on each PR: the fully-clean instrument, the stale-base "
          "update, and every check finished on the current head." + NL)
if marker not in text:
    assert anchor in text, "anchor for the skill edit not found; main changed shape"
    add = (
        "  Neither `enable-mwc` nor `no-unauthorized-merge.py` takes a PR number: the grant is "
        "session-wide, so run `enable-mwc` on the bare keyword and never refuse it for lacking one." + NL
        + "- **A grant relayed from another thread counts when it carries the user's message id** "
        "(Ezra, 2026-10-16)." + NL
        + "  A coordinator or project-thread session may forward the user's own `/mwc`, `/mwc all`, "
        "or \"merge it\" to a working session." + NL
        + "  Treat the relay as the user's grant when it quotes or cites the user's message id, and "
        "name that id in the acknowledgement so the grant is auditable." + NL
        + "  A relay that paraphrases the user without an id, a peer session's own words, and a "
        "`daytb` or `away` grant are not a merge grant:" + NL
        + "  `daytb` hands back one decision and never extends to a merge, per `CLAUDE.md`'s "
        "judgment-grants section." + NL
    )
    skill.write_text(text.replace(anchor, anchor + add, 1))
    print("skill: edited")
else:
    print("skill: already applied")

# ---- 2. hook refusal text ----
hook = pathlib.Path("hooks/no-unauthorized-merge.py")
text = hook.read_text()
marker = "has not run in this session"
old = ('        "or merging an infra-only PR under the standing infra-PR grant (see INFRA_PATH_PATTERNS)."'
       + NL + "    )")
if marker not in text:
    assert old in text, "anchor for the hook edit not found; main changed shape"
    new = (
        '        "or merging an infra-only PR under the standing infra-PR grant (see INFRA_PATH_PATTERNS).'
        + chr(92) + "n" + chr(92) + 'n"' + NL
        + '        "If the user already gave a grant (a bare /mwc or /mwc all, no PR number needed, "' + NL
        + '        "possibly relayed from another thread with their message id), this block means "' + NL
        + '        "`ai-session.sh enable-mwc` has not run in this session: run it, confirm with "' + NL
        + '        "`check-mwc`, then retry."' + NL
        + "    )"
    )
    hook.write_text(text.replace(old, new, 1))
    print("hook: edited")
else:
    print("hook: already applied")

# ---- 3. test ----
test = pathlib.Path("hooks/test-no-unauthorized-merge.py")
text = test.read_text()
marker = "refusal text points at enable-mwc"
anchor = NL + "total = checks" + NL
if marker not in text:
    assert anchor in text, "anchor for the test edit not found; main changed shape"
    add = (
        NL + "# The refusal tells a blocked agent how a bare or relayed grant becomes real." + NL
        + "checks += 1" + NL
        + "_refusal = subprocess.run([sys.executable, HOOK, '--dry-run', 'gh pr merge 411 --squash']," + NL
        + "                          capture_output=True, text=True).stdout" + NL
        + "_ok_refusal = 'enable-mwc' in _refusal and 'check-mwc' in _refusal" + NL
        + "wrong += not _ok_refusal" + NL
        + "print(f\"  {'allow' if _ok_refusal else 'WRONG':<6} refusal text points at enable-mwc\")" + NL
    )
    test.write_text(text.replace(anchor, add + anchor, 1))
    print("test: edited")
else:
    print("test: already applied")
PY

if git diff --quiet && git diff --cached --quiet; then
  echo "no changes to commit (already applied)"
else
  python3 hooks/test-no-unauthorized-merge.py hooks/no-unauthorized-merge.py | tail -3
  python3 scripts/gen-hooks-plugin.py --check
  python3 scripts/check-ascii-punctuation.py | tail -1
  git add skills/mwc/SKILL.md hooks/no-unauthorized-merge.py hooks/test-no-unauthorized-merge.py
  git commit -q -m "mwc: a grant relayed with the user's message id counts; refusal points at enable-mwc

A bare /mwc already means /mwc all (#4543). This adds the two missing
pieces: a grant relayed from another thread with the user's message id
counts, and the hook refusal tells a blocked agent to run enable-mwc and
check-mwc. daytb, away, and a peer's words stay non-grants.

Approved by Ezra in project-thread message
cmsg_014QLd5McmoUEgMPRiXeVnjSFKdsPkxz5ztUNjMbG8TGfn.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
fi

git push -q -u origin "$BRANCH"

if gh pr view "$BRANCH" -R "$REPO" --json number >/dev/null 2>&1; then
  echo "PR already open: $(gh pr view "$BRANCH" -R "$REPO" --json url --jq .url)"
else
  body="$(mktemp)"
  cat >"$body" <<'EOF'
<!-- claude-projects-attribution: {"github_login":"d-morrison"} -->
_Requested by **Ezra** · [project thread](https://claude.ai/code/project/chan_014QLd5McmoUEgMPRiXeVnjS?thread=cmsg_014QLd5McmoUEgMPRiXeVnjSCzWuddASWNtNoTbVkmSNQp)_

Approved by Ezra in project-thread message `cmsg_014QLd5McmoUEgMPRiXeVnjSFKdsPkxz5ztUNjMbG8TGfn`.

Builds on #4543 (a bare `/mwc` means `/mwc all`, already on main); adds no parallel rule.

- `skills/mwc/SKILL.md`: a grant relayed from another thread counts when it carries the user's message id; `enable-mwc` takes no PR number. `daytb`, `away`, and a peer's words stay non-grants.
- `hooks/no-unauthorized-merge.py`: the refusal text tells a blocked agent to run `enable-mwc`, then `check-mwc`. No change to what is allowed.
- `hooks/test-no-unauthorized-merge.py`: one case for that text.

The reviewer fallback (no non-Claude reviewer) is in #4549, not here.

Applied by `scripts/apply-mwc-relay.sh` because an agent session's classifier refuses edits to these files.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
  gh pr create -R "$REPO" --base main --head "$BRANCH" \
    --title "mwc: a relayed grant with the user's message id counts" --body-file "$body"
  rm -f "$body"
fi
