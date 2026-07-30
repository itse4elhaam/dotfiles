#!/usr/bin/env bats

# PaneIdentity tests — verifies the pane coordinate key format
# Key format: <session-name>:<window>.<pane>|<cwd>
# Example:    my-session:1.2|/home/user/project

setup() {
  load "../helpers/binding-store"
  load "../helpers/pane-identity"
}

# ─── pane_identity_build ─────────────────────────────────────────────────────

@test "pane_identity_build constructs key from session, window, pane, cwd" {
  result="$(pane_identity_build "my-session" 1 2 "/home/user/project")"
  [ "$result" = "my-session:1.2|/home/user/project" ]
}

@test "pane_identity_build handles session names with dots" {
  result="$(pane_identity_build "session.v1" 1 1 "/tmp")"
  [ "$result" = "session.v1:1.1|/tmp" ]
}

@test "pane_identity_build handles cwd with spaces" {
  result="$(pane_identity_build "my-session" 1 1 "/home/user/my projects")"
  [ "$result" = "my-session:1.1|/home/user/my projects" ]
}

@test "pane_identity_build handles window index 0 and pane index 0" {
  result="$(pane_identity_build "test" 0 0 "/")"
  [ "$result" = "test:0.0|/" ]
}

# ─── pane_identity_parse ─────────────────────────────────────────────────────

@test "pane_identity_parse parses standard key" {
  pane_identity_parse "my-session:1.2|/home/user/project"
  [ "$pane_session" = "my-session" ]
  [ "$pane_window" = "1" ]
  [ "$pane_index" = "2" ]
  [ "$pane_cwd" = "/home/user/project" ]
}

@test "pane_identity_parse handles session with dots" {
  pane_identity_parse "session.v1:3.4|/tmp"
  [ "$pane_session" = "session.v1" ]
  [ "$pane_window" = "3" ]
  [ "$pane_index" = "4" ]
  [ "$pane_cwd" = "/tmp" ]
}

@test "pane_identity_parse handles cwd with colons (not ambiguous)" {
  pane_identity_parse "my-session:1.1|/home/user/project:sub"
  [ "$pane_session" = "my-session" ]
  [ "$pane_window" = "1" ]
  [ "$pane_index" = "1" ]
  [ "$pane_cwd" = "/home/user/project:sub" ]
}

@test "pane_identity_parse handles cwd with pipe (escaped)" {
  pane_identity_parse "my-session:2.3|/home/user/project|backup"
  [ "$pane_session" = "my-session" ]
  [ "$pane_window" = "2" ]
  [ "$pane_index" = "3" ]
  [ "$pane_cwd" = "/home/user/project|backup" ]
}

@test "pane_identity_parse returns 1 for malformed key (no session)" {
  run pane_identity_parse ":1.2|/tmp"
  [ "$status" -eq 1 ]
}

@test "pane_identity_parse returns 1 for malformed key (no pipe)" {
  run pane_identity_parse "session:1.2"
  [ "$status" -eq 1 ]
}

@test "pane_identity_parse returns 1 for malformed key (no dot)" {
  run pane_identity_parse "session:1|/tmp"
  [ "$status" -eq 1 ]
}

@test "pane_identity_parse returns 1 for empty key" {
  run pane_identity_parse ""
  [ "$status" -eq 1 ]
}

@test "pane_identity_parse round-trip matches build" {
  built="$(pane_identity_build "round-trip" 2 3 "/opt/app")"
  pane_identity_parse "$built"
  [ "$pane_session" = "round-trip" ]
  [ "$pane_window" = "2" ]
  [ "$pane_index" = "3" ]
  [ "$pane_cwd" = "/opt/app" ]
}

# ─── tmux_get_pane_identity (integration with tmux env) ──────────────────────

@test "tmux_get_pane_identity reads from tmux env vars" {
  TMUX_PANE="%1" \
  tmux_session_name="my-session" \
  tmux_window_index="1" \
  tmux_pane_index="2" \
  pane_current_path="/home/user/project" \
  tmux_get_pane_identity
  [ "$pane_identity" = "my-session:1.2|/home/user/project" ]
}
