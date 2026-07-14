# Bootstrap a New TypeScript Project

End-to-end scaffolding of a new TypeScript project. Run after the
questionnaire in `SKILL.md` is answered (or sensibly defaulted).

Throughout, defer code-authoring decisions to the `typescript-best-practices`
skill. The per-package layout conventions are scaffolded into the project as
`contributing/module-organization.md` (template:
`templates/<tree>/contributing/module-organization.md`); follow that doc when shaping
the seeded structure.

## Phase 1: Intake

**Entry:** User wants a new TS project.

**Actions:**
1. Run the `SKILL.md` questionnaire. Don't re-ask anything already provided.
2. Apply defaults for unanswered items and note each assumption.
3. Resolve the **plan**: project kind, package name(s)/scope, publishable?,
   runtime targets, test style, extras.

**Exit:** Echo the plan back as a short bullet list. Get a yes (or corrections)
before writing files. Treat silence on a defaulted item as acceptance, but make
the default visible.

## Phase 2: Copy the Tree

**Entry:** Plan confirmed.

**Actions:**
1. `ls` the target directory to confirm it's empty / safe to scaffold. If it has
   existing files, stop and ask whether to scaffold-in-place or pick a new dir.
2. Copy the whole tree for the chosen kind into the target directory:
   - `single`/`app`/`cli`: `templates/single/`.
   - `monorepo`: `templates/monorepo/`.
3. For `monorepo`, the tree includes one exemplar package at
   `packages/__PKG_DIR__/`. Rename it to the first package's dir name, and copy
   it once per additional initial package.
4. The base tree is intentionally minimal — CI, Changesets, knip, and the
   pre-commit config are **addons** applied later (Phase 3.5). Add the docs extra
   here if enabled: `templates/typedoc.json` → `typedoc.json`.

**Exit:** A base project tree exists with placeholder tokens still in place.

## Phase 3: Resolve Placeholders & Wiring

**Entry:** Tree copied.

**Actions:** Replace placeholder tokens across all copied files:

| Placeholder | Replace with |
| --- | --- |
| `__PKG_NAME__` | `@scope/name` or bare name |
| `__PKG_DESC__` | one-line purpose |
| `__PKG_DIR__` | monorepo package dir name (also rename the directory) |
| `__NODE_VERSION__` | pinned Node (default `22`, must be 22.18+ for tsdown/oxlint) |
| `__AUTHOR__` / `__LICENSE__` | as provided (default MIT) |
| `__FEATURE__` / `__FEATURE_FN__` | first module basename + symbol (also rename `src/feature.ts` / its spec) |

Then verify the wiring (cross-check against `references/repo-root.md`):
- `package.json` `exports`/`main`/`module`/`types` match `tsdown` output paths
  **and the chosen module format** (dual vs ESM-only: for `esm`, set
  `format: ["esm"]` in `tsdown.config.ts` and drop `main` + the CJS `default`
  conditions from `exports`).
- Monorepo: each package `tsconfig.json` extends `../../tsconfig.base.json`
  (packages stay exactly one level under `packages/`); root scripts run via
  `turbo run`; `turbo.json` is present.
- `oxlint.config.ts` keeps the **required opinionated defaults** (not bare
  `correctness`): see `SKILL.md` → "Linting Defaults".
- `app`: strip `exports`/`files`/`publishConfig` and remove the portability rules
  (`no-restricted-globals` + `import/no-nodejs-modules`) from `oxlint.config.ts`.
  `cli`: add `bin` + uncomment the tsdown cli entry/`hashbang`, and remove the
  same portability rules (a CLI uses Node APIs).
- Publishable packages keep `sideEffects: false`, `publishConfig.provenance: true`,
  and `publint`/`attw` in `tsdown.config.ts`. Keep `typedoc.json` only if the
  docs extra is on.
- `contributing/{module-organization,testing}.md`, `AGENTS.md`, and `CLAUDE.md`
  are already in the tree — keep them; `AGENTS.md` carries `__PKG_NAME__`/`__PKG_DESC__`.
- `CLAUDE.md` must remain a **relative symlink to `AGENTS.md`** (do not edit it
  as a file, and don't substitute tokens into it). If the copy deref'd it into a
  real file, recreate it: `ln -s AGENTS.md CLAUDE.md` then `readlink CLAUDE.md`
  should print `AGENTS.md`.

**Exit:** No placeholder tokens remain; base config files are mutually consistent.

## Phase 3.5: Apply Addons

**Entry:** Base tree resolved.

**Actions:**

1. **Resolve which addons** are in the plan. Defaults (see `addons/README.md`):
   `ci` + `precommit` on; `changesets` on if publishable; `knip` on for libraries;
   `ci-environments` + `examples` off unless asked.
2. **Apply each selected addon by following its `addons/<name>/INSTALL.md`.** The
   INSTALL is the single source of truth for what to copy and which
   `package.json` scripts/devDeps + doc-section edits to make — do not restate or
   improvise those steps; follow the file.
3. **Respect ordering + cross-addon coupling** (this is the part no single INSTALL
   owns):
   - Apply **`knip` before `ci`** — the `ci` workflow includes a `check:exports`
     step only if `knip` is present; drop that step otherwise.
   - **`changesets` + `ci` both selected** → also install `release.yml` from the
     changesets addon (publish automation).
   - **`ci-environments`** ships its own workflow + sentinel; it composes
     alongside `ci` (don't merge their jobs). Add both sentinels as required checks.
   - **`examples`** must be excluded from the lint/knip/test gates (its INSTALL
     adds the ignores) so example churn can't break the library's CI.
4. **Apply each addon's doc edits** to the named sections in `AGENTS.md` /
   `README.md` (each INSTALL's "Docs wiring" says which section — e.g. append a
   bullet under `## Contributing guidance`, add a `## Releasing` section). The
   base docs are addon-agnostic (no markers); edit the real sections.

**Exit:** Requested addons applied; `package.json` scripts/devDeps, workflows, and
docs reflect them.

## Phase 4: First Code + Tests

**Entry:** Config present.

The tree already seeds a placeholder primitive (`src/feature.ts`), its barrel
export, and a spec. Replace the placeholder with the real first primitive.

**Actions:**
1. Flesh out `src/<feature>.ts` (renamed from `feature.ts`) following
   `typescript-best-practices` (strict types, named export, TSDoc on the public
   API, no `any`).
2. Confirm it's exported from `src/index.ts`.
3. Update `__tests__/<feature>.spec.ts`: a happy-path behavioral test, plus a
   type-level assertion if the test style includes it (drop the seeded
   `expectTypeOf` block for behavioral-only).
4. Fill `README.md` "Basic Usage" with a real example for the primitive.

**Exit:** Project has at least one real, tested export.

## Phase 5: Install & Quality Gates

**Entry:** Project authored.

**Actions:** Run, in order, reporting each result:

```bash
pnpm install
pnpm format:check   # or: pnpm format to auto-fix, then re-check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm check:exports  # only if the knip addon was applied
```

- If a gate fails, fix and re-run before moving on.
- If a gate **can't** run (no network for `install`, sandbox limits), say so
  explicitly and run whatever subset is possible. Never claim a gate passed if it
  didn't run.

**Exit:** Gates green (or honestly reported as un-runnable).

## Phase 6: Handoff

**Entry:** Gates done.

**Actions:** Summarize for the user:
- The resolved plan and any defaults applied.
- Tree of what was created.
- Quality-gate results.
- Next steps: `pnpm dev`/`build`, `pnpm changeset` (if the changesets addon was
  applied), how to add a package (monorepo), which addons were applied vs.
  available, pointer to `typescript-best-practices` for writing code and the
  project's own `contributing/module-organization.md` (linked from `AGENTS.md`)
  for growing the layout.

**Exit:** User has a runnable project and knows how to extend it.

## Anti-Patterns to Avoid

- Generating files before the plan is confirmed.
- A barrel (`index.ts`) that re-exports everything including internals — keep it
  an intentional API surface (`contributing/module-organization.md`).
- `package.json` exports that don't match real `dist/` output.
- `any` anywhere in the seeded code (`typescript-best-practices`).
- Applying addons that weren't requested, or hand-rolling an addon's files
  instead of following its `INSTALL.md` (scripts/devDeps drift).
- Leaving an addon half-applied (files copied but scripts/devDeps/`AGENTS.md` not updated).
- Claiming gates pass without running them.
- Reinventing config when a template exists — fill the template instead.
