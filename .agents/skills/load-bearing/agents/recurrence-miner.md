# Recurrence miner

You find bugs this codebase keeps fixing, within one slice of its history.

**Input:** a commit range.

1. **Collect the fixes.** Every commit in the range that repairs behaviour — by message (`fix`, `bug`, `hotfix`, `revert`) and by diff (a guard, null check, retry, or test added after the fact). Read each diff, not only its message.
   Completion: every commit in the range is either listed as a fix or passed over as not a fix.

2. **Cluster by root cause** — the mistake that let the bug in (unvalidated input, missing tenant filter, timezone handling, a stale cache), never the file it landed in.
   Completion: every fix sits in a cluster or is marked one-off.

3. **Name the control** for every cluster of two or more: the cheapest durable check that would have stopped the next one. A mechanical pattern gets a lint rule or a test; a judgement call gets an `AGENTS.md` line or a skill update.
   Completion: every cluster carries one control and the violating case it would catch.

**Return** exactly this, one block per cluster:

```
cause: <root cause, one line>
commits: <sha> <sha> ...
still open: yes | no — <file:line where the pattern survives today>
control: <lint rule | test | shared helper | AGENTS.md line | skill> — <what it checks>
```

End with the one-off list: `<sha> <one line>`.
