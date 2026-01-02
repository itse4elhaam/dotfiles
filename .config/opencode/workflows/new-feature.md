# New Feature Workflow

## Overview
Complete workflow for adding new features to dotfiles repository with quality gates.

## Prerequisites
- Feature requirement clearly defined
- Target branch identified (usually `master`)
- No uncommitted changes (clean working directory)

## Stage 1: Planning & Research
**Goal**: Understand requirements and find similar patterns

### Tasks:
1. Use `/study` to analyze existing similar features in codebase
2. Search for best practices: Use `context7` for framework docs
3. Find real-world examples: Use `gh_grep` for production patterns
4. Break down into subtasks: Delegate to `task-manager` for complex features

### Checkpoint:
- [ ] Requirements clear and documented
- [ ] Similar patterns identified
- [ ] Subtasks defined (if complex)
- [ ] Estimated effort and impact

## Stage 2: Branch Creation
**Goal**: Create properly named branch following conventions

### Tasks:
1. Check commit history: `git log --all --format='%an' | sort | uniq -c`
2. Determine naming:
   - Solo work: `feat/feature-name`
   - Collaborative: `feat/elhaam/feature-name`
3. Create branch: `git checkout -b feat/feature-name`
4. Verify: `git branch --show-current`

### Checkpoint:
- [ ] Branch created with correct naming convention
- [ ] Branch pushed to remote (optional)

## Stage 3: Implementation
**Goal**: Implement feature with quality and testing

### Tasks:
1. **For shell scripts**:
   - Use template from `.config/opencode/context/templates/shell-script.md`
   - Follow standards: `set -euo pipefail`, snake_case, quotes
   - Lint continuously: `shellcheck script.sh`

2. **For agent/config files**:
   - Follow existing patterns in codebase
   - Use appropriate temperature settings
   - Document purpose and usage

3. **Parallel execution** (delegate to subagents):
   - Code implementation → `coder-agent`
   - Tests → `tester` or `/dry-run`
   - Documentation → `documentation` agent

### Checkpoint:
- [ ] Feature implemented following project standards
- [ ] Code passes linting (shellcheck for scripts)
- [ ] Edge cases handled
- [ ] Error handling in place

## Stage 4: Testing & Validation
**Goal**: Ensure feature works in all scenarios

### Tasks:
1. Run `/dry-run <scope>` for exhaustive edge case testing
2. Test manually with:
   - Typical inputs
   - Edge cases (empty, null, large values)
   - Error conditions
3. For shell scripts: Test on clean environment
4. For OpenCode changes: Test with actual agent invocation

### Checkpoint:
- [ ] All test scenarios pass
- [ ] Edge cases handled correctly
- [ ] Error messages are clear
- [ ] No breaking changes to existing features

## Stage 5: Documentation
**Goal**: Document feature for users and maintainers

### Tasks:
1. Update relevant files:
   - `AGENTS.md` (if agent/command added)
   - `docs/ai-guide.md` (if system-level change)
   - README in affected directory
2. Add inline comments for complex logic
3. Update context files if needed

### Checkpoint:
- [ ] User-facing documentation complete
- [ ] Technical documentation updated
- [ ] Examples provided where helpful

## Stage 6: UX Review (Optional but Recommended)
**Goal**: Ensure great user experience

### Tasks:
1. Run `/ux-analyze [feature description]`
2. Review UX recommendations
3. Implement critical and high-priority improvements
4. Consider nice-to-have enhancements

### Checkpoint:
- [ ] UX analysis completed
- [ ] Critical UX issues addressed
- [ ] User flow is intuitive

## Stage 7: Code Review & Commit
**Goal**: High-quality, reviewable commit

### Tasks:
1. Review all changes: `git diff`
2. Stage changes: `git add <files>` or `git add -A`
3. Use `/commit` command:
   - CodeRabbit reviews automatically
   - Conventional commit format enforced
   - Past tense required
4. Fix any issues CodeRabbit finds
5. Commit is created automatically

### Checkpoint:
- [ ] Changes reviewed
- [ ] CodeRabbit feedback addressed
- [ ] Commit message follows conventions (past tense)
- [ ] Commit includes all necessary changes

## Stage 8: Pull Request (if collaborative)
**Goal**: Create PR for team review

### Tasks:
1. Push branch: `git push -u origin feat/feature-name`
2. Use `/create-pr <target-branch>` command
3. Ensure PR description includes:
   - What changed
   - Why (motivation)
   - How to test
   - Screenshots (if UI/UX changes)

### Checkpoint:
- [ ] PR created with clear description
- [ ] All CI checks passing
- [ ] Ready for review

## Success Metrics
- Feature works as expected
- No breaking changes
- Code quality maintained
- Documentation updated
- Tests pass
- User experience validated

## Common Pitfalls
1. Skipping shellcheck for scripts → Leads to runtime errors
2. Not testing edge cases → Production bugs
3. Poor commit messages → Hard to understand history
4. Missing documentation → Confusion for future maintainers
5. Not using `/dry-run` → Missing critical edge cases
