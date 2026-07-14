# Templates

Two ready-to-copy **base** project trees for `typescript-bootstrap`. Pick the
tree for the project kind, copy it as the new project root, replace placeholder
tokens, then layer on **addons** (`../addons/`).

- **`single/`** — one publishable package at the repo root. Also the base for
  `app` and `cli` kinds (see adaptations below).
- **`monorepo/`** — a pnpm + Turbo workspace: root config + one exemplar package
  under `packages/__PKG_DIR__/`. Copy that package directory per workspace package.

The base trees are intentionally minimal. CI, Changesets, knip, and the
pre-commit config are **not** in the base — they're applied from `../addons/`
after copying (see `../addons/README.md`). The one shared, kind-agnostic extra
that lives here in `templates/`:

- `typedoc.json` → `typedoc.json` (docs extra, publishable libraries)

## Placeholder tokens

| Token | Replace with |
| --- | --- |
| `__PKG_NAME__` | npm name, e.g. `@scope/core` or `mylib` |
| `__PKG_DESC__` | one-line project purpose |
| `__PKG_DIR__` | monorepo package directory name, e.g. `core` (rename `packages/__PKG_DIR__/`) |
| `__NODE_VERSION__` | pinned Node major, e.g. `22` (must be 22.18+ for tsdown/oxlint) |
| `__AUTHOR__` | author string (default empty) |
| `__LICENSE__` | SPDX id (default `MIT`) |
| `__FEATURE__` | first module file basename, e.g. `rate-limiter` (rename `src/feature.ts`) |
| `__FEATURE_FN__` | first exported symbol, e.g. `rateLimiter` |

## `single/` tree

```text
single/                 # BASE — addons add files on top (see ../addons/)
  src/
    index.ts            # public barrel
    feature.ts          # -> rename to <feature>.ts
  __tests__/
    feature.spec.ts     # -> rename to <feature>.spec.ts
  contributing/
    module-organization.md
    testing.md          # releasing.md is added by the changesets addon
  AGENTS.md             # points agents at contributing/
  CLAUDE.md             # symlink -> AGENTS.md (relative)
  README.md
  package.json          # the publishable package itself
  tsconfig.json         # full strict baseline inline (no extends)
  tsdown.config.ts
  vitest.config.ts
  oxlint.config.ts      # required opinionated lint defaults (TS config)
  oxfmt.config.ts       # format + import sorting + ignorePatterns
  .nvmrc .editorconfig .gitignore
  # added by addons: knip.json, .github/workflows/, lint-staged (in package.json),
  #                  .changeset/ + release scripts + contributing/releasing.md
```

## `monorepo/` tree

```text
monorepo/                # BASE — addons add files on top (see ../addons/)
  packages/
    __PKG_DIR__/        # exemplar package — copy per workspace package
      src/{index.ts, feature.ts}
      __tests__/feature.spec.ts
      package.json      # per-pkg: build/dev/typecheck/test scripts only
      tsconfig.json     # extends ../../tsconfig.base.json
      tsdown.config.ts
      vitest.config.ts  # per-package (Turbo runs tests per package)
  contributing/
    module-organization.md
    testing.md          # releasing.md is added by the changesets addon
  AGENTS.md
  CLAUDE.md             # symlink -> AGENTS.md (relative)
  README.md
  package.json          # root: private; lint/format + turbo orchestration
  turbo.json            # task graph + caching
  tsconfig.base.json    # shared strict baseline; packages extend it
  pnpm-workspace.yaml   # workspaces + supply-chain hardening
  vitest.config.ts      # root config (watch across packages)
  oxlint.config.ts oxfmt.config.ts
  .nvmrc .editorconfig .gitignore
  # added by addons: knip.json, .github/workflows/{ci,_test}.yml,
  #                  lint-staged (in package.json), .changeset/ + release scripts
```

Root-level tooling (oxlint, oxfmt) runs once across the whole workspace;
`build`/`typecheck`/`test` run per package through Turbo. The package
`tsconfig.json` path `../../tsconfig.base.json` is correct at `packages/<name>/`
depth — keep packages exactly one level under `packages/`.

### Adding a package (monorepo)

Copy `packages/__PKG_DIR__/` to `packages/<new>/` and update its `package.json`
name. If the `ci` addon is applied, also add matching CI jobs (a `changes` filter
output, a `test-<new>` job calling `_test.yml`, and the job in the `ci_success`
`needs` list) — see `../addons/ci/INSTALL.md`.

## `CLAUDE.md` is a symlink

In both trees `CLAUDE.md` is a **relative symlink to `AGENTS.md`** — one source
of truth, no second file to maintain. When copying the tree, preserve the
symlink (`cp -a` / `cp -R` keep it; some archive/template mechanisms deref it).
If it ends up a regular file or is missing, recreate it from the project root:

```bash
ln -s AGENTS.md CLAUDE.md   # verify: readlink CLAUDE.md  ->  AGENTS.md
```

On Windows this needs `git config core.symlinks true`; otherwise a one-line
`CLAUDE.md` pointing to `AGENTS.md` is an acceptable fallback.

## Kind adaptations

- **`app`** (from `single/`): strip `exports`/`files`/`publishConfig` from
  `package.json`; the entrypoint is an app entry, not a library barrel.
- **`cli`** (from `single/`): add a `"bin"` field to `package.json`; uncomment the
  cli entry + `hashbang` in `tsdown.config.ts`.

## Linting is a hard requirement

`oxlint.config.ts` ships opinionated defaults (categories beyond `correctness`,
`typescript/no-explicit-any: error`, type-aware linting, runtime-portability
rules for libraries, a `vitest` test override). This is a requirement of the
skill, not a starting point to trim down. (`cli`/`app` kinds remove the
portability rules.)
