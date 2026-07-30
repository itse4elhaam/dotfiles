#!/usr/bin/env bats

setup() {
  load "../helpers/binding-store"
  load "../helpers/pane-identity"
  load "../helpers/feature-flag"

  export XDG_DATA_HOME="$(mktemp -d)"
  _tmp_cleanup="$XDG_DATA_HOME"

  _stub_dir="$(mktemp -d)"
  export PATH="$_stub_dir:$PATH"

  cat > "$_stub_dir/opencode" <<'SCRIPT'
#!/usr/bin/bash
echo "opencode:$*" >> /tmp/opencode_stub_log
if [[ "$*" == *--list-sessions* ]]; then
  echo '["ses_a","ses_b"]'
fi
SCRIPT
  chmod +x "$_stub_dir/opencode"

  cat > "$_stub_dir/fzf" <<'SCRIPT'
#!/usr/bin/bash
if [[ -n "${_FZF_OUTPUT:-}" ]]; then
  echo "$_FZF_OUTPUT"
fi
SCRIPT
  chmod +x "$_stub_dir/fzf"

  : > /tmp/opencode_stub_log 2>/dev/null || true
}

teardown() {
  rm -rf "$_tmp_cleanup" "$_stub_dir"
}

script_under_test() {
  TMUX_PANE="%1" \
  tmux_session_name="test-session" \
  tmux_window_index="1" \
  tmux_pane_index="1" \
  pane_current_path="/home/user/project" \
  bash "$PWD/scripts/opencode-continue-pane" "$@"
}

@test "continues with --continue when no binding exists" {
  run script_under_test
  [ "$status" -eq 0 ]
  grep -q "opencode:--continue" /tmp/opencode_stub_log
}

@test "opens exact session when binding exists" {
  pane_binding_set "test-session:1.1|/home/user/project" "ses_exact"
  run script_under_test
  [ "$status" -eq 0 ]
  grep -q "opencode:--session ses_exact" /tmp/opencode_stub_log
}

@test "uses --continue when binding exists but feature flag is disabled" {
  pane_binding_set "test-session:1.1|/home/user/project" "ses_exact"
  OPENCODE_PANE_RESTORE="0" run script_under_test
  [ "$status" -eq 0 ]
  grep -q "opencode:--continue" /tmp/opencode_stub_log
}

@test "uses --continue when env is false" {
  OPENCODE_PANE_RESTORE="false" run script_under_test
  [ "$status" -eq 0 ]
  grep -q "opencode:--continue" /tmp/opencode_stub_log
}

@test "with --version prints version" {
  run script_under_test --version
  [ "$status" -eq 0 ]
  [[ "$output" == *"0.1.0"* ]]
}

@test "with --help prints usage" {
  run script_under_test --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage"* ]]
}

@test "--pick flows through without fzf interaction" {
  skip "Needs interactive FZF - testing manually"
}
