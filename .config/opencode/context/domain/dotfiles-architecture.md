# Dotfiles Repository Architecture

## Purpose
Personal configuration management using GNU Stow for symlink management.

## Core Concepts

### GNU Stow
- **What**: Symlink farm manager
- **How**: Creates symlinks from `dotfiles/` to `$HOME`
- **Why**: Version control configs without copying files
- **Command**: `stow <package>` creates symlinks for that package

### Package Structure
Each top-level directory is a "stow package":
```
.config/
  opencode/        # OpenCode AI agent system
  ghostty/         # Ghostty terminal emulator config
  lazygit/         # Lazygit TUI config
  crush/           # Crush note-taking config
dev-setup/         # Development environment setup scripts
scripts/           # Utility scripts
docs/              # Documentation
```

### Configuration Categories

1. **Shell Configuration**:
   - `.zshrc`: Zsh shell configuration
   - `.tmux.conf`: Tmux terminal multiplexer
   - `.vimrc`: Vim editor settings

2. **Git Configuration**:
   - `.gitconfig`: Global git settings
   - `.gitignore`: Global ignore patterns
   - `.gitattributes`: Git attributes

3. **OpenCode System** (`.config/opencode/`):
   - `agent/`: 7 primary + 12 subagent definitions
   - `command/`: 11 custom slash commands
   - `context/`: Structured knowledge files
   - `workflows/`: Multi-step process definitions
   - `opencode.json`: MCP server configuration

4. **Development Setup** (`dev-setup/`):
   - `runs/*.sh`: Modular setup scripts
   - `run.sh`: Orchestrator script
   - Installs: tools, languages, runtimes

## Data Flow

### Stow Deployment:
```
dotfiles/.config/opencode/opencode.json
         ↓ (stow .config)
$HOME/.config/opencode/opencode.json (symlink)
```

### Agent Invocation:
```
User command
  → OpenCode routes to agent
    → Agent loads context files
      → Agent executes with MCP tools
        → Agent delegates to subagents (if needed)
```

## Key Principles

1. **Modularity**: Each package is independent
2. **Symlinks**: Never copy, always link
3. **Version Control**: Everything tracked in git
4. **Idempotency**: Scripts can run multiple times safely
5. **Documentation**: AGENTS.md and ai-guide.md guide AI behavior

## Relationships

- `.gitconfig` references `.gitignore` and `.gitattributes`
- OpenCode agents reference context files
- dev-setup scripts are sourced by run.sh
- Shell configs (.zshrc) may source scripts/

## Constraints

- Stow packages must not conflict (same file in multiple packages)
- Shell scripts must pass shellcheck
- OpenCode agents must follow XML structure
- All commits use conventional commits format
- MCP servers disabled by default for performance
