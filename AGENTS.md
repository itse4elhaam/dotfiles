# Dotfiles Repository - Agent Guide

## Project Overview
Personal configuration management using `stow` for symlinks. Includes dev setup scripts, shell configs, and OpenCode customizations.

## Build/Lint/Test Commands
- **Setup**: `dev-setup/run.sh` - Runs all setup scripts in `dev-setup/runs/`
- **Filter**: `dev-setup/run.sh <filter>` - Run specific scripts (e.g., `dev-setup/run.sh basic`)
- **Lint**: `shellcheck **/*.sh` - Lint all shell scripts
- **Tests**: No automated tests currently

## Shell Script Style
- Shebang: `#!/bin/bash`
- Safety: Always use `set -euo pipefail`
- Naming: `snake_case` for variables/functions (e.g., `script_dir`)
- Quoting: Always quote variables: `"$variable"` not `$variable`
- Conditionals: Use `[[ ]]` over `[ ]`
- Arguments: Pass with `"$@"` to preserve spacing
- Linting: Use shellcheck before committing

## Git Workflow
- **Never commit** unless explicitly asked
- **Commit format**: Conventional Commits (feat|fix|chore|docs|refactor|perf|test)
- **Branch naming**: `type/short-desc` (solo work) or `type/elhaam/short-desc` (collaborative)
- **Use**: `/commit` command for commits with CodeRabbit review integration

## OpenCode Customizations
- **Agents**: 3 primary + 12 subagents in `.opencode/agent/`
- **Commands**: 9 custom commands in `.opencode/command/` (commit, study, test, etc.)
- **Tools**: Custom MCP tools in `.opencode/tool/`
- **Context**: Structured guides in `.opencode/context/`
