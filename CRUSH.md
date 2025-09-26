## Project Overview
This is a dotfiles repository for personal configuration management. It uses `stow` to manage symlinks for various configuration files.

## Build, Lint, and Test Commands

- **Build:** `dev-setup/run.sh` - This script runs all the setup scripts in the `dev-setup/runs` directory. You can filter which scripts to run by passing a filter as an argument. For example, `dev-setup/run.sh basic` will only run the `basic.sh` script.
- **Lint:** `shellcheck **/*.sh`
- **Test:** There are no tests in this project yet.

## Code Style Guidelines

### Shell Scripts
- Use `#!/bin/bash` as the shebang.
- Use `set -euo pipefail` to make your scripts more robust.
- Use `shellcheck` for linting.
- Use snake_case for variables and functions (e.g., `script_dir`).
- Use comments to explain complex logic.
- Use `"$@"` to pass all arguments to functions.

### General
- Keep files small and focused on a single task.
- Use a consistent naming convention for files and directories.
- `.crush` directory is already in `.gitignore`.
- Configuration files are organized in the `.config` directory.
- Utility scripts are located in the `scripts` directory.
