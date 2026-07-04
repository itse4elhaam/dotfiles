---
name: conflict-rebase-resolution
description: Merge target branch by gathering a holistic view of the conflicts followed by a safe and user-aligned rebase.
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Conflict Rebase Resolution

The target branch here refers to the branch provided by the user. If no branch is provided, check if any PR is raised using the current branch, if yes then use the target branch of that PR in this conflict resolution as well. Otherwise, ask the user, donot proceed in this case.

Before starting, check if the current git status is dirty or something is already in progress, if yes then abort the skill execution

These steps must be followed in order.

1. Fetch the latest copy of the branch to merge
2. Pull/Merge the branch into the current branch with rebase false, this gives you and the user a holistic view of the conflicts (if any)
3. Analyze the conflicts and for each of them, use subagents to gather relevant context, then report the resolution strategy to the user with confidence level and the reasoning behind your decision and why the conflict existed in the first place. The purpose of this step is to align with the user completely on the strategy.
4. After locking in the strategy, ABORT the current merge.
5. Create a backup branch from the current branch, use this convention: bak/<current-branch>/<timestamp>
6. Start a rebase against the target branch and resolve the conflicts one by one, if you encounter something that's new and unresolved before, report it to the user and align before proceeding. Once everything is resolved complete the rebase
7. When the rebase is over, compare your current branch against the bak/<current-branch>/<timestamp> branch, the purpose of this is to ensure all the diff was intentional
7. When the 6 is over, state your confidence level, anything unexpected that happened and the risk areas

