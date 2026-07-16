# GitHub REST API: Pull Request Review Comments

Reference for the GitHub REST API endpoint used by `posting-pr-review-comments` to publish inline review comments as a single batched review.

## Endpoint

```
POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
```

Creates a pull request review with a batch of inline comments. This is the only supported method for posting inline comments in a single coherent review, avoiding per-comment loop fragility.

**Do NOT use standalone comment endpoints.** Looping over `POST /repos/{owner}/{repo}/pulls/{pull_number}/comments` for each comment is fragile, non-atomic, and produces separate review entries instead of one coherent review.

**Do NOT use `gh pr review --comment`.** This command accepts only a single top-level body comment, not inline comments. It cannot attach comments to specific files and lines. For inline comments, the REST API is required.

### `--repo` vs endpoint path

- `gh pr`, `gh issue`, `gh repo` subcommands that accept `--repo`: use `--repo "$MANIFEST_GH_REPO"` to target the correct repository. `$MANIFEST_GH_REPO` is `"$MANIFEST_HOST/$MANIFEST_REPO"`, the canonical composite derived from the frozen manifest.
- `gh api` does NOT accept `--repo`. Use the explicit `/repos/$MANIFEST_REPO/...` endpoint path. Always add `--hostname "$MANIFEST_HOST"` to `gh api`.

## Safe payload construction — canonical recipe

**Never construct JSON with shell interpolation, eval, generated shell, or an unquoted/dynamic heredoc.** Dynamic JSON must be built only with a real serializer. Use `jq -n --arg/--argjson` or Python `json.dumps`. The frozen manifest `$MANIFEST_JSON` is the single source of truth.

**Only the exact `gh api --method POST` command form below is permitted for publication.** Do not use env wrappers, absolute-path gh, shell aliases/functions, bash/sh -c, eval/indirection, curl/wget/Python/other HTTP clients, GraphQL mutations, standalone comment endpoints, or alternate publication endpoints (see [Literal command prohibition](#literal-command-prohibition)).

### 1. Project PAYLOAD from manifest

```bash
PAYLOAD=$(printf '%s' "$MANIFEST_JSON" | jq '{
  commit_id: .head_sha,
  body: .body,
  event: .event,
  comments: .validated_comments
}')
```

### 2. Create all temp files BEFORE installing trap

Create three temp files: payload, response, and error. All are required. Set trap and secure all three before writing the payload.

```bash
PAYLOAD_FILE=$(mktemp)
RESPONSE_FILE=$(mktemp)
ERROR_FILE=$(mktemp)
trap 'rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$ERROR_FILE"' EXIT
chmod 600 "$PAYLOAD_FILE" "$RESPONSE_FILE" "$ERROR_FILE"
printf '%s' "$PAYLOAD" > "$PAYLOAD_FILE"
```

### 3. POST via `gh api` — capture exit code, branch on success/failure

**This construct is safe under `set -e` (errexit).** The `if` condition evaluates `gh` exit status directly; `POST_RC` is only assigned inside the `else` branch, never reached when errexit would fire. The `POST_RC=0` branch is taken when `gh` succeeds (exit 0), which is also safe under errexit.

```bash
if gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  --hostname "$MANIFEST_HOST" \
  "/repos/$MANIFEST_REPO/pulls/$MANIFEST_PR_NUMBER/reviews" \
  --input "$PAYLOAD_FILE" > "$RESPONSE_FILE" 2>"$ERROR_FILE"; then
  POST_RC=0
else
  POST_RC=$?
fi

if [ "$POST_RC" -eq 0 ]; then
  # Success: parse required response fields.
  # Review ID must be a JSON number, integral, and >0 — string "123" fails.
  REVIEW_ID=$(jq -er 'if (.id | type) == "number" and .id == (.id | floor) and .id > 0 then .id else empty end' "$RESPONSE_FILE") || { echo "FATAL: response missing/invalid review id (must be positive integer)" >&2; exit 1; }
  REVIEW_STATE=$(jq -er '.state' "$RESPONSE_FILE") || { echo "FATAL: response missing review state" >&2; exit 1; }
  # Clean payload and error temp files; keep RESPONSE_FILE for step 13 verification
  rm -f "$PAYLOAD_FILE" "$ERROR_FILE"
else
  # Failure: do NOT parse REVIEW_ID. Never print or log response/error bodies.
  # Preserve RESPONSE_FILE and ERROR_FILE for step 12 classification.
  # Control returns to SKILL.md step 12 which classifies the failure.
  # The EXIT trap cleans all temp files after classification or on unexpected exit.
  :
fi
```

On success, `$RESPONSE_FILE` is kept for step 13 verification. On failure, both `$RESPONSE_FILE` and `$ERROR_FILE` are preserved for step 12 classification.

**Never exit immediately on POST failure.** The `POST_RC` value and preserved files allow step 12 to classify the failure without losing diagnostic information. `gh` stderr is captured privately to `$ERROR_FILE` and used only for HTTP status extraction; the response body is read only privately for diagnostics. Never print response or error bodies to stdout or logs.

### 4. Classification and cleanup (SKILL.md step 12)

After the POST, SKILL.md step 12 classifies the outcome using `$POST_RC`, `$RESPONSE_FILE`, and `$ERROR_FILE`:

- **Success path** (`POST_RC=0`): Step 12 is a no-op. Step 13 verification uses `$RESPONSE_FILE`. After step 13 completes, all temp files are cleaned and the EXIT trap is cleared with `trap - EXIT`.
- **Failure path** (`POST_RC != 0`): Step 12 classifies by HTTP status. Never parse `REVIEW_ID` from `$RESPONSE_FILE` after a failed POST — the response may be an error document with a non-numeric or misleading `id` field. After classification, the EXIT trap cleans all temp files.
- **Unknown outcome** (timeout, disconnect, no HTTP status, 5xx): SKILL.md step 12 runs one bounded reconciliation (paginated reads of all PR reviews + inline comments, filtered by manifest fields, deterministic comparison). Single exact full match → confirmed-created, continue to step 13. Zero/partial/duplicate/read failure → indeterminate stop. Never auto-retry. Absence is not proof. Any retry requires a new current-turn directive and a complete workflow restart from step 1.

### Literal command prohibition

Only the exact `gh api --method POST -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" --hostname "$MANIFEST_HOST" "/repos/$MANIFEST_REPO/pulls/$MANIFEST_PR_NUMBER/reviews" --input "$PAYLOAD_FILE"` command form is permitted for publication. The following are prohibited:

| Prohibition | Rationale |
|---|---|
| **Environment wrappers** (env, npx, docker exec) | Introduces indirection that can bypass variable scoping or permission gates |
| **Absolute-path gh** (e.g. `/usr/bin/gh`) | Hardcodes a runtime path that may not exist on all hosts |
| **Shell aliases/functions** | Aliases and functions are not guaranteed to resolve to the same gh invocation |
| **bash/sh -c '...'** | String-wrapping the command breaks variable scoping and error propagation |
| **eval / indirection** | Dynamic command construction bypasses static analysis of the publish operation |
| **curl / wget / Python / other HTTP clients** | Only `gh api` is permitted; other clients bypass OpenCode's permission gating on `gh` |
| **GraphQL mutations** (`gh api graphql -f query='mutation...'`) | GraphQL mutations for review creation are not a documented stable API |
| **Standalone comment endpoint** (`POST /repos/{owner}/{repo}/pulls/{pull_number}/comments`) | Creates separate review entries instead of one coherent batched review |
| **Alternate publication endpoints** | Only `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` is documented and supported for batched inline comments |

When in doubt, use the exact invocation shown in step 3 above with no deviations.

### Fields

| Field | Required | Type | Description |
|---|---|---|---|
| `commit_id` | Required | string | SHA of the PR head commit to associate comments with. Must match the current PR head. Project from manifest `head_sha`. |
| `body` | Required when `event` is `COMMENT` or `REQUEST_CHANGES` | string | Top-level review body text. Supports Markdown. Must contain a concise summary that does not duplicate inline comments. |
| `event` | Required | string | Review action: `COMMENT`, `APPROVE`, or `REQUEST_CHANGES`. Always send explicitly. Omission defaults to `PENDING`, not `COMMENT`. |
| `comments[].path` | Required | string | Relative file path in the repository. |
| `comments[].line` | Required | integer | Line number in the file. For multi-line comments, this is the **end** line. |
| `comments[].side` | Optional | string | `LEFT` for the original/base version of the file, `RIGHT` for the new/head version. Defaults to `RIGHT`. |
| `comments[].start_line` | Optional | integer | Start line for a multi-line comment. Must be paired with `line` and `start_side`. |
| `comments[].start_side` | Optional | string | Must match `side`. `LEFT` or `RIGHT`. |
| `comments[].body` | Required | string | Comment text. Supports Markdown and GitHub suggestion blocks. |

### Response

On success (200 OK), the response contains the review object with `id`, `body`, `state`, `submitted_at`, `commit_id`, and the `pull_request_url`. The `id` can be used to fetch or manage the review later. Capture the review ID from this response via `jq -er '.id'` on the response temp file.

### Event-to-response-state mapping

The request `event` value differs from the review `state` returned in the response:

| Request event | Response `state` |
|---|---|
| `COMMENT` | `COMMENTED` |
| `APPROVE` | `APPROVED` |
| `REQUEST_CHANGES` | `CHANGES_REQUESTED` |

Never describe `COMMENT` as the API default. Always send `event` explicitly. When verifying the created review, check `state` against this mapping, not equality with the request event.

## Line and side rules

| Scenario | `line` | `side` | Example |
|---|---|---|---|
| Comment on added line | Line number in new file | `RIGHT` | Line 42 added in diff shows `line: 42, side: RIGHT` |
| Comment on unchanged context | Line number in new file | `RIGHT` | Context line at line 50 shows `line: 50, side: RIGHT` |
| Comment on deleted line | Line number in old file | `LEFT` | Line 30 removed shows `line: 30, side: LEFT` |
| Multi-line range (new) | First=start_line, Last=line | `RIGHT` | Lines 10-20 in new file: `start_line: 10, line: 20, side: RIGHT` |
| Multi-line range (deleted) | First=start_line, Last=line | `LEFT` | Lines 5-8 removed: `start_line: 5, line: 8, side: LEFT` |

**Do NOT use the `position` field.** It is deprecated in the REST API (closing down) and removed from the GraphQL schema. Use `line`, `side`, `start_line`, and `start_side` instead. Sources: [GitHub REST Pull Request Comments docs](https://docs.github.com/en/rest/pulls/comments) and [GraphQL deprecation changelog](https://github.blog/changelog/2022-09-13-the-position-field-is-being-removed-from-the-graphql-pullrequest-api/).

## Pagination during context gathering

The `POST .../reviews` endpoint itself is a single write operation (no pagination). However, during step 2 context gathering, paginated reads are required:

- **`PullRequest.reviews`** — paginate through all review bodies. Each page returns `pageInfo { hasNextPage endCursor }`.
- **`PullRequest.reviewThreads`** — paginate to capture all inline threads. Each thread has nested `comments` that may also need pagination.
- **`PullRequest.comments`** — paginate through all top-level PR conversation comments.
- **`PullRequest.commits`** — paginate through all commits on the PR. Each node carries `commit.oid`, `commit.messageHeadline`, `committedDate`, and nested `commit.statusCheckRollup` for per-commit status check context. The head commit's status rollup is the current PR check state.
- **`PullRequest.files`** — may be paginated for large PRs.

See `/github-graphql-first` for pagination patterns with `--paginate --slurp` or explicit cursor loops. Do not assume `first: 100` captures everything.

## Required permissions

- **Personal access token (fine-grained):** `Pull requests: write` (required for posting). `Contents: read` may be needed for repository context gathering but is not a posting-endpoint requirement.
- **Personal access token (classic):** `repo` scope (full control of private repositories). Classic tokens are legacy — prefer fine-grained tokens for least-privilege access.
- **GitHub App:** `Pull requests: write` permission (required for posting).
- **`gh` CLI:** Must be authenticated with a token that has the above permissions. Check with `gh auth status`.

If you get a 401 or 403, run `gh auth status` and verify the token scope.

## Error classification (workflow reference)

See SKILL.md step 12 for the complete error classification workflow. This table summarises the HTTP status patterns and their interpretation for step 12:

| Status | Step 12 classification | Exit code | Notes |
|---|---|---|---|
| **422 — stale anchor** | Diagnosable: commit_id/line mismatch | `exit 2` — restart from step 5 for fresh revalidation + one retry | Recurring 422 after retry: stop (not transient) |
| **422 — malformed/undetermined** | Definitive rejection | `exit 1` — terminal stop | Never falls through to step 13 |
| **401** | Definitive rejection | `exit 1` | Check `gh auth status` |
| **403** | Definitive rejection | `exit 1` | Token needs `Pull requests: write` |
| **404** | Definitive rejection | `exit 1` | Verify repo, PR, and file paths |
| **429** | Definitive rejection | `exit 1` | Never auto-retry rate limits |
| **Timeout / Disconnect / No status / 5xx** | **Unknown outcome. Never auto-retry.** | `exit 1` (or `POST_RC=0` if reconciled) | SKILL.md step 12 runs one bounded reconciliation: paginated fetch of all PR reviews → filter by manifest actor/SHA/state/body → for each candidate, paginated fetch of inline comments → normalized deterministic comparison. Single exact full match → confirmed-created, continue to step 13. Zero/partial/duplicate/read failure → indeterminate stop. Absence is not proof. Any retry requires new current-turn directive. |

## Actor/readback lifecycle

The authenticated actor is verified at multiple points to ensure the published review is attributed to the correct identity:

1. **Step 1 — Resolution:** `ACTOR=$(gh api --hostname "$HOST" user --jq .login)` establishes the authenticated identity for the target host. This value is frozen into the authorization envelope (step 1.6).
2. **Step 10 — Preflight:** `FINAL_ACTOR` is re-fetched and compared against the manifest to detect session changes (e.g. `gh auth switch` between steps). If the actor changed, do not POST.
3. **Step 13 — Verification:** `RESPONSE_ACTOR` from the saved `$RESPONSE_FILE` (`user.login`) must match `$MANIFEST_ACTOR`. This confirms the review was created under the expected identity.

The actor is never obtained from untrusted PR content or user-supplied strings. All actor values originate from `gh api user` on the target host.

## Read-back verification of inline comments

After publication, verify the created review's inline comments. Fetch via the comments endpoint with paginated flattening, then compare against the manifest (see SKILL.md step 13 for the full workflow).

The review-level fields (`id`, `state`, `body`, `commit_id`, `pull_request_url`, `user.login`) are read from the saved `$RESPONSE_FILE` that was preserved from the POST response (step 11 success path in the [canonical recipe](#safe-payload-construction--canonical-recipe)). Actor (`user.login`) must equal the manifest actor.

```bash
# Capture raw paginated output FIRST, then flatten — never pipe directly
# (which would mask gh failure if pipefail is not set)
if RAW_INLINE=$(gh api \
  --method GET \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  --hostname "$MANIFEST_HOST" \
  "/repos/$MANIFEST_REPO/pulls/$MANIFEST_PR_NUMBER/reviews/$REVIEW_ID/comments" \
  --paginate); then
  INLINE_COMMENTS_JSON=$(printf '%s' "$RAW_INLINE" | jq -e -s 'add // []') || {
    echo "FATAL: Inline comments parse failed" >&2; exit 1
  }
else
  echo "FATAL: Inline comments read failed" >&2; exit 1
fi
```

**No code path parses `REVIEW_ID` after a failed POST.** If `POST_RC` was nonzero, `$REVIEW_ID` is never assigned and step 13 is never reached — the workflow routes through step 12 error classification instead.

For each returned inline comment, verify against the manifest entry:
- `path` matches
- `line` matches
- `side` matches
- `body` matches
- If the manifest entry has `start_line` and `start_side` both non-null, verify those match as well. Both-null or absent start fields in both manifest and API comments match as absent.

See SKILL.md step 9 for the validator rules used during sanitization (rejects incomplete range pairs, enforces `start_side == side`, positive integers; accepts both-null as absent).

## Suggestion blocks

GitHub Flavored Markdown suggestion blocks render as clickable "Apply" buttons:

````
```suggestion
replacement code here
```
````

Rules for valid suggestion blocks:
- The replacement must be exact and complete (no placeholders).
- Must be syntactically valid in the target language.
- Must preserve behavior.
- Must fit within the selected diff range (one contiguous hunk).

## Source links

- [Pull Request Reviews API (create)](https://docs.github.com/en/rest/pulls/reviews?apiVersion=2022-11-28#create-a-review-for-a-pull-request) — official REST docs for the batch review endpoint.
- [Pull Request Review Comments API](https://docs.github.com/en/rest/pulls/comments?apiVersion=2022-11-28#create-a-review-comment-for-a-pull-request) — standalone comment endpoint (for reference; not recommended for batched publication).
- [gh pr review manual](https://cli.github.com/manual/gh_pr_review) — `gh pr review` command; does not support inline comments.
- [gh api manual](https://cli.github.com/manual/gh_api) — `gh api` command for raw REST calls.
- [GitHub Changelog: position field removed](https://github.blog/changelog/2022-09-13-the-position-field-is-being-removed-from-the-graphql-pullrequest-api/) — explains the `position` deprecation.
