---
description: Analyze staged changes and create conventional commit
agent: build
---

Create a git commit following these STRICT rules:

1. **Check staged files**:
   !`git diff --cached --name-only`

   **If NO files are staged:**

   - ⚠️ WARNING: No files are currently staged for commit.
   - Show unstaged files: !`git status --short`
   - Inform user: "No files are staged. Would you like to commit ALL modified files? This will stage and commit everything shown above."
   - Wait for explicit user confirmation before proceeding with `git add -A`

   **If files ARE staged:**

   - Proceed with commit.

2. **Analyze changes**: Study the actual changes below:
   !`git diff --cached`

3. **Commit message format** (Conventional Commits):

   - **Type**: feat|fix|docs|style|refactor|perf|test|chore|ci|build
   - **Scope**: Optional, e.g., `(api)`, `(auth)`
   - **Subject**: Brief (<50 chars), imperative mood, no period
   - **Body**: Use ONLY if changes need explanation (multi-line OK)

   NOTE: The git agent has access to context7 for Conventional Commits docs if needed.

   Examples:

   - `feat(auth): add JWT token validation`
   - `fix: resolve null pointer in user service`
   - `docs: update API usage examples`

4. **Quality checks**:

   - Subject is clear and specific (no vague "update" or "fix")
   - Body explains WHY if the change is non-obvious
   - Follows @docs/ai-guide.md: "Keep commit message short and descriptive"

5. **Execute commit**: Use `git commit -m "<subject>" -m "<body>"` if body needed

DO NOT commit unless changes are staged and analyzed. DO NOT ask for confirmation - execute the commit.
