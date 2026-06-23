# GitHub Check States

| State | Meaning | Action Required |
|-------|---------|-----------------|
| `SUCCESS` | Check passed | No |
| `FAILURE` | Check failed | Yes (diagnose root cause) |
| `PENDING` | Check running | Wait, re-check later |
| `IN_PROGRESS` | Check started, not complete | Wait, re-check later |
| `TIMED_OUT` | Check exceeded time limit | Yes (optimize or extend timeout) |
| `CANCELLED` | Check was cancelled/terminated | Investigate cause (user cancel vs. system) |
| `ACTION_REQUIRED` | Manual action needed | Yes (security/vulnerability scan flagged) |
| `NEUTRAL` | Check passed with warnings or optional | No (unless strict mode) |
| `SKIPPED` | Check not run (conditions not met) | No (verify conditions were correct) |
| `WAITING` | Check waiting on dependencies | No (wait for upstream to complete) |
| `QUEUED` | Check queued, not started | No (wait for runner availability) |

## Diagnostic Paths by State

### FAILURE
1. Identify check type (test, lint, build, etc.)
2. Fetch failure message from logs
3. Determine if flaky or consistent
4. Check if failure existed before this PR

### TIMED_OUT
1. Check default timeout for the action
2. Look for slow tests or operations in logs
3. Identify if it's a one-off or recurring
4. Consider: longer timeout vs. optimization

### CANCELLED
1. Check if user/system cancelled
2. Look for resource exhaustion (OOM, disk space)
3. Verify runner availability during that time
4. Check for manual intervention triggers

### ACTION_REQUIRED
1. Usually security scanning (secret detection, dependency vulnerabilities)
2. Check GitHub Security tab for alerts
3. Review the specific detection
4. May require suppressing false positive or fixing real issue

### SKIPPED
1. Verify conditional logic was intentional
2. Check if PR touched files that should trigger the check
3. Look for misconfigured path filters
4. Sometimes indicates a bug in CI configuration

## Common Check Contexts

| Context Pattern | Usually Indicates |
|-----------------|------------------|
| `contexts/*` | GitHub status contexts |
| `ci/*` | Generic CI checks |
| `github-actions/*` | GitHub Actions workflows |
| `codecov/*` | Code coverage uploads |
| `license/cla` | Contributor license agreement |
| `fossa/*` | License compliance scanning |
| `snyk/*` | Security vulnerability scanning |
| `deepcode/*` | Code analysis |
