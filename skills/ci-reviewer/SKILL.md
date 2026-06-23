---
name: ci-reviewer
description: "Reviews CI/CD failures on GitHub Pull Requests. Analyzes failing checks, diagnoses root causes, and provides actionable recommendations for fixes. Use when asked to: (1) review CI failures, (2) diagnose failing checks on a PR, (3) understand why a PR is red, (4) check CI status, (5) debug test failures on a PR, (6) analyze flaky tests, (7) investigate slow builds, (8) troubleshoot GitHub Actions. Trigger on phrases like 'review CI failures', 'failing checks on PR', 'red PR', 'CI is broken', 'tests failing', 'debug CI', 'why is this PR failing', 'check CI status', 'analyze test failures', 'diagnose CI', 'flaky tests', 'slow build', 'GitHub Actions troubleshooting', or any PR URL/link in the conversation."
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - WebFetch
---

# CI Reviewer — Diagnose and Analyze CI/CD Failures

Reviews GitHub PRs for CI/CD failures, diagnoses root causes, and provides actionable recommendations.

## Essential Principles

**Be diagnostic, not prescriptive.** Your job is to understand WHY checks are failing, not to fix them (unless asked). Provide clear analysis of failure patterns, not just a list of failures.

**Context matters.** A failing test in isolation is different from a test that fails only on main, or only on Windows, or intermittently. Gather context before concluding.

**Prioritize by impact.** Distinguish between blocking failures (required checks, core test suites) and non-blocking (optional lints, docs-only changes).

**Respect CI gates.** If a required check is failing, the PR cannot merge. Flag this clearly.

## When to Use

- User pastes a PR URL or references a PR number
- User asks about "failing checks", "red PR", "CI broken"
- User wants to understand why tests are failing
- User asks to "debug CI" or "diagnose CI failures"
- User mentions flaky tests or slow builds

## When NOT to Use

- Bulk PR surveys (use langster-patch instead)
- Fixing the actual failures (unless explicitly requested)
- Non-GitHub CI systems (Travis, CircleCI, etc.)

## Routing

| User intent | Workflow |
|-------------|----------|
| Single PR CI review (URL, number, or "this PR") | [workflows/review-pr-ci.md](workflows/review-pr-ci.md) |
| PR link detected in conversation | [workflows/review-pr-ci.md](workflows/review-pr-ci.md) |

## Quick Reference

| Check type | Common causes | Diagnostic approach |
|------------|---------------|---------------------|
| `failure` | Real regression, env issue | Compare with main branch, check recent commits |
| `timed_out` | Slow test, resource limits | Analyze timing logs, check for resource-heavy tests |
| `cancelled` | Timeout, user cancelled | Check workflow run duration limits |
| `action_required` | Secret scan, vulnerability | Check security alerts, dependency changes |
| `skipped` | Conditional logic, no-op | Usually benign, confirm context |

## Reference Index

| File | Content |
|------|---------|
| [references/check-types.md](references/check-types.md) | Check state meanings and diagnostic paths |
| [references/gh-commands.md](references/gh-commands.md) | Useful gh CLI commands for CI analysis |

## Success Criteria

- [ ] PR info extracted (repo, number, title, author, branch)
- [ ] All check statuses retrieved and analyzed
- [ ] Failures categorized by severity (blocking vs non-blocking)
- [ ] Root cause analysis provided for each failure
- [ ] Actionable recommendations offered (fix strategy, not code)
- [ ] Summary indicates if PR is mergeable or blocked
