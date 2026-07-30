---
name: github-graphql-first
description: Use when fetching structured GitHub data with gh — especially PR review threads, nested repository data, or any data that forms a graph.
---

# GitHub GraphQL First

Use `gh api graphql` as the default for structured GitHub data. Use REST endpoints or `gh pr view --json` only when the data is flat, the GraphQL API cannot expose it, or a command is only for quick PR detection.

## Core rule

If you are about to run `gh api repos/...`, `gh pr view --json`, or multiple REST calls to reconstruct relationships, stop and ask: **is this task-shaped data — naturally a graph?** If yes, use GraphQL.

Good GraphQL fits:
- PR review threads with comments and resolution state
- Review bodies grouped by reviewer and state
- Issue/PR comments plus author metadata
- Nested repository, commit, check, project, or timeline data

Acceptable non-GraphQL fits:
- Detecting the current PR number or branch quickly
- Running an existing high-level `gh` workflow command (`gh pr checks`, `gh pr checkout`)
- GitHub functionality that is absent from the GraphQL schema after checking docs/introspection

When you fall back, state the reason in the final notes.

## Host qualification

Every `gh api graphql` call must include `--hostname "$HOST"`. The host value is either:

- **Provided by a calling skill** (e.g. `posting-pr-review-comments` passes its resolved `$HOST` and `$GH_REPO`). Use those variables directly.
- **Derived from the current repo** when called standalone (no caller-provided host):
  ```bash
  REPO_URL=$(gh repo view --json url --jq .url)
  HOST=$(python3 -c "import urllib.parse,sys; print(urllib.parse.urlparse(sys.argv[1]).hostname)" "$REPO_URL")
  ```
  Derive `$REPO` from `$HOST` and caller-provided target, or from `gh repo view` in standalone mode.

When a caller provides host and repo variables, always prefer them over local derivation. Append `--hostname "$HOST"` to every `gh api graphql` invocation.

## Workflow

1. **Discover the shape.** Research the current GitHub GraphQL docs or introspect the schema before assuming fields exist.
   ```bash
   gh api graphql -f query='query { __type(name: "PullRequest") { fields { name } } }' --hostname "$HOST"
   ```
   Completion: you know the type, field names, and pagination boundaries you need.

2. **Use variables, not string interpolation.** Pass strings with `-f`; pass ints/bools/null with `-F`. Owner/repo variables must come from the canonical target when provided by a caller.
   ```bash
   gh api graphql -f owner="$OWNER" -f repo="$REPO" -F pr="$PR" \
     -f query='query($owner: String!, $repo: String!, $pr: Int!) { ... }' \
     --hostname "$HOST"
   ```
   Completion: shell values are not embedded inside the GraphQL text.

3. **Paginate deliberately.** Every connection needs an explicit pagination plan with `pageInfo { hasNextPage endCursor }`. Use `--paginate --slurp` only for one verified cursor path; page nested or independent connections with separate task-shaped queries.
   Completion: no `first: 100` assumption is left as a hidden truncation risk.

4. **Keep queries task-shaped.** Fetch exactly the fields required for the decision. Do not paste a universal mega-query unless you need every branch of it.
   Completion: the response can be explained in one sentence.

5. **For mutations, batch with aliases only after verifying IDs.** Example shape: `a: resolveReviewThread(...)`, `b: resolveReviewThread(...)`.
   Completion: every mutation target came from a fresh GraphQL read.

## PR review field map

Research current docs first, then usually inspect:

| Need | GraphQL area |
|---|---|
| Review-level bodies | `PullRequest.reviews` |
| Inline threads | `PullRequest.reviewThreads` |
| Thread state | `PullRequestReviewThread.isResolved`, `isOutdated` |
| Thread comments | `PullRequestReviewThread.comments` |
| Top-level PR conversation | `PullRequest.comments` |
| Reviewer identity | `author { login __typename }` |

## Common mistakes

- Using REST because it is shorter, then manually rebuilding thread structure.
- Running one paginated query with several connections and assuming all nested connections paginated.
- Treating bot and human comments the same before checking `author.__typename`, login suffixes, and review context.
- Hardcoding old schema fields instead of checking docs or introspection.
