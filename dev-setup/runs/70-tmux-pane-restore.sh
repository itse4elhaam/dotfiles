#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "$@"; }
execute() { log "$@"; "$@"; }

opencode_plugin_dir="$HOME/.config/opencode/plugins"
store_dir="${XDG_DATA_HOME:-$HOME/.local/share}/opencode"

mkdir -p "$opencode_plugin_dir" "$store_dir"

if [[ -f "$script_dir/../../.config/opencode/plugins/tmux-pane-bind.ts" ]]; then
  target="$opencode_plugin_dir/tmux-pane-bind.ts"
  if [[ ! -f "$target" ]]; then
    execute cp "$script_dir/../../.config/opencode/plugins/tmux-pane-bind.ts" "$target"
    log "Installed tmux-pane-bind plugin"
  else
    log "tmux-pane-bind plugin already installed"
  fi
fi

script_target="/usr/local/bin/opencode-continue-pane"
if [[ -f "$script_dir/../../scripts/opencode-continue-pane" ]]; then
  if [[ ! -f "$script_target" ]]; then
    execute sudo cp "$script_dir/../../scripts/opencode-continue-pane" "$script_target"
    execute sudo chmod +x "$script_target"
    log "Installed opencode-continue-pane to $script_target"
  else
    log "opencode-continue-pane already installed"
  fi
fi

log "Tmux pane restore setup complete"
log "  - Plugin: $opencode_plugin_dir/tmux-pane-bind.ts"
log "  - Script: $script_target"
log "  - Store:  $store_dir/pane-bindings.json"
log ""
log "To enable: add OPENCODE_PANE_RESTORE=1 to your shell rc"
log "To disable: set OPENCODE_PANE_RESTORE=0"
