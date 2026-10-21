---
name: elhaam-review
description: "Review code changes across seven lenses: codebase fit, simplicity, test confidence, security, whole-flow correctness and scale, maintainability, and automation feedback."
---

# Elhaam Review

Review each diff hunk against the surrounding system. Catch boundary mistakes, unnecessary complexity, missing confidence, and hidden assumptions. Turn repeat findings into prevention.

## Required context gathering

1. **Read the diff and changed files.** Identify feature intent, touched layers, and risky hunks. Record base/head and the promised user outcome, including non-goals.
   Completion: every changed file is read and categorized by risk.
2. **Search before judging.** Find existing helpers, constants, types, server/data patterns, tests, and naming conventions near touched code.
   Completion: existing patterns near each hunk are known before any opinion is formed.
3. **For GitHub PR review data, use `/github-graphql-first` when available; otherwise query GraphQL `reviewThreads` directly.** Inline thread context matters; REST-flattened comments are not enough.
   Completion: all threads and replies are collected, including resolved/outdated ones. Verify claimed fixes against current code; distinguish implemented, deferred, and withdrawn concerns.
4. **Falsify candidate findings.** Check callers, validation, installed versions, author replies, and product intent. Name the actor/action/state, observable failure, and causal path. Static proof can suffice.
   Completion: defects survive counterevidence; standards feedback, confidence gaps, and questions remain distinct.
5. **Deliver findings** using the [output contract](#output-contract).
   Completion: HTML is produced; publication occurs only when explicitly authorized.

## Review lenses

### 1. Hunk to codebase boundary

Ask whether each hunk fits the boundary it touches.

- Existing helper available? Prefer it over a local duplicate (`tryCatch`, formatters, validators, query helpers).
- Shared concept? Move to constants/types/enums/options instead of scattering strings or shapes.
- **Single source of truth.** Give shared policy one owner; verify real callers use it. Share meaning, not coincidentally equal values.
- New pattern? Require justification; otherwise align locally.
- Good pattern? Call it out so the author repeats it.

### 2. Simpler implementation, same behavior

Push for simple, linear code without feature loss. Before suggesting simplification, name the behavior, edge cases, auth behavior, UX, and API contracts that must remain unchanged.

- Prefer guard clauses over nested conditionals.
- Extract named functions/variables when logic stops reading like English.
- Keep private functions/components beside their consumer. Preserve comments explaining constraints or rationale.
- Replace nested ternaries/repeated branches with maps or small helpers/components.
- **Cyclomatic complexity.** Review branching paths and the repo's lint threshold; simplify decisions, not just function length.
- Create generic utilities only when operations are genuinely the same shape.

### 3. Tests as confidence

Tests are required when the hunk has logic, risk, or future extension pressure. Existing tests may supply that proof.

- Complex function or transformed data? Ask for focused unit tests.
- User flow? Prefer behavior/user-experience tests over implementation-heavy tests.
- Risky production path? Require multiple scenarios, not only happy-path manual QA.
- Choose scenarios from the conditions that change execution: feature enabled/disabled, fresh/persisted state, and slow/failed dependencies. For asynchronous UI, verify eventual recovery and the next user action. Assert relevant external-call counts and blocking behavior, alongside returned values.
- **Regression tests.** For critical rules, prove the test fails when the rule breaks; use focused mutation testing where needed.
- **Test fidelity.** For cross-layer, database, or packaging changes, read [test confidence](references/conditional-checks.md#test-confidence).
- Repeatable issue? Ask whether a test or lint rule should prevent it next time.

### 4. Server, database, and security boundary

Treat server/data boundaries as public attack surfaces until proven otherwise. Classify exports by caller and effect.

- Every DB access needs proof of auth, ownership/tenant scope, null handling, failure behavior, and IDOR resistance. Trace the enforcement path; proven middleware/service/query/database guarantees count. Authentication alone does not prove ownership.
- **Defensive programming: distrust the boundary.** Bad input and external failures are expected. Validate runtime inputs/provider replies and return controlled errors; preserve recoverable state. Trace casts and non-null assertions to their guarantees.
- **Offensive programming: fail fast on broken invariants.** A broken internal guarantee is our bug to diagnose. Use assertions and exhaustive state handling; fail visibly before unsafe effects. State why the condition must hold; avoid success-shaped defaults that conceal a broken guarantee.
- Choose by fault ownership: an invalid guest request needs defensive handling; an impossible internal transition needs offensive detection. For examples, read [offensive and defensive programming](references/conditional-checks.md#offensive-and-defensive-programming).
- For React or Next.js changes, read [framework boundaries](references/conditional-checks.md#react-and-nextjs), including actions versus routes and internal helpers.
- Do not leak attacker-helpful detail in client-visible errors (`tenant not found for id X`). Log detail server-side.

### 5. Whole-flow correctness and scalability

Look across hunks, not just inside one line. Grouped hunks can create N+1 or repeated work even when each hunk looks locally reasonable; trace request, query, and API-call counts across the full flow.

- Loops with DB/API calls: check N+1 and batching risks.
- `Promise.all`: decide whether one failure should fail everything. Distinguish rejected promises from returned error values; check partial success and retry semantics.
- For multi-step writes, payments, bookings, or jobs with side effects, read [stateful workflows](references/conditional-checks.md#stateful-workflows).
- Check caching, ISR/SSG, background jobs, and data type mismatches under production data.
- Ask how the change behaves with more users, tenants, records, feature flags, and retries.
- For shared hooks, middleware, and workflows, enumerate the user actions that trigger them. Trace awaited DB/API calls through completion. Does each action need that work before returning? Check timeouts, retries, and queued writes. Distinguish immediate optimistic UI feedback from actual request completion.

### 6. Future maintainer clarity

Ask whether a new engineer can safely extend this next month.

- Names reveal intent.
- Assumptions are explicit, not hidden in branches or magic strings: tenant scope, ordering, data shape, feature flags, retries, time zones, and nullability.
- Client/server boundaries are localized.
- Adding one more case does not require copying fragile code.
- For loading flags, locks, pending counters, and disabled controls, trace entry and exit through success, failure, cancellation, and overlapping operations. Verify that completion updates every consumer, including same-tab state and cross-tab listeners.

### 7. Automation feedback loop

**Prevention.** Every repeatable finding needs a durable control: tests, lint/types, a shared helper, documentation/domain language, an `AGENTS.md` pathway, or a skill update.

- Existing rule missed it? Check discovery, configuration, coverage, and whether it runs before adding another rule.
- Protect the next caller/job at the shared boundary. Group symptoms by cause; keep unrelated rollout cleanup as a follow-up.
- For changed enforcement, or enforcement used to dismiss a finding, verify a violating and a legitimate case. Distinguish documented, locally runnable, running in CI, and required before merge/deploy.

## Output contract

Always produce a standalone HTML findings file, readable without conversation context. Markdown requests get Markdown in addition. Use `/readable-html-dossier` when available; otherwise use self-contained HTML with inline CSS. Include scope/revision, evidence/source links, uncertainties, severity-tagged findings, automation follow-ups, and the output path.

Use concise severity-tagged comments:

```md
[P1 security] `path:line` Problem. Why it matters. Smallest fix.
[P1 correctness] `path:line` Action/state. Observable failure. Cause. Smallest fix.
[P2 maintainability] `path:line` Problem. Existing pattern to use. Smallest fix.
[P3 confidence] Missing scenario. What test/manual QA would prove it.
```

Separate **Blockers** (security/correctness/data loss/material confidence gaps), **Should fix** (readability/duplication/constants/local pattern drift), **Teach-back** (good patterns/automation/why it matters), and **Follow-ups** (deferred work).

Severity follows impact; confidence states how well the premise is proved. Category labels do not fix the priority. A confidence gap blocks when the unproved behavior carries material risk. Report a clean review when warranted.

For handoffs, give the user outcome, rationale, constraints, and acceptance evidence. Leave implementation/slice planning to the engineer unless asked.

Publish inline PR comments only when the current user request explicitly directs publication. Then use `/posting-pr-review-comments`, which revalidates fresh PR state and posts one batched review. Requests to review a PR/branch or preview hypothetical findings stay read-only.

## Review discipline

- **Classify every export by caller and effect.** A `use server` export that client code calls is an action with auth and ownership requirements, not a helper.
- **Search existing patterns before judging each hunk.** Find the established conventions first.
- **Require evidence proportional to risk.** Happy-path manual QA is insufficient for data/server/payment logic; demand multi-scenario tests.
- Separate diff proof from production hypotheses. Distinguish code introduction, deployment, feature activation, and symptom onset. Measure latency or label it unmeasured; compare the same workload, path, and completion metric.
- **Name behavior, edge cases, and contracts before simplification.** Silent behavior removal is not simplification; preserve every consumer's specialized behavior.
- **Pair every style flag with a maintainability or extension risk.** Style without consequence is noise.
- **Prevention closes the review.** For every recurring finding, name the smallest durable control from lens 7 and what would prove it works.
