import { describe, expect, expectTypeOf, test } from "vitest";

import { __FEATURE_FN__ } from "../src/__FEATURE__";

// Behavior spec for __FEATURE_FN__. Structure: symbol -> grouping -> behavior,
// with a comment before each `test` describing what it pins. See
// contributing/testing.md.
describe("__FEATURE_FN__", () => {
  describe("with any value", () => {
    /**
     * The primitive is identity for now: it must return its argument unchanged
     * so callers can rely on pass-through semantics.
     */
    test("returns its input", () => {
      expect(__FEATURE_FN__(42)).toBe(42);
    });

    /**
     * The return type must track the argument type (generic identity), so call
     * sites get a precise type without manual annotation. (Behavioral-only
     * projects can drop this type-level block.)
     */
    test("preserves the input type", () => {
      expectTypeOf(__FEATURE_FN__("hello")).toEqualTypeOf<string>();
    });
  });
});
