---
name: conflict-rebase-resolution
description: Resolves merge conflicts via a rebase workflow with a mandatory bak-branch safety net. Creates `bak/<current-branch>`, fetches the target branch, presents a conflict-resolution plan grouped by confidence and validation difficulty, gets user sign-off, then rebase-resolves and verifies the result against the bak branch before pushing. Use when the user is mid-merge / mid-rebase with conflicts, has merge conflicts to resolve, wants to integrate a target branch into theirs safely, asks to "resolve conflicts", "rebase onto <branch>", or wants a guided conflict-resolution flow with a backup.
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Conflict Rebase Resolution

Safe, reversible, user-confirmed conflict resolution via rebase. Two non-negotiable invariants:

1. **A backup branch `bak/<current-branch>` always exists at the pre-resolution state.**
2. **The user signs off on the resolution plan before the rebase begins.**

## When This Skill Activates

- User is mid-merge or mid-rebase with conflicts
- User says "I have conflicts", "resolve these conflicts", "rebase onto main", "integrate <branch>"
- `git status` shows `You have unmerged paths` or `interactive rebase in progress`

## Hard rules (non-negotiable)

- **Never** force-push (`git push --force`, `--force-with-lease`, `-f`). The user must do this themselves, by name.
- **Never** proceed past the plan-presentation step without explicit user sign-off.
- **Never** skip the `bak/<branch>` creation unless the user explicitly says so in this session (carryover consent does not count).
- **Never** delete `bak/<branch>` at the end — the user removes it manually after they're satisfied.
- After rebase, **always** run the bak-diff check (`scripts/verify-bak-diff.sh`) and the test suite before pushing.

## Workflow

### Phase 1 — Preflight (parallel)

Run all of:
- `git rev-parse --abbrev-ref HEAD` (current branch)
- `git status --porcelain=v1`
- `git remote -v`
- `git branch --list 'bak/*'` (existing backups)
- `git log @{u}..HEAD --oneline` (unpushed local commits — if non-empty, we must push first)
- `git rev-parse --abbrev-ref @{u}` (configured upstream)

Check preflight outcomes — bail and tell the user if:
- Detached HEAD (no current branch name) → ask user to attach a branch first
- Working tree is dirty (unstaged or staged, beyond the conflict itself mid-rebase is fine) → ask user to stash or commit
- Not in a git repo → bail
- We are mid-rebase already → continue from Phase 5 below (the bak branch must already exist from earlier — verify and reuse)

### Phase 2 — Push current state and create backup

1. If `git log @{u}..HEAD --oneline` is non-empty:
   - Push the current branch: `git push`
   - If push fails (e.g., remote rejected, permissions) — **stop**, surface the error, ask user.
2. Update upstream of the current branch first if `@{u}` is unset — ask user where it should push, do not guess.
3. Create the backup:
   - If `bak/<branch>` exists locally: `git branch -D bak/<branch>` (user chose option a — unconditional hard delete)
   - `git branch bak/<branch> HEAD` (creates backup at current commit, does not check it out)
   - Verify: `git rev-parse bak/<branch>` must equal `git rev-parse HEAD` before continuing

The skip of the push step is allowed **only** if the user explicitly says "don't push first" or "skip the push" in the current session.

### Phase 3 — Fetch the target and get its latest copy

User names the target branch (e.g., `main`, `develop`). If ambiguous, ask.

- `git fetch origin <target>` (or the appropriate remote — use `git remote -v` to confirm)
- Record `git rev-parse origin/<target>` — this is the rebase target

If a merge is already in progress, abort it now: `git merge --abort` (the user agreed we move to rebase-only workflow by invoking this skill). Confirm with the user before aborting if the merge was started by a different tool — but the default action is abort.

### Phase 4 — Plan conflict resolution

Now do the analysis **before** rebasing. We want the user to sign off on the *plan*, not on a fait accompli.

To get the conflicts without committing to a rebase state, use a dry inspection:
- `git merge-tree --write-tree origin/<target> HEAD` (Git 2.38+) produces conflicted files without touching the working tree. Parse its output for the conflict file list.
- If `merge-tree` is unavailable, fall back to: start rebase, capture the conflict list and `git diff --name-only --diff-filter=U`, then immediately `git rebase --abort` to plan. Re-restart later in Phase 5.

For each conflicted file, dispatch a read-only subagent (`explore`) to gather context in parallel — see [REFERENCE.md](REFERENCE.md) for the dispatch template. Each subagent returns:
- The conflict region(s) in that file
- The semantic intent of "ours" vs "theirs"
- A proposed resolution
- A confidence rating (high / medium / low / needs-user)
- A validation plan (how to verify the merge is correct)
- Whether the conflict is mechanical (rename/format) or semantic (logic/contract)

### Phase 5 — Present plan; get sign-off

Present to user:

```
Conflict resolution plan for rebase of <branch> onto origin/<target>

High confidence (auto-resolve) — N files
  - path/to/file.ts — single rename, no logic; resolution = keep theirs
    validation: tsc passes
  ...

Medium confidence (auto-resolve with care) — N files
  - ...

Low confidence (recommend review) — N files
  - ...

NEEDS USER DECISION — N files
  - path/to/file.ts — conflict at L42-L60: <ours> wants X, <theirs> wants Y.
    Both are valid; the resolution changes public behavior. Please pick:
      A: keep ours (X)  → <impact>
      B: keep theirs (Y)  → <impact>
      C: merge both  → <impact>
```

Then ask: "Ready to start rebase with this plan? Reply YES to proceed, or tell me what to change."

**Do not** proceed to Phase 6 until user explicitly says YES / go / proceed / continue.

### Phase 6 — Execute rebase

1. If not already in rebase: `git rebase origin/<target>`
2. For each conflict, in plan order:
   - Read the marked conflict region
   - Apply the planned resolution (use `Edit`, not `git checkout --theirs/--ours` unless the resolution truly is "take theirs/ours verbatim")
   - `git add <path>` (only this path; do NOT `git add -A`)
   - Continue: `git rebase --continue` (or `git -c core.editor=true rebase --continue` to skip editor)
3. If a conflict was NOT in the plan (new conflict surfaces), STOP — re-run Phase 4 for the new conflict, re-present, re-confirm
4. If rebase fails in a way not covered by conflicts (e.g., hook rejects), STOP and present the error

If the user answered "needs-user decision" items in Phase 5, resolve those per the user's choice.

### Phase 7 — Verify (mandatory, before any push)

Run in order, **all must pass**:

1. `scripts/verify-bak-diff.sh` — compares `HEAD` against `bak/<branch>`:
   - Expected: tree under target's new commits, plus our original local commits; our local commits' *intent* preserved
   - The script surfaces any diff hunk that's in `HEAD` but not explainable by either (a) target's commits or (b) our pre-resolution local commits. **Anything in the "unexpected" bucket is a STOP condition** — present to user, do not push.
2. Run the test suite (project-appropriate: `npm test`, `pytest`, `go test ./...`, etc.). Any failure → STOP, present, do not push.
3. Run typecheck / lint if the repo has them configured. Failures → STOP.

### Phase 8 — Report and stop

Present:
- Rebase completed: `HEAD` is now on `origin/<target>` + our local commits replayed
- `bak/<branch>` is at the pre-resolution state — user can delete it manually when satisfied
- Diff vs bak: summary from `verify-bak-diff.sh` (expected + unexpected buckets)
- Test results
- Recommended next step: `git push` (do NOT run it for the user — the user pushes; this is their verified checkpoint)

If anything in Phase 7 failed: do NOT push. Present the failure, the bak state, and ask how to proceed (options: re-fix, abort rebase via `git rebase --abort` and fall back to `bak/<branch>`, or user takes over).

## STOP conditions

- Preflight bails (above)
- Push of current branch fails (Phase 2)
- User does not sign off (Phase 5)
- New conflict surfaces mid-rebase (Phase 6) — re-plan
- `verify-bak-diff.sh` reports unexpected diff (Phase 7)
- Tests fail (Phase 7)

## MUST DO

- Always dispatch read-only subagents in parallel for conflict context (do not read files serially in the main agent)
- Always verify `bak/<branch>` SHA == HEAD SHA immediately after creating the backup
- Always run `verify-bak-diff.sh` and tests before reporting done
- Always ask the user to name the target branch if ambiguous
- Restore the working tree to clean state if the user aborts mid-flow (`git rebase --abort` then leave `bak/<branch>` in place)

## MUST NOT DO

- Never `git push --force*` of any kind, ever. The user pushes themselves.
- Never `git push` the final result automatically — only the Phase 2 push to capture the current state before backup
- Never delete `bak/<branch>` — that's the user's manual safety release
- Never `git checkout --ours` or `--theirs` as a shortcut when the plan called for a semantic merge
- Never run `git add -A` during rebase — add only the paths you resolved
- Never proceed past sign-off without explicit "yes/proceed/go" from the user

## Quick example invocation

```
User: I have conflicts merging main in
Agent: [preflight] → pushes current branch → creates bak/feature-x →
       fetches origin/main → runs merge-tree → dispatches 4 explore
       subagents in parallel → presents plan with high/med/low/needs-user
       buckets → user picks on needs-user files and says proceed →
       git rebase origin/main → resolves per plan → verify-bak-diff.sh
       → tests → reports; leaves push to user
```

See [REFERENCE.md](REFERENCE.md) for the subagent dispatch template, confidence taxonomy, and conflict-pattern catalog.