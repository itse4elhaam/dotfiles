#!/usr/bin/env bash
# verify-bak-diff.sh
# Compares HEAD against bak/<current-branch> after a conflict-rebase-resolution run.
# Surfaces hunks that are NOT attributable to either:
#   (a) the target branch's new commits, OR
#   (b) our own pre-resolution local commits.
# Anything in the "unexpected" bucket is a STOP condition before push.
#
# Usage: ./verify-bak-diff.sh <current-branch> <target-remote-ref>
#   <current-branch>     e.g. feature-x  (bak/feature-x is the backup)
#   <target-remote-ref>  e.g. origin/main  (the rebase target)
#
# Exit codes:
#   0 — no unexpected changes; safe to proceed
#   1 — unexpected changes detected (review required)
#   2 — usage error or missing refs
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <current-branch> <target-remote-ref>" >&2
  exit 2
fi

BRANCH="$1"
TARGET="$2"
BAK="bak/${BRANCH}"

# Refs must exist
if ! git rev-parse --verify --quiet HEAD >/dev/null; then
  echo "error: HEAD not resolvable" >&2; exit 2
fi
if ! git rev-parse --verify --quiet "${BAK}" >/dev/null; then
  echo "error: backup branch '${BAK}' not found" >&2; exit 2
fi
if ! git rev-parse --verify --quiet "${TARGET}" >/dev/null; then
  echo "error: target ref '${TARGET}' not found" >&2; exit 2
fi

OLD_HEAD=$(git rev-parse "${BAK}")
NEW_HEAD=$(git rev-parse HEAD)
TARGET_SHA=$(git rev-parse "${TARGET}")

echo "OLD_HEAD (bak):   ${OLD_HEAD}"
echo "NEW_HEAD (HEAD):  ${NEW_HEAD}"
echo "TARGET:           ${TARGET_SHA}"
echo

# Set of commits attributed to the target (anything reachable from TARGET but not from BAK).
# These explain hunks that came from the target branch during rebase.
TARGET_COMMITS=$(git rev-list "${OLD_HEAD}..${TARGET_SHA}" 2>/dev/null || true)

# Set of commits attributed to our local work (reachable from BAK, but not from the target's
# merge-base with BAK). These are the commits we replayed.
LOCAL_BASE=$(git merge-base "${OLD_HEAD}" "${TARGET_SHA}" || echo "${OLD_HEAD}")
LOCAL_COMMITS=$(git rev-list "${LOCAL_BASE}..${OLD_HEAD}" 2>/dev/null || true)

echo "== Commits added from target (${TARGET}) =="
if [[ -z "${TARGET_COMMITS}" ]]; then
  echo "  (none — target did not advance beyond our backup base)"
else
  git log --oneline --no-decorate "${TARGET_COMMITS}" 2>/dev/null || echo "${TARGET_COMMITS}"
fi
echo

echo "== Our local commits replayed (from bak/${BRANCH}) =="
if [[ -z "${LOCAL_COMMITS}" ]]; then
  echo "  (none)"
else
  git log --oneline --no-decorate "${LOCAL_COMMITS}" 2>/dev/null || echo "${LOCAL_COMMITS}"
fi
echo

# To detect "unexpected" changes, we identify hunks that:
#   1. Exist in the diff from OLD_HEAD to NEW_HEAD (HEAD moved during rebase)
#   2. Cannot be attributed to any single target commit's patch NOR any single
#      local commit's patch.
# Attribution is done on a path-basis first (any path that appears in either
# TARGET_COMMITS or LOCAL_COMMITS is "reachable"), then per-hunk context.

EXPLAINED_PATHS=$(
  {
    if [[ -n "${TARGET_COMMITS}" ]]; then
      git diff --name-only "${OLD_HEAD}..${TARGET_SHA}"
    fi
    if [[ -n "${LOCAL_COMMITS}" ]]; then
      git diff --name-only "${LOCAL_BASE}..${OLD_HEAD}"
    fi
  } | sort -u
)

ALL_CHANGED_PATHS=$(git diff --name-only "${OLD_HEAD}..${NEW_HEAD}" | sort -u)

UNEXPECTED_PATHS=$(
  comm -23 <(echo "${ALL_CHANGED_PATHS}") <(echo "${EXPLAINED_PATHS}")
)

if [[ -z "${UNEXPECTED_PATHS}" ]]; then
  echo "== UNEXPECTED_CHANGES == (none)"
  echo "== RESULT: clean — all changed paths are attributed to target or our local commits =="
  exit 0
fi

echo "== UNEXPECTED_CHANGES (STOP — review) =="
echo "  Paths changed in HEAD but not attributable to target or local commits:"
while IFS= read -r p; do
  [[ -z "${p}" ]] && continue
  echo "  --- ${p} ---"
  git diff "${OLD_HEAD}..${NEW_HEAD}" -- "${p}" | head -200
  echo
done <<< "${UNEXPECTED_PATHS}"
echo
echo "== RESULT: unexpected changes detected — review the hunks above before pushing =="
exit 1