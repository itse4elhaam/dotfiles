---
agent: git
description: Create a pull request from current branch to target branch
---

# Create Pull Request

Create a pull request from the current branch to a specified target branch with intelligent analysis and description generation.

## Usage

```bash
/create-pr <target-branch>
```

## Arguments

- `target-branch` (required): The branch to merge into (e.g., `master`, `main`, `develop`)

## Examples

```bash
/create-pr master
/create-pr develop
/create-pr release/v1.0
```

## Workflow

When you invoke this command with `$ARGUMENTS`, the git agent will:

### 1. Analyze Current State
- Verify you're on a feature branch (not on target branch)
- Check for uncommitted changes
- Ensure branch is pushed to remote
- Get commit history since branching point

### 2. Gather Context
- Read all commits since branch creation
- Analyze changed files
- Review git diff for scope of changes
- Extract conventional commit types

### 3. Generate PR Description
Create comprehensive PR description including:

#### Title
- Generated from branch name and commit messages
- Follows conventional commit format
- Example: `feat: Added JWT authentication with comprehensive testing`

#### Description Sections

**What Changed**:
- Summary of all changes by category (feat, fix, refactor, etc.)
- List of modified files by domain

**Why**:
- Motivation from commit messages
- Problem being solved
- Link to related issues (if branch contains issue number)

**How to Test**:
- Step-by-step testing instructions
- Commands to run
- Expected outcomes

**Checklist**:
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented if present)
- [ ] All CI checks passing
- [ ] Follows project coding standards

**Additional Context**:
- Screenshots (prompt if UI/UX changes detected)
- Related PRs or issues
- Migration steps (if applicable)

### 4. Create PR via GitHub CLI
Using `gh pr create`:
```bash
gh pr create \
  --base <target-branch> \
  --head <current-branch> \
  --title "Generated Title" \
  --body "Generated Description"
```

### 5. Post-Creation
- Display PR URL
- Show PR number
- List next steps (e.g., request reviewers, enable auto-merge)

## Prerequisites

- **GitHub CLI** (`gh`) must be installed and authenticated
- Current branch must be pushed to remote
- Must have write access to repository

## Smart Features

### Issue Linking
If branch name contains issue number (e.g., `feat/123-add-auth`):
- Automatically link to issue #123
- Include "Closes #123" in description

### Conventional Commit Analysis
Groups commits by type:
- 🎯 **Features**: All `feat:` commits
- 🐛 **Fixes**: All `fix:` commits  
- 📚 **Docs**: All `docs:` commits
- ♻️ **Refactor**: All `refactor:` commits
- ⚡ **Performance**: All `perf:` commits
- ✅ **Tests**: All `test:` commits

### Scope Detection
Analyzes changed files to determine:
- **Backend changes**: API, database, services
- **Frontend changes**: UI, components, styles
- **Infrastructure**: CI/CD, deployment, configs
- **Documentation**: READMEs, docs folder

### Breaking Change Detection
Scans for:
- Commits with `BREAKING CHANGE:` in body
- API signature changes
- Removed functionality
- Configuration changes requiring migration

Adds prominent warning if found:
```
⚠️ BREAKING CHANGES DETECTED

This PR contains breaking changes that require migration:
- [Description of breaking change]
- [Migration steps]
```

## Example Output

```markdown
## PR Created Successfully! 🎉

**PR #42**: feat: Added JWT authentication with comprehensive testing
**URL**: https://github.com/elhaam/dotfiles/pull/42

**Status**: 
✅ Branch pushed
✅ PR created
⏳ CI checks running

**Next Steps**:
1. Review the PR description: gh pr view 42
2. Request reviewers: gh pr edit 42 --add-reviewer username
3. Monitor CI checks: gh pr checks 42
4. Enable auto-merge (optional): gh pr merge 42 --auto --squash

**PR Description Preview**:
───────────────────────────────────────
# Added JWT authentication with comprehensive testing

## What Changed
🎯 **Features**:
- Implemented JWT token generation and validation
- Added authentication middleware
- Created user session management

🐛 **Fixes**:
- Fixed null pointer in user service

✅ **Tests**:
- Added 45 test cases covering edge cases
- Integration tests for auth flow

📚 **Documentation**:
- Updated API documentation
- Added authentication guide

**Files Changed** (12 files):
- `src/auth/jwt.ts` - JWT utilities
- `src/middleware/auth.ts` - Auth middleware
- `tests/auth.test.ts` - Comprehensive tests
- `docs/authentication.md` - Auth guide
- ... 8 more files

## Why
Current system lacks proper authentication. Users can access protected resources without verification, posing security risk.

This PR implements industry-standard JWT authentication with refresh tokens.

Closes #123

## How to Test
1. Start dev server: `npm run dev`
2. Register user: `POST /api/auth/register`
3. Login: `POST /api/auth/login` → Receive access + refresh tokens
4. Access protected route: `GET /api/protected` with Bearer token
5. Verify token expiration and refresh flow

**Expected**:
- ✅ Valid tokens grant access
- ❌ Invalid/expired tokens rejected with 401
- ✅ Refresh token generates new access token

## Checklist
- [x] Tests added/updated (45 new tests)
- [x] Documentation updated (authentication.md)
- [x] No breaking changes
- [x] All CI checks passing
- [x] Follows project coding standards

## Additional Context
- Using `jsonwebtoken` library (industry standard)
- Tokens expire after 15 minutes (refresh after 7 days)
- Secure httpOnly cookies for refresh tokens
───────────────────────────────────────
```

## Error Handling

### Not on Feature Branch
```
Error: Cannot create PR from master branch
→ Create a feature branch first: git checkout -b feat/your-feature
```

### Uncommitted Changes
```
Error: You have uncommitted changes
→ Commit or stash changes before creating PR: git status
```

### Branch Not Pushed
```
Error: Current branch not pushed to remote
→ Push branch: git push -u origin feat/your-feature
```

### GitHub CLI Not Available
```
Error: GitHub CLI (gh) not found
→ Install: brew install gh
→ Authenticate: gh auth login
```

### No Commits Since Branch Point
```
Error: No new commits since branching from master
→ Make changes and commit before creating PR
```

## Best Practices

1. **Use descriptive branch names**: Helps generate better PR titles
2. **Write clear commit messages**: Used in PR description
3. **Follow conventional commits**: Enables automatic categorization
4. **Include issue numbers in branch**: Enables auto-linking
5. **Review before creating**: Use `git log` and `git diff` first

## See Also

- `/commit` - Commit changes with CodeRabbit review
- Workflow: `.config/opencode/workflows/new-feature.md`
- Git standards: `docs/ai-guide.md` (Git Workflow section)
