# Compiler and Project Diagnostics

Use this reference for project discovery, compiler performance, module resolution, migration planning, or monorepo/project-reference decisions. It intentionally does not repeat everyday typing rules, advanced type patterns, package scaffolding, or general lint/build recommendations from the parent skill.

## Detect the Existing Setup First

Do not impose a new layout or toolchain before inspecting the repository.

1. Read the nearest `package.json`, `tsconfig*.json`, workspace manifest, and package-level configs.
2. Prefer existing scripts (`typecheck`, `test`, `build`) over raw tool invocations.
3. Record the installed Node and TypeScript versions; compiler behavior and available options depend on them.
4. Detect the module system from `package.json#type`, `compilerOptions.module`, `moduleResolution`, file extensions, and the actual runtime/bundler.
5. Detect monorepo markers such as `pnpm-workspace.yaml`, `nx.json`, `turbo.json`, `lerna.json`, root workspaces, and existing `references`.
6. Match the repository's import style and existing `baseUrl`/`paths`; remember that TypeScript path aliases do not rewrite runtime imports.

Useful read-only commands when repository tools are insufficient:

```bash
node --version
npx tsc --version
npx tsc --showConfig
```

`--showConfig` is especially useful with extended configs because it reveals the effective compiler options and file set.

## Start with the Narrowest Reproduction

Run the project's typecheck first. If it fails:

- identify which config and package own the file;
- reproduce with the package-level command rather than checking the whole workspace;
- capture the first causal diagnostic, not only downstream errors;
- use `npx tsc -p path/to/tsconfig.json --noEmit` only when no equivalent script exists.

Avoid watch or serve processes during diagnosis. They are long-lived, may use stale caches, and make results harder to reproduce.

## Compiler Performance Diagnostics

Establish a clean baseline before changing flags:

```bash
npx tsc -p tsconfig.json --noEmit --incremental false --extendedDiagnostics
```

Compare at least `Files`, `Types`, `Instantiations`, memory use, and `Check time`. A high file count points toward an overly broad `include`, generated sources, duplicate type packages, or unintended workspace traversal. Very high types/instantiations often point toward large unions, repeated intersections, recursive conditional/mapped types, or circular constraints.

For deeper analysis:

```bash
npx tsc -p tsconfig.json --noEmit --incremental false --generateTrace .typescript-trace
npx @typescript/analyze-trace .typescript-trace
```

Use the analyzer only if it is already available or the user approves adding/running it. Remove generated trace artifacts after diagnosis unless the project intentionally keeps them.

Common targeted fixes:

- narrow `include` and exclude generated/build output;
- replace repeated large intersections with named interfaces or aliases;
- split very large unions and recursive utilities;
- bound recursion and break circular generic constraints;
- enable `incremental` for normal local/build workflows after measuring a clean baseline;
- use project references where package boundaries are real and builds can be ordered;
- consider `skipLibCheck` only as a measured trade-off for declaration-file checking, not as a fix for errors in application source or incompatible dependencies.

If the language server is slow but command-line checking is not, inspect editor-specific project discovery, inferred projects, and files outside the intended `include` set.

## Common Compiler Failures

### “Type instantiation is excessively deep” or “Excessive stack depth comparing types”

Typical causes are unbounded recursion, recursive constraints, huge distributive unions, or repeated expansion of mapped/intersection types.

Fix in this order:

1. minimize the triggering type and call site;
2. add an explicit recursion depth or terminal fallback;
3. name intermediate computations;
4. stop unwanted distribution by wrapping both sides of a conditional in tuples;
5. simplify constraints or move part of the rule to runtime validation;
6. compare `--extendedDiagnostics` before and after.

See `advanced-types-playbook.md` only if the failure originates in custom type-level machinery.

### “The inferred type of X cannot be named”

This often appears during declaration emit when a public value's inferred type depends on an inaccessible, non-exported, or awkward transitive type.

1. Add an explicit exported return/type annotation at the public boundary.
2. Export the necessary named type from its owning package.
3. Replace value imports used only as types with `import type` where appropriate.
4. Inspect circular package/module dependencies.
5. Use `ReturnType<typeof function>` only when it produces a stable public declaration rather than preserving the same inaccessible dependency.

Do not solve this by weakening the export to `unknown` or by asserting a broad type.

### Missing declarations for a dependency

First check whether the package ships types and whether its `exports` map exposes them. Then check for a matching maintained `@types` package. If neither exists, write the smallest accurate local declaration for the APIs actually used:

```ts
declare module "some-untyped-package" {
  export function parse(input: string): unknown;
}
```

Avoid a blanket module declaration that turns every export into an unsafe type. Validate returned `unknown` values at the boundary.

## Module-Resolution Failures

For “Cannot find module” when the file or package exists, inspect the effective config and trace only the failing import:

```bash
npx tsc -p tsconfig.json --noEmit --traceResolution > resolution.log 2>&1
```

Check:

1. `moduleResolution` matches the runtime or bundler (`node16`/`nodenext` for Node semantics, `bundler` for a compatible bundler workflow).
2. `module`, package `type`, source extensions, and emitted/runtime format agree.
3. The dependency's `package.json` `exports`, `types`, and conditional entries expose the requested subpath.
4. Workspace packages are linked and declare the dependency through the repository's normal workspace protocol.
5. `baseUrl`/`paths` targets exist and are not being mistaken for runtime rewriting.
6. File-name casing matches exactly.
7. The failing source belongs to the intended config and is not being picked up by an inferred or parent project.

TypeScript `paths` aliases affect type resolution only. Ensure the bundler, test runner, and runtime independently understand the same aliases, or prefer resolvable package/relative imports.

Clear caches only after identifying which cache may be stale. Avoid deleting lockfiles or reinstalling dependencies as a first diagnostic step.

## JavaScript-to-TypeScript Migration

Migrate incrementally within the existing build:

1. Establish a green baseline for tests and builds.
2. Add TypeScript without changing module format, bundler, linter, and package layout simultaneously.
3. Use a migration config extending the existing config, typically beginning with `allowJs: true`; enable `checkJs` selectively if the initial error volume is manageable.
4. Include both JavaScript and TypeScript during the transition.
5. Convert leaf modules or stable boundaries first, then move inward.
6. Treat external data and untyped libraries as `unknown`; add runtime guards or precise local declarations.
7. Enable stricter options in measured stages, fixing each category rather than suppressing it.
8. Remove transitional flags and declarations when no longer needed.

Example transitional fragment to merge into—not replace—the existing configuration:

```json
{
  "compilerOptions": {
    "allowJs": true,
    "checkJs": true,
    "noEmit": true
  },
  "include": ["src/**/*.js", "src/**/*.jsx", "src/**/*.ts", "src/**/*.tsx"]
}
```

If `checkJs` creates too much noise, scope it with per-file `// @ts-check` while keeping the migration moving. Do not use broad `@ts-ignore` comments or introduce `any` as a migration shortcut.

Automated migration tools are optional accelerators, not prerequisites. Use only tools already present or approved by the user, review every transformation, and keep validation one-shot.

## Monorepos and Project References

Use project references when packages are meaningful compilation units with explicit dependency direction, independent outputs/declarations, or a need for incremental build ordering. Do not add them merely because a repository contains several folders.

A referenced package generally needs:

- `composite: true`;
- a stable `rootDir` and output/declaration strategy when emitting;
- references to direct TypeScript project dependencies;
- package exports that match emitted files;
- no source-level cycle between projects.

A solution-style root config can contain only references:

```json
{
  "files": [],
  "references": [
    { "path": "./packages/core" },
    { "path": "./packages/ui" },
    { "path": "./apps/web" }
  ]
}
```

Build referenced projects with:

```bash
npx tsc -b --pretty false
npx tsc -b --clean
```

Use `--clean` deliberately; it removes TypeScript build outputs for the referenced graph. Prefer the repository's own clean script when one exists.

Avoid project references when packages are not independently compiled, the bundler owns all graph semantics, or the added declaration/output boundaries would be artificial. In those cases, keep focused package configs or one well-scoped config.

Choose Nx, Turborepo, or another task runner based on existing repository needs; project references solve TypeScript compilation graph problems, not general task orchestration. Do not migrate task runners as part of an unrelated compiler fix.

## Strict Configuration Example

`tsconfig-strict.example.json` is a discussion starting point, not a drop-in config. Before adapting it, decide:

- runtime and module resolver;
- application versus declaration-emitting library;
- whether DOM libraries are available;
- whether a bundler or `tsc` emits files;
- whether tests belong in the checked project;
- whether incremental caches and declaration outputs have approved locations;
- whether `skipLibCheck` is an acceptable measured trade-off.

Prefer extending an existing shared config and changing the smallest relevant options.

## One-Shot Validation

Use project scripts and the repository's package manager. A typical fast-fail sequence is:

```bash
npm run -s typecheck || npx tsc --noEmit
npm test -- --run
npm run -s build
```

Adapt the test command to the installed runner; for example, use `npx vitest run` rather than watch mode. Run build only when outputs, declaration emit, module settings, or build configuration are affected.

For a referenced monorepo, prefer the existing filtered workspace command. If none exists:

```bash
npx tsc -b --pretty false
```

Report exactly which commands ran, their scope, and any command that could not run. Do not claim validation from a watch process or from checking only a different package.
