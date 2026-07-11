---
name: elhaam-review
description: Review code changes across seven lenses — codebase boundary, simplicity, test confidence, security, scalability, maintainability, and automation feedback.
---

# Elhaam Review

Review the interaction between each diff hunk and the surrounding system. Catch boundary mistakes, unnecessary complexity, missing confidence, hidden assumptions, and opportunities to make future agents/tools catch the same issue automatically.

## Required context gathering

1. **Read the diff and changed files.** Identify feature intent, touched layers, and risky hunks.
   Completion: every changed file has been read and categorized by risk.
2. **Search before judging.** Find existing helpers, constants, types, server/data patterns, tests, and naming conventions near touched code.
   Completion: existing patterns near each hunk are known before any opinion is formed.
3. **For GitHub PR review data, use `/github-graphql-first` when available; otherwise query GraphQL `reviewThreads` directly.** Inline thread context matters; REST-flattened comments are not enough.
   Completion: all review threads are collected with their full inline context.
4. **Default deliverable is an HTML findings file.** Unless the user explicitly asks for Markdown, create a standalone review dossier using `/readable-html-dossier` when available; otherwise write a concise self-contained HTML file with inline CSS. Include evidence, uncertainty, source links, and the output path.
   Completion: the deliverable format is decided and communicated.

## Review lenses

### 1. Hunk to codebase boundary

Ask whether each hunk fits the boundary it touches.

- Existing helper available? Prefer it over a local duplicate (`tryCatch`, formatters, validators, query helpers).
- Shared concept? Move to constants/types/enums/options instead of scattering strings or shapes.
- New pattern? Require justification; otherwise align locally.
- Good pattern? Call it out so the author repeats it.

### 2. Simpler implementation, same behavior

Push for simple, linear code without feature loss. Before suggesting simplification, name the behavior, edge cases, auth behavior, UX, and API contracts that must remain unchanged.

- Prefer guard clauses over nested conditionals.
- Extract named functions/variables when logic stops reading like English.
- Replace nested ternaries/repeated branches with maps or small helpers/components.
- Create generic utilities only when operations are genuinely the same shape.

### 3. Tests as confidence

Tests are required when the hunk has logic, risk, or future extension pressure.

- Complex function or transformed data? Ask for focused unit tests.
- User flow? Prefer behavior/user-experience tests over implementation-heavy tests.
- Risky production path? Require multiple scenarios, not only happy-path manual QA.
- Repeatable issue? Ask whether a test or lint rule should prevent it next time.

### 4. Server, database, and security boundary

Treat server/data boundaries as public attack surfaces until proven otherwise.

- Classify server code by caller and effect: client-triggered mutations belong in server actions with auth and ownership checks; public/client-readable GET access belongs in route handlers; server-internal reads and shared logic belong in `server-only` helpers.
- Do not export read/query helpers as `use server` actions just for reuse.
- Every DB access must prove auth, ownership/tenant scope, null handling, failure behavior, and IDOR resistance at or adjacent to the query.
- Do not leak attacker-helpful detail in client-visible errors (`tenant not found for id X`). Log detail server-side.

### 5. Scalability and grouped-hunk effects

Look across hunks, not just inside one line. Grouped hunks can create N+1 or repeated work even when each hunk looks locally reasonable; trace request, query, and API-call counts across the full flow.

- Loops with DB/API calls: check N+1 and batching risks.
- `Promise.all`: decide whether one failure should fail everything.
- Check caching, ISR/SSG, background jobs, and data type mismatches under production data.
- Ask how the change behaves with more users, tenants, records, feature flags, and retries.

### 6. Future maintainer clarity

Ask whether a new engineer can safely extend this next month.

- Names reveal intent.
- Assumptions are explicit, not hidden in branches or magic strings: tenant scope, ordering, data shape, feature flags, retries, time zones, and nullability.
- Client/server boundaries are localized.
- Adding one more case does not require copying fragile code.

### 7. Automation feedback loop

Every repeatable review finding should become future leverage: test coverage, lint/type rule, shared helper, documentation/domain language, agent instruction, or skill update.

## Output contract

Default to a standalone HTML findings file for human review. Use Markdown only when the user explicitly requests Markdown. The file must be readable without conversation context and include: scope reviewed, evidence links, unresolved uncertainties, severity-tagged findings, and automation follow-ups.

Use concise severity-tagged comments inside the dossier:

```md
[P1 security] `path:line` Problem. Why it matters. Smallest fix.
[P2 maintainability] `path:line` Problem. Existing pattern to use. Smallest fix.
[P3 confidence] Missing scenario. What test/manual QA would prove it.
```

Separate **Blockers** (security/correctness/data loss/missing confidence), **Should fix** (readability/duplication/constants/local pattern drift), and **Teach-back** (good patterns/automation opportunities/why it matters).

## Review discipline

- **Classify every export by caller and effect.** A `use server` export that client code calls is an action with auth and ownership requirements, not a helper.
- **Search existing patterns before judging each hunk.** Every diff sits inside established conventions — find them first.
- **Require evidence proportional to risk.** Happy-path manual QA is insufficient for data/server/payment logic; demand multi-scenario tests.
- **Name the behaviour, edge cases, and contracts before suggesting simplification.** Silent behaviour removal is not simplification.
- **Pair every style flag with a maintainability or extension risk.** Style without consequence is noise.
- **Convert every repeatable finding into leverage.** Each repeated issue should produce a test, lint rule, shared helper, or agent instruction.
