---
name: good-tests
description: Write, add, review, or fix tests and testing strategy. Use when a task mentions tests, testing, specs, coverage, mocks, fixtures, assertions, TDD, test failures, unit tests, integration tests, end-to-end tests, Jest, Vitest, Playwright, or Cypress.
---

# Good Tests

Protect observable behaviour at stable boundaries. Optimise for confidence, not test count.

## Choose the seam

Use the highest affordable seam that proves the behaviour:

| Seam | Use for | Prefer |
|---|---|---|
| Unit | Pure logic and edge-heavy transformations | Inputs and outputs |
| Integration | Modules, persistence, queues, and service boundaries | Real collaborators and disposable infrastructure |
| End to end | Critical user journeys and wiring | Behaviour visible to the user |

Avoid proving the same invariant at every layer unless each layer covers a distinct failure mode.

## Process

1. Inspect the existing runner, nearby tests, helpers, factories, and CI commands. Follow local conventions unless they reduce confidence.
   Completion: the relevant behaviour, established test seams, and exact commands are known.
2. Name the invariant and the regression it prevents before writing assertions. Cover the happy path, meaningful boundaries, and realistic failures; omit permutations that add no new confidence.
   Completion: every planned case protects a distinct behaviour or risk.
3. Write the smallest test at the chosen seam. For a bug, prove the test goes red for the reported regression before applying or accepting the fix when this is safe and practical.
   Completion: the failure is attributable to the intended behaviour, not broken setup.
4. Make the test green, then run the narrowest relevant suite followed by the repository's broader required checks.
   Completion: relevant tests pass without weakening assertions or skipping failures.
5. Report the behaviours protected, commands run, and meaningful risks left untested.
   Completion: another engineer can tell what confidence was gained and what remains uncertain.

## Test design

- Name tests after observable behaviour: condition, action, outcome.
- Keep arrange, act, and assert visually obvious. Prefer one behaviour per test; use multiple assertions when they describe one outcome.
- Assert public outputs, persisted state, emitted events, or user-visible effects. Assert internal calls only when the call itself is the contract.
- Prefer real domain code, in-memory adapters, disposable databases, fake clocks, and deterministic fixtures.
- Mock true external boundaries such as third-party networks, expensive infrastructure, time, and randomness. Keep mocks contract-shaped and minimal.
- Use factories with meaningful defaults. Override only values relevant to the case.
- Make failures diagnostic: the test name and assertion should reveal which invariant broke.
- Keep tests deterministic and isolated from execution order, wall-clock timing, shared mutable state, and live services.

## Review gate

A test is ready when:

- it would fail for the regression it claims to prevent;
- refactoring internals without changing behaviour would usually leave it green;
- mocks do not recreate the implementation under test;
- setup is shorter than the behaviour it explains, or extracted behind a clear factory;
- the suite remains fast enough for its intended feedback loop.
