# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-07
**Context:** Dotfiles & Dev Environment

## OVERVIEW
Personal configuration management using `stow` for symlinks. Includes dev setup scripts (`dev-setup/`), shell configs, and extensive OpenCode customizations (`.config/opencode/`).

## STRUCTURE
```
./
├── dev-setup/     # Setup scripts & runner (idempotent)
├── scripts/       # Standalone utility scripts
├── docs/          # Documentation (AI guide, etc)
├── .config/       # Application configurations
│   └── opencode/  # AI Agents, Commands, Context
└── .stow-local-ignore
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| **System Setup** | `dev-setup/run.sh` | Main entry point |
| **Setup Scripts** | `dev-setup/runs/` | Individual setup units |
| **AI Agents** | `.config/opencode/agent/` | Custom agent defs |
| **AI Commands** | `.config/opencode/command/` | Slash commands |
| **Shell Config** | `.bashrc`, `.zshrc` | Root level dotfiles |

## CODE MAP
| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `run.sh` | Script | `dev-setup/run.sh` | Orchestrates setup scripts |
| `execute` | Func | `dev-setup/run.sh` | Wrapper for dry-run support |
| `opencode.json` | Config | `.config/opencode/` | Main AI config |

## CONVENTIONS
- **Shell**: `#!/bin/bash`, `set -euo pipefail`, `snake_case` vars.
- **Git**: Conventional Commits (`feat`, `fix`, `chore`).
- **Safety**: Always quote variables `"$var"`. Use `[[ ]]` tests.
- **Idempotency**: Setup scripts must be safe to re-run.

## COMMANDS
```bash
# Run all setup scripts
./dev-setup/run.sh

# Run specific setup (grep filter)
./dev-setup/run.sh basic

# Lint scripts
shellcheck **/*.sh

# Commit with AI review
/commit
```

## NOTES
- **Stow**: Root files are symlinked to `$HOME`.
- **OpenCode**: Custom agents stored in `.config/opencode` override defaults.
