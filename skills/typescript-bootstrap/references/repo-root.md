# Repo-Root Files

What each root-level file is for, and how the pieces fit together. The two
ready-to-copy **base** trees live in `../templates/single/` and
`../templates/monorepo/`; this doc explains the *why* and the wiring between the
files in them.

Some files below are added by **addons** (`../addons/`), not the base tree —
they're marked **(addon: `<name>`)**. The wiring/rationale is documented here;
the install steps live in each `../addons/<name>/INSTALL.md`.

## The dependency graph between configs

The configs are not independent — they reference each other. Get these
relationships right or builds/types/exports silently drift:

```
tsconfig.base.json ──extended by──> packages/*/tsconfig.json
tsdown.config.ts ──reads──> tsconfig ──emits──> dist/ (rolldown bundle + oxc dts)
tsdown (publint+attw) ──validates──> package.json exports + emitted types
package.json "exports"/"main"/"module"/"types" ──must match──> dist/ output + module format
vitest.config.ts ──uses──> tsconfig paths (via vite-tsconfig-paths or alias)
oxlint.config.ts (lint) ── coexists with ──> oxfmt.config.ts (format), no rule overlap
turbo.json ──orchestrates──> per-package build/typecheck/test (monorepo only)
pnpm-workspace.yaml ──declares──> packages/* + supply-chain policy (monorepo only)
# addons (added on top of the base tree):
knip.json ──reads──> entry (src/index.ts) ──flags──> dead exports + unused deps
lint-staged (in package.json) ──runs──> oxlint --fix + oxfmt on staged files
.github/workflows ──mirror──> the local quality gates
.changeset/config.json ──tracks──> publishable packages/*
```

## Root `package.json`

- **Single package:** the package itself — name, version, scripts, `exports`,
  `files`, deps. In `templates/single/package.json`.
- **Monorepo root:** `"private": true`, no `exports`/`files`. Holds only
  workspace-wide devDeps and orchestration scripts (`-r`/`--filter`). In
  `templates/monorepo/package.json`; per-package `package.json` lives at
  `templates/monorepo/packages/__PKG_DIR__/package.json`.

Scripts every project should expose (so the quality gates work uniformly):

```jsonc
{
  "build": "tsdown",          // monorepo root: "turbo run build"
  "typecheck": "tsc --noEmit", // monorepo root: "turbo run typecheck"
  "test": "vitest run",        // monorepo root: "turbo run test"
  "lint": "oxlint --type-aware",
  "format": "oxfmt",
  "format:check": "oxfmt --check",
  "check:exports": "knip"
}
```

Publishable packages also set `"sideEffects": false` (enables tree-shaking) and
`"publishConfig": { "access": "public", "provenance": true }` (npm provenance via
CI OIDC). Per-package `package.json` in the monorepo holds only
`build`/`dev`/`typecheck`/`test`; lint/format/exports run once at the root.

## `tsconfig.base.json` / `tsconfig.json`

- The base holds the strict compiler baseline (see `typescript-best-practices`
  for the exact flags) and shared `compilerOptions`.
- Beyond `strict: true`, the baseline also enables `noUncheckedIndexedAccess`
  (array/record access yields `T | undefined`), `noImplicitOverride`, and
  `verbatimModuleSyntax` (type-only imports must say so — pairs with the
  inline-type-imports lint rule).
- Per-package `tsconfig.json` does `"extends": "../../tsconfig.base.json"` and
  only sets `rootDir`, `outDir`, `include`, and any path overrides.
- For a single package, base and package tsconfig can be one file.

## `tsdown.config.ts`

- Lives **per buildable package** (not at a monorepo root).
- Declares `entry` (usually `src/index.ts`), `format`, `dts: true`,
  `sourcemap`, `clean`. For a `cli`, set `hashbang`/`banner` with the shebang on
  the binary entry.
- Powered by rolldown (bundling) + oxc (declarations); API mirrors tsup.
- **Module format** is `["esm", "cjs"]` (dual) by default; the questionnaire can
  switch it to `["esm"]` (ESM-only), in which case also drop `main` and the CJS
  `default` conditions from `package.json` `exports`.
- **`publint: true` + `attw: true`** are enabled so each build validates the
  package against its output: publint checks the `package.json` publish fields,
  attw ("are the types wrong") checks that types resolve correctly under node16,
  bundler, and CJS-interop resolution modes. This enforces — automatically — the
  rule that `exports`/`types` must match `dist/`.
- Its output paths are the source of truth that `package.json` `exports` must
  mirror.
- Build-time only: requires Node 22.18+ (output `target` can be lower).

## `turbo.json` (monorepo only)

- Task orchestrator. `build` declares `dependsOn: ["^build"]` (build a package's
  dependencies first) and caches `dist/**`; `typecheck`/`test` also depend on
  `^build`. `dev` is `cache: false, persistent: true`.
- Root scripts run `turbo run <task>` so caching + dep-graph ordering apply.
  `outputLogs` is trimmed (`errors-only` / `new-only`) to keep CI/local runs quiet.
- Not used in the single tree (one package, nothing to orchestrate).

## `knip.json` (addon: `knip`)

- Detects **dead exports** (exported but never imported anywhere), unused files,
  and unused dependencies. Run via `pnpm check:exports`.
- `entry` is the public barrel (`src/index.ts`); `project` is `src/**`. In the
  monorepo it's workspace-aware (`packages/*`).
- Directly enforces the "barrels are an API contract, don't export
  implementation-only helpers" rule from `contributing/module-organization.md`.
  Default-on for libraries; the questionnaire can disable it for early, churny apps.

## pre-commit (addon: `precommit`)

- Adds a `lint-staged` config block to `package.json` that applies
  `oxlint --fix` + `oxfmt` to **staged files only**. Deliberately format/lint
  only — not typecheck/test/build — so commits stay fast. CI is the full gate.
- **No husky and no top-level `.husky/` directory** (matches langchainjs/flue).
  The git hook is not auto-installed; `pnpm lint-staged` runs the check, and the
  addon's `INSTALL.md` documents an optional no-husky `.githooks/` + `core.hooksPath`
  setup for anyone who wants it auto-wired.

## `vitest.config.ts`

- One at the root runs the whole repo. For monorepos, use a workspace config or
  `projects` so each package's tests are discovered.
- Wire TS path aliases here (e.g. `vite-tsconfig-paths`) so tests import the same
  way source does.

## `oxlint.config.ts` (lint — required opinionated defaults)

- A **TypeScript** config (`defineConfig` from `oxlint`) — chosen over
  `.oxlintrc.json` so it can carry comments and computed values. Requires the
  Node-based `oxlint` package on Node 22.18+ (this stack's baseline). **This skill
  requires more than the bare `correctness` default**:
  - `categories`: `correctness`/`suspicious` → `error`, `perf`/`style` → `warn`.
  - `plugins`: `typescript`, `unicorn`, `import`, `oxc` (native, Rust — no JS
    dependency tree).
  - `rules`: `typescript/no-explicit-any: "error"` (enforces the no-`any`
    baseline), `no-console` warned with `warn`/`error` allowed,
    `typescript/consistent-type-imports` for inline type imports.
  - **Runtime portability (libraries, EventKit-style):** declares CommonJS + Web
    Worker globals (`env: { commonjs, worker }`) and bans the Node-only globals
    via `no-restricted-globals` — computed as `globals.node` minus `globals.worker`
    (so `process`/`Buffer` are banned but `fetch`/`URL`/`crypto`/streams survive),
    plus `import/no-nodejs-modules`. Keeps `src/` portable to edge/workers/bun.
    **Remove both for `cli`/`app` kinds.**
  - `options.typeAware: true` so type-aware rules actually run (CLI `--type-aware`).
  - `overrides` for `**/__tests__/**`: enable the `vitest` plugin, relax
    `no-console`, and re-allow Node (Vitest runs on Node).
- Setting `plugins` overwrites the default plugin set, so list everything you
  want enabled.

## `oxfmt.config.ts` (format)

- Formatting source of truth via `oxfmt` (TS config via `defineConfig`): double
  quotes, semicolons, trailing commas, print width ~100. Also owns **import
  ordering** and **comment wrapping** (EventKit-style) — these are formatter
  concerns, not lint rules; verify the exact option names against the installed
  oxfmt schema.
- oxfmt and oxlint are designed to coexist; do not duplicate stylistic rules in
  the lint config.
- Ignore patterns live in the config's `ignorePatterns` field (`dist/`,
  `pnpm-lock.yaml`, generated docs) — no separate `.oxfmtignore` file.

## `.changeset/config.json` (addon: `changesets`)

- Only for publishable kinds. Configures changelog generation, access (`public`),
  and which packages are versioned together (usually independent).

## `pnpm-workspace.yaml`

- Monorepo only. Lists `packages/*` (and `examples/*`, `docs` if present).
- Carries supply-chain hardening: `onlyBuiltDependencies: []` blocks postinstall
  build scripts until you allow-list trusted native packages (`pnpm approve-builds`
  shows what wants to build); `minimumReleaseAge: 1440` refuses dependency
  versions published less than 24h ago (dodges freshly-published malicious
  releases), with `minimumReleaseAgeExclude` for trusted fast-movers.
- For the single tree (no workspace file) the same keys live under a `pnpm`
  field in `package.json`.

## Dotfiles

- `.nvmrc` — pins Node (22.18+ for this stack).
- `.editorconfig` — whitespace/EOL consistency across editors.
- `.gitignore` — at minimum `node_modules/`, `dist/`, `coverage/`, `.turbo/`,
  `*.tsbuildinfo`.

## `.github/workflows/` (addon: `ci`)

- **Single tree (`ci.yml`):** a `check` job (frozen-lockfile install →
  `format:check` → `lint` → `check:exports` → `typecheck` → `build` →
  verify-clean-tree) plus a `test` job over a `node: [22, 24]` matrix, and a
  `ci_success` fan-in sentinel for branch protection.
- **Monorepo tree (`ci.yml` + `_test.yml`):** a `check` job (root lint/format/
  exports/typecheck), a `changes` job (dorny/paths-filter) so PRs only test
  changed packages while pushes to `main` test everything, one `test-<pkg>` job
  per package calling the reusable `_test.yml` (Node matrix), and a `ci_success`
  sentinel.
- Hardening baked in: `concurrency` cancellation, `permissions: contents: read`,
  and a comment recommending SHA-pinning actions for public repos. Mirror the
  local quality gates so green-locally means green-in-CI.
- The `check:exports` step is only included when the `knip` addon is also applied;
  drop it otherwise (see `../addons/ci/INSTALL.md`).

## `typedoc.json`

- Docs extra, published libraries only. Points at the public entrypoints; relies
  on the explicit-barrel discipline from `contributing/module-organization.md` to stay clean.

## `README.md`

- Generate from the questionnaire's purpose + a minimal usage example
  (badges optional, short "Basic Usage" code block, links to
  docs/contributing/license).

## `contributing/` + `AGENTS.md` + `CLAUDE.md`

- `contributing/module-organization.md` is the project's own copy of the
  module-organization conventions (source layout, boundaries, export style,
  import order, barrels, review checklist). It lives *in the repo* so it travels
  with the code and is the sensible default contributors and agents follow.
- `AGENTS.md` (root) is a short pointer file: project name/purpose, the stack,
  the quality gates, and a link into `contributing/`. It is not a place to
  duplicate the conventions — it directs readers to them.
- `CLAUDE.md` (root) **must be a symlink to `AGENTS.md`**, not a copy — one
  source of truth, zero drift. The templates ship it as a relative symlink
  (`CLAUDE.md -> AGENTS.md`). Recreate it with:

  ```bash
  ln -s AGENTS.md CLAUDE.md
  ```

  Caveats: keep the link **relative** (`AGENTS.md`, not an absolute path) so it
  survives being copied/moved. On Windows, symlinks require `git config
  core.symlinks true` (and Developer Mode or admin) to materialize; if a
  contributor's checkout can't use symlinks, a one-line `CLAUDE.md` that says
  "see AGENTS.md" is an acceptable fallback. After scaffolding, verify with
  `readlink CLAUDE.md` (should print `AGENTS.md`).
- The base tree ships `contributing/module-organization.md` and
  `contributing/testing.md`, linked from `AGENTS.md`. `contributing/releasing.md`
  is added by the **`changesets` addon** (it's specific to the publish flow).
  Add more `contributing/*.md` over time and link them too.
