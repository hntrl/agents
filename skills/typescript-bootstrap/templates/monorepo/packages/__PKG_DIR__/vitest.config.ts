import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: false,
    environment: "node",
    include: ["__tests__/**/*.{spec,test}.ts"],
    typecheck: {
      // Enable type-level assertions (expectTypeOf / Equal-Expect helpers).
      enabled: true,
      include: ["__tests__/**/*.{spec,test}.ts"],
    },
  },
});
