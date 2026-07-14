# Addon: examples (runnable usage examples)

Adds an `examples/` directory of focused, self-contained, runnable usages of the
library. Ships an index (`examples/README.md`, with a "Contributing an example"
convention block) plus one seed example (`examples/basic/`).

**Default:** off. **Depends on:** the library itself. **Standalone.**

## Files

- `examples/README.md` → `examples/README.md` (index + conventions).
- `examples/basic/` → `examples/basic/` (seed: `package.json`, `src/main.ts`,
  `README.md`).

## Reconcile against the base tree

### `monorepo`
1. Copy `examples/` → `<root>/examples/`. The workspace already globs `examples/*`
   (in `pnpm-workspace.yaml`), so the example links to the local package.
2. Keep `"__PKG_NAME__": "workspace:*"` in `examples/basic/package.json`.
3. Replace `__PKG_NAME__` / `__FEATURE_FN__` with the real package name + first export.

### `single` / `app` / `cli`
1. Copy `examples/` → `<root>/examples/`.
2. There's no workspace, so the example can't use `workspace:*`. Change the dep to
   a published range, e.g. `"__PKG_NAME__": "^0.1.0"` — OR add a workspace by
   creating a `pnpm-workspace.yaml` with `packages: ["examples/*"]` and a root
   `package.json` if you want it linked. For a single-package repo, examples are
   usually doc/snippet-oriented (pin to the published version).
3. Replace `__PKG_NAME__` / `__FEATURE_FN__` accordingly.

## Exclude examples from the core gates (required)

Examples must not break the library's CI when they churn. Wire these exclusions:

1. **oxlint** — add `"examples/**"` to `ignorePatterns` in `oxlint.config.ts`.
2. **knip** (if the `knip` addon is applied) — add `"examples/**"` to `ignore`
   in `knip.json`.
3. **CI / tests** — the base `vitest.config.ts` only includes `**/__tests__/**`,
   so example sources aren't picked up; just don't add example dirs to the CI
   `test`/`build` matrix. (Monorepo: don't add a `changes`/`test-<pkg>` job for
   examples.)
4. **format** — optional; you may also add `examples/**` to `ignorePatterns` in
   `oxfmt.config.ts` if you don't want examples held to the repo's format gate.

## Removing later

Delete `examples/` and the `examples/**` exclusion entries you added.
