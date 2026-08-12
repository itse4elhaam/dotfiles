---
name: triage-proposed-change
description: Triage a proposed code change before implementation. Estimate risk and minimal patch size, determine test modifications and new regression tests, find existing behavior pins, and report data-flow and architectural impact. Use when deciding how large, risky, or invasive a requested code change is before touching code.
---

# Triage Proposed Change

Assess the smallest coherent implementation of the proposed change. Explore the codebase first. Do not edit or implement anything.

## Inspect

Trace the current behavior end to end:

- caller or user entry point
- modules and boundaries crossed
- data reads, transforms, writes, caches, queues, and external calls
- tests, schemas, validators, types, constraints, or other executable checks that pin the behavior

Search for existing helpers and patterns before assuming new code is needed.

If a fact can be discovered from the repository, discover it instead of asking. If an ambiguity would change the risk tier or patch estimate by more than roughly 2x, show both branches; otherwise use the smallest reasonable interpretation.

Completion: current behavior, desired behavior, touched boundaries, and existing behavior pins are known.

## Rate the change

Choose the highest applicable risk tier. Risk is blast radius plus reversibility, not LOC alone.

- **LOW** — local behavior at one stable seam; easy rollback; no persisted-data, auth, external-contract, or cross-boundary change.
- **MEDIUM** — crosses modules or changes API behavior, caching, source-of-truth placement, or request/data flow, but remains straightforward to reverse.
- **HIGH** — changes persisted data shape or migrations, auth/permissions, payments or irreversible side effects, concurrency/ordering invariants, public/breaking contracts, broad fan-out, or is difficult to roll back.

Estimate the minimal patch as a range of hand-written added/changed LOC. Split code from tests and migration/config work. Ignore generated files and formatting churn.

## Judge test impact

Treat a behavior as **pinned** only when an automated test, schema/constraint, or runtime validation would fail if the core invariant regressed.

- **YES** — the changed behavior is directly protected at a stable seam.
- **PARTIAL** — surrounding behavior is covered, but the changed invariant can still regress unnoticed.
- **NO** — no executable protection for the changed invariant was found.

Modify existing tests when the intended contract itself changes. Add a new regression test when the new behavior is not already pinned at an existing stable seam. Prefer the highest existing seam that proves the behavior; do not add redundant implementation-detail tests.

## Judge architecture and data flow

Data flow changes when the source, ownership, transformation location, ordering, caching, persistence, client/server boundary, async path, or external side effect changes.

Architecture impact:

- **NONE** — same boundaries, dependencies, source of truth, and public contracts.
- **LOCAL** — introduces or changes a helper/module dependency inside the existing architecture without moving ownership or changing dependency direction.
- **STRUCTURAL** — changes a source of truth, ownership boundary, dependency direction, persistence model, public contract, or infrastructure component.

State the long-term consequence, not merely the files touched.

## Output

Reply with only this compact triage:

```text
Risk: LOW|MEDIUM|HIGH — <one-line reason>
Patch: ~<x-y> code LOC | ~<a-b> test LOC | migration/config: <none or estimate>
Tests: modify <YES|NO> — <what> | add <YES|NO> — <what>
Pinned: YES|PARTIAL|NO — <specific test/validation and invariant, or what is missing>
Data flow: NO|YES — <unchanged, or before → after>
Architecture: NONE|LOCAL|STRUCTURAL — <long-term consequence>
Validation: <smallest set of automated/manual checks that proves the change>
Confidence: HIGH|MEDIUM|LOW — <what makes the estimate certain or uncertain>
```

Keep each field to one line. Cite concrete symbols/tests when useful. No implementation plan, prose preamble, or generic advice unless the user asks for it.
