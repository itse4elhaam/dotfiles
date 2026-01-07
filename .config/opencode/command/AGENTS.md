# COMMANDS KNOWLEDGE BASE

## OVERVIEW
Custom slash commands definitions for OpenCode.

## STRUCTURE
Each file is a markdown file with YAML frontmatter defining the command.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| **Definitions** | `*.md` | Filename = command name |

## CONVENTIONS
- **Frontmatter**:
  ```yaml
  name: /command
  agent: agent-name
  description: string
  args: []
  ```
- **Arguments**: Use `$ARGUMENTS` in prompt
- **Subtasks**: `subtask: true` for complex flows

## COMMANDS
- `/commit`: Git commit with review
- `/study`: Deep analysis
- `/test`: Run tests
