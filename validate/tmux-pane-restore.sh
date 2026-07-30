#!/usr/bin/bash
set -euo pipefail

PASS=0
FAIL=0

pass() { PASS=$((PASS+1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }

check() {
  local desc="$1" cmd="$2"
  if sh -c "$cmd"; then
    pass "$desc"
  else
    fail "$desc"
  fi
}

echo "=== tmux-pane-restore validation ==="
echo ""

check "opencode-continue-pane script exists" \
  "test -x '$PWD/scripts/opencode-continue-pane'"

check "tmux-pane-bind plugin file exists" \
  "test -f '$PWD/.config/opencode/plugins/tmux-pane-bind.ts'"

check "tmux.conf has resurrect-processes config" \
  "grep -q 'resurrect-processes' '$PWD/.tmux.conf'"

check "bats tests pass for pane_identity" \
  "bats '$PWD/test/bats/pane_identity.bats' &>/dev/null"

check "bats tests pass for binding_store" \
  "bats '$PWD/test/bats/binding_store.bats' &>/dev/null"

check "bats tests pass for opencode_continue_pane" \
  "bats '$PWD/test/bats/opencode_continue_pane.bats' &>/dev/null"

check "vitest tests pass for plugin" \
  "cd '$PWD' && npx vitest run &>/dev/null"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
