# Shell Script Template

```bash
#!/bin/bash
# Description: [What this script does]
# Usage: ./script.sh [arguments]
# Dependencies: [Required commands/tools]

set -euo pipefail

# ============================================================================
# Constants and Configuration
# ============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "$0")"

# Add your constants here
# readonly CONFIG_FILE="$HOME/.config/app/config.json"

# ============================================================================
# Functions
# ============================================================================

# Function: show_usage
# Description: Display usage information
# Args: None
# Returns: None
show_usage() {
  cat << EOF
Usage: $SCRIPT_NAME [OPTIONS] [ARGUMENTS]

Description:
  [Detailed description of what this script does]

Options:
  -h, --help     Show this help message
  -v, --verbose  Enable verbose output

Arguments:
  arg1           [Description of arg1]
  arg2           [Description of arg2]

Examples:
  $SCRIPT_NAME arg1 arg2
  $SCRIPT_NAME --verbose arg1

EOF
}

# Function: log_info
# Description: Log informational message
# Args: $1 - Message to log
# Returns: None
log_info() {
  echo "[INFO] $1"
}

# Function: log_error
# Description: Log error message to stderr
# Args: $1 - Error message
# Returns: None
log_error() {
  echo "[ERROR] $1" >&2
}

# Function: validate_prerequisites
# Description: Check if required commands are available
# Args: None
# Returns: 0 on success, 1 on failure
validate_prerequisites() {
  local required_commands=("git" "jq")  # Add required commands
  
  for cmd in "${required_commands[@]}"; do
    if ! command -v "$cmd" &> /dev/null; then
      log_error "Required command not found: $cmd"
      return 1
    fi
  done
  
  return 0
}

# Function: parse_arguments
# Description: Parse command line arguments
# Args: All script arguments ("$@")
# Returns: 0 on success, 1 on failure
parse_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        show_usage
        exit 0
        ;;
      -v|--verbose)
        VERBOSE=true
        shift
        ;;
      -*)
        log_error "Unknown option: $1"
        show_usage
        return 1
        ;;
      *)
        # Positional argument
        ARGS+=("$1")
        shift
        ;;
    esac
  done
  
  return 0
}

# ============================================================================
# Main Logic
# ============================================================================

# Function: main
# Description: Main script logic
# Args: All script arguments ("$@")
# Returns: 0 on success, 1 on failure
main() {
  # Initialize variables
  local -a ARGS=()
  local VERBOSE=false
  
  # Parse arguments
  parse_arguments "$@" || return 1
  
  # Validate prerequisites
  validate_prerequisites || return 1
  
  # Validate required arguments
  if [[ ${#ARGS[@]} -lt 1 ]]; then
    log_error "Missing required arguments"
    show_usage
    return 1
  fi
  
  # Your main script logic here
  log_info "Starting script execution..."
  
  # Example: Process arguments
  for arg in "${ARGS[@]}"; do
    log_info "Processing: $arg"
    # Add your processing logic
  done
  
  log_info "Script completed successfully!"
  return 0
}

# ============================================================================
# Script Execution
# ============================================================================

# Run main function
main "$@"
exit $?
```

## Usage

Copy this template when creating new shell scripts:
```bash
cp .config/opencode/context/templates/shell-script.md new-script.sh
chmod +x new-script.sh
```

Then customize:
1. Update description and usage
2. Add your constants
3. Implement your functions
4. Fill in main logic
5. Test with `shellcheck new-script.sh`
