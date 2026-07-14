# Stack Rationale

Why the bootstrap defaults are what they are. Use this to justify the stack to a
user, or to make a principled substitution when they want something different.

## pnpm (+ workspaces)

- Content-addressed store → fast installs, strict dependency isolation (no
  phantom deps), which keeps package boundaries honest.
- First-class workspaces (`pnpm-workspace.yaml`) make the `single → monorepo`
  growth path cheap: a single package can become `packages/*` without changing
  tooling.

Substitution: npm/yarn workspaces work, but lose strictness guarantees. If the
user insists, keep `workspaces` in root `package.json` instead of
`pnpm-workspace.yaml` and drop pnpm-specific scripts.

## TypeScript, `strict: true`

- Non-negotiable baseline. All the type-safety guidance in
  `typescript-best-practices` assumes strict mode.
- A shared `tsconfig.base.json` keeps every package on the same compiler floor;
  packages `extends` it and only override `outDir`/`rootDir`/paths.

## tsdown (build, rolldown + oxc)

- `tsdown` is the rolldown-powered library bundler from VoidZero (same org as
  oxc/rolldown). It uses oxc to emit `.d.ts` and rolldown to bundle → very fast
  dual ESM/CJS builds with declarations in one config.
- API is intentionally tsup-compatible (`defineConfig`, `entry`, `format`,
  `dts`), so the mental model and migration are familiar.
- Pairs cleanly with the `package.json` `exports` map and can even
  auto-generate/validate `exports`, plus run `publint`/`attw` on the output.
- Per-package `tsdown.config.ts` keeps build concerns local to the package that
  produces output.

Caveat: tsdown requires **Node 22.18+ to build** (the build environment only;
output can target lower Node via the `target` option). Pin CI accordingly.

Substitution: `tsc` alone (types only, no bundling) for apps; raw `rolldown` for
finer control. Keep the `exports`/output contract intact whatever the bundler.

## Vitest (test)

- Fast, ESM-native, Jest-compatible API, first-class TypeScript.
- Supports both behavioral tests and type-level assertions (`expectTypeOf`),
  which the best-practices skill expects for inference/narrowing coverage.
- A root `vitest.config.ts` (or workspace config) runs the whole repo.

## oxlint + oxfmt (lint + format, oxc)

- `oxlint` is the oxc linter: Rust-fast, ESLint-compatible config, with many
  popular plugins (`typescript`, `unicorn`, `import`, `vitest`, ...) implemented
  **natively in Rust** — broad rule coverage with no large JS plugin dependency
  tree. The bootstrap ships it as a TypeScript config (`oxlint.config.ts`) so the
  config can carry comments and computed values (e.g. the portability ban list).
- `oxfmt` is the oxc formatter (Prettier-style), owning formatting so the linter
  doesn't carry stylistic rules — including import ordering and comment wrapping.
  oxfmt and oxlint are designed to coexist, so there's no ESLint/Prettier-style
  rule conflict to manage.
- **Good defaults are a hard requirement of this skill**, so the bootstrap ships
  an opinionated `oxlint.config.ts` (not the bare `correctness` default):
  `correctness`/`suspicious` as errors, `perf`/`style` warnings,
  `typescript/no-explicit-any` as an error to enforce the no-`any` baseline from
  `typescript-best-practices`, type-aware linting on, runtime-portability rules
  for libraries, and a relaxed test override. See `repo-root.md` and
  `templates/single/oxlint.config.ts`.

Substitution: ESLint flat config + Prettier still works if a team standardizes
on it, but you lose the speed and the single-toolchain simplicity. If you swap
back, keep an equivalently strict ruleset — the no-`any` rule is non-negotiable.

## Changesets (versioning)

- Per-package semver + changelog generation that understands workspaces.
- Only wired for publishable kinds; an `app` usually doesn't need it.
- Standard `.changeset/` workflow, so contributors get a familiar release flow.

## TypeDoc (optional docs)

- Generates API docs from TSDoc comments. Only worth wiring for published
  libraries that want a reference site.
- The explicit-barrel discipline in `contributing/module-organization.md` is what keeps generated
  docs clean.

## Node pinning + EditorConfig

- `.nvmrc` pins the Node version so CI and contributors match. Default to
  **22.18+** since tsdown and oxlint's TS config require it at build time.
- `.editorconfig` keeps whitespace consistent across editors before oxfmt even
  runs.

## When to deviate

The stack is opinionated, not sacred. Swap a piece when the user has a concrete
reason (existing org standard, platform constraint, runtime like Bun/Deno). When
you do, keep the *contracts* stable: strict types, explicit public exports,
build output matching `package.json`, and runnable quality gates.
