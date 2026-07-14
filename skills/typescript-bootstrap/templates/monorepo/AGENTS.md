# AGENTS.md

Guidance for AI agents (and humans) working in this repository.

## Project

__PKG_NAME__ — __PKG_DESC__

A pnpm monorepo; packages live under `packages/`. Each package follows the same
internal layout (`src/`, `__tests__/`, its own `tsconfig.json` extending the
root `tsconfig.base.json`, and `tsdown.config.ts`).

## Contributing guidance

Before making changes, read the contributing docs in [`contributing/`](./contributing/):

- [`contributing/module-organization.md`](./contributing/module-organization.md) — how code is organized inside packages: source layout, module boundaries, export style, import order, public API barrels, and the review checklist. **This is the sensible default for the repo; follow it.**
- [`contributing/testing.md`](./contributing/testing.md) — test layout, what to cover, and conventions.

When adding files or shaping public APIs, conform to the module-organization
conventions rather than inventing a new structure.

## Stack  

- Package manager: pnpm (workspaces)
- Monorepo orchestration: Turbo (`turbo run <task>`)
- Language: TypeScript (`strict: true`)
- Build: tsdown (rolldown + oxc), per package
- Lint: oxlint (`oxlint --type-aware`) at the root
- Format: oxfmt at the root
- Test: Vitest, per package

## Quality gates

Run the relevant subset before considering work done:

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```
