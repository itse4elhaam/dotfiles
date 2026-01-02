# Bugfix Workflow

## Overview
Systematic approach to fixing bugs with root cause analysis and prevention.

## Stage 1: Bug Reproduction
**Goal**: Reliably reproduce the issue

### Tasks:
1. Gather information:
   - What's the expected behavior?
   - What's the actual behavior?
   - Steps to reproduce
   - Environment details
2. Create minimal reproduction case
3. Document the bug in issue/notes

### Checkpoint:
- [ ] Bug reproduced consistently
- [ ] Minimal reproduction case documented
- [ ] Scope of impact understood

## Stage 2: Root Cause Analysis
**Goal**: Understand WHY the bug exists

### Tasks:
1. Use `/study` to understand affected code
2. Trace execution path leading to bug
3. Identify root cause (not just symptom)
4. Check for similar issues elsewhere in codebase

### Checkpoint:
- [ ] Root cause identified (not just symptom)
- [ ] Understand why it wasn't caught earlier
- [ ] Similar issues checked

## Stage 3: Branch Creation
**Goal**: Isolate bugfix work

### Tasks:
1. Create branch: `fix/bug-description`
2. Link to issue if exists (e.g., `fix/123-null-pointer`)

### Checkpoint:
- [ ] Branch created following conventions

## Stage 4: Fix Implementation
**Goal**: Fix root cause, not just symptom

### Tasks:
1. Implement fix addressing root cause
2. Add defensive checks if missing
3. Improve error handling if needed
4. Consider using `/dry-run` to validate fix

### Checkpoint:
- [ ] Root cause fixed (not just patched)
- [ ] Defensive programming added
- [ ] Error handling improved

## Stage 5: Regression Testing
**Goal**: Ensure fix works and doesn't break anything

### Tasks:
1. Test original reproduction case → Should pass
2. Run `/dry-run` on fixed code → All edge cases
3. Test related functionality → No breaking changes
4. Add test case to prevent regression

### Checkpoint:
- [ ] Original bug fixed
- [ ] No new bugs introduced
- [ ] Edge cases handled
- [ ] Regression test added

## Stage 6: Commit & Review
**Goal**: Document the fix properly

### Tasks:
1. Use `/commit` with clear message:
   - `fix: resolved null pointer in user service`
   - Explain what was broken and how it's fixed
2. CodeRabbit review
3. Address any security/performance concerns

### Checkpoint:
- [ ] Commit message explains the fix
- [ ] CodeRabbit approved
- [ ] Ready to merge

## Success Metrics
- Bug no longer reproducible
- Root cause addressed
- Regression test added
- No new bugs introduced
