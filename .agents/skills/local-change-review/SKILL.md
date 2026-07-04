---
name: local-change-review
description: Reviews uncommitted local changes by grouping related diffs into logical change-sets, staging each group, then writing a per-group explanation covering what changed, UX impact, why, and how it was verified. Use when the user asks to "review local changes", "walk through my diff", "group and explain my changes", "review staged/unstaged changes before commit", or wants a structured per-change narrative of the working tree.
allowed-tools: Read, Bash, Grep, Glob, Edit
---

# Local Change Review

Walk through the working tree (unstaged + staged) and produce a staged group plus a written explanation per logical change. The goal is legibility, not commits — only the index changes; the working tree is never touched.

**Group by intent, not by file.** Two unrelated bug fixes are two groups even if they're both `fix:`. A rename plus an in-place edit inside the renamed file are two groups — the rename is `refactor:`, the edit is whatever it actually does. When two files look like one group but might not be, split them and let the user merge. Present the numbered group list to the user for a sanity check before staging anything.

**If `git status` shows unmerged paths, a merge/rebase/cherry-pick in progress, or anything that isn't a clean working tree, bail.** Direct the user to `conflict-rebase-resolution`. Also bail and warn loudly if any path looks like a secret — `.env*`, `*.pem`, `*.key`, a long-lived token in code — do not stage it.

For each group, in order: `git reset` to clear the index (never `--hard`), `git add` only this group's paths (never `git add -A` or `git add .`), then `git diff --staged` to capture the staged diff. Leave the group staged. Move to the next group. A path that is both staged and unstaged means the user staged an earlier version and edited further — treat the staged state and the remaining unstaged delta as two separate groups and surface this clearly.

For each group, write:

```
## Group N: <one-line intent>
Type: <refactor|fix|feat|config|docs|chore|mixed>
Files: <list>

### What changed
<2-5 sentences. Concrete: what moved/renamed/added/removed. No "improved the code".>

### UX / behavior impact
<What a caller/user observes. "No observable change — internal only" if none. Before/after if behavior changed.>

### Why
<Reason this change exists. Reference the bug/PRD/migration/smell. If you can't infer it, write "Unknown — flagging for user." Do not invent.>

### How verified
- Tests: <files run, command, pass/fail — or "none run">
- Manual: <how to verify, or "not verified — recommend manual check">
- Static: <typecheck/lint output, or "not run">
```

The **Why** is the part that matters most. If you don't know, say so — never confabulate a plausible-sounding reason. The **How verified** section is required even when the answer is "none run"; never skip it, and never claim a change is verified when you only observed it ran without errors.

After the last group, write a final summary: total groups, total files, LOC added/removed; call out any group whose Why was inferred (flagging for user confirmation); list any files left unstaged and not part of any group as orphans.

Never commit, push, amend, or modify working-tree files. If you can't cleanly stage a group because Git records it as one hunk (a rename that also edits the file), merge the groups and note the merge in the explanation block.