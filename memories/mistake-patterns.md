# Recurring Mistake Patterns & Fixes

## Pattern 1: Assumption Over Verification
**Mistake**: Assume a tool call succeeded without checking output or verifying result
**Example**: Assumed `gh pr create` worked; never verified PR actually existed
**Fix**: Always verify critical operations complete successfully:
- Check tool output for errors
- Verify the artifact exists (PR, commit, file, etc.)
- Never assume success; always confirm

## Pattern 2: Passivity on Standing Rules
**Mistake**: Ask permission for things I already have standing instructions to do
**Example**: Asked "Would you like me to create the PR now?" when CLAUDE.md says "Open a PR for every pushed feature branch"
**Fix**: Act on standing rules without asking:
- Consult memories and CLAUDE.md before acting
- If a standing rule applies, execute it
- Only ask when genuinely ambiguous or architecturally significant

## Pattern 3: Give Up Instead of Diagnose
**Mistake**: Accept "command not found" as final; don't search for the tool
**Example**: `gh` returned "command not found"; I didn't search for it
**Fix**: When a command fails, diagnose immediately:
- Search for the executable (`which`, `find`, package manager)
- Check standard locations (Homebrew: `/opt/homebrew/bin/`)
- Use full path if found
- Only consider alternatives after confirming tool is truly missing

## Pattern 4: Incomplete Tool Use
**Mistake**: Use a tool but don't follow through to verify it worked
**Example**: Ran `gh pr create` but never checked if PR was created
**Fix**: Complete the full workflow:
- Run the command
- Verify the result (check output, verify artifact exists)
- If verification fails, diagnose and retry

## Pattern 5: Not Consulting Own Knowledge
**Mistake**: Act without consulting memories and instructions I already have
**Example**: Didn't reference CLAUDE.md's "Open a PR for every pushed feature branch" rule
**Fix**: Before acting, consult:
- `/memories/` for standing rules and patterns
- CLAUDE.md for project-specific guidance
- Prior session notes for context
- Only then decide whether to ask or act

undefined
