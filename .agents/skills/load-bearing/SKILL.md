---
name: load-bearing
description: Audit a codebase for longevity work — map its data flows, find the load-bearing ones, trace them for architectural smells and recurring bugs.
disable-model-invocation: true
---

# Load-bearing

Find the work that keeps this codebase alive in two years: the cracks in what carries weight.

**Leading words:** _flow_ — one path data takes from an entry point (route, action, job, webhook, cron, consumer, CLI) to where it rests or leaves; _load-bearing_ — a flow whose break or slowdown users or money would notice; _heavy_ — a flow whose data grows with users, tenants, or time; _pinned_ — behaviour a test turns red the moment it breaks; _recurrence_ — the same cause fixed more than once.

## Steps

1. **Map every flow.** Enumerate entry points from the environment — route directories, job registries, webhook handlers, cron config, queue consumers — and follow each to its sink: table, bucket, external API, response.
   Completion: every entry point appears with its sink; a flow you could not trace is listed as untraced, with why.

2. **Find the load-bearing ones.** Weigh each flow on data weight (rows touched, payload size, growth), frequency, what breaks for the user or business, and churn (`git log` hot spots). Cap the set at six; present it and wait for the user to confirm it.
   Completion: every flow tagged heavy or light; the load-bearing set named, each with a one-line reason, confirmed by the user.

3. **Trace each load-bearing flow** — one subagent per flow, briefed with [`agents/flow-tracer.md`](agents/flow-tracer.md). It walks the flow in execution order and applies every smell below.
   Completion: every smell on every load-bearing flow returns a finding with `file:line`, or "clean" with the evidence that cleared it.

4. **Mine recurrence** — in parallel with step 3. Take the last 12 months or 500 commits, whichever is smaller, and split it into slices of about 100 commits; one subagent per slice, briefed with [`agents/recurrence-miner.md`](agents/recurrence-miner.md). Merge their clusters by root cause, not by file.
   Completion: every fix commit in the window sits in a cluster or is marked one-off; every cluster of two or more names its durable control — lint rule, test, shared helper, `AGENTS.md` line, or skill.

5. **Falsify.** Try to kill each finding: real callers, existing guards, actual data volume, product intent. A survivor names the actor, the action, and the wrong outcome they see.
   Completion: every finding left is either proved with a failure path or labelled a hypothesis with what would prove it.

6. **Rank by longevity payoff** — blast radius and likelihood against fix size; small fixes on heavy flows first. When a trace kept bouncing between shallow modules, add a follow-up to run `/improve-codebase-architecture` on that area. Deliver with `/readable-html-dossier`.
   Completion: every finding carries a smell, a flow, a fix size, and the evidence behind it.

## Smells

- **Slow by schema** — latency the schema causes and a migration or query change fixes: no index on a filter/join/sort column, N+1 across the flow, unbounded reads, whole rows or blobs fetched for one field, JSON queried by key, independent awaits run in sequence, column types that force casts. Read `EXPLAIN` when a database is reachable; otherwise label it unmeasured.
- **Unguarded boundary** — outside input or a provider reply trusted without runtime validation; casts and non-null assertions with no guarantee behind them; success-shaped defaults covering a broken invariant. Fault ownership rules: [defensive and offensive](~/.agents/skills/elhaam-review/references/conditional-checks.md#offensive-and-defensive-programming).
- **Open door** — data access proved authenticated but not scoped to owner or tenant.
- **Fragile write** — multi-step writes or side effects with no transaction, idempotency, or recovery owner. See [stateful workflows](~/.agents/skills/elhaam-review/references/conditional-checks.md#stateful-workflows).
- **Silent failure** — swallowed errors, partial `Promise.all` treated as success, a load-bearing flow with no log or metric; the first to know is a customer.
- **Split truth** — one rule or shape defined in more than one place, free to drift.
- **Unpinned** — load-bearing behaviour no test turns red: untested, happy-path only, or tested with the breaking part mocked out.
- **No guardrail** — checks that exist but run nowhere: lint, typecheck, or tests missing from CI or pre-commit.
