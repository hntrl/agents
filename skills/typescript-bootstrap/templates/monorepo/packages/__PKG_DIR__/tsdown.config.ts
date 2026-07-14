import { defineConfig } from "tsdown";

export default defineConfig({
  entry: ["src/index.ts"],
  // Dual ESM + CJS by default. For ESM-only, use: format: ["esm"]
  // (also drop "main"/the CJS `default` conditions from package.json exports).
  format: ["esm", "cjs"],
  dts: true,
  sourcemap: true,
  clean: true,
  treeshake: true,
  // Validate the published package against the built output (publishable kinds):
  // publint catches invalid package.json publish fields; attw catches
  // "are the types wrong" under every module-resolution mode.
  publint: true,
  attw: true,
});
