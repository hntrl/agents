# Examples

Real, runnable usages of `__PKG_NAME__`. Each subdirectory is one focused,
self-contained example with its own `README` and dependencies.

| Example | Description |
| --- | --- |
| [`basic`](./basic) | Minimal end-to-end usage of the public API |

## Contributing an example

When adding a new example:

- **One use-case per example** — keep it focused; don't build a kitchen sink.
- **Self-contained package** — its own `package.json`, `README.md`, and `src/`.
- **Depend on this library deliberately:**
  - monorepo: `"__PKG_NAME__": "workspace:*"` (linked via the workspace);
  - single repo: pin to a published range, e.g. `"__PKG_NAME__": "^0.1.0"`.
- **Include a `README`** with setup + run instructions.
- **Add tests** only for non-trivial reusable helpers — examples are docs first.
- Examples are **excluded from the library's lint/knip/test gates** (see the
  addon INSTALL), so they won't break core CI; keep them runnable regardless.
- **Follow the structure** of `basic/` as a reference.
