#!/usr/bin/env bash
# Tests for oc-fork — sources the script to test pure functions in isolation.
# Usage:  bash oc-fork.test.sh
# Deps:   A POSIX shell (bash), temp directory for fixtures

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="${SCRIPT_DIR}/oc-fork"

[[ -f "$SOURCE" ]] || { echo "FAIL: source script not found: $SOURCE"; exit 1; }

# ---- test harness ----------------------------------------------------------

PASS=0
FAIL=0

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "  PASS  $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $label"
    echo "        expected: '$expected'"
    echo "        actual:   '$actual'"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  if echo "$haystack" | grep -Fq "$needle" 2>/dev/null; then
    echo "  PASS  $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $label"
    echo "        expected to contain: '$needle'"
    echo "        in: '$haystack'"
    FAIL=$((FAIL + 1))
  fi
}

summary() {
  echo ""
  echo "Results: $PASS passed, $FAIL failed"
  if [[ "$FAIL" -gt 0 ]]; then
    exit 1
  fi
}

cleanup() {
  [[ -d "$TMPDIR" ]] && rm -rf "$TMPDIR"
}
trap cleanup EXIT

TMPDIR=$(mktemp -d /tmp/oc-fork-test.XXXXXX)

# ---- source the script to get pure functions --------------------------------
# We set MODE/DRY_RUN defaults the same way the script does
MODE="fork"
DRY_RUN=0
source "$SOURCE"

# ===== read_session_file tests ==============================================
echo "=== read_session_file ==="

# 1. Missing file
result=$(read_session_file "/nonexistent/file.json" 600000 1000000)
assert_eq "missing file returns SESSION_FILE_MISSING" "SESSION_FILE_MISSING" "$result"

# 2. Valid file with fresh timestamp
NOW=$((1700000000 * 1000))
cat > "$TMPDIR/valid.json" <<JSON
{"sessionId":"ses_test123","directory":"/home/test","timestamp":${NOW}}
JSON
result=$(read_session_file "$TMPDIR/valid.json" 600000 $NOW)
assert_eq "valid fresh session" "ses_test123" "$result"

# 3. Stale file
PAST=$((NOW - 700000 * 1000))
cat > "$TMPDIR/stale.json" <<JSON
{"sessionId":"ses_stale","directory":"/home/test","timestamp":${PAST}}
JSON
result=$(read_session_file "$TMPDIR/stale.json" 600000 $NOW)
assert_contains "stale file returns SESSION_STALE" "SESSION_STALE" "$result"

# 4. Malformed file (missing sessionId)
cat > "$TMPDIR/noid.json" <<JSON
{"directory":"/home/test","timestamp":${NOW}}
JSON
result=$(read_session_file "$TMPDIR/noid.json" 600000 $NOW)
assert_eq "missing sessionId returns SESSION_ID_MISSING" "SESSION_ID_MISSING" "$result"

# 5. Malformed file (missing timestamp)
cat > "$TMPDIR/nots.json" <<JSON
{"sessionId":"ses_nots","directory":"/home/test"}
JSON
result=$(read_session_file "$TMPDIR/nots.json" 600000 $NOW)
assert_eq "missing timestamp returns SESSION_TIMESTAMP_MISSING" "SESSION_TIMESTAMP_MISSING" "$result"

# 6. Barely fresh (edge of staleness window)
BORDER=$((NOW - 600000))
cat > "$TMPDIR/border.json" <<JSON
{"sessionId":"ses_border","directory":"/home/test","timestamp":${BORDER}}
JSON
result=$(read_session_file "$TMPDIR/border.json" 600000 $NOW)
assert_eq "borderline fresh session" "ses_border" "$result"

# 7. Barely stale (1ms over limit)
OVER=$((NOW - 600001))
cat > "$TMPDIR/over.json" <<JSON
{"sessionId":"ses_over","directory":"/home/test","timestamp":${OVER}}
JSON
result=$(read_session_file "$TMPDIR/over.json" 600000 $NOW)
assert_contains "borderline stale returns SESSION_STALE" "SESSION_STALE" "$result"

# 8. Unreadable file (cat fails due to permissions)
touch "$TMPDIR/noperm.json"
chmod 000 "$TMPDIR/noperm.json"
result=$(read_session_file "$TMPDIR/noperm.json" 600000 $NOW)
chmod 644 "$TMPDIR/noperm.json"
assert_eq "unreadable (no permission) returns SESSION_FILE_UNREADABLE" "SESSION_FILE_UNREADABLE" "$result"

# ===== parse_args tests =====================================================
echo ""
echo "=== parse_args ==="

# 9. Default mode (no args)
parse_args
assert_eq "default mode is fork" "fork" "$MODE"
assert_eq "default dry_run is 0" "0" "$DRY_RUN"

# 10. --copy-id flag
parse_args --copy-id
assert_eq "--copy-id sets mode copy" "copy" "$MODE"

# 11. -c short flag
parse_args -c
assert_eq "-c sets mode copy" "copy" "$MODE"

# 12. --dry-run flag
parse_args --dry-run
assert_eq "--dry-run sets DRY_RUN=1" "1" "$DRY_RUN"

# 13. combined flags
parse_args -c --dry-run
assert_eq "-c --dry-run mode" "copy" "$MODE"
assert_eq "-c --dry-run dry_run" "1" "$DRY_RUN"

# 14. --help (should exit 0, we test via subshell)
set +e
output=$(parse_args --help 2>&1)
rc=$?
set -e
assert_eq "--help exits 0" "0" "$rc"
assert_contains "--help prints usage" "Usage:" "$output"

# ===== check_prereqs tests ==================================================
echo ""
echo "=== check_prereqs ==="

# 15. tmux in PATH (should be if running in tmux, but we test the function)
result=$(check_prereqs)
# If tmux is in PATH, result is "ok"; if not, "tmux_missing". Either is OK.
if [[ "$result" == "ok" ]] || [[ "$result" == "tmux_missing" ]] || [[ "$result" == "opencode_missing" ]]; then
  echo "  PASS  check_prereqs returns valid status: $result"
  PASS=$((PASS + 1))
else
  echo "  FAIL  check_prereqs unexpected: $result"
  FAIL=$((FAIL + 1))
fi

# ===== summary ==============================================================
summary
