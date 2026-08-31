---
name: using-git-worktrees
description: Git worktrees with explicit location confirmation. Use when creating, moving, relocating, or choosing a directory for a Git worktree.
---

# Using Git worktrees

Keep worktrees outside the main checkout and make their location a human decision.

## 1. Confirm the location

Ask the user where to place the worktree before running any command that creates or moves it. Ask every time, even when the repository already has a worktree convention.

Use the question tool with these choices in this order:

1. `/home/elhaam/workspace/coding/[projectName]/worktrees/` marked `Recommended` - example to look at here is `/home/elhaam/workspace/coding/bluum/worktrees/`
2. `.worktrees/` inside the repository

Allow a custom answer. The first choice is the default, but selection still belongs to the user. Continue only after the user answers.

Completion criterion: the user has selected an explicit worktree root for this operation.

## 2. Choose the destination name

Use `<repository>.<branch>` under the selected root. Replace `/` in the branch name with `-`.

Example:

```text
repository: bluum-medusa
branch: fix/klaviyo-checkout-links
destination: /home/elhaam/workspace/coding/bluum/worktrees/bluum-medusa.fix-klaviyo-checkout-links
```

If the requested destination already exists, ask the user for a different name.

Completion criterion: the destination is unique and names both the repository and branch.

## 3. Preserve Git state

Load `git-master`. Prefix every Git command with `GIT_MASTER=1`.

Before creating or moving a worktree, record:

```bash
GIT_MASTER=1 git worktree list --porcelain
GIT_MASTER=1 git status --short --branch
```

For a new worktree:

```bash
GIT_MASTER=1 git worktree add <destination> -b <branch>
```

For an existing worktree:

```bash
GIT_MASTER=1 git worktree move <source> <destination>
```

Use `git worktree move` rather than a filesystem move. Preserve staged, unstaged, and untracked files. Do not commit them unless the user separately asks for a commit.

Completion criterion: Git registers the worktree at the confirmed destination.

## 4. Verify the result

Run:

```bash
GIT_MASTER=1 git worktree list --porcelain
GIT_MASTER=1 git -C <destination> status --short --branch
```

Compare the final status with the status recorded before the operation. Report the destination and any preserved changes.

Completion criterion: the destination exists, Git lists it, and the worktree's changes match the pre-operation state.
