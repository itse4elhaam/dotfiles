# shellcheck disable=SC2154

pane_binding_store_path() {
  local data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
  echo "$data_home/opencode/pane-bindings.json"
}

pane_binding_get() {
  local key="$1"
  local store
  store="$(pane_binding_store_path)"
  if [[ ! -f "$store" ]]; then
    return 1
  fi
  local val
  val="$(jq -r --arg key "$key" '.[$key].sessionID // empty' "$store")"
  if [[ -z "$val" ]]; then
    return 1
  fi
  echo "$val"
}

pane_binding_set() {
  local key="$1" session_id="$2"
  local store
  store="$(pane_binding_store_path)"
  local dir
  dir="$(dirname "$store")"
  mkdir -p "$dir"

  local tmp
  tmp="$(mktemp "$dir/pane-bindings.XXXXXX.json")"

  if [[ -f "$store" ]]; then
    jq --arg key "$key" --arg sid "$session_id" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      '.[$key] = { sessionID: $sid, updatedAt: $now }' "$store" > "$tmp"
  else
    echo '{}' | jq --arg key "$key" --arg sid "$session_id" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      '.[$key] = { sessionID: $sid, updatedAt: $now }' > "$tmp"
  fi

  mv "$tmp" "$store" || { rm -f "$tmp"; return 1; }
  rm -f "$tmp"
}

pane_binding_delete() {
  local key="$1"
  local store
  store="$(pane_binding_store_path)"
  if [[ ! -f "$store" ]]; then
    return
  fi
  local dir
  dir="$(dirname "$store")"
  local tmp
  tmp="$(mktemp "$dir/pane-bindings.XXXXXX.json")"
  jq --arg key "$key" 'del(.[$key])' "$store" > "$tmp" || { rm -f "$tmp"; return 1; }
  mv "$tmp" "$store" || { rm -f "$tmp"; return 1; }
  rm -f "$tmp"
}

pane_binding_list() {
  local store
  store="$(pane_binding_store_path)"
  if [[ ! -f "$store" ]]; then
    echo '{}'
    return
  fi
  cat "$store"
}
