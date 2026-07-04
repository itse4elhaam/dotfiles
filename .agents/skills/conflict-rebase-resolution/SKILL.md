---
name: conflict-rebase-resolution
description: Resolves merge conflicts via a rebase workflow with a mandatory bak-branch safety net. Creates `bak/<current-branch>`, fetches the target branch, presents a conflict-resolution plan grouped by confidence and validation difficulty, gets user sign-off, then rebase-resolves and verifies the result against the bak branch before pushing. Use when the user is mid-merge / mid-rebase with conflicts, has merge conflicts to resolve, wants to integrate a target branch into theirs safely, asks to "resolve conflicts", "rebase onto <branch>", or wants a guided conflict-resolution flow with a backup.
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Conflict Rebase Resolution

Resolve merge conflicts by rebasing onto the target branch, with a **bak-branch safety net** and a **plan-then-signoff** gate. The result is verified against the backup before any push. The user pushes themselves; you never force-push.

**Invariants.** A `bak/<current-branch>` backup must exist at the pre-resolution state before any destructive action. The user must sign off on the plan before the rebase begins. `scripts/verify-bak-diff.sh` and the project's test suite must pass before any push. Never `git push --force*` of any kind — the user pushes. Never delete `bak/<branch>` — the user removes it manually when satisfied.

**Preflight.** Run `git rev-parse --abbrev-ref HEAD`, `git status --porcelain=v1`, `git remote -v`, `git branch --list 'bak/*'`, `git log @{u}..HEAD --oneline`, and `git rev-parse --abbrev-ref @{u}` in parallel. Bail if detached HEAD, dirty working tree (beyond a mid-rebase conflict state, which is fine), or not a git repo — surface the exact problem and ask the user to resolve it.

**Backup.** If `git log @{u}..HEAD --oneline` is non-empty, `git push` first; if push fails, stop. Skip this push only on an explicit user instruction in this session — carryover consent doesn't count. Then create the backup: if `bak/<branch>` already exists, `git branch -D bak/<branch>` (unconditional hard-delete); then `git branch bak/<branch> HEAD`. Verify `git rev-parse bak/<branch>` equals `git rev-parse HEAD` before continuing — if not, something went wrong, stop.

**Fetch target; abort any merge.** The user names the target branch; ask if ambiguous. `git fetch origin <target>` and record `origin/<target>` as the rebase target. If a merge is in progress, `git merge --abort` — this skill is rebase-only by design.

**Plan before rebasing.** Inspect conflicts without committing to a rebase state: `git merge-tree --write-tree --name-only origin/<target> HEAD` (Git ≥2.38). Fallback: start the rebase, capture `git diff --name-only --diff-filter=U`, then `git rebase --abort` to plan; restart the rebase later. For each conflicted file, dispatch one `explore` subagent in parallel with this prompt shape:

```
TASK: Analyze one Git conflict and propose a resolution.
File: <PATH>. Conflict region:
<<<<<<< HEAD
<ours>
=======
<theirs>
>>>>>>> origin/<target>

Return exactly this shape:
1. semantic_intent_ours: <product-level what "ours" does, one sentence>
2. semantic_intent_theirs: <one sentence>
3. proposed_resolution: <exact code the merged region should contain>
4. confidence: <high|medium|low|needs-user>
5. confidence_rationale: <one sentence>
6. validation_plan: <how to verify; one sentence>
7. conflict_kind: <rename|format|api-shape|logic|contract|data-shape|other>

Rules: read-only. If both sides change behavior materially or you can't determine intent confidently, set confidence to needs-user. Never propose "keep both" unless the two changes are genuinely orthogonal (additive, not competing).
```

**Present the plan and wait for sign-off.** Bucket the resolutions by confidence: **high** (mechanical — rename, import rewrite, formatting — auto-resolve), **medium** (semantic but one side is clearly correct — auto-resolve, review after), **low** (best-guess — auto-resolve but flag explicitly in the final report), **needs-user** (two valid product directions or unclear intent — STOP, present choice A/B/C with impact). Also surface validation difficulty per file (easy / medium / hard / runtime-only). Then ask: "Ready to rebase with this plan? Reply YES to proceed, or tell me what to change." **Do not proceed to the rebase until the user explicitly says yes/proceed/go.**

**Execute the rebase.** `git rebase origin/<target>` (if not already in rebase from the planning fallback). For each conflict, per plan: apply the resolution with `Edit` (use `git checkout --ours`/`--theirs` only when the plan truly was "take theirs/ours verbatim"), then `git add <path>` for only that path — never `git add -A` — then `git -c core.editor=true rebase --continue`. If a conflict NOT in the plan surfaces, `git rebase --abort`, re-run the planning phase with the new file added, re-present, re-confirm — never resolve on the fly. If the rebase fails for non-conflict reasons (hook rejects, etc.), stop and surface the error.

**Verify before any push — all must pass.** Run `scripts/verify-bak-diff.sh <current-branch> origin/<target>`; any non-empty `UNEXPECTED_CHANGES` bucket is a STOP — present those hunks to the user, do not push. Run the project's test suite; any failure is a STOP — never delete or skip a failing test to make the suite green during this workflow. Run typecheck/lint if the repo has them configured; failure is a STOP.

**Report and stop.** Present: the rebase completed (HEAD is on `origin/<target>` plus local commits replayed); the location of `bak/<branch>` for manual cleanup; the diff-vs-bak summary from the script (expected + unexpected buckets); the test results. **Do not push.** Tell the user to push. On any verification failure: do not push, present the failure, the bak state, and options (re-fix / `git rebase --abort` to fall back to bak / user takes over).

Dispatch `explore` subagents in parallel for conflict context — never read files serially in the main agent. If the user aborts mid-flow, `git rebase --abort` and leave `bak/<branch>` in place.