# AI Guide

## Core Rules

### 1. Proactive Tool Usage (MANDATORY)
**Never rely on training data for technology guidance.**

| Trigger | Action |
|---------|--------|
| User mentions tech/library | `context7` lookup FIRST |
| Need code patterns | `gh_grep` search AUTOMATICALLY |
| Complex/multi-step problem | `sequential-thinking` IMMEDIATELY |
| User shares preference | `memory` to persist |

### 2. Delegation (Context Preservation)
**Delegate early to prevent context exhaustion.**

| Task Type | Route To |
|-----------|----------|
| Code implementation | `coder-agent` |
| Code review | `reviewer` |
| Tests | `tester` |
| Documentation | `documentation` |
| Multi-step workflow | `task-manager` FIRST |
| Git operations | `/commit` command |

**Anti-pattern**: Reading 10 files + writing code + tests + docs in main agent = context exhaustion.

### 3. Parallel Execution
Batch independent operations in single response:
```
task(subagent_type="coder-agent", prompt="Implement feature")
task(subagent_type="tester", prompt="Write tests")
task(subagent_type="documentation", prompt="Document API")
```

## Language Standards

### TypeScript
- `interface` (prefix `I`) over `type` (prefix `T`)
- No `any` — use `unknown`
- `readonly` arrays, `as const` for strictness
- `zod` for runtime validation

### Shell
- `#!/bin/bash` + `set -euo pipefail`
- Quote variables: `"$var"`
- Use `[[ ]]` for conditionals

### React/Next.js
- Functional components + hooks
- Avoid `useEffect` abuse (derive state)
- TailwindCSS over CSS modules
- `zod` for forms/APIs

## Coding Principles

| Principle | Rule |
|-----------|------|
| Defensive | Null-check inputs, fail fast with clear errors |
| Control Flow | Guard clauses > nesting; object maps > complex conditionals |
| Performance | `Set` for lookups; `for` loops in hot paths |
| Quality | <30 line functions; object params if >2 args |

## Git Workflow

### Commits
- Use `/commit` command (auto CodeRabbit review)
- Conventional commits, **past tense** ("added", "fixed")
- Review diff before committing

### Branches
- Solo: `type/short-desc` (e.g., `feat/setup-script`)
- Collab: `type/elhaam/short-desc`

## MCP Servers

### Always Enabled (Use Proactively)
| Server | When |
|--------|------|
| `context7` | Tech/library mentioned |
| `gh_grep` | Need real patterns |
| `sequential-thinking` | Complex problems |
| `memory` | Persist preferences |
| `octocode` | GitHub analysis |

### Enable On-Demand
`playwright`, `linear`, `next-devtools`, `aid`, `chrome-devtools`

## Tool Priority

| Need | Tool |
|------|------|
| Known file path | `Read` |
| Remote GitHub | `octocode` |
| Open-ended search | `explore` agent |
| Pattern search | `Grep`/`ast_grep` |

## Anti-Patterns

- Relying on training data for API syntax
- Implementing inline instead of delegating
- Sequential execution of independent tasks
- `any`, `@ts-ignore`, empty catch blocks
- Committing without `/commit` command
