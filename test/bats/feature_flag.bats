#!/usr/bin/env bats

setup() {
  load "../helpers/feature-flag"
}

@test "pane_restore_enabled returns 0 when OPENCODE_PANE_RESTORE is unset" {
  unset OPENCODE_PANE_RESTORE
  run pane_restore_enabled
  [ "$status" -eq 0 ]
}

@test "pane_restore_enabled returns 0 when OPENCODE_PANE_RESTORE is empty" {
  OPENCODE_PANE_RESTORE="" run pane_restore_enabled
  [ "$status" -eq 0 ]
}

@test "pane_restore_enabled returns 0 when OPENCODE_PANE_RESTORE is 1" {
  OPENCODE_PANE_RESTORE="1" run pane_restore_enabled
  [ "$status" -eq 0 ]
}

@test "pane_restore_enabled returns 0 when OPENCODE_PANE_RESTORE is true" {
  OPENCODE_PANE_RESTORE="true" run pane_restore_enabled
  [ "$status" -eq 0 ]
}

@test "pane_restore_enabled returns 1 when OPENCODE_PANE_RESTORE is 0" {
  OPENCODE_PANE_RESTORE="0" run pane_restore_enabled
  [ "$status" -eq 1 ]
}

@test "pane_restore_enabled returns 1 when OPENCODE_PANE_RESTORE is false" {
  OPENCODE_PANE_RESTORE="false" run pane_restore_enabled
  [ "$status" -eq 1 ]
}

@test "pane_restore_enabled returns 1 when OPENCODE_PANE_RESTORE is no" {
  OPENCODE_PANE_RESTORE="no" run pane_restore_enabled
  [ "$status" -eq 1 ]
}

@test "pane_restore_enabled returns 1 when OPENCODE_PANE_RESTORE is disabled" {
  OPENCODE_PANE_RESTORE="disabled" run pane_restore_enabled
  [ "$status" -eq 1 ]
}

@test "pane_restore_enabled returns 0 when OPENCODE_PANE_RESTORE is yes" {
  OPENCODE_PANE_RESTORE="yes" run pane_restore_enabled
  [ "$status" -eq 0 ]
}

@test "pane_restore_enabled returns 0 when OPENCODE_PANE_RESTORE is on" {
  OPENCODE_PANE_RESTORE="on" run pane_restore_enabled
  [ "$status" -eq 0 ]
}

@test "pane_restore_enabled returns 0 when OPENCODE_PANE_RESTORE is enabled" {
  OPENCODE_PANE_RESTORE="enabled" run pane_restore_enabled
  [ "$status" -eq 0 ]
}

@test "pane_restore_enabled returns 1 when OPENCODE_PANE_RESTORE is garbage" {
  OPENCODE_PANE_RESTORE="garbage" run pane_restore_enabled
  [ "$status" -eq 1 ]
}

@test "pane_restore_enabled returns 0 when OPENCODE_PANE_RESTORE is TRUE (case-insensitive)" {
  OPENCODE_PANE_RESTORE="TRUE" run pane_restore_enabled
  [ "$status" -eq 0 ]
}

@test "pane_restore_enabled returns 1 when OPENCODE_PANE_RESTORE is FALSE (case-insensitive)" {
  OPENCODE_PANE_RESTORE="FALSE" run pane_restore_enabled
  [ "$status" -eq 1 ]
}
