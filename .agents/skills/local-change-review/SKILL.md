---
name: local-change-review
description: Group uncommitted local changes into small, intentional commits.
allowed-tools: Read, Bash, Grep, Glob, Edit
disable-model-invocation: true
---

# Local Change Review

Review the user's local working tree and turn it into small, intentional, user-approved commits.

This skill is for uncommitted local changes only. Do not use it for reviewing a PR, remote branch, or already-pushed commit series unless the user explicitly asks for that.

## Process

Read and execute one step at a time. Complete the current step fully before reading the next one.

### 1. Inspect repository state

Run:

- `git status --short`
- `git diff`
- `git diff --staged`
- `git ls-files --others --exclude-standard`

Identify:

- unstaged changes
- staged changes
- untracked files
- deleted files
- renamed files, if visible
- current branch
- current `HEAD`

If anything is already staged, treat it as user-owned. Do not unstage, modify, or commit it without explaining what is staged and asking how to handle it.

Completion criterion:

Every local change is accounted for as unstaged, staged, or untracked before grouping begins.

### 2. Group changes by commit intent

Group changes by coherent commit intent, not merely by file, code pattern, or directory.

A group should represent one reason to change the system.

Good group examples:

- add checkout phone validation
- persist selected filters in the URL
- fix loading state on product cards
- rename booking status values across API and UI

Bad group examples:

- all TypeScript changes
- all UI files
- small files
- miscellaneous cleanup

Prefer the smallest coherent commit. Do not split one semantic change merely to reduce file count.

Completion criterion:

Every local change belongs to exactly one proposed group, or is explicitly marked as uncertain.

### 3. Present one group at a time

Present groups one by one, starting with the simplest and lowest-risk group.

For each group, show:

- group name
- files and hunks involved
- reason for the change
- user-facing or system-facing effect
- validation evidence from existing or new tests
- manual UI test steps, when applicable
- risk level: low, medium, or high
- proposed commit message
- any uncertainties

Do not stage anything until the group has been presented.

Completion criterion:

The user has enough context to decide whether this group should be staged, changed, skipped, or split.

### 4. Stage only the approved group

After the user approves staging the group, stage only the hunks that belong to that group.

Prefer the smallest safe staging unit:

1. hunk
2. file
3. directory

Only stage a whole file when every change in that file belongs to the current group.

After staging, run:

- `git diff --staged`
- `git diff`

Verify that:

- the staged diff contains only the approved group
- the unstaged diff still contains all remaining unrelated changes
- no user-owned staged changes were accidentally mixed in

Completion criterion:

The staged diff exactly matches the approved group and excludes unrelated local changes.

### 5. Wait for user review

Show the staged diff summary and proposed commit message.

Then stop.

Do not commit until the user explicitly approves the staged group.

If the user gives feedback:

- address the feedback
- re-check the staged and unstaged diffs
- present the updated staged group again
- wait for approval again

Completion criterion:

The user explicitly approves committing the currently staged group.

### 6. Commit the approved group

Commit only the approved staged group using the approved commit message.

After committing, run:

- `git status --short`
- `git diff`
- `git diff --staged`

Completion criterion:

The commit succeeded, the staging area is clean unless intentionally preserved, and remaining local changes are visible.

### 7. Repeat from inspection

After each commit, start again from repository inspection.

Do not rely on the original grouping plan. Re-group the remaining local changes based on the current working tree.

Continue until there are no local changes left, or the user chooses to stop.

### 8. Final report

When finished, report:

- commits created
- changes intentionally left uncommitted
- validation performed
- areas not tested
- any remaining risks or uncertainties
