# Shell Scripting Standards

## Mandatory Requirements

### Shebang
```bash
#!/bin/bash
# or
#!/usr/bin/env bash
```

### Safety First
**Always include**:
```bash
set -euo pipefail
```

- `set -e`: Exit on error
- `set -u`: Exit on undefined variable
- `set -o pipefail`: Fail on pipe errors

### Naming Conventions
- **Variables**: `snake_case` (e.g., `script_dir`, `user_name`)
- **Functions**: `snake_case` (e.g., `validate_input`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)

### Quoting Rules
**Always quote variables**:
```bash
# Good
echo "$variable"
cd "$directory"
rm "$file_path"

# Bad
echo $variable    # Word splitting issues
cd $directory     # Breaks with spaces
rm $file_path     # Dangerous!
```

**Use arrays for multiple values**:
```bash
# Good
files=("file1.txt" "file2.txt" "file with spaces.txt")
for file in "${files[@]}"; do
  process "$file"
done

# Bad
files="file1.txt file2.txt file with spaces.txt"  # Breaks!
```

### Conditionals
**Use `[[ ]]` over `[ ]`**:
```bash
# Good
if [[ "$var" == "value" ]]; then
  echo "Match"
fi

if [[ -f "$file" && -r "$file" ]]; then
  cat "$file"
fi

# Bad
if [ "$var" = "value" ]; then  # Less powerful
  echo "Match"
fi
```

### Function Arguments
**Pass and receive properly**:
```bash
# Good
function greet() {
  local name="$1"
  local greeting="${2:-Hello}"  # Default value
  echo "$greeting, $name!"
}

greet "World" "Hi"

# Preserve spacing with "$@"
function run_command() {
  echo "Running: $*"
  "$@"  # Preserves all arguments with spacing
}

run_command ls -la "my directory"
```

### Error Handling
```bash
# Check command success
if ! command -v jq &> /dev/null; then
  echo "Error: jq is not installed" >&2
  exit 1
fi

# Validate inputs
if [[ -z "$1" ]]; then
  echo "Usage: $0 <argument>" >&2
  exit 1
fi

# Handle errors in functions
function safe_operation() {
  if ! some_command; then
    echo "Error: Operation failed" >&2
    return 1
  fi
}
```

### Linting
**Always run shellcheck**:
```bash
shellcheck script.sh
shellcheck **/*.sh  # All scripts
```

Fix all warnings before committing.

## Best Practices

### Documentation
```bash
#!/bin/bash
# Description: What this script does
# Usage: ./script.sh <arg1> <arg2>
# Author: Elhaam

set -euo pipefail

# Global constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CONFIG_FILE="$HOME/.config/app/config.json"

# Function: Validate configuration
# Args: None
# Returns: 0 on success, 1 on failure
validate_config() {
  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Config file not found: $CONFIG_FILE" >&2
    return 1
  fi
  return 0
}

# Main execution
main() {
  validate_config || exit 1
  # ... rest of script
}

main "$@"
```

### Idempotency
Scripts should be safe to run multiple times:
```bash
# Good: Check before creating
if [[ ! -d "$directory" ]]; then
  mkdir -p "$directory"
fi

# Good: Check before linking
if [[ ! -L "$link" ]]; then
  ln -s "$target" "$link"
fi

# Bad: Fails on second run
mkdir "$directory"  # Error if exists
```

### Defensive Programming
```bash
# Check prerequisites
command -v git &> /dev/null || {
  echo "Error: git is required" >&2
  exit 1
}

# Validate paths
if [[ ! -d "$HOME/dotfiles" ]]; then
  echo "Error: dotfiles directory not found" >&2
  exit 1
fi

# Use mktemp for temporary files
temp_file="$(mktemp)"
trap 'rm -f "$temp_file"' EXIT  # Cleanup on exit
```

## Common Patterns

### Script Template
```bash
#!/bin/bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

main() {
  local arg1="${1:-default}"
  
  # Script logic here
  
  echo "Done!"
}

main "$@"
```

### Filtering with sed/awk
```bash
# Filter specific scripts
find . -name "*.sh" -type f | grep -E "(basic|zsh)"
```

### Looping
```bash
# Loop through files
for script in dev-setup/runs/*.sh; do
  if [[ -f "$script" ]]; then
    bash "$script"
  fi
done

# Loop through arguments
for arg in "$@"; do
  process "$arg"
done
```

## Anti-Patterns to Avoid

1. **Unquoted variables**: `cd $dir` → Use `cd "$dir"`
2. **Using `cd` without checking**: 
   ```bash
   # Bad
   cd "$dir"
   rm -rf *  # Dangerous if cd failed!
   
   # Good
   cd "$dir" || exit 1
   rm -rf ./*
   ```
3. **Parsing `ls` output**: Use glob patterns or `find` instead
4. **Using `echo` for values**: Use `printf` for formatted output
5. **Ignoring errors**: Always check return codes for critical operations
