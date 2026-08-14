# shellcheck disable=SC2154

pane_identity_build() {
  local session="$1" window="$2" pane="$3" cwd="$4"
  echo "${session}:${window}.${pane}|${cwd}"
}

pane_identity_parse() {
  local key="$1"

  if [[ "$key" != *"|"* ]]; then
    return 1
  fi

  local left="${key%%|*}"
  local right="${key#*|}"

  if [[ "$left" != *:* ]]; then
    return 1
  fi

  local session_part="${left%%:*}"
  local coord_part="${left#*:}"

  if [[ "$coord_part" != *.* ]]; then
    return 1
  fi

  local window_part="${coord_part%%.*}"
  local pane_part="${coord_part#*.}"

  if [[ -z "$session_part" || -z "$window_part" || -z "$pane_part" ]]; then
    return 1
  fi

  pane_session="$session_part"
  pane_window="$window_part"
  pane_index="$pane_part"
  pane_cwd="$right"
  return 0
}

tmux_get_pane_identity() {
  local session="${tmux_session_name:-$(tmux display-message -p '#{session_name}' 2>/dev/null)}"
  local window="${tmux_window_index:-$(tmux display-message -p '#{window_index}' 2>/dev/null)}"
  local pane="${tmux_pane_index:-$(tmux display-message -p '#{pane_index}' 2>/dev/null)}"
  local cwd="${pane_current_path:-$(tmux display-message -p '#{pane_current_path}' 2>/dev/null)}"
  pane_identity="$(pane_identity_build "$session" "$window" "$pane" "$cwd")"
}
