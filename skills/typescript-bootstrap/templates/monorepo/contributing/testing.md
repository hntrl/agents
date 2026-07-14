# Testing

How we test in this repo. Tests run on Vitest.

## What makes a good test

Test **behavior through the public interface, not implementation.** Code can be
rewritten entirely; the tests shouldn't have to change as long as behavior holds.

- **Good tests** exercise real code paths through public APIs and read like a
  specification ("emits buffered values on flush"). They survive refactors
  because they don't know about internal structure.
- **Bad tests** are coupled to implementation: they reach into internals, assert
  on private shape, or mock collaborators you own. The tell: a test breaks when
  you rename/restructure something but behavior didn't change.

Guidance:

- Assert observable outcomes (return values, emitted events, thrown errors), not
  the steps taken to produce them.
- Don't export internals just to test them — test through the public surface.
- Prefer real objects over mocks; mock only true boundaries (network, clock, fs).
- You can't test everything — spend effort on critical paths and tricky logic,
  not every theoretical input.
- Write tests one behavior at a time alongside the code (vertical slices), not a
  big batch of imagined tests up front.

## File types: `.spec.ts` vs `issue-*.test.ts`

Two distinct kinds of test file, with different jobs:

- **`<feature>.spec.ts` — the behavior spec.** Drives the intended, top-level
  behavior of a feature/module. This is the living specification: the full
  `describe` hierarchy of what the public API is supposed to do. New features and
  intentional behavior changes land here.
- **`issue-{issue#}.test.ts` — regression tests.** When you fix a bug, add a file
  named for the issue (e.g. `issue-142.test.ts`) that reproduces *just that one
  condition* at the top level. It typically has a single top-level `test` (or one
  small `describe`) pinning the exact thing that regressed. Keep it minimal and
  focused — it exists to fail before the fix and guard against the bug returning,
  not to re-spec the feature.

Rule of thumb: if you're describing what the feature *should do*, it's a `.spec`;
if you're pinning *a specific bug so it can't come back*, it's an `issue-*`.

## Organizing a `.spec.ts`: symbol → grouping → behavior

Structure specs as a three-level `describe`/`test` hierarchy:

1. **Symbol** — the exported thing under test (`describe("createClient", ...)`).
2. **Member** *(classes/objects only)* — one `describe` per public member, named
   for the member (`describe("getUrl()", ...)`). Skip this level for a plain
   function (the function *is* the symbol).
3. **Grouping** — a scenario or mode (`describe("when given a baseUrl", ...)`).
4. **Behavior** — one observable behavior per `test` (`test("resolves relative paths against it", ...)`).

For a **function**, the symbol is the unit — go straight symbol → grouping → behavior:

```ts
import { describe, expect, test } from "vitest";

import { createClient } from "../src/client";

describe("createClient", () => {
  describe("when given a baseUrl", () => {
    /**
     * Relative request paths must resolve against the configured base so callers
     * can pass short paths instead of absolute URLs.
     */
    test("resolves relative request paths against the base", () => {
      const client = createClient({ baseUrl: "https://api.example.com" });
      expect(client.resolve("/users")).toBe("https://api.example.com/users");
    });
  });

  describe("when no baseUrl is given", () => {
    /**
     * Without a base there is nothing to resolve against; passing a relative path
     * is a programmer error and must fail loudly rather than produce a bad URL.
     */
    test("throws on a relative request path", () => {
      const client = createClient({});
      expect(() => client.resolve("/users")).toThrow(/absolute URL/);
    });
  });
});
```

For a **class**, add a member level so each public method/getter gets its own
`describe` under the class — `Client` → `getUrl()` → grouping → behavior:

```ts
import { describe, expect, test } from "vitest";

import { Client } from "../src/client";

describe("Client", () => {
  describe("getUrl()", () => {
    describe("when given a baseUrl", () => {
      /** Relative paths resolve against the configured base. */
      test("resolves relative paths against the base", () => {
        const client = new Client({ baseUrl: "https://api.example.com" });
        expect(client.getUrl("/users")).toBe("https://api.example.com/users");
      });
    });

    describe("when no baseUrl is given", () => {
      /** No base to resolve against — a relative path is a programmer error. */
      test("throws on a relative path", () => {
        const client = new Client({});
        expect(() => client.getUrl("/users")).toThrow(/absolute URL/);
      });
    });
  });

  describe("setHeader()", () => {
    /**
     * Each public member gets its own top-level describe under the class, so the
     * spec maps 1:1 to the public surface and reads as a per-member contract.
     */
    test("overwrites an existing header", () => {
      const client = new Client({});
      client.setHeader("accept", "text/plain");
      client.setHeader("accept", "application/json");
      expect(client.headers.get("accept")).toBe("application/json");
    });
  });
});
```

Notes:

- Use `describe` + `test` (not `it`). One observable behavior per `test`.
- For classes, **one `describe` per public member** under the class symbol; only
  test public members (don't reach into private state).
- Each `test` is self-contained — the hierarchy is for *organization*, not for
  sharing mutable state between tests. Avoid order-dependent tests.
- Name `test`s after the behavior, phrased as an assertion about the system.

## Document every test

Put a short **`/** */` block comment immediately before each `test` block**
explaining what the test represents — the intent/spec it pins, not a restatement
of the code. A reader should understand *why this test exists* without parsing
the assertions.

```ts
/**
 * A drained stream must reject new pushes so callers can't silently lose data
 * after close.
 */
test("rejects push() after drain()", async () => {
  /* ... */
});
```

For `issue-*.test.ts`, the comment should reference the bug it reproduces.

## What to cover

- Happy path and realistic inputs.
- Empty / boundary inputs.
- Error propagation (assert on thrown error type/message, not just that it throws).
- Cancellation / cleanup for anything async or resource-holding.
- Public type behavior, via type-level assertions (`expectTypeOf`) when the point
  of the API is inference or narrowing.

## Conventions

- No `any` in tests — use `unknown` + narrowing, precise unions, or local
  interfaces.
- Keep shared setup explicit (e.g. `__tests__/setup.ts`); avoid hidden globals.
- Tests live in `__tests__/`, mirroring the source concept they validate.

## Running

```bash
pnpm test          # run once
pnpm test:watch    # watch mode
```
