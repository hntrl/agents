# Review PR CI Status

Analyzes CI/CD failures for a single GitHub PR.

## Phase 1: Extract PR Identifier

**Entry:** User has referenced a PR (URL, number, or "this PR").

**Actions:**
1. Parse the PR reference:
   - **URL**: Extract `owner/repo` and PR number
   - **Number only**: Use from context or prompt user
   - **"this PR"**: Use current repo context if available, otherwise prompt
2. Resolve full `owner/repo` identifier if not provided.

**Exit:** `OWNER/REPO#NUMBER` confirmed.

## Phase 2: Fetch PR Metadata

**Entry:** PR identifier confirmed.

**Actions:**
```bash
gh pr view {OWNER}/{REPO}#{NUMBER} \
  --json number,title,author,state,headRefName,baseRefName,url,body,isDraft,mergeable,statusCheckRollup
```

Capture:
- Title and author
- Source/target branches
- Draft status
- Merge eligibility
- Overall status check rollup

**Exit:** PR metadata collected.

## Phase 3: Fetch Detailed Check Status

**Entry:** Phase 2 complete.

**Actions:**
```bash
gh api repos/{OWNER}/{REPO}/commits/{headRefName}/status
gh api repos/{OWNER}/{REPO}/pulls/{NUMBER}/checks
```

For each check in `statusCheckRollup`, capture:
- Name
- State (`SUCCESS`, `FAILURE`, `PENDING`, `TIMED_OUT`, `CANCELLED`, `ACTION_REQUIRED`, `NEUTRAL`, `SKIPPED`)
- Context (e.g., `ci/check`, `lint`, `test`)
- URL (link to detailed logs)
- Started at / completed at (for timing analysis)

**Exit:** All checks enumerated with states.

## Phase 4: Categorize Failures

**Entry:** Phase 3 complete.

**Actions:**
1. **Separate blocking from non-blocking:**
   - Required checks that fail → blocking
   - Optional checks that fail → non-blocking
   - Skipped/cancelled → note but don't flag as failure

2. **Group by failure type:**

   | Category | Indicators | Priority |
   |----------|------------|----------|
   | **Test failure** | `test`, `jest`, `pytest`, `unittest` | High |
   | **Lint error** | `lint`, `eslint`, `ruff`, `mypy` | Medium |
   | **Build failure** | `build`, `compile`, `pack` | High |
   | **Type error** | `typecheck`, `mypy`, `tsc` | Medium |
   | **Timeout** | `timed_out`, `cancelled` | Medium |
   | **Security** | `secret`, `vulnerability`, `snyk` | High |
   | **Coverage** | `coverage`, `codecov` | Low |
   | **Integration** | `e2e`, `integration` | Medium |

3. **Identify patterns:**
   - All checks failing vs. isolated failures
   - Consistent across all commits vs. intermittent
   - Check-specific (only `macos-latest` fails) vs. environment-wide

**Exit:** Failures grouped and prioritized.

## Phase 5: Analyze Each Failure

**Entry:** Phase 4 complete.

**Actions:**
For each blocking/near-blocking failure:

1. **Fetch recent logs** (if available via gh):
   ```bash
   gh run view {run_id} --log
   ```

2. **Determine root cause type:**
   - **Code regression**: Test was passing, now fails → real bug or changed behavior
   - **Environmental**: Works locally, fails in CI → env difference (OS, versions, deps)
   - **Flaky test**: Passes sometimes → timing, randomness, external deps
   - **Configuration**: Wrong env vars, missing secrets, misconfigured runners
   - **Timeout**: Resource exhausted, test too slow → optimization needed
   - **Dependency**: External API changed, lockfile drift → update deps

3. **Document the failure:**

   ```
   ### {check_name}
   
   **State:** {FAILURE/TIMED_OUT/etc}
   **Type:** {test/lint/build/etc}
   **Duration:** {if available}
   
   **Error Summary:** {1-2 sentence description from logs}
   
   **Likely Root Cause:** {your analysis}
   
   **Recommended Action:** {how to fix, generally}
   
   **Log URL:** {link to full logs}
   ```

**Exit:** Each failure has a diagnostic summary.

## Phase 6: Generate Report

**Entry:** Phase 5 complete.

**Actions:**
Output a structured report:

```
## CI Review — {OWNER}/{REPO}#{NUMBER}

**Title:** {pr_title}
**Author:** {author}
**Branch:** {headRefName} → {baseRefName}
**Status:** Draft | Ready | Blocked | Mergeable
**Last Updated:** {timestamp}

### Summary

| Check | Status | Type | Duration |
|-------|--------|------|----------|
| {check_1} | ✅ PASS | test | 2m 34s |
| {check_2} | ❌ FAIL | lint | 12s |
| {check_3} | ⏳ PENDING | build | — |

**Verdict:** PR is BLOCKED | can proceed with caution | mergeable

### Failures

{failure analyses from Phase 5}

### Recommendations

1. **{priority action}** — {brief explanation}
2. **{secondary action}** — {brief explanation}

### Logs

- Full run logs: {workflow URL}
- Individual check logs: see table above
```

**Exit:** Report generated and displayed.

## Phase 7: Offer Next Steps

**Entry:** Report complete.

**Actions:**
1. Offer to fetch more detailed logs for specific failures
2. Offer to compare with `main` branch baseline
3. Offer to check for similar failures in recent PRs
4. **Do not offer to fix the failures** unless explicitly asked
