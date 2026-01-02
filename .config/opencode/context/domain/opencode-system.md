# OpenCode Agent System

## System Architecture

### Hierarchy
```
User
  ↓
Primary Agents (7)
  ↓
Subagents (12)
  ↓
MCP Tools (12 servers)
```

### Primary Agents
1. **openagent**: Main orchestrator (temperature: 0.5)
2. **codebase-agent**: Code analysis specialist (0.5)
3. **system-builder**: Agent/workflow builder (0.5)
4. **git**: Git operations (0.1 - deterministic)
5. **sales**: Business communications (0.7 - creative)
6. **teach**: Socratic teaching method (0.7)
7. **ask**: Q&A specialist (0.5)

### Subagents

**Code Subagents** (`.config/opencode/agent/subagents/code/`):
- coder-agent (0.2): Implementation
- reviewer (0.3): Code review
- tester (0.2): Test creation
- build-agent (0.2): CI/CD
- codebase-pattern-analyst (0.4): Pattern detection
- dry-run-tester (0.2): Exhaustive edge case testing
- ux-analyzer (0.6): UX analysis with case studies

**Core Subagents** (`.config/opencode/agent/subagents/core/`):
- task-manager (0.3): Task breakdown
- documentation (0.5): Docs generation

**System Builder Subagents** (`.config/opencode/agent/subagents/system-builder/`):
- domain-analyzer (0.4): Domain modeling
- agent-generator (0.3): Agent creation
- context-organizer (0.3): Context file management
- workflow-designer (0.4): Workflow design
- command-creator (0.3): Command generation

## Custom Commands (11)
Located in `.config/opencode/command/`:

1. `/commit`: Git commit with CodeRabbit review
2. `/study`: Deep codebase analysis
3. `/test`: Run tests with reporting
4. `/context`: Build context files
5. `/clean`: Code cleanup
6. `/optimize`: Performance analysis
7. `/prompt-enchancer`: Improve prompts
8. `/worktrees`: Git worktree management
9. `/build-context-system`: Initialize OpenAgents
10. `/ux-analyze`: UX analysis with case studies
11. `/dry-run`: Exhaustive edge case testing

## MCP Servers (12)
All DISABLED by default in `opencode.json`:

**High Priority**:
- context7: Framework docs
- octocode: GitHub analysis
- memory: Cross-session persistence

**Medium Priority**:
- gh_grep: Production code patterns
- aid: Code analysis
- augments: Framework examples

**As Needed**:
- playwright: UI testing
- next-devtools: Next.js debugging
- desktop-commander: File operations
- mindpilot: Diagrams

**Low Priority**:
- ddg-search: Web search
- sequential-thinking: Problem solving
- mcp-compass: MCP discovery
- chrome-devtools: Browser debugging

## Context Organization

**Domain** (`context/domain/`):
- Core concepts and terminology
- System architecture
- Business rules

**Processes** (`context/processes/`):
- Workflows and procedures
- Integration patterns
- Escalation paths

**Standards** (`context/standards/`):
- Code quality criteria
- Validation rules
- Error handling patterns

**Templates** (`context/templates/`):
- Output formats
- Common patterns
- Boilerplate code

## Delegation Strategy

### When to Delegate Immediately:
- Multi-step task → task-manager
- Code implementation → coder-agent
- Code review → reviewer
- Testing → tester or dry-run-tester
- Documentation → documentation
- Git operations → /commit command
- UX analysis → ux-analyzer
- Edge case testing → dry-run-tester

### Context Preservation Rules:
1. >3 file operations → delegate
2. Response >500 lines → delegate
3. Multiple independent subtasks → delegate in parallel
4. Exploratory research → use task tool
5. Main agent: planning, coordination, communication only

## Performance Optimization

### Parallel Execution:
- Multiple subagents can work concurrently
- Batch MCP calls when possible
- Example: coder-agent + tester + documentation in parallel

### Context Efficiency:
- 80% tasks: Level 1 (isolated)
- 20% tasks: Level 2 (filtered context)
- Rare: Level 3 (windowed)

### Expected Gains:
- +20% routing accuracy
- +25% consistency
- 80% context reduction
- +17% overall performance
