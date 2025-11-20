# Context System Guide

## Quick Reference

**Golden Rule**: Fetch context when needed, not before (lazy loading)

**Key Principle**: Reference files WITHOUT @ symbol - agent fetches only when needed

**Structure**: standards/ (quality + analysis), workflows/ (process + review), system/ (internals)

**Session Location**: `.tmp/sessions/{timestamp}-{task-slug}/context.md`

---

## Overview

Context files provide guidelines and templates for specific tasks. Use lazy loading (fetch when needed) to keep prompts lean.

## Available Context Files

All files are in `.opencode/context/core/` with organized subfolders:

### Standards (Quality Guidelines + Analysis)
- `.opencode/context/core/standards/code.md` - Modular, functional code principles
- `.opencode/context/core/standards/docs.md` - Documentation standards
- `.opencode/context/core/standards/tests.md` - Testing standards
- `.opencode/context/core/standards/patterns.md` - Core patterns (error handling, security)
- `.opencode/context/core/standards/analysis.md` - Analysis framework

### Workflows (Process Templates + Review)
- `.opencode/context/core/workflows/delegation.md` - Delegation template
- `.opencode/context/core/workflows/task-breakdown.md` - Complex task breakdown
- `.opencode/context/core/workflows/sessions.md` - Session lifecycle
- `.opencode/context/core/workflows/review.md` - Code review guidelines

## Lazy Loading (Recommended)

Reference files **WITHOUT** `@` symbol - agent fetches only when needed:

```markdown
"Write code following .opencode/context/core/standards/code.md"
"Review using .opencode/context/core/workflows/review.md"
"Break down task using .opencode/context/core/workflows/task-breakdown.md"
```

**Benefits:**
- No prompt bloat
- Fetch only what's relevant
- Faster for simple tasks
- Agent decides when to load

## When to Use Each File

### .opencode/context/core/standards/code.md
- Writing new code
- Modifying existing code
- Following modular/functional patterns
- Making architectural decisions

### .opencode/context/core/standards/docs.md
- Writing README files
- Creating API documentation
- Adding code comments

### .opencode/context/core/standards/tests.md
- Writing new tests
- Running test suites
- Debugging test failures

### .opencode/context/core/standards/patterns.md
- Error handling
- Security patterns
- Common code patterns

### .opencode/context/core/standards/analysis.md
- Analyzing codebase patterns
- Investigating bugs
- Evaluating architecture

### .opencode/context/core/workflows/delegation.md
- Delegating to general agent
- Creating task context
- Multi-file coordination

### .opencode/context/core/workflows/task-breakdown.md
- Tasks with 4+ files
- Estimated effort >60 minutes
- Complex dependencies

### .opencode/context/core/workflows/sessions.md
- Session lifecycle
- Cleanup procedures
- Session isolation

### .opencode/context/core/workflows/review.md
- Reviewing code
- Conducting code audits
- Providing PR feedback

## Temporary Context (Session-Specific)

When delegating, create focused task context:

**Location**: `.tmp/sessions/{timestamp}-{task-slug}/context.md`

**Structure**:
```markdown
# Task Context: {Task Name}

Session ID: {id}
Created: {timestamp}
Status: in_progress

## Current Request
{What user asked for}

## Requirements
- {requirement 1}
- {requirement 2}

## Decisions Made
- {decision 1}

## Files to Modify/Create
- {file 1} - {purpose}

## Static Context Available
- .opencode/context/core/standards/code.md
- .opencode/context/core/standards/tests.md

## Constraints/Notes
{Important context}

## Progress
- [ ] {task 1}
- [ ] {task 2}

---
**Instructions for Subagent:**
{Specific instructions}
```

## Session Management

### Session Structure
```
.tmp/sessions/{session-id}/
├── context.md          # Task context
├── notes.md            # Working notes
└── artifacts/          # Generated files
```

### Session ID Format
`{timestamp}-{random-4-chars}`
Example: `20250119-143022-a4f2`

### Cleanup
- Ask user before deleting session files
- Remove after task completion
- Keep if user wants to review

## Best Practices

✅ Use lazy loading (no @ symbol)
✅ Fetch only relevant context
✅ Create temp context when delegating
✅ Clean up sessions after completion
✅ Reference specific sections when possible
✅ Keep temp context focused and concise

**Golden Rule**: Fetch context when needed, not before.
