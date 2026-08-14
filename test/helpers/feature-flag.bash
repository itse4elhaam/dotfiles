pane_restore_enabled() {
  local val="${OPENCODE_PANE_RESTORE:-}"
  if [[ -z "$val" ]]; then
    return 0
  fi
  case "${val,,}" in
    1|true|yes|on|enabled) return 0 ;;
    *) return 1 ;;
  esac
}
