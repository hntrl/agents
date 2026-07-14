# Addon: knip (dead-export / unused-dependency checking)

Adds [knip](https://knip.dev) to flag exports nothing imports, unused files, and
unused dependencies. Enforces the "barrels are an API contract, no junk-drawer
exports" rule from `contributing/module-organization.md`.

**Default:** on for libraries; consider off for very early apps with high churn.
**Depends on:** nothing. **Pairs with:** the `ci` addon (adds a `check:exports` CI step).

## Files

- `knip.single.json` → copy to the project root as `knip.json` (single/app/cli).
- `knip.monorepo.json` → copy to the project root as `knip.json` (monorepo).

## Reconcile against the base tree

### `single` / `app` / `cli`
1. Copy `knip.single.json` → `<root>/knip.json`.
2. Add the script to `package.json`:
   ```jsonc
   "scripts": { "check:exports": "knip" }
   ```
3. Add the devDependency: `"knip": "^6.20.0"`.

### `monorepo`
1. Copy `knip.monorepo.json` → `<root>/knip.json` (workspace-aware: it maps
   `packages/*` to per-package entry points).
2. Add `"check:exports": "knip"` to the **root** `package.json` scripts.
3. Add `"knip": "^6.20.0"` to the **root** devDependencies.

## Docs wiring

Add `pnpm check:exports` to the gate list in the `## Quality gates` fenced block
of `AGENTS.md` (e.g. after `pnpm lint`), so it reads alongside the other gates.

## After installing

- Run `pnpm check:exports`.
- If the `ci` addon is applied, it already includes the `check:exports` step —
  keep it. (If `ci` is applied but `knip` is not, that step must be removed; see
  `../ci/INSTALL.md`.)

## Removing later

Delete `knip.json`, the `check:exports` script + devDep, and any CI step that
runs it.
