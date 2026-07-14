# Releasing

Versioning and publishing run on [Changesets](https://github.com/changesets/changesets).
In a monorepo it understands the pnpm workspace and versions each package
independently.

## Recording a change

Any change that affects a published package needs a changeset:

```bash
pnpm changeset
```

Pick the bump (patch / minor / major following semver) and write a short,
user-facing summary. (In a monorepo, `changeset` also prompts for which
package(s) the change affects.) The changeset file is committed with your PR.

## Cutting a release

```bash
pnpm version      # apply pending changesets: bump versions + update CHANGELOG(s)
pnpm release      # build, then publish to npm
```

`pnpm release` runs the build first and publishes with npm provenance
(`publishConfig.provenance: true`). In a monorepo the build runs through Turbo so
packages build in dependency order and only changed packages publish. Publishing
runs tsdown's `publint` and `attw` checks, so a release fails fast if
`package.json` publish fields or the emitted types are wrong.

## Pre-publish checklist

- [ ] A changeset exists covering every affected package.
- [ ] `pnpm build` is clean and each `dist/` matches its `exports` map.
- [ ] `pnpm check:exports` (knip) is clean (if the knip addon is installed).
- [ ] CHANGELOG entry reads clearly for consumers.
- [ ] Monorepo: internal dependency version bumps look right (Changesets `updateInternalDependencies`).
