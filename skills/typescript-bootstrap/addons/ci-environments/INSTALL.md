# Addon: ci-environments (run the suite under multiple runtimes)

Runs the **existing Vitest suite** under several JS runtimes/environments, to
catch behavior that breaks outside plain Node (edge, workers, Bun). Distinct from
`publint`/`attw` (static packaging checks) — this actually executes your tests.

**Default:** off (niche — only matters if your code must run beyond Node).
**Depends on:** Vitest (base). **Pairs with:** the `ci` addon (separate workflow;
composes alongside it). Standalone — works without the `ci` addon too.

## Supported runtimes

| Runtime | How | Status |
| --- | --- | --- |
| node | Vitest `environment: 'node'` | first-class |
| edge-runtime | Vitest `environment: 'edge-runtime'` (`@edge-runtime/vm`) | first-class |
| cloudflare / workerd | `@cloudflare/vitest-pool-workers` | first-class (opt-in; needs wrangler config) |
| **bun** | `bunx vitest` | **best-effort / unofficial** |
| deno | — | **not supported** here |

- **Bun caveat:** `bunx vitest` runs Vitest on Bun's **Node-compatibility layer**.
  It does *not* exercise Bun's native test runner, and may break on Bun upgrades.
  Its CI job is `continue-on-error` (advisory, doesn't block merges).
- **Deno:** Vitest does not run on Deno. Real Deno coverage needs `deno test`
  (a different runner + test files), which is out of scope for this addon. Add it
  by hand as a separate smoke job if you truly need it.

## Files

- `vitest.environments.config.ts` → copy to the project root (single) or the
  package root (monorepo). Defines `node` / `edge` (/ `cloudflare`) as Vitest
  projects over your existing `__tests__/`.
- `single/.github/workflows/test-environments.yml` → single/app/cli.
- `monorepo/.github/workflows/test-environments.yml` → monorepo.

## Reconcile against the base tree

### `single` / `app` / `cli`
1. Copy `vitest.environments.config.ts` → `<root>/`.
2. Copy `single/.github/workflows/test-environments.yml` → `.github/workflows/`.
3. Add devDependency `"@edge-runtime/vm": "^5.0.0"` (for the `edge` project).
4. (Optional) cloudflare: add `"@cloudflare/vitest-pool-workers"`, a `wrangler.toml`,
   uncomment the `cloudflare` project in the config and the matrix entry.

### `monorepo`
1. Copy `vitest.environments.config.ts` → `packages/<pkg>/` (each package whose
   portability you care about).
2. Copy `monorepo/.github/workflows/test-environments.yml` → `.github/workflows/`;
   replace `__PKG_NAME__` and add a matrix entry / job per such package.
3. Add `"@edge-runtime/vm"` to that package's devDependencies (+ cloudflare deps if used).

## Compose with the `ci` addon

This ships its **own** workflow + sentinel (`environments_success`), so it runs
independently. If you use branch protection, add `environments_success` (and the
`ci` addon's `ci_success`) as required checks. Don't fold these jobs into the
`ci` addon's `check`/`test` jobs — keeping them separate isolates flaky/edge
runtimes from the core gate.

## Action SHA pinning

The workflow uses `@vN` tags marked for pinning. For a public repo, pin each to a
full commit SHA. Fetch the current SHA with the GitHub CLI:

```bash
gh api repos/actions/checkout/commits/v4 --jq '.sha'
gh api repos/pnpm/action-setup/commits/v4 --jq '.sha'
gh api repos/actions/setup-node/commits/v4 --jq '.sha'
gh api repos/oven-sh/setup-bun/commits/v2 --jq '.sha'
# then: uses: actions/checkout@<sha> # v4
```

## Removing later

Delete `vitest.environments.config.ts`, `.github/workflows/test-environments.yml`,
the `@edge-runtime/vm` (+ cloudflare) devDeps, and any required-check entries.
