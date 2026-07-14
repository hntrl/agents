# __PKG_NAME__

__PKG_DESC__

A pnpm monorepo. Packages live under [`packages/`](./packages/).

## Development

```bash
pnpm install
pnpm dev          # build all packages in watch mode
pnpm test         # run the test suite
pnpm typecheck    # type-only check across packages
pnpm build        # build all packages
```

## Adding a package

Copy an existing package under `packages/<name>/` (each has `src/`,
`__tests__/`, `package.json`, `tsconfig.json` extending the root
`tsconfig.base.json`, and `tsdown.config.ts`). Run `pnpm install` to link it
into the workspace.

## Contributing

See [`contributing/module-organization.md`](./contributing/module-organization.md)
for how code is organized in this repo. Agents should start from
[`AGENTS.md`](./AGENTS.md).

## License

__LICENSE__
