---
name: local-change-review
description: Reviews uncommitted local changes by grouping related diffs into logical change-sets, staging each group, then writing a per-group explanation covering what changed, UX impact, the why, and how it was verified. Use when the user asks to "review local changes", "walk through my diff", "group and explain my changes", "review staged/unstaged changes before commit", or wants a structured per-change narrative of the working tree.
allowed-tools: Read, Bash, Grep, Glob, Edit
---

# Local Change Review

Walk through the current working tree (unstaged + staged changes) and produce a grouped, structured narrative review — one `git add` per group, one explanation block per group.

The goal is not to merge or commit. The goal is to make the intent of each change legible: what changed, why, what UX/behavior is affected, and how (if at all) it was verified.

## When This Skill Activates

- User asks to review local changes, walk through the diff, or explain what they changed
- User wants to prepare a clean staged history before committing
- User is unsure whether their working tree is one logical change or several

## Workflow

### 1. Inspect — do not stage yet

Run in parallel:
- `git status --porcelain=v1` (full working tree state)
- `git diff` (unstaged)
- `git diff --staged` (already staged — keep as-is for the user's existing intent)
- `git log --oneline -5` (recent context)

Record:
- Which paths are staged vs unstaged vs untracked
- Whether the repo is mid-merge, mid-rebase, or has conflicts (BAIL if so — direct user to `conflict-rebase-resolution`)

### 2. Group — by shared intent, not by file

Group changes by **what the change accomplishes**, using the rubric in [REFERENCE.md](REFERENCE.md). Common groups:

- refactor: rename/move with no behavior change
- fix: bug fix (cite the bug being fixed)
- feat: new capability, new surface
- config/infra: build config, env, deps
- docs/tests: docs, tests, comments only
- chore: whitespace, formatting, `.gitignore`

Multiple groups of the same type → split them (e.g., two unrelated `fix:` → group A and group B), identified by the *system affected*, not the type label.

Output a numbered group list with member paths and one-line intent. Present it to the user for sanity-check before staging.

### 3. Stage and explain — one group at a time

For each group:

1. Reset the index to only that group's paths (do NOT touch unstaged paths from other groups):
   - `git reset` (unstage everything, safe — doesn't touch working tree)
   - `git add <path1> <path2> ...` for this group only
2. Capture the staged diff: `git diff --staged`
3. Write the explanation block (template below).
4. Leave the group staged. Move to next group.

If a group's change cannot be cleanly staged without another group's paths (e.g., a rename touches both), merge the groups and note the merge.

### 4. Per-group explanation block

For each group, produce:

```
## Group N: <one-line intent>
Type: <refactor|fix|feat|config|docs|chore|mixed>
Files: <list>
Staged diffstat: <8 lines max>

### What changed
<2-5 sentences. Concrete. No "improved the code" — say what moved/renamed/added/removed.>

### UX / behavior impact
<What a user or caller of this system will observe. If none, state "No observable UX change — internal only." If behavior changed, describe the before/after.>

### Why
<The reason this change exists. Reference the bug, the PRD, the migration, or the code smell that motivated it. If you can't infer the why, say so — do not invent.>

### How verified
- Tests: <list test files run, command run, pass/fail — or "none">
- Manual: <how one would manually verify, or "not verified — recommend manual check">
- Static: <typecheck/lint output, or "not run">
```

### 5. Final summary

After the last group, emit:
- Total groups, total files, total LOC (added/removed)
- Any group whose **Why** was inferred (flag for user confirmation)
- Any file left **unstaged** and not part of any group (list them — these are orphans)
- A note that nothing was committed and the index now reflects the last group; user can `git reset` to clear

## STOP conditions

- Repo is mid-merge/rebase/cherry-pick → do not run; redirect to `conflict-rebase-resolution`.
- Working tree contains a `git` command's lockfile or `.git/index` issues → bail with the exact error.
- A change appears to be a secret/credential (long-lived token, private key, `.env`) → stage it as its own `chore/secrets` group ONLY if user has explicitly asked for this review; otherwise skip staging and warn loudly.

## MUST DO

- Use `git reset` (no `--hard`, no `--keep`) to clear the index between groups — never `git checkout --` or `git restore` on working tree files
- Preserve the working tree exactly — only the index changes
- Keep each explanation block to the template; no freeform prose outside the headings
- If you can't tell whether two files belong to the same group, default to splitting them and let the user merge

## MUST NOT DO

- Do not commit, push, or amend
- Do not run `git add -A` or `git add .`
- Do not modify, write, or delete any working-tree file
- Do not invent a "Why" — if you don't know, say so
- Do not skip the verification section even if it's "none" — state it explicitly

## Quick example invocation

```
User: review my local changes
Agent: [runs git status / diff] → presents 3 groups → user confirms →
       stages group 1, writes explanation → stages group 2, writes explanation →
       ... → final summary, nothing committed
```

See [REFERENCE.md](REFERENCE.md) for the full change-pattern taxonomy and edge cases.