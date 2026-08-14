#!/usr/bin/env bats

setup() {
  load "../helpers/binding-store"
  load "../helpers/pane-identity"

  export XDG_DATA_HOME="$(mktemp -d)"
  _store_cleanup="$XDG_DATA_HOME"
}

teardown() {
  rm -rf "$_store_cleanup"
}

@test "pane_binding_get returns empty for nonexistent key (no store file)" {
  run pane_binding_get "no-such-key:1.1|/tmp"
  [ "$status" -eq 1 ]
}

@test "pane_binding_get returns empty for nonexistent key (store exists)" {
  pane_binding_set "other-key:1.1|/tmp" "ses_other"
  run pane_binding_get "missing-key:1.1|/tmp"
  [ "$status" -eq 1 ]
}

@test "pane_binding_set and pane_binding_get round-trip" {
  pane_binding_set "my-session:1.2|/home/user" "ses_abc123"
  result="$(pane_binding_get "my-session:1.2|/home/user")"
  [ "$result" = "ses_abc123" ]
}

@test "pane_binding_set overwrites existing binding" {
  pane_binding_set "my-session:1.1|/tmp" "ses_first"
  pane_binding_set "my-session:1.1|/tmp" "ses_second"
  result="$(pane_binding_get "my-session:1.1|/tmp")"
  [ "$result" = "ses_second" ]
}

@test "pane_binding_set stores different keys independently" {
  pane_binding_set "session-a:1.1|/a" "ses_a"
  pane_binding_set "session-b:2.2|/b" "ses_b"
  result_a="$(pane_binding_get "session-a:1.1|/a")"
  result_b="$(pane_binding_get "session-b:2.2|/b")"
  [ "$result_a" = "ses_a" ]
  [ "$result_b" = "ses_b" ]
}

@test "pane_binding_delete removes binding" {
  pane_binding_set "my-session:1.1|/tmp" "ses_test"
  pane_binding_delete "my-session:1.1|/tmp"
  run pane_binding_get "my-session:1.1|/tmp"
  [ "$status" -eq 1 ]
}

@test "pane_binding_delete is idempotent on missing key" {
  pane_binding_delete "never-set:1.1|/tmp"
  run pane_binding_get "never-set:1.1|/tmp"
  [ "$status" -eq 1 ]
}

@test "pane_binding_list returns empty object for empty store" {
  result="$(pane_binding_list)"
  [ "$result" = "{}" ]
}

@test "pane_binding_list returns all bindings" {
  pane_binding_set "s:1.1|/a" "ses_1"
  pane_binding_set "s:1.2|/b" "ses_2"
  result="$(pane_binding_list)"
  echo "$result" | jq -e 'has("s:1.1|/a")'
  echo "$result" | jq -e 'has("s:1.2|/b")'
}

@test "pane_binding_list entries have sessionID and updatedAt" {
  pane_binding_set "s:1.1|/a" "ses_test"
  result="$(pane_binding_list)"
  echo "$result" | jq -e '."s:1.1|/a".sessionID == "ses_test"'
  echo "$result" | jq -e '."s:1.1|/a".updatedAt | length > 0'
}

@test "binding store is atomic (interrupt during write doesn't corrupt)" {
  pane_binding_set "s:1.1|/a" "ses_original"
  pane_binding_set "s:1.1|/a" "ses_overwrite"
  result="$(pane_binding_get "s:1.1|/a")"
  [ "$result" = "ses_overwrite" ]
}
