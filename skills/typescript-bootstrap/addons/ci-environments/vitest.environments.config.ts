import { defineConfig } from "vitest/config";

// Runs the existing test suite under multiple JS runtimes/environments.
// Select a project with: vitest --project node | edge | cloudflare
//
// node + edge-runtime + cloudflare all run the *same* specs through Vitest, just
// with a different environment/pool. Bun is handled separately in CI via
// `bunx vitest` (it can't be expressed as a Vitest project; see INSTALL.md).
export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: "node",
          environment: "node",
          include: ["**/__tests__/**/*.{spec,test}.ts"],
        },
      },
      {
        test: {
          name: "edge",
          // requires: pnpm add -D @edge-runtime/vm
          environment: "edge-runtime",
          include: ["**/__tests__/**/*.{spec,test}.ts"],
        },
      },
      // Cloudflare Workers (workerd) — requires:
      //   pnpm add -D @cloudflare/vitest-pool-workers
      // and a wrangler config. Uncomment to enable:
      // {
      //   extends: true,
      //   test: {
      //     name: "cloudflare",
      //     include: ["**/__tests__/**/*.{spec,test}.ts"],
      //     poolOptions: {
      //       workers: { wrangler: { configPath: "./wrangler.toml" } },
      //     },
      //   },
      // },
    ],
  },
});
