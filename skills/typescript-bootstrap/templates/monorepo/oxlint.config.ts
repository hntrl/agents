import globals from "globals";
import { defineConfig } from "oxlint";

// Runtime portability: keep src/ free of Node-only globals so the library also
// runs on edge / workers / bun. We declare CommonJS + Web Worker globals as
// available, and ban every Node global that the worker runtime does NOT also
// provide (i.e. the truly Node-only ones like `process`, `Buffer`).
// Web-standard globals (fetch, URL, crypto, streams, ...) live in
// globals.worker, so they survive the ban.
const workerGlobals = new Set(Object.keys(globals.worker));
const nodeOnlyGlobals = Object.keys(globals.node).filter(
  (name) => !workerGlobals.has(name),
);

export default defineConfig({
  plugins: ["typescript", "unicorn", "import", "oxc"],
  categories: {
    correctness: "error",
    suspicious: "error",
    perf: "warn",
    style: "warn",
  },
  env: {
    es2024: true,
    commonjs: true,
    worker: true,
  },
  options: {
    typeAware: true,
  },
  rules: {
    "typescript/no-explicit-any": "error",
    "typescript/consistent-type-imports": [
      "error",
      { fixStyle: "inline-type-imports" },
    ],
    "no-console": ["warn", { allow: ["warn", "error"] }],
    "no-debugger": "error",
    "eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    "import/no-cycle": "error",
    "no-restricted-globals": ["error", ...nodeOnlyGlobals],
    "import/no-nodejs-modules": "error",
  },
  overrides: [
    {
      files: ["**/__tests__/**", "**/*.{spec,test}.ts"],
      plugins: ["typescript", "unicorn", "import", "oxc", "vitest"],
      env: { vitest: true, node: true },
      rules: {
        "no-console": "off",
        "no-restricted-globals": "off",
        "import/no-nodejs-modules": "off",
      },
    },
  ],
  ignorePatterns: ["dist/", "coverage/", "docs/api/", "node_modules/"],
});
