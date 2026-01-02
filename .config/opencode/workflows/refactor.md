# Refactoring Workflow

## Overview
Safe code refactoring with pattern analysis and quality improvement.

## Stage 1: Identify Refactoring Target
**Goal**: Decide what needs refactoring and why

### Triggers:
- Code smells detected
- Duplicate code
- Complex functions (>30 lines)
- Hard to test code
- Performance issues

### Tasks:
1. Use `codebase-pattern-analyst` to identify patterns
2. Use `/clean` command for automated cleanup
3. Document refactoring goals

### Checkpoint:
- [ ] Clear refactoring goal defined
- [ ] Expected benefits articulated
- [ ] Scope bounded (not too large)

## Stage 2: Safety Checks
**Goal**: Ensure safe refactoring

### Tasks:
1. Ensure tests exist (or add them first)
2. Run tests → All passing before refactoring
3. Commit current state → Safety checkpoint
4. Use `/dry-run` to understand current behavior

### Checkpoint:
- [ ] Tests passing
- [ ] Clean commit point exists
- [ ] Current behavior understood

## Stage 3: Refactor
**Goal**: Improve code structure without changing behavior

### Tasks:
1. Make small, incremental changes
2. Run tests after each change
3. Use `reviewer` agent for feedback
4. Follow refactoring patterns from refactoring.guru

### Checkpoint:
- [ ] Code structure improved
- [ ] All tests still passing
- [ ] Behavior unchanged

## Stage 4: Validate
**Goal**: Ensure nothing broke

### Tasks:
1. Run full test suite
2. Use `/dry-run` on refactored code
3. Compare behavior: before vs after
4. Check performance (if relevant)

### Checkpoint:
- [ ] All tests pass
- [ ] Behavior identical to before
- [ ] No performance regression

## Stage 5: Commit
**Goal**: Document the refactoring

### Tasks:
1. Use `/commit` with message:
   - `refactor: extracted auth logic into separate module`
   - Explain why refactoring was needed
2. CodeRabbit review

### Checkpoint:
- [ ] Commit message explains refactoring rationale
- [ ] CodeRabbit approved
