# Addons

Opt-in capabilities layered onto a base tree (`templates/single` or
`templates/monorepo`) **after** it's copied. Each addon is a self-contained
directory with its files plus an `INSTALL.md` that says exactly what to copy, the
`package.json` scripts/devDeps to add, and how to reconcile single vs. monorepo.

The base trees are intentionally minimal: source layout, `tsconfig`, `tsdown`,
`oxlint`/`oxfmt`, `vitest`, and the project docs (`README`, `AGENTS.md`,
`CLAUDE.md`, `contributing/`). Everything below is added only when requested.

| Addon | What it adds | Default | Notes / depends on |
| --- | --- | --- | --- |
| `changesets/` | `.changeset/config.json` + `changeset`/`version`/`release` scripts + optional `release.yml` | on for publishable libs (`single`/`monorepo`), off for `app` | publishing flow; `release.yml` when `ci` also on |
| `ci/` | GitHub Actions (`.github/workflows/`), Node version matrix, sentinel | on | mirrors base scripts; runs `check:exports` if `knip` present |
| `precommit/` | `lint-staged` config (no husky, no `.husky/`) | on | needs oxlint+oxfmt (always present) |
| `knip/` | `knip.json` + `check:exports` script | on for libraries | pairs with `ci` |
| `ci-environments/` | run the Vitest suite under node/edge/cloudflare (+ bun, best-effort) | off | own workflow + sentinel; composes with `ci` |
| `examples/` | `examples/` dir (index + `basic/` seed) | off | excluded from lint/knip/test gates |

## How the workflow uses these

After copying the base tree and resolving placeholders, the bootstrap workflow
(`workflows/bootstrap-project.md`) applies each requested addon by following its
`INSTALL.md`. Defaults above are applied unless the questionnaire overrides them;
each addon is independently removable.

Cross-addon coupling is documented per addon (e.g. CI references the `knip` step;
a release workflow assumes `changesets`). The `INSTALL.md` files call these out.
