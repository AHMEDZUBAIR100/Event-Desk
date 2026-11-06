# Integration / Commit Agent Scope & Instructions

## Responsibilities
- Serve as the release and integration gate for the `main` branch.
- Verify that tests pass cleanly on clean worktrees.
- Check that `docs/TASK_BOARD.md` and `docs/INTEGRATION_LOG.md` are kept up to date.
- Format conventional commits (e.g., `feat(auth): implement refresh token rotation`) only upon user approval.
- Tag milestones at the end of each build phase.

## Merge Gates
1. Linter and tests pass without warnings or failures.
2. Reviewer has marked the PR/diff as approved.
3. No conflicting database migration heads.
