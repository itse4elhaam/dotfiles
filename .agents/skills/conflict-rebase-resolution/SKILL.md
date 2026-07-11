---
name: conflict-rebase-resolution
description: Merge target branch by gathering a holistic view of the conflicts followed by a safe and user-aligned rebase.
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Conflict Rebase Resolution

Safely resolve a merge or rebase by building a full picture of the conflicts first, then executing a verified resolution.

**Leading word:** *safety net* — the backup branch and user alignment are your safety net against unintended changes.

## Identify the target

The target branch is the branch the user provides. If no branch is provided, check whether the current branch has an open PR and use its target branch. If neither source gives a target, ask the user.

Completion: the target branch is identified or the user has been asked.

## Pre-flight check

Confirm the working tree is clean — no dirty files or in-progress operations. A clean state is required before starting any merge or rebase.

Completion: `git status` reports a clean working tree.

## Workflow

Execute these steps in order. Complete each step before reading the next one.

1. **Fetch the target.** Pull the latest copy of the target branch.
   Completion: the target branch's remote ref is up to date.

2. **Merge to reveal conflicts.** Merge the target into the current branch with `rebase=false`. This surfaces all conflicts (if any) for a complete picture before any resolution begins.
   Completion: the merge output shows either a clean merge or a full conflict list with no hidden resolutions.

3. **Recon each conflict.** For each conflict, use subagents (explore, librarian) to gather relevant context from both sides. **Treat subagent findings as a starting point, not the final truth.** Always verify subagent output against the actual code — re-read the files, check surrounding context, and confirm the findings. Subagents may miss nuances, misunderstand the conflict, or return incomplete information. After verification, report the resolution strategy to the user with confidence level, the reasoning behind your decision, and why the conflict existed. The purpose of this step is to align with the user completely on the strategy.
   Completion: every conflict has a user-aligned resolution strategy with supporting evidence and confidence level.

4. **Lock the strategy, then abort.** After the user confirms the strategy, abort the current merge with `git merge --abort`.
   Completion: the working tree is back to the pre-merge state with no merge in progress.

5. **Create a safety net.** Create a backup branch from the current branch using the convention: `bak/<current-branch>/<timestamp>`.
   Completion: the backup branch exists and matches the current branch HEAD.

6. **Rebase and resolve.** Start a rebase against the target branch and resolve conflicts one by one using the approved strategy. If a new, previously unseen conflict appears, report it to the user and align before proceeding. Complete the rebase once all conflicts are resolved.
   Completion: the rebase completes successfully with all conflicts resolved.

7. **Verify against safety net.** Compare the current branch against the backup branch (`bak/<current-branch>/<timestamp>`). Confirm every diff is intentional and no changes were lost or introduced accidentally.
   Completion: every difference between the rebased branch and the backup is accounted for and intentional.

8. **Report the outcome.** State confidence level, anything unexpected, and any risk areas the user should know about.
   Completion: the user has a clear picture of the result and any residual risks.

