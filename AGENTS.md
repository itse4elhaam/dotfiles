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
- **Commit format**: Conventional Commits (feat|fix|chore|docs|refactor|perf|test)
- **Branch naming**: `type/short-desc` (solo work) or `type/elhaam/short-desc` (collaborative)
- **Use**: `/commit` command for commits with CodeRabbit review integration
- **Auto-commit**: When invoked via `/commit`, commits immediately after analysis
- **Staging logic**: Commit staged files if any exist; if nothing is staged, stage all changes with `git add -A`

## OpenCode Customizations
- **Agents**: 3 primary + 12 subagents in `.opencode/agent/`
- **Commands**: 9 custom commands in `.opencode/command/` (commit, study, test, etc.)
- **Tools**: Custom MCP tools in `.opencode/tool/` (requires `@opencode-ai/plugin` dependency)
- **Plugins**: Cursor CLI plugin in `.config/opencode/plugin/` (symlinked to `~/.config/opencode/plugin/`)
- **Context**: Structured guides in `.opencode/context/`
- **Dependencies**: `.config/opencode/package.json` - Install with `cd .config/opencode && npm install`

## Cursor AI Provider
- **Location**: `.config/opencode/plugin/cursor-proxy.ts`
- **Type**: Native provider via local HTTP proxy (Cursor models appear in model switcher)
- **Architecture**: HTTP server (port 9876) translates OpenAI format → cursor-agent CLI → Cursor API
- **Installation**: Auto-loads when OpenCode starts (plugin directory symlinked via stow)
- **Models**: 6 models available in `/models` command
  - `cursor/auto` - Auto (Cursor picks best) ⭐ recommended
  - `cursor/claude-4.5-opus-high-thinking` - Claude 4.5 Opus High Thinking
  - `cursor/claude-4.5-sonnet-thinking` - Claude 4.5 Sonnet Thinking
  - `cursor/gpt-5.1-codex` - GPT 5.1 Codex
  - `cursor/gpt-5.1-codex-high` - GPT 5.1 Codex High
  - `cursor/gemini-3-pro` - Gemini 3 Pro
- **Requirements**: Cursor Pro subscription (~$20/month) for API access
- **Usage**: Select Cursor models from `/models` command - chat naturally like Claude/GPT-4
- **Logs**: `.opencode/cursor-proxy.log` (proxy server logs)
- **Config**: `.config/opencode/opencode.json` (provider.cursor section with baseURL: http://127.0.0.1:9876)
- **Backup**: Old tool-based plugin saved as `cursor-cli-tools-backup.ts`
- **Docs**: `.config/opencode/plugin/README-cursor-plugin.md`
