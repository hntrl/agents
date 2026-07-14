# Addon: pre-commit (staged-files lint/format)

Adds a `lint-staged` configuration that runs `oxlint --fix` + `oxfmt` on staged
files. Modeled on langchainjs / flue: **no husky, no top-level `.husky/`
directory**. This is local fast-feedback only — the **`ci` addon owns lint/format
enforcement** (its `check` job runs `pnpm lint` + `pnpm format:check`). The hook
is optional and developer-installed; skipping it never lets a lint error merge.

**Default:** on (the config is cheap and adds no top-level files).
**Depends on:** `oxlint` + `oxfmt` (always in the base tree).

## Files

None to copy — this addon is a `package.json` config block plus a devDependency.
(Optionally, a committed hook script; see below.)

## Reconcile against the base tree

Same for `single` and `monorepo` (in the **root** `package.json`):

1. Add the config block (note: lives inside `package.json`, so it adds **no**
   top-level file):
   ```jsonc
   "lint-staged": {
     "*.{ts,tsx,js,jsx}": ["oxlint --fix", "oxfmt"]
   }
   ```
2. Add the devDependency: `"lint-staged": "^17.0.8"`.

That's the default footprint: a config + one dev dep, no hook installer, no
`.husky/`. `pnpm lint-staged` runs it; CI enforces format/lint regardless.

## Optional: auto-install a git hook (no husky)

If you want the check to run automatically on commit without husky and without a
top-level `.husky/` dir, use git's native `core.hooksPath` pointing at a
committed `.githooks/` directory:

1. Create `.githooks/pre-commit` containing:
   ```sh
   pnpm lint-staged
   ```
2. Add a `prepare` script so clones wire it up:
   ```jsonc
   "scripts": { "prepare": "git config core.hooksPath .githooks || true" }
   ```

This keeps the hook in a single committed dir and avoids the husky dependency.
On Windows the hook still requires a POSIX-capable shell (Git Bash) to run.

## Removing later

Delete the `lint-staged` config block + devDep (and `.githooks/` + the `prepare`
script if you added the optional hook).
