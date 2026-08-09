---
name: implementation-ownership
description: Use when an agent has implemented a non-trivial change that needs an ownership decision before approval or handoff, or when the user says they do not understand an implementation ("I don't get what this does", "why did you do it this way"). Produces a decision-oriented review: the problem it solves, why this approach, the assumptions it leans on, its failure modes and how we would know, the smallest safe rollback, the understanding level, and one approval recommendation.
---

# Implementation Ownership

Turn an unfamiliar agent-generated implementation from a black box into an explicit ownership decision. The reviewer does not need to understand every line; they need to know enough to approve it, and to know what they still do not know. This is the approval review, not the explanation: `/understand-code-like-an-owner` narrates how the code works; this skill decides whether to keep it, at what understanding level, and how it comes out again.

**Leading words:** _ownership_, a change whose keeper can predict its behavior, detect its failures, and roll it back; _black box_, an implementation whose behavior the reviewer cannot predict from outside, the state this review exists to end.

**Scope.** Produces a recommendation, not a fix and not a walkthrough. It does not repair the implementation, and it does not re-narrate the code; use `/understand-code-like-an-owner` for the data-flow explanation.

## Workflow

Run the six questions in order. Each ends on a completion criterion; do not move on until it is met.

### 1. What problem is this solving?

Read the real diff and its surrounding code, not a summary of them. State the problem the change exists to solve and describe the change's observable behavior before its syntax; the behavior is what you own, the syntax is how it is written.

Completion: the problem is stateable in one sentence a non-author can verify against the diff, and the behavior is described without reading out the code.

### 2. Why was this approach chosen over the alternatives?

Name the approach, then name at least one realistic alternative the implementer could have chosen: a simpler variant, an existing utility, or doing nothing. Give the concrete reason this approach wins for this change and its context. "Best practice" and "standard pattern" are knowledge gaps, not reasons.

Completion: one realistic alternative named and one concrete differentiator stated that ties the choice to this change.

### 3. What assumptions does it rely on?

Extract the assumptions the change leans on, each as an explicit "this holds" statement, tagged by source: code (implicit contracts), config (flags, env vars), data model (schema, invariants), runtime (timing, ordering, external services).

Completion: every assumption the change depends on is listed with its source and what must hold.

### 4. What are its likely failure modes?

For each assumption and each new code path, name what breaks when the assumption stops holding. Every assumption and every new path gets at least one failure mode.

Completion: no assumption from step 3 and no new code path is left without a failure mode.

### 5. How would we know it is broken?

Map each failure mode to a concrete detection signal: a log line, a metric, a test, an alert, an invariant, or a user-visible symptom. A detection without a signal is not detection.

Completion: every failure mode from step 4 is paired with a signal someone could observe.

### 6. How could we replace or remove it?

Find the smallest safe replacement or rollback path. Name the state that must be preserved, the minimal change that undoes this one, and what could ship instead that keeps the problem solved. If no safe path exists, that is itself a finding, not an excuse to skip this step.

Completion: a concrete replacement or rollback path with the state it preserves.

### 7. Assign the understanding levels

Assign the reviewer's current level and the level needed to approve, using the table. Default target: operational. Raise the target when the change is security-sensitive, architecture-defining, performance-critical, business-critical, a competitive advantage, modified repeatedly, or difficult or expensive to replace; each of those warrants implementation-level study of at least the relevant internals.

Completion: a current level and a recommended level, each one cell of the table, with the warrant named when the recommended level is implementation.

### 8. Recommend

List every knowledge gap: any answer in steps 1-6 that was a guess. If a gap touches an assumption whose failure would blind detection or block rollback, approval is unsafe at the current level. Then recommend exactly one option:

- Approve with conceptual understanding.
- Approve after an operational walkthrough.
- Study specific internals.
- Simplify or reject.

Completion: one recommendation, with the gaps that would make it wrong stated.

## Understanding levels

| Level | The reviewer can |
|---|---|
| Black box | Predict only that it does "something"; treat behavior as a coin flip. |
| Conceptual | State the problem and the approach in general terms, but not how it behaves in operation. |
| Operational | Predict behavior for real inputs, name the failure modes and their signals, and operate or roll it back. |
| Implementation | Rebuild it from memory, reason about every branch, and modify it safely. |

## Guardrails

### Rationalizations that hide a black box

| Rationalization | Correction |
|---|---|
| "Tests pass, so it is fine." | Tests prove only what they assert: not that the problem is the right problem, the assumptions hold, or the failures are detectable. A green suite is consistent with a black box. |
| "The agent can fix it later." | Later depends on detection (step 5) and cheap recovery. A break you cannot see never gets fixed; ownership is now or never. |
| "Reading line by line is too slow." | True, and irrelevant: ownership does not require implementation-level reading. Answer the six questions from the diff, the behavior, and the surfaces. |
| "It is a mature library, so it is safe." | Maturity is the library's property; the risk is in the coupling. Your assumptions, config, and data are the failure modes. Judge the change, not the vendor. |
| "We can always rewrite it." | Rewrites happen under pressure and without the author. The honest version is step 6's smallest safe replacement, named now. |

### Red flags in the review

- Restating the code without a system boundary: what feeds the change and what it feeds are unnamed.
- Invented alternatives: the differentiator is generic or the alternative could never have been chosen.
- Failure modes without detection or recovery.
- "Monitor logs" without naming the log line, metric, or threshold.
- "Revert the commit" as the rollback, ignoring migration, config, and state side effects.
- Claiming understanding without testing it: no walkthrough, no replay on a real input, no prediction checked against the code.

## Output format

Deliver the review in this order:

- **What changed**: the real diff, described by behavior.
- **Problem it solves**: one sentence from step 1.
- **Why this approach**: approach, alternative, differentiator.
- **Assumptions**: each with its source.
- **Failure modes and detection**: each failure paired with its signal.
- **Replacement / rollback path**: the smallest safe path and the state it preserves.
- **Understanding level**: current and recommended, with the warrant.
- **Approval recommendation**: exactly one of the four options.
- **Questions still unanswered**: every guess made in steps 1-6.

## Verification

Before delivering, confirm every item:

- Every output section is filled from evidence in the diff and surrounding code, not from paraphrasing the code.
- Every failure mode has a concrete detection signal.
- The rollback path names the state it preserves.
- Both understanding levels are assigned, recommended at least operational unless a warrant raises it.
- The recommendation is exactly one of the four options and follows from the levels and gaps.
- Questions still unanswered lists every guess.
- The review is written for the human who must approve: product language, engineering terms glossed.

## Done when

The human who must live with the change can answer, for this implementation: what problem it solves, why this approach, what it assumes, how it fails and how they would know, and how it comes out again, and has one recommendation to accept or override.
