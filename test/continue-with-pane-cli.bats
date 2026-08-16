#!/usr/bin/env bats

setup() {
  export TEST_ROOT="$(mktemp -d)"
  export XDG_DATA_HOME="$TEST_ROOT/data"
  export OPENCODE_REAL_BIN="$TEST_ROOT/opencode-real"
  export TMUX_PANE="%20"
  export OPENCODE_PANE_IDENTITY="peasy:2.3"
  export OPENCODE_TEST_LOG="$TEST_ROOT/opencode.log"

  cat > "$OPENCODE_REAL_BIN" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$OPENCODE_TEST_LOG"
if [[ "${1:-}" == "--help" ]]; then
  printf 'OpenCode help\n'
fi
EOF
  chmod +x "$OPENCODE_REAL_BIN"
}

teardown() {
  rm -rf "$TEST_ROOT"
}

binding_path() {
  local digest
  digest="$(printf '%s' "$OPENCODE_PANE_IDENTITY" | sha256sum | cut -d' ' -f1)"
  printf '%s/opencode/pane-sessions/%s.json\n' "$XDG_DATA_HOME" "$digest"
}

write_binding() {
  local path
  path="$(binding_path)"
  mkdir -p "$(dirname "$path")"
  jq -n \
    --arg pane "$OPENCODE_PANE_IDENTITY" \
    --arg session_id "$1" \
    '{pane: $pane, sessionID: $session_id, updatedAt: "2026-08-10T00:00:00Z"}' > "$path"
}

@test "forwards ordinary OpenCode arguments unchanged" {
  run "$BATS_TEST_DIRNAME/../scripts/opencode" run "hello world"

  [ "$status" -eq 0 ]
  [ "$(cat "$OPENCODE_TEST_LOG")" = "run hello world" ]
}

@test "resumes the exact session bound to this pane" {
  write_binding "ses_exact"

  run "$BATS_TEST_DIRNAME/../scripts/opencode" --continue-with-pane

  [ "$status" -eq 0 ]
  [ "$(cat "$OPENCODE_TEST_LOG")" = "--session ses_exact" ]
}

@test "starts a new session when this pane has no binding" {
  run "$BATS_TEST_DIRNAME/../scripts/opencode" --continue-with-pane

  [ "$status" -eq 0 ]
  [ "$(cat "$OPENCODE_TEST_LOG")" = "" ]
}

@test "keeps other OpenCode arguments when resuming the pane session" {
  write_binding "ses_exact"

  run "$BATS_TEST_DIRNAME/../scripts/opencode" /tmp/project --continue-with-pane --mini

  [ "$status" -eq 0 ]
  [ "$(cat "$OPENCODE_TEST_LOG")" = "/tmp/project --mini --session ses_exact" ]
}

@test "rejects pane continuation outside tmux" {
  unset TMUX_PANE OPENCODE_PANE_IDENTITY

  run "$BATS_TEST_DIRNAME/../scripts/opencode" --continue-with-pane

  [ "$status" -eq 2 ]
  [[ "$output" == *"inside tmux"* ]]
  [ ! -s "$OPENCODE_TEST_LOG" ]
}

@test "rejects conflicting explicit session selection" {
  run "$BATS_TEST_DIRNAME/../scripts/opencode" --continue-with-pane --session ses_other

  [ "$status" -eq 2 ]
  [[ "$output" == *"cannot be combined"* ]]
  [ ! -s "$OPENCODE_TEST_LOG" ]
}

@test "rejects equals-form explicit session selection" {
  run "$BATS_TEST_DIRNAME/../scripts/opencode" --session=ses_other --continue-with-pane

  [ "$status" -eq 2 ]
  [[ "$output" == *"cannot be combined"* ]]
  [ ! -s "$OPENCODE_TEST_LOG" ]
}

@test "advertises the custom flag in top-level help" {
  unset OPENCODE_PANE_IDENTITY

  run "$BATS_TEST_DIRNAME/../scripts/opencode" --help

  [ "$status" -eq 0 ]
  [[ "$output" == *"--continue-with-pane"* ]]
}

@test "ignores a corrupt binding instead of resuming an arbitrary session" {
  local path
  path="$(binding_path)"
  mkdir -p "$(dirname "$path")"
  printf 'not-json\n' > "$path"

  run "$BATS_TEST_DIRNAME/../scripts/opencode" --continue-with-pane

  [ "$status" -eq 0 ]
  [ "$(cat "$OPENCODE_TEST_LOG")" = "" ]
}
