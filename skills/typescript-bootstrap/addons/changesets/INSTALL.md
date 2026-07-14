# Addon: Changesets (versioning + publishing)

Adds [Changesets](https://github.com/changesets/changesets) for per-package
semver bumps, changelog generation, and npm publishing.

**Default:** on for publishable kinds (`single`/`monorepo` libraries); off for `app`.

## Files

- `config.json` → copy to the project root as `.changeset/config.json`.
- `releasing.md` → copy to `contributing/releasing.md` (covers both single and
  monorepo; the monorepo-specific notes are inline).
- `release.yml` → (optional CI automation) copy to `.github/workflows/release.yml`.
  See "CI release automation" below.

## Reconcile against the base tree

### `single` / `cli` (publishable)
1. Copy `config.json` → `<root>/.changeset/config.json`.
2. Add scripts to `package.json`:
   ```jsonc
   "scripts": {
     "changeset": "changeset",
     "version": "changeset version",
     "release": "pnpm build && changeset publish"
   }
   ```
3. Add devDependency: `"@changesets/cli": "^2.31.0"`.
4. Ensure `package.json` has `"publishConfig": { "access": "public", "provenance": true }`
   (the base tree already sets this).
5. Copy `releasing.md` → `contributing/releasing.md`.
6. Wire up the docs (see "Docs wiring" below).

### `monorepo`
1. Copy `config.json` → `<root>/.changeset/config.json`.
2. Add scripts to the **root** `package.json`:
   ```jsonc
   "scripts": {
     "changeset": "changeset",
     "version": "changeset version",
     "release": "turbo run build && changeset publish"
   }
   ```
   (Note `release` uses `turbo run build`, not `pnpm build`, so the whole
   workspace builds in dependency order before publish.)
3. Add `"@changesets/cli": "^2.31.0"` to **root** devDependencies.
4. Copy `releasing.md` → `contributing/releasing.md`.
5. Wire up the docs (see "Docs wiring" below).

## Docs wiring

The base docs don't mention this addon (base stays addon-agnostic). Edit the
named sections that already exist:

### `AGENTS.md` (both trees)
- Append to the bullet list under **`## Contributing guidance`**:
  ```markdown
  - [`contributing/releasing.md`](./contributing/releasing.md) — Changesets-based versioning and the publish flow.
  ```
- Append to the bullet list under **`## Stack`**:
  ```markdown
  - Versioning: Changesets
  ```

### `README.md` (both trees)
Add a new `## Releasing` section after the `## Development` section:
```markdown
## Releasing

\`\`\`bash
pnpm changeset    # record a change
pnpm version      # apply version bumps + changelogs
pnpm release      # build + publish
\`\`\`
```
(For the monorepo, `release` runs `turbo run build` before publish; for single
it's `pnpm build`. The `pnpm release` line is the same either way.)

## CI release automation (optional)

`release.yml` automates publishing via `changesets/action`: on push to `main` it
opens/updates a "Version Packages" PR, and when that PR merges (changesets
consumed) it publishes to npm. Works for both trees unchanged — it just calls
`pnpm release`, so the single-vs-monorepo build difference lives in the `release`
script, not the workflow.

**Default:** apply when **both** `changesets` and the `ci` addon are selected
(usable with `changesets` alone too).

1. Copy `release.yml` → `.github/workflows/release.yml`.
2. Add the `NPM_TOKEN` repo secret (an npm automation/granular token with publish
   rights). `GITHUB_TOKEN` is provided by Actions.
3. Provenance: the workflow sets `id-token: write` + `NPM_CONFIG_PROVENANCE`, which
   pairs with `publishConfig.provenance: true` in `package.json`.
4. **Pin the actions to SHAs — required here** (this workflow holds `NPM_TOKEN`).
   The file ships `@vN # TODO: pin to SHA`; replace each using the GitHub CLI:
   ```bash
   gh api repos/actions/checkout/commits/v4 --jq '.sha'
   gh api repos/pnpm/action-setup/commits/v4 --jq '.sha'
   gh api repos/actions/setup-node/commits/v4 --jq '.sha'
   gh api repos/changesets/action/commits/v1 --jq '.sha'
   # then: uses: changesets/action@<sha> # v1
   ```

## After installing

- `pnpm changeset` to record a change; `pnpm version` then `pnpm release` to cut
  one locally — or let `release.yml` drive it from `main`.

## Removing later

Delete `.changeset/`, `.github/workflows/release.yml`, the
`changeset`/`version`/`release` scripts, the `@changesets/cli` devDep,
`contributing/releasing.md`, and the AGENTS.md (Contributing/Stack bullets) /
README (`## Releasing`) additions.
