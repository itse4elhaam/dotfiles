---
name: pr-review-dossier
description: Build an evidence-backed HTML dossier of existing GitHub PR review feedback — investigate reviewer concerns, decide the way ahead.
---

# PR Review Dossier

Build an unbiased investigation dossier for PR review feedback that recommends a way ahead or approval decision. This is a read-only review-feedback intake, evidence check, and HTML report workflow; it is not the existing `/review` two-axis branch review, `/check-pr` readiness flow, or fix loop like `greploop`.

**REQUIRED SUB-SKILLS:** Use `/github-graphql-first` for GitHub data access and `/readable-html-dossier` for the final report.

## Scope boundary

Use `/check-pr` for PR readiness, failing checks, fixing/resolving comments, or preparing to merge. Use `/greploop` for iterative Greptile optimization. Use `/review` for two-axis diff/spec review. This skill is read-only unless the user separately asks for fixes.

## Workflow

1. **Find the PR for the branch.** Prefer the cheapest reliable command for detection, such as `gh pr view --json number,headRefName,url`.
   Completion: you have exactly one PR number/url, or you report that the current branch has no raised PR.

2. **Fetch review data through GraphQL.** Use `/github-graphql-first`; gather at least:
   - review-level bodies from `reviews`
   - top-level PR conversation comments from `comments`
   - inline review threads from `reviewThreads`, including all comments, path/line, `isResolved`, `isOutdated`, and author metadata
   Completion: no relevant reviews, reviewer bodies, or review threads are missing due to pagination.

3. **Separate reviewer accounts.** Classify by account, then by category:
   - **Human review:** authors that are not bots/apps.
   - **Bot review:** `Bot`/`App` actors, `[bot]` logins, CI/review apps, linters, and automated review agents.
   Completion: every account that left review material appears exactly once in a reviewer inventory.

4. **Pull the major thread before inline threads.** For each reviewer account, read their review-level body/top-level guidance first, then their inline review threads. Treat the major body as context, not as proof.
   Completion: each inline finding can be traced back to reviewer, category, and any broader guidance they provided.

5. **Investigate without bias.** For each review issue, inspect the current code, relevant history/diff, and surrounding tests. Decide one of:
   - **Correct:** the issue still applies.
   - **Stale:** later code changes or reviewer context make it obsolete.
   - **Incorrect:** the claim is contradicted by code, tests, or requirements.
   - **Needs human decision:** tradeoff/product ambiguity remains.
   Completion: every issue has evidence and a suggested fix or no-fix rationale.

6. **Use parallel subagents when available.** Split investigation by reviewer account, file area, or bot/human category. **Treat subagent results as a starting point, not a finished product.** Always verify their findings against the actual code — re-read files, check diffs, and confirm evidence before accepting a conclusion. Do not let subagents decide final truth without controller verification.
   Completion: findings are reconciled into one consistent inventory.

7. **Write the HTML dossier.** Use `/readable-html-dossier`. Include:
   - PR title/url/branch
   - reviewer inventory by human vs bot
   - issue cards with status, evidence, file links, suggested fix, and staleness rationale
   - background context needed by a human reader
   - links to domain-language docs when relevant
   Completion: the report is a standalone `.html` file and the path is reported.

## Bias controls

- Do not assume humans are correct or bots are noisy.
- Do not mark a thread stale only because it is resolved; inspect the current code.
- Do not mark a bot finding actionable only because it is automated; verify the failure mode.
- Preserve reviewer wording in evidence, but write conclusions in your own neutral language.
- When a fix is suggested, name the smallest code change that would satisfy the valid concern.

## Report sections

Use these sections unless the PR has no review material:

1. Summary verdict
2. Reviewer inventory
3. Human review findings
4. Bot review findings
5. Stale / incorrect findings
6. Suggested fix plan
7. Decision / way ahead
8. Evidence appendix

## Stop conditions

- No PR exists for the current branch: report that and stop.
- GitHub auth fails: report the exact command that failed and what permission is needed.
- GraphQL schema lacks required data: research the current docs, then use the narrowest fallback and explain why.
