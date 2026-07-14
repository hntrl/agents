# Module Organization

How code is organized *inside* a package in this project: where modules live,
how they split, and how public APIs are exported. This is the sensible default
for the repo — follow it unless there's a documented reason not to.

## Core Principles

- Organize around stable concepts, not around implementation accidents.
- Keep modules small: one primary concept (a class, function, primitive, adapter, or utility) per file.
- Make public API surfaces deliberate. A barrel file is an API contract, not a convenience dump.
- Keep internal helpers internal until there is a real composition need.
- Generated output belongs outside source directories.

## Package Layout

For a package (standalone or inside a monorepo):

```text
packages/<package-name>/   # or the repo root for a single-package project
  src/
    index.ts              # public export surface
    <feature>.ts          # main feature modules
    <feature-group>/
      index.ts            # grouped public exports
      <feature>.ts        # one concept per file
    utils/
      <small-helper>.ts   # generic helpers only
  __tests__/
    <feature>.spec.ts
  package.json
  tsconfig.json
  tsdown.config.ts
```

> Note: `src/` is the default source directory (the most common convention). If
> a package prefers `lib/`, that works too as long as `tsdown` and `tsconfig`
> agree. Keep generated output in `dist/`.

Use this when building reusable libraries. For applications, adapt the idea:
feature boundaries and explicit public surfaces still matter, but package
publishing fields may not.

## Module Boundaries

- Put source code in `src/` (or the package's established source directory).
- Put generated output in `dist/`; never import from `dist/` in source.
- Use `src/index.ts` as the public package barrel.
- Use sub-barrels for coherent groups, e.g. `client/index.ts`, `parsers/index.ts`.
- Keep files focused:
  - one concept (class/function/primitive) per file,
  - one adapter per file,
  - shared type helpers in `utils/types.ts`,
  - shared runtime helpers in targeted `utils/*.ts` files.
- Avoid circular dependencies. If two modules need the same type/helper, move it to a lower-level `utils/` module.

## Export Style

Prefer explicit public exports:

```ts
export * from "./client";
export * from "./parsers";
export * from "./errors";

export { createClient, type ClientOptions, type RequestHandler } from "./client";
```

Rules:

- Use named exports for library primitives.
- Avoid default exports for reusable library APIs.
- Use inline type exports/imports: `import { Foo, type Bar } from "pkg"`.
- Do not export test helpers.
- Do not export implementation-only helpers just because another file might someday use them.
- If an export is internal but needed for docs/build tooling, mark it clearly with TSDoc such as `@internal`.

## Import Organization

Order imports as:

1. external modules,
2. blank line,
3. parent/sibling/index imports.

Example:

```ts
import { z } from "zod";

import { type Result } from "../utils/types";
import { parseConfig } from "./config";
```

Prefer package imports at public boundaries and relative imports inside a package. Avoid deep imports across package boundaries unless they are explicitly exported.

## Public API Barrels

A package `index.ts` should communicate the intended API shape:

```ts
export * from "./client";
export * from "./parsers";

export { ValidationError } from "./utils/errors";
export { createClient } from "./client";
```

Review every barrel change as a public API change:

- Is this stable enough to support?
- Does it expose implementation details?
- Does it create a circular import risk?
- Does it make docs/API generation clearer or noisier?

## Feature Grouping Patterns

### A coherent feature group

Group related single-concept files under a folder with its own barrel:

```text
src/parsers/
  index.ts
  json.ts
  yaml.ts
  toml.ts
```

Each file should export one concept plus any option types specific to it. Shared types for the group belong in `utils/types.ts` or a nearby shared module.

### Core primitives vs. things that use them

Isolate the lower-level building blocks from the higher-level code that consumes them, so the dependency direction stays one-way:

```text
src/core/
  index.ts
  client.ts
  transport.ts
```

Primitives that coordinate shared behavior should not import from the higher-level features that use them.

### Utilities

Use `utils/` for small, generic helpers only:

```text
src/utils/
  array.ts
  errors.ts
  result.ts
  types.ts
```

Do not let `utils/` become a junk drawer. If a helper is only used by one module, keep it local.

## Tests

Mirror source concepts in tests. `<feature>.spec.ts` files are behavior specs;
`issue-{issue#}.test.ts` files are focused regression tests for fixed bugs:

```text
__tests__/
  parsers/
    json.spec.ts
    yaml.spec.ts
  core/
    client.spec.ts
  issue-142.test.ts
```

Guidelines:

- Put tests near the package they validate.
- Name tests after behavior, not implementation files, when that reads better.
- Keep shared test setup explicit, e.g. `__tests__/setup.ts`.
- Do not export production-only internals solely for tests; test through public behavior when possible.

See `contributing/testing.md` for the full conventions: what makes a good test,
the `describe` symbol → grouping → behavior hierarchy, the `.spec` vs `issue-*`
split, and the required per-`test` doc comments.

## Package Metadata

For publishable packages, configure `package.json` deliberately:

```json
{
  "main": "./dist/index.js",
  "module": "./dist/index.mjs",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": {
        "types": "./dist/index.d.mts",
        "default": "./dist/index.mjs"
      },
      "default": {
        "types": "./dist/index.d.ts",
        "default": "./dist/index.js"
      }
    },
    "./package.json": "./package.json"
  },
  "files": ["dist/", "CHANGELOG.md", "LICENSE.md", "README.md"]
}
```

Rules:

- Keep source paths out of published package exports unless intentionally publishing source.
- Include declarations for every public entrypoint.
- Keep `files` narrow.
- Add subpath exports only when they are intended public API.

## Review Checklist

Before finishing an organization/layout change:

- [ ] Source and generated output are separated.
- [ ] Public barrels export only intended APIs.
- [ ] Internal helpers remain internal.
- [ ] Related concepts are grouped coherently.
- [ ] No circular dependencies were introduced.
- [ ] Tests mirror the source concepts they validate.
- [ ] Package `exports`, `main`, `module`, and `types` align with build output.
- [ ] Docs/API generation still sees the intended public surface.
