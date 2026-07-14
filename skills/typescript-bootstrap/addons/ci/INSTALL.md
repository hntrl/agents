# Addon: CI (GitHub Actions — test/lint quality gates)

Adds a GitHub Actions workflow that mirrors the local quality gates across a Node
version matrix, with a fan-in sentinel for branch protection.

This addon is the **enforcement gate for lint + format** (the `check` job runs
`pnpm format:check` and `pnpm lint`), alongside typecheck/test/build. The
`precommit` addon only runs lint/format on staged files locally for fast
feedback and is not a substitute — CI is what actually blocks a bad merge.

**Default:** on. **Depends on:** the base scripts (`format:check`, `lint`,
`typecheck`, `test`, `build`). **Pairs with:** `knip` (the workflow runs
`check:exports`) and `changesets` (you can add a release workflow).

## Files

- `single/.github/workflows/ci.yml` → for single/app/cli.
- `monorepo/.github/workflows/ci.yml` + `monorepo/.github/workflows/_test.yml` →
  for monorepo.

## Reconcile against the base tree

### `single` / `app` / `cli`
1. Copy `single/.github/workflows/ci.yml` → `<root>/.github/workflows/ci.yml`.
2. It runs a `check` job (format/lint/typecheck/build + verify-clean-tree) and a
   `test` job over `node: [22, 24]`, plus a `ci_success` sentinel.
3. **If the `knip` addon is NOT installed**, delete the `Check exports (knip)`
   step from the `check` job.

### `monorepo`
1. Copy both files into `<root>/.github/workflows/`.
2. `ci.yml` runs root `check` (lint/format/exports/typecheck), a `changes` job
   (dorny/paths-filter) so PRs only test changed packages while pushes to `main`
   test everything, one `test-<pkg>` job per package calling the reusable
   `_test.yml`, and a `ci_success` sentinel.
3. The template wires one package (`__PKG_DIR__` → `__PKG_NAME__`). **Per extra
   package**, add: a `changes` filter output, a `test-<pkg>` job calling
   `_test.yml`, and that job to the `ci_success` `needs` list.
4. **If the `knip` addon is NOT installed**, delete the `Check exports` step.

## Hardening notes (both variants)

- Already includes `concurrency` cancellation and `permissions: contents: read`.
- **Recommended** (required for the publish workflow, see `changesets`): pin each
  `actions/*` to a full commit SHA. SHAs are intentionally NOT pre-baked so the
  template doesn't ship stale pins. Fetch the current SHA with the GitHub CLI:
  ```bash
  gh api repos/actions/checkout/commits/v4 --jq '.sha'
  gh api repos/pnpm/action-setup/commits/v4 --jq '.sha'
  gh api repos/actions/setup-node/commits/v4 --jq '.sha'
  gh api repos/dorny/paths-filter/commits/v3 --jq '.sha'   # monorepo only
  # then: uses: actions/checkout@<sha> # v4
  ```
- A release workflow (changesets publish) is not included here; the `changesets`
  addon ships `release.yml` for automated publishing.

## Removing later

Delete `.github/workflows/` (or the specific files).
