---
name: pr-description-generator
description: "Generate a comprehensive Pull Request description for the current branch and optionally create the PR via gh CLI. Use when the user asks to: (1) create a PR, (2) open a pull request, (3) generate a PR description, (4) write a PR body, (5) submit changes for review, or (6) push and create a PR. Trigger on phrases like 'create a PR', 'open a PR', 'make a pull request', 'PR for my changes', 'submit a PR', or 'push and create PR'."
---

# PR Description Generator

Generate a PR description for the current branch and optionally create the PR via `gh pr create`.

## Important Rules

- **Never** add `Co-authored-by` lines attributing an LLM or AI assistant. The PR should read as if a human wrote it.
- Always let the user review and edit the description before creating the PR.
- **Never commit artifacts** like `.pr-description.md`, `.issue-context.json`, `.issue-body.md`, etc. Only commit actual source code changes.

## Workflow

### 1. Analyze Changes

```bash
BRANCH=$(git branch --show-current)
BASE=$(git remote show origin | grep "HEAD branch" | cut -d: -f2 | tr -d ' ')
git status --porcelain
git diff origin/$BASE...HEAD --name-only
git diff origin/$BASE...HEAD --stat
git log origin/$BASE..HEAD --pretty=format:"- %s"
git diff origin/$BASE...HEAD
```

If not in a git repo or no remote configured, inform the user and stop. Include both committed and uncommitted changes in the analysis.

### 2. Identify Affected Packages

For each changed file, walk up the directory tree to find the nearest `package.json` and read its `"name"` field to determine which packages are affected.

### 3. Generate PR Title

Use conventional commit format: `<type>(<scope>): <description>`

- type: feat, fix, docs, refactor, test, chore
- scope: affected package or area (optional)
- description: imperative mood summary

### 4. Commit Uncommitted Changes

If there are uncommitted source code changes, stage and commit them using the title from step 3, then push.

**Do NOT use `git add .` or `git add -A`.** Explicitly add only the source files that are part of the change. Never stage generated artifacts like `.pr-description.md`, `.issue-context.json`, `.issue-body.md`, or any other non-source files.

```bash
git add path/to/file1 path/to/file2
git commit -m "<title from step 3>"
git push origin $(git branch --show-current)
```

If everything is already committed and pushed, skip this step.

### 5. Generate PR Description

Use this format:

```markdown
## Summary

Fixes #<issue> (if issue context exists)

<2-3 sentence summary of the core change>

## Changes

<Group changes by package/area. Describe what changed and why.
Note any new dependencies, breaking changes, or architectural decisions.>
```

Keep it concise. For large PRs with many files, group by directory and suggest splitting if appropriate. Don't include test plans or other non-code changes in the description. Treat PR descriptions as a whitepaper for the changes -- we should communicate why we're making these changes and what the impact is.

### 6. Save and Let User Review

Save the description to `.pr-description.md`:

```bash
cat > .pr-description.md << 'EOF'
<generated description>
EOF
```

Tell the user:

```
PR description saved to .pr-description.md
Please review and edit the file, then let me know when you're ready to create the PR.
```

**Stop and wait for the user to confirm.** Do not proceed until they say it's ready.

### 7. Create the PR

Once the user confirms, re-read `.pr-description.md` (they may have edited it), then create the PR:

```bash
gh pr create --title "<title>" --body-file .pr-description.md
# Add --draft if the user requests it
```

Display:

```
✅ PR Created!

Branch: <branch> → <base>
Title: <title>
URL: <pr-url>
```
