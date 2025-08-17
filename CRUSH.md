## Build, Lint, and Test Commands

- **Build:** `dev-setup/run.sh`
- **Lint:** `shellcheck **/*.sh`
- **Test:** There are no tests in this project yet.

## Code Style Guidelines

### Shell Scripts
- Use `#!/bin/bash` as the shebang.
- Use `set -euo pipefail` to make your scripts more robust.
- Use `shellcheck` to lint your scripts.
- Use snake_case for variables and functions.
- Use comments to explain complex logic.
- Use `"$@"` to pass all arguments to a function.

### General
- Keep files small and focused on a single task.
- Use a consistent naming convention for files and directories.
- Add a `.crush` directory to your `.gitignore` file.
