---
name: typescript-best-practices
Apply strict TypeScript library-style best practices, including advanced type-level design. Use when authoring, reviewing, or refactoring TypeScript code; designing public APIs; tightening types; diagnosing TypeScript configuration or compiler issues; or setting up TypeScript lint/build/test conventions. You MUST trigger whenever TypeScript is involved with the work that you do.
---

# TypeScript Best Practices

Use this skill to write idiomatic TypeScript: explicit public APIs, strong generic inference, clear async behavior, and zero tolerance for `any`.

## Non-Negotiables

1. **No `any`. Not in production code, not in tests, not in overload implementations.**
   - Use `unknown` at boundaries.
   - Use generics for value flow.
   - Use type predicates and assertion functions for narrowing.
   - Use `never` for impossible states.
   - If a third-party API forces unsafe typing, isolate it in the smallest possible adapter and narrow immediately.
2. **No type assertions as a shortcut.** Prefer runtime checks and type guards. If an assertion is unavoidable, keep it local, document why, and assert to a precise type, never to `any`.
3. **Public APIs must infer useful types.** Callers should rarely annotate generic arguments manually.
4. **Every exported function/class/type should have a reason to exist.** Keep internals private or unexported unless they support composition.
5. **Tests must prove behavior and type intent.** Runtime tests cover behavior; type-level expectations or compile-time examples cover inference/narrowing.

## Reference Routing

Keep this file as the default guidance. Open a reference only when the task needs its narrower material:

- Open [`references/advanced-types-playbook.md`](references/advanced-types-playbook.md) when designing or debugging custom generics, conditional or mapped types, template-literal protocols, bounded recursive types, typed event/API/builder contracts, or type tests. Do not open it for routine annotations, narrowing, or everyday application code.
- Open [`references/compiler-and-project-diagnostics.md`](references/compiler-and-project-diagnostics.md) when detecting an unfamiliar project setup, diagnosing compiler performance or module resolution, planning an incremental JavaScript migration, deciding whether monorepo project references fit, or selecting reproducible one-shot validation commands. Do not use it as scaffolding guidance or as a replacement for the type rules in this file.
- Consult [`references/tsconfig-strict.example.json`](references/tsconfig-strict.example.json) only while reviewing or adapting an existing TypeScript configuration. It is an example to tailor to the project's runtime, module resolver, emit strategy, libraries, and file layout—not a config to copy wholesale. Read the diagnostics reference first when those choices are unclear.

## Type System Rules

### Strict Compiler Baseline

Use strict TS settings for every package:

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "noImplicitThis": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "strictBindCallApply": true,
    "noFallthroughCasesInSwitch": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noEmitOnError": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

Run typecheck before considering the work complete.

### `unknown` at Boundaries, Narrow Immediately

Use `unknown` for input whose shape is not yet known:

```ts
export function isPromiseLike<T = unknown>(value: unknown): value is PromiseLike<T> {
  return hasProperty(value, "then") && typeof value.then === "function";
}

function hasProperty<K extends PropertyKey>(
  value: unknown,
  key: K
): value is Record<K, unknown> {
  return value !== null && (typeof value === "object" || typeof value === "function") && key in value;
}
```

Do not write:

```ts
function isPromise(value: any): value is PromiseLike<any>;
```

### Prefer Type Predicates for Narrowing APIs

When an API filters or validates values, expose overloads that preserve narrowing:

```ts
export function filter<T, S extends T>(
  predicate: (value: T, index: number) => value is S
): OperatorFunction<T, S>;
export function filter<T>(
  predicate: (value: T, index: number) => boolean
): OperatorFunction<T, T>;
export function filter<T>(predicate: BooleanConstructor): OperatorFunction<T, Truthy<T>>;
export function filter<T>(
  predicate: ((value: T, index: number) => boolean) | BooleanConstructor
): OperatorFunction<T, T> {
  return (source) =>
    new source.AsyncObservable<T>(async function* () {
      let index = 0;
      for await (const value of source) {
        if (predicate(value, index++)) yield value;
      }
    });
}
```

If the implementation type cannot express all overload return types directly, prefer a private helper with a precise generic over weakening the public implementation to `any`.

### Use Utility Types to Encode Semantics

Create small, reusable type helpers instead of repeating ad hoc conditional types:

```ts
type Falsy = null | undefined | false | 0 | -0 | 0n | "";
export type Truthy<T> = T extends Falsy ? never : T;

export type InputTuple<T extends readonly unknown[]> = {
  [K in keyof T]: ObservableInput<T[K]>;
};

export type ObservedValueOf<T> = T extends ObservableInput<infer Value> ? Value : never;
```

Guidelines:

- Use `readonly unknown[]` for tuple constraints.
- Use `infer` for extracting types from generic wrappers.
- Use branded symbols or unique sentinels for internal impossible/empty states instead of overloaded `undefined` meanings.

```ts
const kUnset = Symbol("unset");
type Unset = typeof kUnset;
```

### Overloads for Public API Ergonomics

Use overloads when input options change the return type:

```ts
export function asObservable<T>(opts: { materialize: true }): Observable<Event<T>>;
export function asObservable<T>(opts?: { materialize?: false }): Observable<T>;
export function asObservable<T>(opts?: { materialize?: boolean }): Observable<T> | Observable<Event<T>> {
  return opts?.materialize ? materialize<T>() : dematerialize<T>();
}
```

Rules:

- Put the most specific overloads first.
- Keep implementation signatures safe: use unions and `unknown`, not `any`.
- Ensure overload behavior is covered by tests.

### Preserve `this` Types Explicitly

For callbacks that depend on receiver state, type `this` explicitly:

```ts
export type SubscriberCallback<T, R = void> = (
  this: Subscriber<T>,
  value: T
) => R | Promise<R>;
```

Do not rely on implicit `this`, and do not erase it with arrow functions when the receiver matters.

## Advanced Type-Level Design

Reach for conditional, mapped, template-literal, or recursive types only when they make a public contract safer or more ergonomic. Keep the runtime representation simple, bound recursion, and prove inference with type tests.

- Prefer `satisfies`, `as const`, generic constraints, and built-in utility types before custom type-level machinery.
- Use conditional types with `infer` to extract relationships from existing types rather than duplicating declarations.
- Use mapped types for systematic transformations; key remapping must preserve a comprehensible public surface.
- For recursive types, define a depth limit or a simpler fallback to avoid excessive-instantiation errors and slow editor feedback.
- When compiler performance or module resolution fails, begin with the project’s `typecheck` script (or `tsc --noEmit`), then use `--extendedDiagnostics` or `--traceResolution` only to isolate the cause.

Do not introduce type gymnastics for internal convenience. If an advanced type is hard to explain with one sentence and a type test, prefer a simpler runtime validation or a narrower API.

## Runtime Design Patterns

### Small Composable Primitives

EventKit favors tiny primitives that compose:

- `Observable<T>` represents a value stream.
- `OperatorFunction<T, R>` transforms one observable into another.
- schedulers coordinate async work.
- utilities are pure functions with narrow responsibilities.

When adding functionality, ask:

1. Is this a primitive, an operator, an adapter, or a utility?
2. Can it be expressed as composition of existing primitives?
3. Does it need to be public, or can it stay local?

### Async Generators for Pullable Streams

Use `async function*` when values are produced over time:

```ts
return new source.AsyncObservable<R>(async function* () {
  let index = 0;
  for await (const value of source) {
    yield transform(value, index++);
  }
});
```

Rules:

- Keep cancellation/cleanup in `finally` blocks.
- Avoid unbounded buffers. If buffering is necessary, document the memory behavior.
- Prefer explicit scheduling/backpressure primitives over hidden timers.
- If you use `setTimeout(..., 0)` or microtask tricks, explain why in a comment and test the edge case.

### Resource Cleanup

For APIs that attach listeners or hold external resources:

```ts
async function* listen<T>(target: EventTarget): AsyncGenerator<T> {
  const controller = new AbortController();
  try {
    // attach listeners with { signal: controller.signal }
    while (!controller.signal.aborted) {
      // yield values
    }
  } finally {
    controller.abort();
  }
}
```

Cleanup rules:

- Use `AbortController` where supported.
- Close sockets/streams/event sources in `finally`.
- Ensure cancellation paths are tested.

### Error Handling

- Throw typed domain errors for expected invalid states.
- Use `unknown` in `catch` positions; narrow before reading properties.
- Preserve original errors unless adding clear context.
- Avoid swallowing errors in async work. If a background promise is intentionally observed only for rejection handling, document why.

```ts
export class NoValuesError extends Error {
  constructor() {
    super("Observable completed without emitting a value");
    this.name = "NoValuesError";
  }
}
```

## Code Style

### Imports

Order imports as:

1. external modules,
2. blank line,
3. parent/sibling/index imports.

Alphabetize within groups when practical. Use inline type imports:

```ts
import { AsyncObservable, type OperatorFunction } from "@eventkit/async-observable";

import { type Truthy } from "../utils/types";
import { map } from "./map";
```

### Formatting

Use Prettier-like defaults:

- double quotes,
- semicolons,
- trailing commas where valid in ES5,
- print width around 100,
- no dense clever formatting.

### Comments and Docs

Document exported APIs with TSDoc:

```ts
/**
 * Applies a transformation to each value emitted by the source observable.
 *
 * @param transform Function called with the value and zero-based emission index.
 * @group Operators
 */
```

Use comments for:

- non-obvious async scheduling,
- invariants,
- public API examples,
- edge cases that tests might not make obvious.

Do not comment obvious code. Do not leave stale TODOs without a clear owner or reason.

### Naming

- Types/interfaces: `PascalCase`.
- Functions/operators: `camelCase`.
- Private/internal class fields: prefix with `_` when they reflect internal mutable state, e.g. `_subscribers`.
- Symbols/sentinels: `kName`, e.g. `kUnset`, `kCancelSignal`.
- Generic type parameters should be meaningful when there is more than one: `Value`, `Result`, `Source`, `Input`, not `T1`, `T2` unless the relationship is obvious.

## Testing Standards

Use Vitest-style behavioral tests:

```ts
import { describe, expect, it, vi } from "vitest";
```

Structure tests by behavior:

```ts
describe("filter", () => {
  describe("when predicate is a type guard", () => {
    it("narrows emitted values", async () => {
      // ...
    });
  });
});
```

Test requirements:

- happy path,
- empty input,
- error propagation,
- cancellation/cleanup,
- ordering/concurrency behavior,
- type guard/inference behavior,
- public overload behavior.

No `any` in tests. Use `unknown`, precise unions, `Record<string, unknown>`, or local test interfaces.

For type behavior, prefer compile-time assertions:

```ts
type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2
  ? true
  : false;
type Expect<T extends true> = T;

type _narrowsToString = Expect<Equal<ObservedValueOf<typeof result>, string>>;
```

Or use `expectTypeOf` if the project already includes it.

## Package and Build Conventions

For library packages:

- Use `pnpm` workspaces.
- Build with `tsup` or an equivalent declaration-emitting bundler.
- Publish `main`, `module`, `types`, and `exports` fields deliberately.
- Include only `dist/`, changelog/license/readme files in package `files`.
- Use Changesets for material public changes.

Example package scripts:

```json
{
  "scripts": {
    "build": "tsup",
    "typecheck": "tsc --noEmit",
    "test": "vitest"
  }
}
```

Root-level quality gates:

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Run the subset relevant to the change, and explain if a gate cannot be run.

## Refactoring Checklist

Before finishing TypeScript work:

- [ ] No `any` appears in changed TypeScript files.
- [ ] No new broad type assertions hide unsafe behavior.
- [ ] Public APIs infer types at call sites.
- [ ] Boundary `unknown` values are narrowed by reusable guards.
- [ ] Async resources clean up on completion, cancellation, and error.
- [ ] Tests cover success, failure, edge cases, and type behavior.
- [ ] `pnpm typecheck` passes for affected packages.
- [ ] Formatting/linting pass or remaining issues are explicitly reported.

## Review Heuristics

When reviewing code, flag these immediately:

- `any`, `as any`, `Array<any>`, `Record<string, any>`, `Promise<any>`.
- callbacks without typed parameters where inference is not obvious.
- exported functions returning `unknown` because implementation typing was skipped.
- implementation overloads that erase public overload safety.
- unbounded queues/buffers in async code without documented constraints.
- event listeners, streams, sockets, intervals, or timers without cleanup.
- tests that only assert output but not cancellation/error/type behavior.

Preferred replacement patterns:

| Anti-pattern | Prefer |
| --- | --- |
| `value: any` | `value: unknown` + type guard |
| `Record<string, any>` | `Record<string, unknown>` or an explicit interface |
| `(...args: any[]) => any` | `(...args: unknown[]) => unknown` or a generic function type |
| `catch (err: any)` | `catch (err: unknown)` + narrowing |
| `as any` | narrow, overload, or introduce a precise helper type |

If preserving compatibility with existing unsafe code, isolate unsafe edges and leave the surrounding code strictly typed. The goal is not merely to satisfy the compiler; it is to make invalid states hard to express.
