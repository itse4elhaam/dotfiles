#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
source_path="$repo_root/scripts/opencode"
target_dir="$HOME/.local/bin"
target_path="$target_dir/opencode"

mkdir -p "$target_dir"

if [[ -e "$target_path" && "$(readlink -f "$target_path")" != "$(readlink -f "$source_path")" ]]; then
  printf 'Refusing to replace existing %s\n' "$target_path" >&2
  exit 1
fi

ln -sfn "$source_path" "$target_path"
chmod +x "$source_path"

printf 'Installed opencode --continue-with-pane wrapper at %s\n' "$target_path"
printf 'Restart OpenCode once so it loads continue-with-pane.ts.\n'
