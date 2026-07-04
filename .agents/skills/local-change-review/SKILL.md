---
name: local-change-review
description: A way to review local changes by grouping them into similar patterns, staging them and waiting for user feedback.
allowed-tools: Read, Bash, Grep, Glob, Edit
---

# Local Change Review

Study the local diff using `git diff` and determine the patterns of these changes. Then group the changes to help the user understand the intent and method behind them. Present every group to the user ONE BY ONE starting with the simplest one first.

For each presented group, stage the relevant files - the less files, the better/group, for the group, state the reason behind the change, how it affects the user experience and how it is being validated by any existing or new test (and what that test tests) - and how to test this through the UI.

After staging the changes, wait for the user to review the changes and address any feedback provided. After user's approval, commit this group.

Once the commit goes through, repeat the process from the start until everything is reviewed and then commited by the user.

