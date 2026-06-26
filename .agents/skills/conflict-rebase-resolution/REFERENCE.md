# conflict-rebase-resolution — Reference

## Subagent dispatch template (Phase 4)

For each conflicted file, dispatch an `explore` subagent in parallel. Use this exact prompt shape — change only the file path and conflict excerpt:

```
TASK: Analyze a single Git conflict and propose a resolution.

CONTEXT:
- We are rebasing branch <BRANCH> onto origin/<TARGET>.
- File under conflict: <PATH>
- The conflict region is below (between `<<<<<<<` and `>>>>>>>`):

<<<<<<< HEAD
<ours version>
=======
<theirs version>
>>>>>>> origin/<target>

EXPECTED OUTCOME (return exactly this shape, nothing else):
1. semantic_intent_ours: <one sentence — what "ours" is trying to do, in product terms>
2. semantic_intent_theirs: <one sentence — what "theirs" is trying to do>
3. proposed_resolution: <the exact code the merged file should contain at this region>
4. confidence: <one of: high | medium | low | needs-user>
5. confidence_rationale: <one sentence>
6. validation_plan: <one sentence — e.g. "run tsc; call site X must still type-check">
7. conflict_kind: <one of: rename | format | api-shape | logic | contract | data-shape | other>

CONSTRAINTS:
- Read-only. Do not edit any file.
- If both sides change behavior materially, set confidence to "needs-user".
- If the resolution requires deciding between two valid product directions, set confidence to "needs-user".
- If you cannot determine the intent of either side confidently, set confidence to "low".
- Never propose "keep both" unless the two changes are genuinely orthogonal (additive, not competing).

REFERENCE: Use only the file content you can read with the Read tool. Do not invoke other subagents.
```

Dispatch N of these in parallel (one per conflicted file). Collect results, bucket by confidence, present in Phase 5.

## Confidence taxonomy

| Level | Meaning | Action |
|---|---|---|
| high | Mechanical conflict (rename, formatting, import reorder). No semantic question. Resolution unambiguous. | Auto-resolve in rebase. |
| medium | Semantic conflict but one side's intent is clearly the correct end state. Resolution requires care but not a human decision. | Auto-resolve, then manual review after rebase. |
| low | Semantic conflict; agent has a best guess but might be wrong. Resolution possible but should be reviewed by user before push. | Auto-resolve, BUT flag explicitly in the post-rebase report. |
| needs-user | Two valid directions, contract change, or agent lacks confident intent for one side. | Stop. Present choice. Do not resolve until user decides. |

## Validation difficulty rubric

Each conflict gets a validation difficulty tag, used to bucket Phase 5 presentation:

- **easy** — pure refactor / rename; `tsc`/equivalent catches regressions automatically. No manual check needed.
- **medium** — logic change; unit test exists for the affected function. Run that test.
- **hard** — logic change; no direct test exists; manual reproduction needed.
- **runtime-only** — behavior change appears only at runtime under specific input/data. Typecheck won't catch it. Must run a scenario manually.

The Phase 5 plan always surfaces validation difficulty alongside confidence. A `needs-user` decision often coincides with `hard` or `runtime-only` validation.

## Conflict-pattern catalog

| Pattern | How to recognize | Default confidence |
|---|---|---|
| Pure rename | File renames on one side, edits to the file on the other. Both touches trace back to the same logical unit. | high |
| Import path rewrite | Imports/re-exports changed on theirs; ours references old path. | high |
| Formatting / lint autofix | Whitespace, semicolons, quote style. | high |
| API contract change | theirs changed a function signature used by ours. | needs-user (unless change is purely additive) |
| Additive feature | ours adds a new file/function; theirs edits an unrelated part of the file. | high |
| Mutually exclusive edits at the same line | Both sides edit the same lines for different reasons. | needs-user |
| Data/migration schema | Conflicts in `*.sql`, migrations, seed files. | needs-user |
| Lockfile | `package-lock.json`, `yarn.lock`, `Cargo.lock`. | high (regenerate, never hand-merge) |
| Generated files | `*.min.js`, build output, snapshots. | high (regenerate) |
| Config with environment-specific values | Keys for one env vs another. | needs-user |

For lockfiles and generated files, the correct resolution is almost always **regenerate** after rebase completes — never hand-merge and never pick one side's lockfile as-is (can reintroduce stale transitive deps).

## Failure and recovery

### `verify-bak-diff.sh` reports unexpected diff

The script prints:
- `EXPECTED_CHANGES` bucket: hunks attributed to target's new commits, or to our local commits pre-resolution
- `UNEXPECTED_CHANGES` bucket: anything else

Any non-empty `UNEXPECTED_CHANGES` → STOP. Present the hunks to the user. Likely causes:
- A resolution accidentally dropped a hunk
- A `git checkout --ours/--theirs` was used where a semantic merge was needed
- A resolution edited beyond the conflict region

Recovery options to present:
1. Inspect the unexpected hunk with the user and edit manually
2. `git rebase --abort`, return to pre-resolution state, restart with corrected plan
3. `git reset --hard bak/<branch>` to discard the entire rebase (most destructive; confirm with user explicitly)

### Rebase hits a conflict not in the plan

`git rebase --abort` to return to pre-rebase state. Re-run Phase 4 with the newly-discovered conflict added. Re-present plan. Re-confirm.

This is preferable to resolving on the fly — keeps the user's sign-off meaningful.

### Tests fail after rebase

Tests that passed at `bak/<branch>` should still pass. If they fail, it's one of:
1. The target introduced a breaking change that our tests now catch — expected; surface to user, they decide whether to fix tests or revert
2. The rebase resolution broke something not caught by typecheck — surface, re-plan that file
3. A flaky test — rerun once; if still red, treat as real

Never delete or skip a failing test to make the suite green during this workflow.

## Git plumbing reference for rebase workflow

| Goal | Command | Notes |
|---|---|---|
| Dry-run conflict file list (Git ≥2.38) | `git merge-tree --write-tree --name-only origin/<target> HEAD` | Returns conflicted paths without touching working tree |
| Inspect a specific conflict | `git diff --merge -- <path>` or read the file with markers | For dispatching to subagents |
| Start rebase | `git rebase origin/<target>` | Use the remote-tracking ref, not the local copy |
| Continue after resolving | `git -c core.editor=true rebase --continue` | Skips the per-commit editor |
| Skip an empty commit during rebase | `git rebase --skip` | Use only if a local commit became empty after rebase (was fully merged) |
| Abort everything | `git rebase --abort` | Returns to pre-rebase HEAD — the same SHA as `bak/<branch>` |
| List current conflicts during rebase | `git diff --name-only --diff-filter=U` | Use to drive per-file resolution iteratively |
| Push the current branch (Phase 2) | `git push` | Only Phase 2; never after rebase without user ok |

## Why rebase, not merge?

This skill is named *rebase* resolution because:
- A merge commit hides what was actually resolved (it's all in one merge diff)
- Rebase replays each local commit on top of the target, surfacing conflicts at the exact commit where they originate — easier to attribute and validate
- The `bak/<branch>` safety net makes the rebase reversible, removing the usual objection ("rebases lose history")

If a user insists on a merge workflow, do not run this skill — direct them to a different resolution approach, since the verify-bak-diff and plan-then-execute structure assumes rebase semantics.