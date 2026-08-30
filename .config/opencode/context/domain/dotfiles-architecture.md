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
5. **Documentation**: AGENTS.md files guide AI behavior

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

## OpenCode Session Fork & Session ID Copy

The repo provides two complementary features for working with OpenCode sessions inside tmux:

### Architecture

```
Plugin (session-expose.ts)
  ↓ writes pane-keyed file
/tmp/opencode-session-<TMUX_PANE>  →  JSON: { sessionId, directory, timestamp }
  ↓ read by
scripts/oc-fork (invoked via tmux keybind)
```

### Components

1. **Plugin** (`.config/opencode/plugins/session-expose.ts`):
   - Auto-loaded by OpenCode (local `.ts` files in `plugins/` are auto-discovered)
   - On each tool execution, writes the current session ID, working directory, and timestamp to
     `/tmp/opencode-session-<TMUX_PANE>` (pane-keyed to prevent race conditions after forking)
   - Errors are silently caught — never breaks a tool call

2. **Helper script** (`scripts/oc-fork`):
   - Two modes: fork (default) and copy session ID (`-c` / `--copy-id`)
   - Invoked via `run-shell` from tmux keybinds (uses `tmux display -p` — NOT `$TMUX`/`$TMUX_PANE`)
   - Reads session ID from the pane-keyed file, validates freshness (10-minute staleness window)
   - Fork mode: `tmux split-window -h -c "$CWD" opencode --session "$ID" --fork`
   - Copy mode: loads session ID into tmux buffer + system clipboard (xclip on X11)
   - Error handling covers: outside tmux, missing session data, stale data, opencode not in PATH
   - Supports `--dry-run` for testing
   - ShellCheck-clean, `set -euo pipefail`

3. **Tests** (`scripts/oc-fork.test.sh`):
   - Lightweight source-and-assert harness (no bats dependency)
   - Tests: missing/malformed/stale session files, arg parsing, prerequisite checks
   - Sources the script directly to test pure functions in isolation

4. **tmux keybinds** (`.tmux.conf`):
   - `prefix+F` → Fork current OpenCode session to new right-split pane
   - `prefix+C-f` → Copy current OpenCode session ID to clipboard

### Keybind Reference

| Key | Action | Context |
|-----|--------|---------|
| `prefix+F` | Fork session to new pane | Inside opencode, after at least one message sent |
| `prefix+C-f` | Copy session ID to clipboard | Inside opencode, after at least one message sent |

### Changing Keybinds

Edit `.tmux.conf` and modify or duplicate the `bind F` / `bind C-f` lines.
Reload with `tmux source-file ~/.tmux.conf` or `prefix+r`.

### Requirements

- OpenCode v1.17+ with `@opencode-ai/plugin` API
- tmux 3.x (for `#{pane_current_path}` format)
- `opencode` in PATH
- Optional: `xclip` for system clipboard on X11
