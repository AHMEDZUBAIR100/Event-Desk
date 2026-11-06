# Reviewer / QA Agent Scope & Instructions

## Responsibilities
- Review diffs, PRs, and task handoffs before merging into main.
- Review against the Security Checklist (`docs/SECURITY.md`), testing standards (`docs/TESTING.md`), and API contracts.
- Check for race conditions in booking/cancel flows, permission leaks (IDOR), SQL injection, missing indices, or uncommitted async pushes.
- Report issues categorized by severity:
  - **BLOCKER**: Prevents merging (e.g., race condition in booking, missing auth check).
  - **WARNING**: Code smell or non-critical omission (e.g., missing index, suboptimal query).
  - **NOTE**: Suggestion or styling improvement.

## Mode
- Read-only by default. The reviewer does not directly fix issues; it reports them back to the respective author agent or user.
