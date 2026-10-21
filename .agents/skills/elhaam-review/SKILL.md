---
name: elhaam-review
description: Review code changes and PRs for codebase fit, simplicity, test confidence, security, whole-flow correctness and scale, maintainability, and prevention of repeat findings.
---

# Elhaam Review

Review the interaction between each diff hunk and the surrounding system. Catch boundary mistakes, unnecessary complexity, missing confidence, hidden assumptions, and opportunities to make future agents/tools catch the same issue automatically.

## Required context gathering

1. **Establish scope and behavior.** Record the reviewed base/head or working-tree state. Read the diff and changed files against the requested outcome, relevant requirements, and agreed non-goals. Trace the affected user or consumer action through its callers and dependencies.
   Completion: every changed file is read and categorized by risk; the intended behavior and relevant boundaries are understood.
2. **Search before judging.** Find existing helpers, constants, types, server/data patterns, tests, and naming conventions near touched code.
   Completion: existing patterns near each hunk are known before any opinion is formed.
3. **For GitHub PR review data, use `/github-graphql-first` when available; otherwise query GraphQL `reviewThreads` directly.** Inline thread context matters; REST-flattened comments are not enough.
   Completion: all review threads and replies are collected, including resolved/outdated threads. Verify claimed fixes against the reviewed code; distinguish implemented, deferred, and withdrawn concerns.
4. **Try to disprove each candidate finding.** Check caller guarantees, existing validation, installed framework/runtime versions, author explanations, and the intended product contract. For a defect, name a concrete actor/action/state, the observable failure, and the causal code path. A static proof can suffice; state any assumption that still needs verification.
   Completion: each reported defect survives this check. Keep standards feedback, confidence gaps, and open questions distinct from proved defects.

## Review lenses

### 1. Hunk to codebase boundary

Ask whether each hunk fits the boundary it touches.

- Existing helper available? Prefer it over a local duplicate (`tryCatch`, formatters, validators, query helpers).
- Shared policy or concept? Keep its constants, types, and logic under one owner, and check that the real callers use it. Reuse should preserve each caller's contract; choose placement from actual consumers and local conventions.
- New pattern? Require justification; otherwise align locally.
- Good pattern? Call it out so the author repeats it.

### 2. Simpler implementation, same behavior

Push for simple, linear code without feature loss. Before suggesting simplification, name the behavior, edge cases, auth behavior, UX, and API contracts that must remain unchanged.

- Prefer guard clauses over nested conditionals.
- Extract meaningful functions, variables, or components when logic becomes hard to follow or needs comments to narrate its steps. Keep private extractions beside their sole consumer. Preserve comments explaining constraints or non-obvious rationale.
- Replace nested ternaries/repeated branches with maps or small helpers/components.
- Create generic utilities only when operations are genuinely the same shape.

### 3. Tests as confidence

Require evidence proportional to the changed contract and failure cost. First inspect what existing tests actually prove.

- Test through the public interface used by the real consumer, including the built/installed entry point when packaging changes. Keep application layers real where practical and replace external dependencies at their boundaries. Focused unit tests suit independent business rules; integration tests should carry most cross-layer permutations. Use browser or native-UI tests for essential journeys and behavior specific to that environment.
- When correctness depends on database authorization, constraints, transactions, or concurrency, require evidence using the real database behavior. Include legitimate success cases alongside rejection cases.
- For critical rules, require a regression test that fails when the rule is broken, using a focused mutation check when needed. Assertions should use independent expected outcomes, not recompute them through the implementation.
- Choose scenarios from the conditions that change execution: feature enabled/disabled, fresh/persisted state, and slow/failed dependencies. For asynchronous UI, verify eventual recovery and the next user action. Assert relevant external-call counts and blocking behavior, alongside returned values.
- State what was exercised, simulated, and left unverified, and whether the relevant suite runs in CI. Test counts, a changed test file, source-text assertions, or isolated helper tests do not by themselves prove the journey.

### 4. Server, database, and security boundary

Trace actual entry points and trust boundaries before judging exposure.

- For protected data, trace authentication and ownership/tenant scope along every reachable path. Prove where middleware, service, query, or database enforcement supplies each guarantee. Authentication alone does not prove resource authorization. Flag an absent/bypassable guarantee at a reachable operation, or state the evidence still needed; public access must match the intended contract.
- Validate untrusted input and provider replies at the boundary; trace casts and non-null assertions to the guarantees they rely on. Follow the repository's contract for expected failures; make broken internal invariants visible and stop unsafe effects. Check for fallbacks that disguise failure as empty data, zero amounts, or success.
- For React or Next.js changes, read the framework section of [conditional checks](references/conditional-checks.md#react-and-nextjs).
- Do not leak attacker-helpful detail in client-visible errors (`tenant not found for id X`). Log detail server-side.

### 5. Whole-flow correctness and scalability

Look across hunks, not just inside one line. Grouped hunks can create N+1 or repeated work even when each hunk looks locally reasonable; trace request, query, and API-call counts across the full flow.

- Loops with DB/API calls: check N+1 and batching risks.
- Check actual failure semantics: thrown/rejected errors versus returned error values, partial success, and the caller or job runner's retry behavior. Decide whether one failure should fail the whole operation.
- For multi-step writes, payments, bookings, or jobs with side effects, read the recovery section of [conditional checks](references/conditional-checks.md#stateful-workflows).
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

For recurring findings, first check whether the intended rule already exists and why it failed to prevent this instance.

- Prefer the smallest effective control: a shared policy boundary, behavioral test, compiler/lint rule, or clearer agent guidance. Check whether it also covers the next caller or job without another manual guard.
- For enforcement changed here or used to dismiss a finding, use existing evidence or a focused check of a violating and a legitimate case through its actual entry point. Distinguish documented, locally runnable, running in CI, and required before merge/deploy. State what remains unverified.
- Group repeated symptoms by cause. Keep unrelated cleanup as a follow-up; add guidance only when missing guidance caused the failure.

## Output contract

Default to a standalone HTML findings file using `/readable-html-dossier` when available. An explicit user format request takes precedence. Keep it readable without conversation context and include the reviewed scope/revision, evidence links, verification limits, and prioritized findings.

Use concise comments that give the consequence and direction:

```md
[P1 correctness] `path:line` When [action/state], [observable failure] because [cause]. Smallest fix. Evidence that would prove it.
[P2 standards] `path:line` Existing rule/pattern. Concrete maintenance or consistency cost. Smallest alignment.
[P2 confidence] Critical behavior not yet proved. Missing scenario and the evidence needed.
```

Assign severity by the consequence under the stated conditions. State confidence separately; an uncertain premise is a risk or question, not a confirmed defect. Separate merge blockers, should-fix items, and optional follow-ups. A confidence gap blocks only when the unproved behavior carries material risk. Report a clean review when warranted, and call out specific good patterns worth repeating.

For a handoff, explain the user outcome, reason for the change, constraints, and acceptance evidence. Leave implementation and slice planning to the engineer unless the user asks for that plan.

Publish inline PR comments only when the current user request explicitly directs publication. Then use `/posting-pr-review-comments`, which revalidates fresh PR state and posts one batched review. A request to review or preview findings stays read-only.

## Review discipline

- Separate what the diff proves from production hypotheses. When attributing a regression, distinguish code introduction, deployment, feature activation, and symptom onset. Support latency claims with measurements or label them unmeasured; compare the same workload, path, and completion metric.
- Before suggesting simplification, preserve the identified behavior, edge cases, and contracts. For extraction, verify every affected consumer still receives its specialized behavior.
- Anchor standards feedback in an established convention or a concrete maintenance cost. Keep speculative redesign separate from defects in the requested change.
