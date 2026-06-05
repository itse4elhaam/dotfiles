#!/bin/bash
set -euo pipefail

# ~/.dotfiles/scripts/startup-workspaces.sh

# Workspace numbers:
# wmctrl uses 0-based indexes:
# 0 = desktop/workspace 1
# 1 = desktop/workspace 2
WORKSPACE_1=0
WORKSPACE_2=1

GHOSTTY_CMD=(ghostty -e bash -lc "tmux new-session -A -s main")
EDGE_CMD=(microsoft-edge-stable)
UPWORK_CMD=(gtk-launch upwork)

wait_for_window() {
  local class_name="$1"
  local timeout="${2:-20}"
  local elapsed=0

  while [[ "$elapsed" -lt "$timeout" ]]; do
    local window_id
    window_id="$(xdotool search --onlyvisible --class "$class_name" 2>/dev/null | tail -n 1 || true)"

    if [[ -n "$window_id" ]]; then
      echo "$window_id"
      return 0
    fi

    sleep 1
    elapsed=$((elapsed + 1))
  done

  return 1
}

move_window_to_workspace() {
  local window_id="$1"
  local workspace="$2"

  wmctrl -ir "$window_id" -t "$workspace"
}

focus_window() {
  local window_id="$1"

  wmctrl -ia "$window_id"
}

# Give GNOME/Pop Shell some time after login before opening apps.
sleep 5

# ------------------------------------------------------------
# 1. Open Ghostty on workspace 1 and run tmux
# ------------------------------------------------------------
wmctrl -s "$WORKSPACE_1"
"${GHOSTTY_CMD[@]}" &

GHOSTTY_WINDOW="$(wait_for_window ghostty 20 || wait_for_window Ghostty 10 || true)"

if [[ -n "${GHOSTTY_WINDOW:-}" ]]; then
  move_window_to_workspace "$GHOSTTY_WINDOW" "$WORKSPACE_1"
fi

# ------------------------------------------------------------
# 2. Open Edge on workspace 2 and restore tabs with Ctrl+Shift+T
# ------------------------------------------------------------
wmctrl -s "$WORKSPACE_2"
"${EDGE_CMD[@]}" &

EDGE_WINDOW="$(wait_for_window microsoft-edge 25 || wait_for_window Microsoft-edge 10 || wait_for_window edge 10 || true)"

if [[ -n "${EDGE_WINDOW:-}" ]]; then
  move_window_to_workspace "$EDGE_WINDOW" "$WORKSPACE_2"
  focus_window "$EDGE_WINDOW"

  # Give Edge a moment to become ready before sending shortcut.
  sleep 3

  # Restore recently closed session/tabs.
  xdotool key --clearmodifiers ctrl+shift+t
fi

# ------------------------------------------------------------
# 3. Open Upwork Tracker on workspace 2
# ------------------------------------------------------------
wmctrl -s "$WORKSPACE_2"
"${UPWORK_CMD[@]}" &

UPWORK_WINDOW="$(wait_for_window Upwork 25 || wait_for_window upwork 10 || true)"

if [[ -n "${UPWORK_WINDOW:-}" ]]; then
  move_window_to_workspace "$UPWORK_WINDOW" "$WORKSPACE_2"
fi

# ------------------------------------------------------------
# Final focus should be Edge
# ------------------------------------------------------------
if [[ -n "${EDGE_WINDOW:-}" ]]; then
  focus_window "$EDGE_WINDOW"
fi
