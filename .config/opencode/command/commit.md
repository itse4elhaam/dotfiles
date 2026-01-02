---
description: Analyze staged changes and create conventional commit
agent: build
---

Create a git commit following these STRICT rules:

1. **Check staged files**:
   !`git diff --cached --name-only`

   **If files ARE staged:**
   
   - ✅ STRICT: Commit ONLY the staged files.
   - ❌ DO NOT stage additional files.
   - ❌ DO NOT run `git add`.
   - Proceed with commit using ONLY what is already staged.

   **If NO files are staged:**

   - ⚠️ WARNING: No files are currently staged for commit.
   - Show unstaged files: !`git status --short`
   - Stage ALL modified/untracked files: !`git add -A`
   - Proceed with commit of all changes.

2. **Study author's commit pattern**:
   !`git log --author="<author>" --oneline -10`
   
   Analyze the author's commit message style (verb tense, formatting, scope usage).

3. **Analyze changes**: Study the actual changes below:
   !`git diff --cached`

4. **Commit message format** (Conventional Commits):

   - **Type**: feat|fix|docs|style|refactor|perf|test|chore|ci|build
   - **Scope**: Optional, e.g., `(api)`, `(auth)`
   - **Subject**: Brief (<50 chars), PAST TENSE (e.g., "added feature", "fixed bug"), no period
   - **Body**: Use ONLY if changes need explanation (multi-line OK)
   - **CRITICAL**: Study previous commits by the same author and follow their style/pattern

   NOTE: The git agent has access to context7 for Conventional Commits docs if needed.

   Examples (PAST TENSE):

   - `feat(auth): added JWT token validation`
   - `fix: resolved null pointer in user service`
   - `docs: updated API usage examples`

5. **Quality checks**:

   - Subject is clear and specific (no vague "update" or "fix")
   - Body explains WHY if the change is non-obvious
   - Follows @docs/ai-guide.md: "Keep commit message short and descriptive"
   - MATCHES the author's previous commit style (PAST TENSE)

6. **Execute commit**: Use `git commit -m "<subject>" -m "<body>"` if body needed

Execute the commit immediately after analysis. No user confirmation required.
