---
name: typescript-bootstrap
description: "Scaffold a brand-new TypeScript project on a modern, opinionated stack (pnpm + oxc tooling + rolldown/tsdown + Vitest + Changesets + strict TS). Runs a short questionnaire first, then generates a faithful project skeleton: repo-root config, opinionated lint defaults, package layout, public export surface, tests, and quality gates. Use when the user wants to: (1) start a new TypeScript project/library/monorepo, (2) bootstrap or scaffold a TS package, (3) set up a TypeScript stack from scratch, or (4) create a new repo with oxlint/tsdown/Vitest/Changesets. Trigger on phrases like 'new TypeScript project', 'bootstrap a TS library', 'scaffold a package', 'set up a monorepo', or 'start a TypeScript repo'."
---

# TypeScript Bootstrap — Project Scaffolding

Use this skill to create a **new** TypeScript project on a known-good, opinionated stack. It pairs a short intake questionnaire with a faithful template buildout so the result is consistent (pnpm + oxc tooling + rolldown/tsdown + Vitest + Changesets + strict TS), modular, and ready to ship.

This skill is about **standing a project up**. The module-organization conventions ship *into* each new project as `contributing/module-organization.md` (in both `templates/single/` and `templates/monorepo/`), pointed at by a generated `AGENTS.md`/`CLAUDE.md` — that doc is the project's sensible default for layout, boundaries, and public API surfaces.

## When to Use

- "Start a new TypeScript library / CLI / monorepo."
- "Bootstrap a package with oxlint + tsdown + Vitest + Changesets."
- "Set up a strict-TS repo from scratch."
- Adding a new package to a workspace that already follows this stack.

## When NOT to Use

- Refactoring an existing project's layout → use the conventions in `templates/single/contributing/module-organization.md` directly.
- Pure type-safety / API-design review → use `typescript-best-practices`.
- Non-TypeScript scaffolding.

## The Stack (defaults)

A modern, oxc-powered stack, split into an always-on **base** and opt-in **addons**.

### Base (always in the tree)

| Concern | Default | Notes |
| --- | --- | --- |
| Package manager | `pnpm` (workspaces) | `pnpm-workspace.yaml` at root for monorepos; supply-chain hardening (`onlyBuiltDependencies`, `minimumReleaseAge: 1440`) |
| Monorepo orchestration | `Turbo` | `turbo.json` runs `build`/`typecheck`/`test` with dep-graph ordering + caching (monorepo tree only) |
| Language | TypeScript, `strict: true` | Plus `noUncheckedIndexedAccess`, `noImplicitOverride`, `verbatimModuleSyntax`. See `typescript-best-practices` |
| Bundler | `tsdown` (rolldown + oxc) | Dual ESM + CJS + `.d.ts` by default (ESM-only is a questionnaire option); `publint` + `attw` validation on |
| Test runner | `Vitest` | Behavioral + type-level tests |
| Lint | `oxlint` (oxc) | **Opinionated defaults are required — see below.** Native TS/import/unicorn/vitest plugins, type-aware |
| Format | `oxfmt` (oxc) | double quotes, semis, width ~100 |
| Node | pinned via `.nvmrc`, **22.18+ required to build** | tsdown/oxlint TS configs need Node 22.18+; runtime output can target lower |

### Addons (opt-in, layered after copying the base tree)

Niche/heavier capabilities live in `addons/<name>/`, each with an `INSTALL.md` that says what to copy and how to reconcile against single vs. monorepo. Apply only the requested ones; defaults below.

| Addon | Adds | Default |
| --- | --- | --- |
| `changesets` | `.changeset/config.json`, `changeset`/`version`/`release` scripts, `contributing/releasing.md`, optional `release.yml` | on for publishable libs, off for `app` |
| `ci` | GitHub Actions (`.github/workflows/`), Node version matrix, fan-in sentinel | on |
| `precommit` | `lint-staged` config (no husky / no top-level `.husky/`) | on |
| `knip` | `knip.json` + `check:exports` script | on for libraries |
| `ci-environments` | run the Vitest suite under node/edge/cloudflare (+ bun, best-effort) | off |
| `examples` | `examples/` dir (index + `basic/` seed), excluded from gates | off |

See `addons/README.md` for the index and each addon's `INSTALL.md` for exact steps.

### Linting Defaults (required, not optional)

Good lint defaults are a hard requirement of this skill. Both trees ship a committed `oxlint.config.ts` (e.g. `templates/single/oxlint.config.ts`) — a TS config (via `defineConfig` from `oxlint`) so it can carry comments and computed values — configured beyond the bare `correctness` default:

- **Categories:** `correctness: "error"`, `suspicious: "error"`, `perf: "warn"`, `style: "warn"`.
- **Plugins enabled:** `typescript`, `unicorn`, `import`, `oxc`, plus `vitest` for test files.
- **Enforces the `typescript-best-practices` baseline:** `typescript/no-explicit-any: "error"`, `no-console` warned (allow `warn`/`error`), consistent type imports.
- **Type-aware linting on** (`options.typeAware: true`) so rules that need type info actually run.
- **Runtime portability (libraries, EventKit-style):** declares CommonJS + Web Worker globals as available (`env: { commonjs, worker }`) and, via `no-restricted-globals`, bans every Node global the worker runtime does *not* also provide — i.e. the truly Node-only ones (`process`, `Buffer`, ...), computed as `globals.node` minus `globals.worker` from the `globals` package. Web-standard globals (`fetch`, `URL`, `crypto`, streams) survive because they're in `globals.worker`. Plus `import/no-nodejs-modules`. Keeps `src/` runnable on edge/workers/bun; the test override re-allows Node (Vitest runs on Node). **Remove these two rules for `cli`/`app` kinds**, where Node APIs are expected.
- **Test overrides:** relax `no-console`, re-allow Node, and enable the `vitest` plugin under `**/__tests__/**`.

Do not ship a project with only the default `correctness` category — fill the template so the project starts with the full opinionated set.

Requires the Node-based `oxlint` (TS config) on Node 22.18+, which this stack already uses. Formatting (incl. EventKit-style import ordering + comment wrapping) is owned by `oxfmt.config.ts`, not the linter.

## How This Skill Works

1. **Run the questionnaire** (below). Ask only what you can't infer; use defaults for the rest.
2. **Resolve the plan** — decide project kind, layout, and which **addons** to apply.
3. **Scaffold** — follow `workflows/bootstrap-project.md`: copy the base tree from `templates/<kind>/`, resolve placeholders, then apply each requested addon per its `addons/<name>/INSTALL.md`.
4. **Verify** — run the quality gates and report what passed.

Do not generate files before the questionnaire is answered (or sensibly defaulted). A bootstrap is a set of long-lived decisions; get them right up front.

## Questionnaire

Ask these in one batch. Anything the user already told you, don't re-ask. Anything unspecified, apply the default and state the assumption.

1. **Project name & npm scope** — e.g. `acme` / `@acme/core`. (no default — must ask if unknown)
2. **Project kind** —
   - `single` — one publishable package (default for "a library"),
   - `monorepo` — multiple packages under `packages/*`,
   - `app` — an application (no publish fields, looser export rules),
   - `cli` — a binary with a `bin` entry.
3. **What does it do?** — one-line purpose, used for README + package description + the first primitive's name.
4. **Publishable?** — yes/no. Drives `package.json` `exports`/`files`/`publishConfig` and whether the `changesets` addon is applied. (default: yes for `single`/`monorepo`, no for `app`)
5. **Module format** — `dual` (ESM + CJS) or `esm` (ESM-only)? (default: `dual`). For `esm`: set `format: ["esm"]` in `tsdown.config.ts` and drop the CJS pieces from `package.json` (`main` + the CJS `default` conditions in `exports`); keep `module`/`types`/the `import` condition. ESM-only is simpler and smaller but excludes consumers still on `require()`.
6. **Test style** — Vitest behavioral only, or behavioral + type-level (`expectTypeOf` / `Equal`/`Expect`)? (default: both)
7. **Addons** — which of `changesets`, `ci`, `precommit`, `knip`, `ci-environments`, `examples` to apply (see `addons/`). Defaults: `ci` + `precommit` on; `changesets` on if publishable; `knip` on for libraries (consider off for early, churny apps); `ci-environments` + `examples` off unless asked.
8. **Other extras** — TypeDoc docs site, `.vscode` settings. (default: docs only if publishable library)

If `monorepo`, also ask: **which initial packages** to create (names + one-liners).

Echo the resolved plan back as a short bullet list before scaffolding, so the user can correct it cheaply.

## Project Kinds → Layout

### `single` (publishable library)

Base tree (`templates/single/`) — addons add files on top (marked `(+addon)`):

```text
<repo>/
  src/
    index.ts              # public export surface (the API contract)
    <feature>.ts          # one concept per file
    <group>/index.ts      # sub-barrels for coherent groups
    utils/                # small, generic helpers only
  __tests__/
    <feature>.spec.ts
  contributing/           # module-organization.md, testing.md  (releasing.md via changesets addon)
  AGENTS.md               # points agents at contributing/
  CLAUDE.md               # symlink -> AGENTS.md
  package.json
  tsconfig.json
  tsdown.config.ts
  vitest.config.ts
  oxlint.config.ts  oxfmt.config.ts
  .nvmrc  .editorconfig  .gitignore
  README.md
```

### `monorepo`

Base tree (`templates/monorepo/`) — addons add files on top (marked `(+addon)`):

```text
<repo>/
  packages/
    <pkg-a>/              # each: src/, __tests__/, package.json, tsconfig.json, tsdown.config.ts, vitest.config.ts
    <pkg-b>/
  contributing/           # module-organization.md, testing.md  (releasing.md via changesets addon)
  AGENTS.md  CLAUDE.md          # CLAUDE.md is a symlink -> AGENTS.md
  pnpm-workspace.yaml     # workspaces + supply-chain hardening
  turbo.json              # task graph + caching
  package.json            # root: scripts + devDeps only, private: true
  tsconfig.base.json      # shared strict baseline, packages extend it
  vitest.config.ts        # root config (watch across packages)
  oxlint.config.ts  oxfmt.config.ts
  .nvmrc  .editorconfig  .gitignore
  README.md
```

## Repo-Root Files

The base templates are two ready-to-copy project trees — copy the one matching the project kind as the new project root, replace placeholder tokens, then apply addons:

| Project kind | Copy this tree | Notes |
| --- | --- | --- |
| `single` | `templates/single/` | one publishable package at the repo root |
| `app` | `templates/single/` | then strip `exports`/`files`/`publishConfig` from `package.json`; remove the portability rules from `oxlint.config.ts` |
| `cli` | `templates/single/` | then add `"bin"` + uncomment the cli entry/`hashbang` in `tsdown.config.ts`; remove the portability rules from `oxlint.config.ts` |
| `monorepo` | `templates/monorepo/` | root config + `packages/__PKG_DIR__/` exemplar; copy that package dir per workspace package |

Each base tree contains its config (`package.json`, `tsconfig`, `tsdown.config.ts`, `vitest.config.ts`, `oxlint.config.ts`, `oxfmt.config.ts`, dotfiles), source skeleton (`src/`, `__tests__/`), and project docs (`README.md`, `AGENTS.md`, `CLAUDE.md`, `contributing/{module-organization,testing}.md`). The monorepo tree also has `pnpm-workspace.yaml`, `turbo.json`, and `tsconfig.base.json`. **CI, Changesets, knip, and the pre-commit config are addons** (`addons/`), applied after copying — see the Stack → Addons table.

See `references/repo-root.md` for what each file is for and how the pieces fit together, `templates/README.templates.md` for the tree layouts + placeholder tokens, and `addons/README.md` for the addon index. `AGENTS.md` is a short pointer that directs agents to the `contributing/` guidance; `CLAUDE.md` is a **symlink to `AGENTS.md`** (single source of truth, no second file to maintain).

## Routing

| User intent | Go to |
| --- | --- |
| Stand up a new project end-to-end | `workflows/bootstrap-project.md` |
| Apply an opt-in capability (CI, changesets, knip, precommit) | `addons/<name>/INSTALL.md` (index: `addons/README.md`) |
| Decide per-file/module layout, barrels, exports | `templates/single/contributing/module-organization.md` |
| Understand the root config files | `references/repo-root.md` |
| Choose / justify the stack | `references/stack-rationale.md` |
| Write the actual code inside | `typescript-best-practices` skill |

## Quality Gates

After scaffolding, the project must pass:

```bash
pnpm install
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
# + pnpm check:exports   (only if the knip addon was applied)
```

Run the subset relevant to what was generated and report results. If a gate can't run (e.g., no network for install), say so explicitly rather than claiming success.

## Bootstrap Checklist

Before declaring the project ready:

- [ ] Questionnaire answered or defaulted, plan echoed back and confirmed.
- [ ] Layout matches the chosen project kind.
- [ ] `src/index.ts` exports only the intended public surface.
- [ ] Root config files present and internally consistent (paths, exports, build output align).
- [ ] Strict TS baseline in place (`strict: true`, see `typescript-best-practices`).
- [ ] `package.json` `exports`/`main`/`module`/`types` match tsdown output (publishable kinds).
- [ ] `oxlint.config.ts` ships the required opinionated defaults (not bare `correctness`), including `typescript/no-explicit-any` and type-aware linting.
- [ ] Runtime-portability rules present for library kinds (`no-restricted-globals` from `globals.node` + `import/no-nodejs-modules`); **removed for `cli`/`app`**.
- [ ] Stricter TS flags present (`noUncheckedIndexedAccess`, `noImplicitOverride`, `verbatimModuleSyntax`).
- [ ] Module format matches the questionnaire (dual vs ESM-only); `tsdown.config.ts` + `exports` agree.
- [ ] `sideEffects: false` + `publishConfig.provenance: true` on publishable packages; `publint`/`attw` enabled in `tsdown.config.ts`.
- [ ] Monorepo: `turbo.json` present and root scripts run via `turbo run`.
- [ ] `contributing/{module-organization,testing}.md` scaffolded, linked from `AGENTS.md`.
- [ ] `CLAUDE.md` is a relative symlink to `AGENTS.md` (`readlink CLAUDE.md` → `AGENTS.md`), not a copy.
- [ ] Tests scaffolded and runnable (behavioral; type-level if selected).
- [ ] **Requested addons applied** per their `INSTALL.md` (defaults: `ci` + `precommit`; `changesets` if publishable; `knip` for libraries), and reflected in `package.json` scripts/devDeps + `AGENTS.md`.
- [ ] Quality gates run; results reported honestly.
