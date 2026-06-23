# Useful gh CLI Commands for CI Analysis

## PR Status

```bash
# View PR with check status
gh pr view {owner}/{repo}#{number} --json title,author,state,statusCheckRollup,url

# Get full status check rollup
gh api repos/{owner}/{repo}/commits/{ref}/status

# List all checks for a PR
gh api repos/{owner}/{repo}/pulls/{number}/checks
```

## Workflow Runs

```bash
# List recent workflow runs
gh run list --repo {owner}/{repo} --limit 10

# View specific run details
gh run view {run_id} --repo {owner}/{repo}

# Get run logs (downloads)
gh run download {run_id} --repo {owner}/{repo} --dir ./logs

# View run with verbose output
gh run view {run_id} --repo {owner}/{repo} --verbose

# Check run times
gh run view {run_id} --repo {owner}/{repo} --json createdAt,updatedAt,startedAt,completedAt
```

## Checks

```bash
# Get check runs for a commit
gh api repos/{owner}/{repo}/commits/{sha}/check-runs

# Get combined status for a ref
gh api repos/{owner}/{repo}/commits/{ref}/statuses
```

## Comparison

```bash
# Compare branch status with main
gh api repos/{owner}/{repo}/commits/main/status

# Get recent commits to compare against
gh log {base}..{head} --oneline

# Find if check passed on main
gh api repos/{owner}/{repo}/commits/main/check-runs --jq '.check_runs[] | select(.name == "check-name")'
```

## Debugging

```bash
# View PR comments (may contain CI debug info)
gh pr comment list {owner}/{repo}#{number}

# View checks timeline (shows order and timing)
gh api repos/{owner}/{repo}/commits/{ref}/check-runs --jq '.check_runs[] | {name, status, conclusion, started_at, completed_at}'
```

## Filtering and jq Tips

```bash
# List only failing checks
gh api repos/{owner}/{repo}/commits/{ref}/check-runs --jq '.check_runs[] | select(.conclusion == "failure")'

# Get check durations
gh api repos/{owner}/{repo}/commits/{ref}/check-runs --jq '.check_runs[] | select(.conclusion != null) | {name, duration: (.completed_at - .started_at)}'

# Count checks by conclusion
gh api repos/{owner}/{repo}/commits/{ref}/check-runs --jq '[.check_runs[].conclusion] | group_by(.) | map({status: .[0], count: length})'
```
