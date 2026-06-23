---
name: changeset-generator
description: "Generate changeset files for current branch changes in a monorepo. Changesets document changes and determine version bumps (patch/minor/major) when publishing packages. Use when the user asks to: (1) create a changeset, (2) generate a changeset, (3) document changes for release, (4) prepare a version bump, (5) write a changeset file, or (6) summarize branch changes for publishing. Trigger on phrases like 'create changeset', 'generate changeset', 'make a changeset', 'changeset for my changes', 'version bump', or 'document my changes'."
---

# Changeset Generator

Generate a `.changeset/<name>.md` file documenting the current branch's changes for versioning and publishing.

## Workflow

### 1. Analyze Git Changes

```bash
BRANCH=$(git branch --show-current)
BASE=$(git remote show origin | grep "HEAD branch" | cut -d: -f2 | tr -d ' ')
git diff origin/$BASE...HEAD --name-only
git log origin/$BASE..HEAD --pretty=format:"- %s"
git diff origin/$BASE...HEAD
```

If not in a git repo or no changes exist from base branch, inform the user and stop.

### 2. Identify Affected Packages

For each changed file, walk up the directory tree to find the nearest `package.json` and read its `"name"` field. This is the affected package.

```bash
# For each changed file path, find the nearest package.json
dirname <changed-file> | xargs -I{} sh -c 'cd {} && while [ ! -f package.json ] && [ "$PWD" != "/" ]; do cd ..; done && cat package.json' | jq -r '.name'
```

Deduplicate the results. Only include packages with actual source code changes. Ignore test-only, docs-only, examples, and internal tooling changes — inform the user no changeset is needed for these.

### 3. Determine Bump Type

For each affected package:

- **major**: Breaking changes (removed/renamed APIs, changed signatures). Look for `BREAKING CHANGE` in commits.
- **minor**: New features (new functions, options, exports). Look for `feat` prefix in commits.
- **patch**: Bug fixes, internal refactors. Look for `fix` prefix in commits.

If uncertain, describe the changes and ask the user to decide. If you're torn between minor and patch, bias towards patch. YOU SHOULD NEVER USE MAJOR.

### 4. Check Existing Changesets

```bash
ls .changeset/*.md 2>/dev/null | grep -v README.md
```

If changesets exist, show them and ask the user whether to add a new one, edit an existing one, or skip.

### 5. Write the Changeset

Generate a unique filename from the branch name or a short slug. Write the file:

```bash
cat > .changeset/<filename>.md << 'EOF'
---
"package-name": patch
---

fix(scope): brief description of the change
EOF
```

Format rules:
- Frontmatter lists each affected package with its bump type
- Summary uses conventional commit style
- Add bullet points for additional detail only when needed

### 6. Confirm

Display a summary:

```
✅ Changeset created: .changeset/<filename>.md

Packages:
  - <package>: <bump>

Summary: <description>
```
